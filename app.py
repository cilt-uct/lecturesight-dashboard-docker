import hmac
import io
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, abort, jsonify, request, send_from_directory
from PIL import Image, UnidentifiedImageError
from werkzeug.security import safe_join

CODE_DIR = Path(__file__).parent / "code"
NAME = re.compile(r"[A-Za-z0-9_-]{1,30}")
VENUE_FILE = re.compile(r"([A-Za-z0-9_-]{1,30})-(status\.txt|metrics\.json|profile\.scn|overview\.png)")
STATUSES = {"idle", "active", "offline", "recording"}
TIMEZONE = ZoneInfo("Africa/Johannesburg")

app = Flask(__name__, static_folder=None)
app.config.update(
    VENUES_DIR=os.environ.get("VENUES_DIR", str(CODE_DIR / "venues")),
    STATUS_TOKEN=os.environ.get("STATUS_TOKEN", ""),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    MAX_FORM_MEMORY_SIZE=512 * 1024,
    MAX_FORM_PARTS=10,
)


def venue_path(filename):
    joined = safe_join(str(app.config["VENUES_DIR"]), filename)
    if joined is None or not VENUE_FILE.fullmatch(filename):
        abort(404)
    path = Path(joined)
    if path.is_symlink():
        abort(404)
    return path


def read_venues():
    venues = []
    for path in sorted(Path(app.config["VENUES_DIR"]).glob("*-status.txt")):
        name = path.name.removesuffix("-status.txt")
        if not NAME.fullmatch(name) or path.is_symlink() or not path.is_file():
            continue
        with path.open(encoding="utf-8") as source:
            status = source.read(65).strip()
            updated = datetime.fromtimestamp(os.fstat(source.fileno()).st_mtime, TIMEZONE)
        if status not in STATUSES:
            continue
        venues.append({
            "name": name,
            "last_updated": updated.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
        })
    return venues


def write_file(path, data):
    # Replace rather than truncate so concurrent readers never see partial files.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as target:
        temporary = Path(target.name)
        try:
            target.write(data)
            target.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(OSError)
def storage_error(error):
    app.logger.exception("Venue storage operation failed")
    return "Venue storage is unavailable.\n", 500


@app.route("/status/", methods=["GET", "POST"])
@app.route("/status/index.php", methods=["GET", "POST"])
def status():
    if request.method == "GET":
        # venues.json is now generated on demand; legacy cron calls remain valid.
        return "1"

    token = app.config["STATUS_TOKEN"]
    if token and not hmac.compare_digest(
        request.headers.get("Authorization", "").encode(), ("Bearer " + token).encode()
    ):
        abort(401)
    if request.headers.get("Origin") or request.headers.get("Sec-Fetch-Site") == "cross-site":
        abort(403, "Updates must be sent by a server, not a browser.")
    if request.mimetype != "multipart/form-data":
        abort(400, "Expected multipart/form-data.")
    fields = {"name", "status", "metrics", "profile"}
    if (
        set(request.form) - fields
        or set(request.files) != {"overview-image"}
        or any(len(request.form.getlist(key)) != 1 for key in request.form)
        or len(request.files.getlist("overview-image")) != 1
    ):
        abort(400, "Unexpected or repeated fields.")
    name = request.form.get("name", "")
    if not NAME.fullmatch(name):
        abort(400, "Invalid or missing venue name.")

    files = {}
    for field, suffix in (
        ("status", "status.txt"), ("metrics", "metrics.json"), ("profile", "profile.scn")
    ):
        if field in request.form:
            value = request.form[field]
            if len(value.encode()) > 256 * 1024:
                abort(413)
            if field == "status" and (len(value) > 64 or value.strip() not in STATUSES):
                abort(400, "Invalid status.")
            if field == "metrics":
                try:
                    json.loads(value, parse_constant=lambda value: abort(400, "Invalid JSON."))
                except (ValueError, RecursionError):
                    abort(400, "Invalid JSON.")
            files[suffix] = value.encode()

    image = request.files["overview-image"].read()
    try:
        with Image.open(io.BytesIO(image), formats=["PNG"]) as png:
            if png.width * png.height > 16_000_000:
                abort(400, "Image dimensions are too large.")
            png.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        abort(400, "Expected a valid PNG image.")
    files["overview.png"] = image

    # Validate every input before writing any venue data; ignore uploaded filenames.
    for suffix, data in files.items():
        write_file(venue_path(f"{name}-{suffix}"), data)
    return "File is valid, and was successfully uploaded.\n"


@app.get("/api/")
@app.get("/api/index.php")
def api():
    return jsonify(read_venues())


@app.get("/venues.json")
def venues_json():
    return jsonify({
        venue["name"]: [venue["last_updated"], venue["status"]]
        for venue in read_venues()
    })


@app.get("/venues/<filename>")
def venue_file(filename):
    path = venue_path(filename)
    response = send_from_directory(path.parent, path.name)
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    if filename.endswith("-overview.png"):
        response.mimetype = "image/png"
    elif filename.endswith("-metrics.json"):
        response.mimetype = "application/json"
    else:
        response.mimetype = "text/plain"
    return response


@app.get("/")
@app.get("/<path:filename>")
def static_file(filename="index.html"):
    if filename in {"index.html", "robots.txt", "humans.txt"}:
        return send_from_directory(CODE_DIR, filename)
    directory, separator, asset = filename.partition("/")
    if directory not in {"css", "js"} or not separator:
        abort(404)
    return send_from_directory(CODE_DIR / directory, asset)
