"""
Itinerary Agent – Tool 1: Distance & travel-time calculator.

Uses the Haversine formula plus a curated lookup of popular
destination coordinates to estimate distances and realistic
travel times between points of interest.
"""

import json
import math
from langchain_core.tools import tool


# ── curated coordinate database (easily extensible) ──────
_KNOWN_PLACES: dict[str, tuple[float, float]] = {
    # Europe
    "eiffel tower": (48.8584, 2.2945),
    "louvre museum": (48.8606, 2.3376),
    "notre-dame cathedral": (48.8530, 2.3499),
    "sacré-cœur": (48.8867, 2.3431),
    "arc de triomphe": (48.8738, 2.2950),
    "colosseum": (41.8902, 12.4922),
    "trevi fountain": (41.9009, 12.4833),
    "vatican city": (41.9029, 12.4534),
    "big ben": (51.5007, -0.1246),
    "tower of london": (51.5081, -0.0759),
    "buckingham palace": (51.5014, -0.1419),
    "sagrada familia": (41.4036, 2.1744),
    "park güell": (41.4145, 2.1527),
    "brandenburg gate": (52.5163, 13.3777),

    # Asia
    "taj mahal": (27.1751, 78.0421),
    "red fort": (28.6562, 77.2410),
    "gateway of india": (18.9220, 72.8347),
    "meiji shrine": (35.6764, 139.6993),
    "tokyo tower": (35.6586, 139.7454),
    "senso-ji temple": (35.7148, 139.7967),
    "great wall of china": (40.4319, 116.5704),
    "forbidden city": (39.9163, 116.3972),

    # Americas
    "statue of liberty": (40.6892, -74.0445),
    "times square": (40.7580, -73.9855),
    "central park": (40.7829, -73.9654),
    "golden gate bridge": (37.8199, -122.4783),
    "hollywood sign": (34.1341, -118.3215),
    "machu picchu": (-13.1631, -72.5450),

    # Other
    "sydney opera house": (-33.8568, 151.2153),
    "burj khalifa": (25.1972, 55.2744),
    "pyramids of giza": (29.9792, 31.1342),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_travel(distance_km: float) -> dict:
    """Heuristic travel-time estimates for different modes."""
    return {
        "walking_min": round(distance_km / 5 * 60),       # ~5 km/h
        "driving_min": round(distance_km / 40 * 60),      # ~40 km/h city avg
        "public_transit_min": round(distance_km / 25 * 60),  # ~25 km/h
    }


def _lookup(name: str) -> tuple[float, float] | None:
    return _KNOWN_PLACES.get(name.lower().strip())


@tool
def calculate_distance(origin: str, destination: str) -> str:
    """Calculate the approximate distance and travel time between two places.

    Useful for deciding how to order activities within a day and
    choosing realistic transit modes.

    Args:
        origin: Name of the starting point (e.g. "Eiffel Tower").
        destination: Name of the ending point (e.g. "Louvre Museum").

    Returns:
        JSON with distance_km, walking_min, driving_min, and
        public_transit_min estimates — or an error message.
    """
    o = _lookup(origin)
    d = _lookup(destination)
    if o is None or d is None:
        # Return a reasonable city-scale estimate instead of failing.
        # This prevents the LLM from looping trying different names.
        return json.dumps({
            "origin": origin,
            "destination": destination,
            "distance_km": 5.0,
            "walking_min": 60,
            "driving_min": 15,
            "public_transit_min": 20,
            "note": "Estimated (exact coordinates unavailable). "
                    "Assume typical intra-city distance. "
                    "Do NOT retry — proceed with planning.",
        })

    dist = _haversine_km(o[0], o[1], d[0], d[1])
    travel = _estimate_travel(dist)
    return json.dumps({
        "origin": origin,
        "destination": destination,
        "distance_km": round(dist, 2),
        **travel,
    })
