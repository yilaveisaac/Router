import os
import logging
from functools import lru_cache

import requests
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

# Nominatim's usage policy requires a real, identifying User-Agent.
# Replace the contact part with your own app name and email.
_USER_AGENT = "geo-router-app (contact: YOUR_EMAIL_HERE)"
_geolocator = Nominatim(user_agent=_USER_AGENT)

# Point this at your own OSRM instance in production (set in the environment).
# The public demo server is for light, non-commercial use only.
OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")

# If a point is further than this from the nearest road, tell the user.
SNAP_WARNING_M = 500


@lru_cache(maxsize=256)
def geocode(location):
    """Return (lon, lat, matched_address) for a free-text place name."""
    result = _geolocator.geocode(location, timeout=10)
    if not result:
        raise ValueError(f"Could not find location: {location}")
    return (result.longitude, result.latitude, result.address)


@lru_cache(maxsize=256)
def reverse_geocode(lat, lon):
    """Best-effort short, readable label for coordinates (e.g. the user's GPS fix)."""
    try:
        result = _geolocator.reverse((lat, lon), timeout=10, addressdetails=True)
        if not result:
            return "Your location"
        addr = result.raw.get("address", {})
        street = addr.get("road") or addr.get("neighbourhood") or addr.get("suburb")
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county")
        state = addr.get("state")
        parts = [x for x in (street, city, state) if x]
        return ", ".join(parts) if parts else result.address
    except Exception:
        return "Your location"


def _fmt_m(metres):
    return f"{metres / 1000:.1f} km" if metres >= 1000 else f"{round(metres)} m"


def get_route(origin_coords, destination_name):
    """
    origin_coords: (lat, lon), typically the user's browser geolocation fix.
    destination_name: free-text place name, geocoded via Nominatim.

    Distances are returned in metres and durations in seconds (the units OSRM
    uses). Converting to km, miles or minutes is left to the caller, so there is
    one source of truth and one place where unit conversion happens.
    """
    origin_lat, origin_lon = origin_coords
    if not (-90 <= origin_lat <= 90 and -180 <= origin_lon <= 180):
        raise ValueError("Your location coordinates are not valid.")

    dest_lon, dest_lat, dest_address = geocode(destination_name)

    # OSRM expects longitude,latitude order.
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        "?overview=full&geometries=geojson"
    )
    response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
    response.raise_for_status()
    route_json = response.json()

    if route_json.get("code") != "Ok" or not route_json.get("routes"):
        raise ValueError("No route could be found between these points.")

    route = route_json["routes"][0]
    # OSRM's GeoJSON geometry is [lon, lat] per point. Leaflet wants [lat, lon].
    coordinates = [[lat, lon] for lon, lat in route["geometry"]["coordinates"]]

    distance_m = route["distance"]  # metres
    duration_s = route["duration"]  # seconds

    # OSRM snaps each input point to the nearest road and reports how far it moved.
    warnings = []
    snaps = [w.get("distance", 0) for w in route_json.get("waypoints", [])]
    if len(snaps) == 2:
        if snaps[0] > SNAP_WARNING_M:
            warnings.append(
                f"Your location is about {_fmt_m(snaps[0])} from the nearest road, "
                "so the route starts from the nearest road."
            )
        if snaps[1] > SNAP_WARNING_M:
            warnings.append(
                f"The destination is about {_fmt_m(snaps[1])} from the nearest road, "
                "so the route ends at the nearest road."
            )

    # Sanity check: a driving route should not be meaningfully shorter than the
    # straight line between the points (allowing for the snapping above).
    straight_line_m = geodesic((origin_lat, origin_lon), (dest_lat, dest_lon)).meters
    if distance_m + sum(snaps) < straight_line_m * 0.99:
        logger.warning(
            "Route shorter than straight line: route=%.0fm straight=%.0fm dest=%s",
            distance_m, straight_line_m, destination_name,
        )

    return {
        "coordinates": coordinates,
        "origin_label": reverse_geocode(origin_lat, origin_lon),
        "destination_label": destination_name,
        "destination_matched": dest_address,
        "distance_m": round(distance_m, 1),
        "duration_s": round(duration_s, 1),
        "straight_line_m": round(straight_line_m, 1),
        "warnings": warnings,
    }