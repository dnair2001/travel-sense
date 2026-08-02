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
# (min_lon, max_lat, max_lon, min_lat) -- Nominatim's "left,top,right,bottom" viewbox order.
ViewBox = Tuple[float, float, float, float]

# Degrees of padding added around a resolved destination's bounding box before
# using it to restrict activity searches. ~1 degree is roughly 110km -- room
# for a reasonable day trip (Kamakura from Tokyo, Versailles from Paris)
# while still excluding a same-named place on the other side of the world.
_VIEWBOX_PADDING_DEGREES = 1.0

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


# Nominatim's free-text search reliably fails on a possessive "'s" inside a
# place name (e.g. "Imperial Palace's East Gardens" returns zero results,
# but the identical place without the apostrophe matches immediately) --
# stripping it costs nothing since the possessive isn't part of the place's
# actual name anyway.
_POSSESSIVE = re.compile(r"(\w)['’]s\b")


def clean_geocode_query(query: str) -> str:
    cleaned = _LEADING_VERB_PHRASE.sub("", query.strip(), count=1).strip()
    cleaned = _POSSESSIVE.sub(r"\1", cleaned)
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


# Every activity query is built by the frontend as "{title}, {destination}",
# so the text after the last comma is a reliable destination hint we can use
# to bias the search -- without it, a generic title like "Korean BBQ
# Restaurant" can match a same-named place anywhere on Earth (real example:
# it resolved to Little Tokyo, Los Angeles for a Tokyo trip).
def _destination_hint(query: str) -> Optional[str]:
    if "," not in query:
        return None
    return query.rsplit(",", 1)[-1].strip() or None


class GeocodingService:
    def __init__(self) -> None:
        self._cache: Dict[str, Optional[GeocodeResult]] = {}
        self._viewbox_cache: Dict[str, Optional[ViewBox]] = {}
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def geocode(self, query: str) -> Optional[GeocodeResult]:
        normalized = clean_geocode_query(query)
        if not normalized:
            return None

        viewbox = self._resolve_viewbox(_destination_hint(query))

        result = self._geocode_single(normalized, viewbox)
        if result is not None:
            return result

        fallback = fallback_geocode_query(normalized)
        if fallback and fallback != normalized:
            return self._geocode_single(fallback, viewbox)
        return None

    def _resolve_viewbox(self, near: Optional[str]) -> Optional[ViewBox]:
        if not near:
            return None
        if near in self._viewbox_cache:
            return self._viewbox_cache[near]

        with self._lock:
            if near in self._viewbox_cache:
                return self._viewbox_cache[near]
            self._throttle()
            box = self._fetch_bounding_box(near)
            self._viewbox_cache[near] = box
            return box

    def _geocode_single(self, normalized: str, viewbox: Optional[ViewBox] = None) -> Optional[GeocodeResult]:
        cache_key = f"{normalized}|{viewbox}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
            self._throttle()
            result = self._fetch(normalized, viewbox)
            self._cache[cache_key] = result
            return result

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)
        self._last_request_time = time.monotonic()

    def _fetch(self, query: str, viewbox: Optional[ViewBox] = None) -> Optional[GeocodeResult]:
        params = {"q": query, "format": "json", "limit": 1}
        if viewbox:
            params["viewbox"] = ",".join(str(coordinate) for coordinate in viewbox)
            params["bounded"] = 1

        try:
            response = httpx.get(
                NOMINATIM_URL,
                params=params,
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

    def _fetch_bounding_box(self, query: str) -> Optional[ViewBox]:
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

        try:
            min_lat, max_lat, min_lon, max_lon = (float(value) for value in results[0]["boundingbox"])
        except (KeyError, TypeError, ValueError):
            return None

        return (
            min_lon - _VIEWBOX_PADDING_DEGREES,
            max_lat + _VIEWBOX_PADDING_DEGREES,
            max_lon + _VIEWBOX_PADDING_DEGREES,
            min_lat - _VIEWBOX_PADDING_DEGREES,
        )
