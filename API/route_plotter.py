import os
import logging
from functools import lru_cache

import requests
import pandas as pd
from geopy.geocoders import Nominatim

FILE = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(FILE)

logger = logging.getLogger(__name__)

# CHANGED: Nominatim's usage policy requires a real, identifying User-Agent
# (one app + contact per policy) — replace with your own app name/email.
_USER_AGENT = "geo-router-app ([email protected])"

# NEW: point this at your own OSRM instance in production (set in the environment).
# The public demo server is for light, non-commercial use only.
OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
_geolocator = Nominatim(user_agent=_USER_AGENT)


@lru_cache(maxsize=256)
def geocode(location):
    """Return (lon, lat) for a free-text place name."""
    result = _geolocator.geocode(location, timeout=10)
    if not result:
        raise ValueError(f"Could not find location: {location}")
    return (result.longitude, result.latitude)


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


@lru_cache(maxsize=1)
def _average_fuel_price():
    price_data = pd.read_csv(os.path.join(BASE_DIR, "fuel-prices-for-be-assessment.csv"))
    return float(price_data["Retail Price"].mean())


def get_route(origin_coords, destination_name):
    """
    origin_coords: (lat, lon) — typically the user's browser geolocation fix.
    destination_name: free-text place name, geocoded via Nominatim.
    Returns a JSON-serializable dict ready for the client to render on Leaflet.
    """
    origin_lat, origin_lon = origin_coords
    dest_lon, dest_lat = geocode(destination_name)

    start = f"{origin_lon},{origin_lat}"
    end = f"{dest_lon},{dest_lat}"

    # CHANGED: ask OSRM for full route geometry directly instead of looping
    # over every node and re-fetching each one individually from the OSM API.
    # That old approach was slow (dozens of blocking requests per route) and
    # violated the OSM API's usage policy against bulk per-node lookups.
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/{start};{end}"
        "?overview=full&geometries=geojson"
    )
    response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
    response.raise_for_status()
    route_json = response.json()

    if route_json.get("code") != "Ok" or not route_json.get("routes"):
        raise ValueError("No route could be found between these points.")

    route = route_json["routes"][0]
    # OSRM's GeoJSON geometry is [lon, lat] per point — Leaflet wants [lat, lon]
    coordinates = [[lat, lon] for lon, lat in route["geometry"]["coordinates"]]

    distance_miles = route["distance"] / 1609.34
    duration_minutes = route["duration"] / 60

    average_price = _average_fuel_price()
    gallons = distance_miles / 10  # assumes 10 miles/gallon
    total_fuel_cost = gallons * average_price

    return {
        "coordinates": coordinates,
        "origin_label": reverse_geocode(origin_lat, origin_lon),
        "destination_label": destination_name,
        "distance_miles": round(distance_miles, 1),
        "duration_minutes": round(duration_minutes, 1),
        "gallons": round(gallons, 2),
        "average_price": round(average_price, 2),
        "total_cost": round(total_fuel_cost, 2),
    }