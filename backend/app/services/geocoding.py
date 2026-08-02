import re
import threading
import time
from typing import Dict, Optional, Tuple

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TravelSense/1.0 (https://travelsense.app)"
# Nominatim's usage policy caps unauthenticated use at 1 request/second.
MIN_INTERVAL_SECONDS = 1.1

GeocodeResult = Tuple[float, float, str]

# LLM-generated activity titles are usually phrased as instructions ("Explore
# Tsukiji Outer Market", "Visit the Louvre"), and Nominatim's free-text search
# matches those noticeably worse than the bare place name -- stripping the
# leading verb phrase measurably improves hit rate.
_LEADING_VERB_PHRASE = re.compile(
    r"^(explore|visit|discover|follow|head( over)? to|check out|see|tour|"
    r"walk( around| through)?|wander( around| through)?|stroll( around| through)?|"
    r"start (with|at)|enjoy|experience)\s+(the\s+)?",
    re.IGNORECASE,
)


def clean_geocode_query(query: str) -> str:
    cleaned = _LEADING_VERB_PHRASE.sub("", query.strip(), count=1).strip()
    return cleaned or query.strip()


# Titles like "Dinner in Bairro Alto, Lisbon" or "Lunch at Time Out Market,
# Lisbon" don't get caught by the leading-verb stripper above, but the place
# name after the last "at"/"in"/"near" resolves reliably on its own -- used
# as a second attempt when the full cleaned query comes back empty.
_TRAILING_LOCATION_PHRASE = re.compile(r"\b(?:at|in|near)\s+(.+)$", re.IGNORECASE)


def fallback_geocode_query(query: str) -> Optional[str]:
    match = _TRAILING_LOCATION_PHRASE.search(query)
    if not match:
        return None
    candidate = match.group(1).strip()
    return candidate or None


class GeocodingService:
    def __init__(self) -> None:
        self._cache: Dict[str, Optional[GeocodeResult]] = {}
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def geocode(self, query: str) -> Optional[GeocodeResult]:
        normalized = clean_geocode_query(query)
        if not normalized:
            return None

        result = self._geocode_single(normalized)
        if result is not None:
            return result

        fallback = fallback_geocode_query(normalized)
        if fallback and fallback != normalized:
            return self._geocode_single(fallback)
        return None

    def _geocode_single(self, normalized: str) -> Optional[GeocodeResult]:
        if normalized in self._cache:
            return self._cache[normalized]

        with self._lock:
            if normalized in self._cache:
                return self._cache[normalized]
            self._throttle()
            result = self._fetch(normalized)
            self._cache[normalized] = result
            return result

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)
        self._last_request_time = time.monotonic()

    def _fetch(self, query: str) -> Optional[GeocodeResult]:
        try:
            response = httpx.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": USER_AGENT},
                timeout=10.0,
            )
            response.raise_for_status()
            results = response.json()
        except (httpx.HTTPError, ValueError):
            return None

        if not results:
            return None

        first = results[0]
        try:
            return float(first["lat"]), float(first["lon"]), first.get("display_name", query)
        except (KeyError, TypeError, ValueError):
            return None
