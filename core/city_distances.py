import time

from django.core.management.base import BaseCommand

from API.route_plotter import geocode, get_route

# Edit this list to the routes you want in the guide.
PAIRS = [
    ("Lagos", "Ibadan"),
    ("Lagos", "Abuja"),
    ("Lagos", "Benin City"),
    ("Lagos", "Port Harcourt"),
    ("Abuja", "Kaduna"),
    ("Abuja", "Kano"),
    ("Abuja", "Port Harcourt"),
    ("Port Harcourt", "Enugu"),
]


def fmt_duration(seconds):
    hours, mins = divmod(int(round(seconds / 60)), 60)
    return f"{hours} h {mins:02d} min" if hours else f"{mins} min"


class Command(BaseCommand):
    help = "Print <tr> rows of road distance and free-flow time for the city-distances guide."

    def handle(self, *args, **options):
        for origin, destination in PAIRS:
            try:
                o_lon, o_lat, _ = geocode(f"{origin}, Nigeria")
                data = get_route((o_lat, o_lon), f"{destination}, Nigeria")
            except Exception as exc:
                self.stderr.write(f"SKIPPED {origin} -> {destination}: {exc}")
                continue

            km = data["distance_m"] / 1000
            self.stdout.write(
                f"<tr><td>{origin} &rarr; {destination}</td>"
                f"<td>{km:.0f} km</td>"
                f"<td>{fmt_duration(data['duration_s'])}</td></tr>"
            )
            time.sleep(2)  # stay inside Nominatim's 1 request/second policy