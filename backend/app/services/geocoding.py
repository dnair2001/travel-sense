import re
import threading
import time
from typing import Dict, List, Optional, Tuple

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TravelSense/1.0 (https://travelsense.app)"
# Nominatim's usage policy caps unauthenticated use at 1 request/second.
MIN_INTERVAL_SECONDS = 1.1

GeocodeResult = Tuple[float, float, str, bool]  # (lat, lon, display_name, is_approximate)
# (min_lon, max_lat, max_lon, min_lat) -- Nominatim's "left,top,right,bottom" viewbox order.
ViewBox = Tuple[float, float, float, float]

# Degrees of padding added around a resolved destination's bounding box before
# using it to restrict activity searches. ~1 degree is roughly 110km -- room
# for a reasonable day trip (Kamakura from Tokyo, Versailles from Paris)
# while still excluding a same-named place on the other side of the world.
_VIEWBOX_PADDING_DEGREES = 1.0

# Tighter padding used only for the "any venue in the city" chain-name
# fallback below, applied around the destination's resolved *point* (not its
# administrative bounding box -- that can be wildly oversized, e.g.
# Nominatim's box for "Tokyo" spans all of Japan since Tokyo Prefecture
# legally includes islands ~1,000km away). That search has no specific name
# text pulling it toward the right place, so anything looser than a tight
# radius risks a same-named branch in a genuinely different city (confirmed:
# with the day-trip-sized padding above, "Yayoi-ken" bounded to "Tokyo"
# returned a branch in Shizuoka). ~0.15 degrees is roughly 16km, comfortably
# covering central Tokyo without reaching that far.
_ANY_VENUE_PADDING_DEGREES = 0.15

# Some itinerary activities are genuine day trips well outside the city
# itself -- e.g. "Grutas de Tolantongo" from Mexico City is ~150-170km away,
# farther than even the primary search's day-trip padding above, and its
# name doesn't combine with the city suffix into a query Nominatim can match
# at all (confirmed: "Tolantongo, Mexico City" returns zero results even
# completely unbounded, while the bare name resolves immediately). Tried
# only after the tight any-venue-in-city search above has failed, using the
# same non-venue-class filtering, so a nearby false-positive road or business
# is still preferred over a same-named place on the other side of the world.
_DAY_TRIP_VENUE_PADDING_DEGREES = 2.5


def _pad_box(raw_bbox: Optional[Tuple[float, float, float, float]], padding: float) -> Optional[ViewBox]:
    if not raw_bbox:
        return None
    min_lat, max_lat, min_lon, max_lon = raw_bbox
    return (min_lon - padding, max_lat + padding, max_lon + padding, min_lat - padding)


def _point_viewbox(point: Tuple[float, float], padding: float) -> ViewBox:
    lat, lon = point
    return (lon - padding, lat + padding, lon + padding, lat - padding)


# A relative distance measure for ranking nearby candidates, not real
# distance -- fine at the city scale this is used at, no need for haversine.
def _distance_squared(point: Tuple[float, float], anchor: Tuple[float, float]) -> float:
    return (point[0] - anchor[0]) ** 2 + (point[1] - anchor[1]) ** 2


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


# LLM-generated titles often describe a neighborhood as "<Name>
# District/Neighborhood/Area/Ward" -- Nominatim's free-text search frequently
# returns zero results for the padded phrase, or worse, silently matches an
# unrelated same-named place elsewhere (confirmed: "Ginza District, Tokyo"
# resolved to Little Tokyo, Los Angeles; "Shibuya Area, Tokyo" matched a
# smoking area inside a random Shibuya building instead of the neighborhood
# itself) even though the bare neighborhood name matches correctly. Applied
# unconditionally rather than only as a fallback, since a spurious low-
# quality match -- not just a zero-result failure -- can otherwise mask the
# better candidate. "Quarter"/"Zone" are deliberately excluded since a
# handful of real place names genuinely end in one of these words (e.g. the
# French Quarter).
_TRAILING_GENERIC_DESCRIPTOR = re.compile(r"\s+(district|neighbo(?:u)?rhood|area|ward)\b", re.IGNORECASE)


def strip_generic_descriptor(query: str) -> Optional[str]:
    stripped = _TRAILING_GENERIC_DESCRIPTOR.sub("", query).strip()
    return stripped if stripped and stripped != query else None


def clean_geocode_query(query: str) -> str:
    cleaned = _LEADING_VERB_PHRASE.sub("", query.strip(), count=1).strip()
    cleaned = _POSSESSIVE.sub(r"\1", cleaned)
    cleaned = _TRAILING_GENERIC_DESCRIPTOR.sub("", cleaned).strip()
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


def _venue_name(query: str) -> str:
    return query.split(",", 1)[0].strip()


# A chain name (e.g. "Yayoi-ken") has many real branches but no single
# canonical address, so every attempt above legitimately finds nothing. As a
# last resort, search just the venue name (dropping the city suffix, since
# combining them can itself fail the same way "Odaiba Rainbow Bridge" does)
# bounded to the destination and take the first result that's an actual
# point of interest -- these class/type values are Nominatim matches on a
# shared substring of the name that are clearly never "the chain restaurant"
# (a park, a road, a pharmacy, a clinic), confirmed against real results for
# "Yayoi-ken" in Tokyo.
_NON_VENUE_CLASSES = {"highway", "boundary", "natural", "waterway", "railway", "leisure"}
_NON_VENUE_TYPES = {
    "pharmacy", "doctors", "clinic", "hospital", "dentist", "bank", "atm",
    "toilets", "parking", "fuel", "post_office", "police", "fire_station",
    "townhall", "school", "kindergarten", "university", "college",
    "veterinary", "social_facility", "nursing_home",
}


# A leading "<Area> <Landmark>" compound sometimes returns zero results as
# one phrase even though the landmark alone matches fine (confirmed: "Odaiba
# Rainbow Bridge, Tokyo" fails; "Rainbow Bridge, Tokyo" doesn't). Drops just
# the first word of the venue phrase as one extra attempt -- not a cascading
# drop of every leading word, to keep this from ever discarding so much of
# the name that a match becomes a coincidence rather than the right place.
def _drop_leading_word(query: str) -> Optional[str]:
    venue, _, rest = query.partition(",")
    words = venue.split()
    if len(words) < 2:
        return None
    shortened = " ".join(words[1:])
    candidate = f"{shortened},{rest}" if rest else shortened
    return candidate.strip()


# Attempts to try in order: the cleaned query, its trailing "at/in/near"
# phrase, a generic-descriptor-stripped version of each, and a version with
# the venue phrase's leading word dropped -- deduplicated and
# order-preserving, since later, cheaper rewrites should only fire once the
# more specific attempts before them have failed.
def _candidate_queries(normalized: str) -> List[str]:
    candidates = [normalized]

    fallback = fallback_geocode_query(normalized)
    if fallback and fallback not in candidates:
        candidates.append(fallback)

    for base in list(candidates):
        stripped = strip_generic_descriptor(base)
        if stripped and stripped not in candidates:
            candidates.append(stripped)

    dropped = _drop_leading_word(normalized)
    if dropped and dropped not in candidates:
        candidates.append(dropped)

    return candidates


DestinationInfo = Tuple[Tuple[float, float, float, float], Tuple[float, float]]  # (raw bbox, point)


class GeocodingService:
    def __init__(self) -> None:
        self._cache: Dict[str, Optional[GeocodeResult]] = {}
        self._destination_cache: Dict[str, Optional[DestinationInfo]] = {}
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def geocode(self, query: str) -> Optional[GeocodeResult]:
        normalized = clean_geocode_query(query)
        if not normalized:
            return None

        destination = self._resolve_destination(_destination_hint(query))
        raw_bbox = destination[0] if destination else None
        viewbox = _pad_box(raw_bbox, _VIEWBOX_PADDING_DEGREES)

        for candidate in _candidate_queries(normalized):
            result = self._geocode_single(candidate, viewbox)
            if result is not None:
                return result

        # A city's administrative bounding box can be wildly oversized for
        # this purpose (confirmed: Nominatim's box for "Tokyo" spans the
        # whole of Japan, including islands ~1,000km away, since Tokyo
        # Prefecture legally includes them) -- so the tight any-venue
        # fallback is centered on the destination's resolved point instead.
        if destination:
            anchor = destination[1]
            venue_name = _venue_name(normalized)

            tight_viewbox = _point_viewbox(anchor, _ANY_VENUE_PADDING_DEGREES)
            result = self._find_any_venue_in_city(venue_name, tight_viewbox, anchor)
            if result is not None:
                return result

            day_trip_viewbox = _point_viewbox(anchor, _DAY_TRIP_VENUE_PADDING_DEGREES)
            result = self._find_any_venue_in_city(venue_name, day_trip_viewbox, anchor)
            if result is not None:
                return result

            # Nothing matched by name at all, at any radius -- rather than
            # dropping the activity from the map entirely, place it at the
            # destination's own center point so it still shows up roughly
            # where it should, clearly flagged as approximate (is_approximate)
            # so the frontend can render it distinctly instead of implying
            # it's the actual address.
            lat, lon = anchor
            near = _destination_hint(query)
            return (lat, lon, f"Approximate location near {near}", True)
        return None

    # Cached per destination string, not per padding, so the day-trip-sized
    # viewbox and the tight any-venue viewbox share one Nominatim lookup.
    def _resolve_destination(self, near: Optional[str]) -> Optional[DestinationInfo]:
        if not near:
            return None
        if near in self._destination_cache:
            return self._destination_cache[near]

        with self._lock:
            if near in self._destination_cache:
                return self._destination_cache[near]
            self._throttle()
            info = self._fetch_destination_info(near)
            self._destination_cache[near] = info
            return info

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

    def _find_any_venue_in_city(
        self, venue_name: str, viewbox: ViewBox, anchor: Tuple[float, float]
    ) -> Optional[GeocodeResult]:
        cache_key = f"any:{venue_name}|{viewbox}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
            self._throttle()
            result = self._fetch_any(venue_name, viewbox, anchor)
            self._cache[cache_key] = result
            return result

    def _fetch_any(self, query: str, viewbox: ViewBox, anchor: Tuple[float, float]) -> Optional[GeocodeResult]:
        params = {
            "q": query,
            "format": "json",
            "limit": 10,
            "viewbox": ",".join(str(coordinate) for coordinate in viewbox),
            "bounded": 1,
        }

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

        venues = []
        for candidate in results:
            if candidate.get("class") in _NON_VENUE_CLASSES or candidate.get("type") in _NON_VENUE_TYPES:
                continue
            try:
                venues.append(
                    (float(candidate["lat"]), float(candidate["lon"]), candidate.get("display_name", query), False)
                )
            except (KeyError, TypeError, ValueError):
                continue

        if not venues:
            return None

        # Nominatim's default order here is relevance/importance, not
        # distance -- without this, "any real branch" can pick one much
        # farther from the destination's center than another candidate it
        # already returned in the same response.
        return min(venues, key=lambda venue: _distance_squared((venue[0], venue[1]), anchor))

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
            return float(first["lat"]), float(first["lon"]), first.get("display_name", query), False
        except (KeyError, TypeError, ValueError):
            return None

    def _fetch_destination_info(self, query: str) -> Optional[DestinationInfo]:
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
            lat, lon = float(first["lat"]), float(first["lon"])
            min_lat, max_lat, min_lon, max_lon = (float(value) for value in first["boundingbox"])
        except (KeyError, TypeError, ValueError):
            return None

        return (min_lat, max_lat, min_lon, max_lon), (lat, lon)
