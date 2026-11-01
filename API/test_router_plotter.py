"""
Run with:  python manage.py test API.test_route_plotter
(or `python -m unittest` from the folder containing the API package).

These tests use a canned OSRM response, so they check OUR maths and ordering
(units, lon/lat order, snapping warnings), not OSRM's road data itself.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from API import route_plotter as rp


def fake_osrm(distance=123456.7, duration=5400.0, snaps=(5.0, 8.0)):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "code": "Ok",
        "routes": [{
            "distance": distance,
            "duration": duration,
            "geometry": {"coordinates": [[3.40, 6.50], [3.50, 6.60], [3.90, 7.38]]},  # lon, lat
        }],
        "waypoints": [{"distance": snaps[0]}, {"distance": snaps[1]}],
    }
    return resp


class GetRouteTests(TestCase):
    def setUp(self):
        self.geocode = patch.object(rp, "geocode", return_value=(3.9, 7.38, "Ibadan, Oyo, Nigeria")).start()
        self.reverse = patch.object(rp, "reverse_geocode", return_value="Lagos").start()
        self.addCleanup(patch.stopall)

    @patch.object(rp.requests, "get")
    def test_units_are_passed_through_in_metres_and_seconds(self, get):
        get.return_value = fake_osrm(distance=123456.7, duration=5400.0)
        data = rp.get_route((6.5, 3.4), "Ibadan")
        self.assertEqual(data["distance_m"], 123456.7)
        self.assertEqual(data["duration_s"], 5400.0)

    @patch.object(rp.requests, "get")
    def test_request_uses_lon_lat_order(self, get):
        get.return_value = fake_osrm()
        rp.get_route((6.5, 3.4), "Ibadan")  # origin lat 6.5, lon 3.4
        url = get.call_args[0][0]
        self.assertIn("3.4,6.5;3.9,7.38", url)

    @patch.object(rp.requests, "get")
    def test_coordinates_flipped_for_leaflet(self, get):
        get.return_value = fake_osrm()
        data = rp.get_route((6.5, 3.4), "Ibadan")
        self.assertEqual(data["coordinates"][0], [6.5, 3.4])   # [lat, lon]
        self.assertEqual(data["coordinates"][-1], [7.38, 3.9])

    @patch.object(rp.requests, "get")
    def test_no_warning_when_points_are_near_roads(self, get):
        get.return_value = fake_osrm(snaps=(5.0, 8.0))
        self.assertEqual(rp.get_route((6.5, 3.4), "Ibadan")["warnings"], [])

    @patch.object(rp.requests, "get")
    def test_warns_when_destination_far_from_road(self, get):
        get.return_value = fake_osrm(snaps=(5.0, 2300.0))
        warnings = rp.get_route((6.5, 3.4), "Ibadan")["warnings"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("destination", warnings[0].lower())

    @patch.object(rp.requests, "get")
    def test_no_route_raises(self, get):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"code": "NoRoute", "routes": []}
        get.return_value = resp
        with self.assertRaises(ValueError):
            rp.get_route((6.5, 3.4), "Ibadan")

    def test_invalid_origin_coordinates_raise(self):
        with self.assertRaises(ValueError):
            rp.get_route((95.0, 3.4), "Ibadan")
        with self.assertRaises(ValueError):
            rp.get_route((6.5, 200.0), "Ibadan")