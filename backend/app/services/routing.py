from typing import Dict, List, Tuple

import httpx

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1"
USER_AGENT = "TravelSense/1.0 (https://travelsense.app)"

# The public OSRM demo server only has a "driving" profile configured -- it
# accepts other profile names in the URL without validating them, but always
# routes and times as if driving. So we request "driving" honestly and trust
# its real distance/duration for that mode, then derive a walking estimate
# from the same distance at a fixed walking pace. There's no free, no-API-key
# source for real transit times, so we don't attempt to estimate those here.
WALKING_SPEED_M_PER_S = 1.4  # ~5 km/h, a typical walking pace


class RoutingError(ValueError):
    pass


class RoutingService:
    def get_route(self, coordinates: List[Tuple[float, float]]) -> Dict:
        if len(coordinates) < 2:
            raise RoutingError("Need at least 2 points to route between.")

        # OSRM expects "lng,lat" pairs, coordinates come in as (lat, lng).
        coord_str = ";".join(f"{lng},{lat}" for lat, lng in coordinates)
        url = f"{OSRM_BASE_URL}/driving/{coord_str}"

        try:
            response = httpx.get(
                url,
                params={"overview": "full", "geometries": "geojson"},
                headers={"User-Agent": USER_AGENT},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingError(f"Could not compute a route: {exc}") from exc

        if data.get("code") != "Ok" or not data.get("routes"):
            raise RoutingError("No route found between these stops.")

        route = data["routes"][0]
        legs = [
            {
                "distance_m": leg.get("distance", 0.0),
                "driving_duration_s": leg.get("duration", 0.0),
                "walking_duration_s": leg.get("distance", 0.0) / WALKING_SPEED_M_PER_S,
            }
            for leg in route.get("legs", [])
        ]

        total_distance = route.get("distance", 0.0)
        return {
            "geometry": route.get("geometry"),
            "distance_m": total_distance,
            "driving_duration_s": route.get("duration", 0.0),
            "walking_duration_s": total_distance / WALKING_SPEED_M_PER_S,
            "legs": legs,
        }
