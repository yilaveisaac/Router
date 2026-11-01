import json
import logging

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

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


@require_POST
@csrf_protect
def locate_api(request):
    # CHANGED: POST + JSON body (was GET with ?lat=&lng=) so precise coordinates
    # are not written into web-server access logs as part of the URL.
    try:
        payload = json.loads(request.body)
        # Rounded so nearby fixes share a cache entry in reverse_geocode
        lat = round(float(payload["lat"]), 4)
        lng = round(float(payload["lng"]), 4)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Provide lat and lng."}, status=400)

    return JsonResponse({"label": reverse_geocode(lat, lng)})


# NEW: guide pages. The slug is also the template file name in templates/guides/.
GUIDES = [
    {
        "slug": "how-distance-and-travel-time-are-calculated",
        "title": "How distance and travel time are calculated, and why they differ from Google Maps",
        "summary": "What happens between typing a destination and seeing a route, and how far to trust the numbers.",
    },
    {
        "slug": "estimate-fuel-cost-for-a-road-trip",
        "title": "How to estimate fuel cost for a road trip",
        "summary": "A simple formula, a worked example and the extras that push costs up.",
    },
    {
        "slug": "distances-between-nigerian-cities",
        "title": "Distances and driving times between major Nigerian cities",
        "summary": "Road distances and free-flow driving times for popular intercity routes.",
    },
    {
        "slug": "location-not-detected-fix",
        "title": "Location not detected? How to allow location access in your browser",
        "summary": "Fix permission and device settings, and learn how live location works.",
    },
    {
        "slug": "road-trip-planning-checklist",
        "title": "A road trip planning checklist for long drives",
        "summary": "What to check, carry and plan before you set off.",
    },
]


def guides_index(request):
    return render(request, "guides/index.html", {"guides": GUIDES})


def guide_detail(request, slug):
    guide = next((g for g in GUIDES if g["slug"] == slug), None)
    if guide is None:
        raise Http404("Guide not found")
    others = [g for g in GUIDES if g["slug"] != slug]
    return render(request, f"guides/{slug}.html", {"guide": guide, "guides": others})