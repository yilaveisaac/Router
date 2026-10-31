import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from API.route_plotter import get_route, reverse_geocode

logger = logging.getLogger(__name__)


def index(request):
    # CHANGED: page no longer handles the POST form submit directly —
    # the destination form now calls get_route_api via fetch() instead.
    return render(request, "index.html")


@require_POST
@csrf_protect
def get_route_api(request):
    # CHANGED: reads JSON body (was request.GET on a POST-only view, a mismatch
    # that meant this endpoint never actually worked)
    try:
        payload = json.loads(request.body)
        origin_lat = float(payload["origin_lat"])
        origin_lng = float(payload["origin_lng"])
        destination = payload["destination"].strip()
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid request. Provide origin_lat, origin_lng and destination."},
            status=400,
        )

    if not destination:
        return JsonResponse({"error": "Please enter a destination."}, status=400)

    try:
        data = get_route((origin_lat, origin_lng), destination)
    except ValueError as e:
        # Known, user-facing failure: bad destination name, no route found, etc.
        return JsonResponse({"error": str(e)}, status=404)
    except Exception:
        # CHANGED: unexpected failures are now logged instead of silently
        # swallowed, so you can actually see what broke in production
        logger.exception("Route lookup failed for destination=%s", destination)
        return JsonResponse(
            {"error": "Something went wrong finding that route. Please try again."},
            status=500,
        )

    return JsonResponse(data)


@require_GET
def locate_api(request):
    # NEW: turns the browser's GPS coordinates into a readable place name
    try:
        # Rounded so nearby fixes share a cache entry in reverse_geocode
        lat = round(float(request.GET["lat"]), 4)
        lng = round(float(request.GET["lng"]), 4)
    except (KeyError, ValueError):
        return JsonResponse({"error": "Provide lat and lng."}, status=400)

    return JsonResponse({"label": reverse_geocode(lat, lng)})