from typing import Dict, List, Tuple

import httpx

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1"
USER_AGENT = "TravelSense/1.0 (https://travelsense.app)"

# The public OSRM demo server only has a "car" profile configured -- it
# accepts any profile name in the URL without validating it, but always
# routes and times as if driving. Real self-hosted OSRM deployments do
# support "foot"/"bike", so we still request "foot" for forward
# compatibility, but we can't trust the returned duration for walking: a
# 15-minute walk comes back timed as a 90-second drive. Distance and the
# route geometry/steps (which roads to take) are still real and useful, so
# we keep those and recompute duration ourselves from a walking speed.
WALKING_SPEED_M_PER_S = 1.4  # ~5 km/h, a typical walking pace


class RoutingError(ValueError):
    pass


class RoutingService:
    def get_route(self, coordinates: List[Tuple[float, float]]) -> Dict:
        if len(coordinates) < 2:
            raise RoutingError("Need at least 2 points to route between.")

        # OSRM expects "lng,lat" pairs, coordinates come in as (lat, lng).
        coord_str = ";".join(f"{lng},{lat}" for lat, lng in coordinates)
        url = f"{OSRM_BASE_URL}/foot/{coord_str}"

        try:
            response = httpx.get(
                url,
                params={"overview": "full", "geometries": "geojson", "steps": "true"},
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
        legs = []
        for leg in route.get("legs", []):
            steps = [
                {
                    "instruction": _format_maneuver(step.get("maneuver", {}), step.get("name", "")),
                    "distance_m": step.get("distance", 0.0),
                }
                for step in leg.get("steps", [])
                # OSRM emits a zero-distance "arrive" step at the very end of
                # every leg; it duplicates the leg's own arrival, so drop it.
                if step.get("maneuver", {}).get("type") != "arrive"
            ]
            leg_distance = leg.get("distance", 0.0)
            legs.append(
                {
                    "distance_m": leg_distance,
                    "duration_s": leg_distance / WALKING_SPEED_M_PER_S,
                    "steps": steps,
                }
            )

        total_distance = route.get("distance", 0.0)
        return {
            "geometry": route.get("geometry"),
            "distance_m": total_distance,
            "duration_s": total_distance / WALKING_SPEED_M_PER_S,
            "legs": legs,
        }


def _format_maneuver(maneuver: Dict, road_name: str) -> str:
    maneuver_type = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")
    name = road_name.strip() or "the road"

    if maneuver_type == "depart":
        return f"Head out on {name}"
    if maneuver_type == "arrive":
        return "Arrive at your destination"
    if maneuver_type == "roundabout" or maneuver_type == "rotary":
        return f"Enter the roundabout and take the exit onto {name}"
    if maneuver_type in ("turn", "end of road", "fork", "merge", "ramp", "roundabout turn"):
        if modifier:
            return f"Turn {modifier} onto {name}"
        return f"Continue onto {name}"
    if maneuver_type in ("new name", "continue"):
        return f"Continue on {name}"
    return f"Continue on {name}"
