import io
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import NotFound

from app import app, venue_path, write_file


def png_bytes(size=(1, 1)):
    output = io.BytesIO()
    Image.new("1", size).save(output, format="PNG")
    return output.getvalue()


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.original_config = app.config.copy()
        self.addCleanup(app.config.update, self.original_config)
        app.config.update(TESTING=True, VENUES_DIR=self.directory.name, STATUS_TOKEN="")
        self.client = app.test_client()

    def post(self, fields=None, image=None, route="/status/", **kwargs):
        data = {
            "name": "A-venue_1",
            "status": "active",
            "overview-image": (io.BytesIO(png_bytes() if image is None else image), "../../x.php"),
        }
        data.update(fields or {})
        data = {key: value for key, value in data.items() if value is not None}
        return self.client.post(route, data=data, content_type="multipart/form-data", **kwargs)

    def test_empty_routes_and_methods(self):
        for route in ("/api/", "/api/index.php"):
            self.assertEqual(self.client.get(route).json, [])
            self.assertEqual(self.post(route=route).status_code, 405)
        self.assertEqual(self.client.get("/venues.json").json, {})
        for route in ("/status/", "/status/index.php"):
            self.assertEqual(self.client.get(route).text, "1")
            self.assertEqual(self.client.put(route).status_code, 405)
        self.assertEqual(list(self.path.iterdir()), [])

    def test_upload_and_legacy_routes(self):
        profile = "SIZE 0 0 0 640 480\nCALIBRATION lectern 1 2 3 4"
        for route in ("/status/", "/status/index.php"):
            response = self.post({"metrics": '{"cpu": 1}', "profile": profile}, route=route)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, "File is valid, and was successfully uploaded.\n")
        timestamp = 1767225600
        os.utime(self.path / "A-venue_1-status.txt", (timestamp, timestamp))
        venue = {
            "name": "A-venue_1", "last_updated": "2026-01-01 02:00:00", "status": "active"
        }
        self.assertEqual(self.client.get("/api/").json, [venue])
        self.assertEqual(
            self.client.get("/venues.json").json,
            {"A-venue_1": [venue["last_updated"], "active"]},
        )
        self.assertFalse((self.path.parent / "venues.json").exists())
        expected = {
            "overview.png": ("image/png", png_bytes()),
            "profile.scn": ("text/plain", profile.encode()),
            "metrics.json": ("application/json", b'{"cpu": 1}'),
            "status.txt": ("text/plain", b"active"),
        }
        for suffix, (mimetype, data) in expected.items():
            response = self.client.get("/venues/A-venue_1-" + suffix)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, mimetype)
            self.assertEqual(response.data, data)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("sandbox", response.headers["Content-Security-Policy"])
            response.close()
        self.assertEqual(len(list(self.path.iterdir())), 4)

    def test_optional_fields_preserve_data(self):
        self.assertEqual(self.post({"profile": "original"}).status_code, 200)
        self.assertEqual(self.post({"status": None}).status_code, 200)
        self.assertEqual((self.path / "A-venue_1-profile.scn").read_text(), "original")
        self.assertEqual((self.path / "A-venue_1-status.txt").read_text(), "active")

    def test_invalid_names_and_fields_do_not_write(self):
        for name in ("", "../escape", "/tmp/file", "a\n", "a" * 31, "vénue", "__proto__!"):
            with self.subTest(name=name):
                self.assertEqual(self.post({"name": name}).status_code, 400)
        for fields in (
            {"name": None},
            {"status": "<script>alert(1)</script>"},
            {"status": " " * 65 + "idle"},
            {"metrics": "not JSON"},
            {"metrics": '{"cpu": NaN}'},
            {"metrics": "[" * 2000},
            {"unknown": "value"},
        ):
            with self.subTest(fields=fields):
                self.assertEqual(self.post(fields).status_code, 400)
        self.assertEqual(list(self.path.iterdir()), [])

    def test_valid_names_and_statuses(self):
        for name in ("a" * 30, "_venue", "1", "-venue"):
            self.assertEqual(self.post({"name": name}).status_code, 200)
        for status in ("idle", "active", "recording", "offline", " idle\n"):
            self.assertEqual(self.post({"status": status}).status_code, 200)
            self.assertEqual(self.client.get("/api/").json[2]["status"], status.strip())

    def test_missing_duplicate_or_fake_images(self):
        for data in (
            {"name": "venue", "status": "idle"},
            MultiDict([
                ("name", "one"), ("name", "two"),
                ("overview-image", (io.BytesIO(png_bytes()), "x.png")),
            ]),
            MultiDict([
                ("name", "venue"),
                ("overview-image", (io.BytesIO(png_bytes()), "x.png")),
                ("overview-image", (io.BytesIO(png_bytes()), "y.png")),
            ]),
        ):
            self.assertEqual(self.client.post(
                "/status/", data=data, content_type="multipart/form-data"
            ).status_code, 400)
        for image in (b"", b"<?php echo 'bad'; ?>", png_bytes()[:32], png_bytes((5000, 4000))):
            with self.subTest(length=len(image)):
                self.assertEqual(self.post(image=image).status_code, 400)
        self.assertEqual(list(self.path.iterdir()), [])

    def test_limits(self):
        self.assertEqual(self.post({"profile": "x" * (256 * 1024 + 1)}).status_code, 413)
        app.config["MAX_CONTENT_LENGTH"] = 1024
        self.assertEqual(self.post(image=b"x" * 2048).status_code, 413)
        self.assertEqual(list(self.path.iterdir()), [])

    def test_token_and_cross_site_protection(self):
        app.config["STATUS_TOKEN"] = "unit-test-value"
        for headers in ({}, {"Authorization": "invalid"}):
            self.assertEqual(self.post(headers=headers).status_code, 401)
        headers = {"Authorization": "Bearer " + app.config["STATUS_TOKEN"]}
        self.assertEqual(self.post(headers=headers).status_code, 200)
        app.config["STATUS_TOKEN"] = ""
        for headers in ({"Origin": "https://example.invalid"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.post(headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/status/", data={"name": "venue"}).status_code, 400)

    def test_static_allowlist_and_traversal(self):
        for route in ("/", "/index.html", "/css/app.css", "/js/jquery.min.js", "/robots.txt"):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            response.close()
        for route in (
            "/app.py", "/requirements.txt", "/README.md", "/status/app.py",
            "/venues/index.html", "/venues/../app.py", "/css/../README.md",
            "/js/../venues/A-status.txt", "/css/%2e%2e/README.md", "/.env",
        ):
            self.assertEqual(self.client.get(route).status_code, 404, route)

    def test_venue_path_defense_in_depth(self):
        for filename in ("../A-status.txt", "/tmp/A-status.txt", "x/../A-status.txt", "x.py"):
            with self.subTest(filename=filename), self.assertRaises(NotFound):
                venue_path(filename)
        self.assertEqual(venue_path("A-status.txt"), self.path / "A-status.txt")

    def test_prototype_name_is_preserved_as_data(self):
        self.assertEqual(self.post({"name": "__proto__"}).status_code, 200)
        self.assertEqual(self.client.get("/api/").json[0]["name"], "__proto__")
        self.assertEqual(
            self.client.get("/venues.json").json["__proto__"][1], "active"
        )

    def test_legacy_data_is_filtered_and_sorted(self):
        for name, status in (
            ("B", "idle\n"), ("A", "active"), ("bad.name", "idle"),
            ("unsafe", "<img src=x onerror=alert(1)>"),
        ):
            (self.path / f"{name}-status.txt").write_text(status)
        self.assertEqual(
            [(venue["name"], venue["status"]) for venue in self.client.get("/api/").json],
            [("A", "active"), ("B", "idle")],
        )

    def test_symlinks_are_not_read_or_written(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private.txt"
            target.write_text("idle")
            (self.path / "A-venue_1-status.txt").symlink_to(target)
            self.assertEqual(self.client.get("/api/").json, [])
            self.assertEqual(self.client.get("/venues/A-venue_1-status.txt").status_code, 404)
            self.assertEqual(self.post().status_code, 404)
            self.assertEqual(target.read_text(), "idle")

    def test_atomic_replacement_and_error_cleanup(self):
        target = self.path / "A-status.txt"
        target.write_bytes(b"old")
        with target.open("rb") as previous:
            write_file(target, b"new")
            self.assertEqual(previous.read(), b"old")
        self.assertEqual(target.read_bytes(), b"new")
        with patch("app.os.replace", side_effect=OSError("private filesystem details")):
            with self.assertLogs(app.logger, level="ERROR"):
                response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private filesystem details", response.text)
        self.assertEqual(list(self.path.iterdir()), [target])

    def test_concurrent_writes_leave_complete_files(self):
        target = self.path / "A-status.txt"
        payloads = [str(i).encode() * 1024 for i in range(10)]
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(lambda data: write_file(target, data), payloads))
        self.assertIn(target.read_bytes(), payloads)
        self.assertEqual(list(self.path.iterdir()), [target])


if __name__ == "__main__":
    unittest.main()
