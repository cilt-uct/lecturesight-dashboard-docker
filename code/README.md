# LectureSight Dashboard
The dashboard displays overview images from running LectureSight applications.
The Python application in `../app.py` receives updates and serves this directory's
public assets. Deployment instructions are in the repository README.

The code is based on https://github.com/cilt-uct/lecturesight-dashboard and has been simplified.

## Status (`/status/` or `/status/index.php`)

POST writes validated venue data into `venues/`. GET returns `1` for compatibility
with old health/cron calls; it no longer writes a file. `/venues.json` generates
the dashboard's `{name: [last_updated, status]}` object on demand. Timestamps
use Africa/Johannesburg time in `YYYY-MM-DD HH:MM:SS` format.

POST:
```
POST /status/index.php
Header:
    Content-Type: multipart/form-data
Body:
    overview-image [FILE, required] : Valid PNG, at most 16 million pixels
    name    [TEXT, required] : 1–30 ASCII letters, digits, underscores or hyphens
    profile [TEXT, optional] : Scene profile (text/plain)
    status  [TEXT, optional] : idle, active, offline or recording; at most 64 characters
    metrics [TEXT, optional] : Valid JSON, excluding NaN/Infinity
```

Response:
```
HTTP/1.1 200 OK
File is valid, and was successfully uploaded.
```
```
HTTP/1.1 400 Bad Request
Invalid input (no venue files written).
```

GET:
```
GET /status/index.php
```
Response:
```
HTTP/1.1 200 OK
1
```

The request limit is 8 MiB, with at most 256 KiB per text field. Repeated or
unknown fields are rejected. Missing optional fields leave their existing files
unchanged. Invalid input returns 400, oversized requests return 413, and storage
failures return 500. If `STATUS_TOKEN` is configured, POST also requires
HTTP bearer authentication using its configured value; otherwise it returns 401.
Browser-originated requests with Origin or cross-site Fetch Metadata return 403.
Only GET/HEAD and POST
are supported here (plus automatic OPTIONS).

## API (`/api/` or `/api/index.php`)

GET returns an array of `{name, last_updated, status}` objects, or `[]` when empty.
Other write methods return 405. `/venues.json` returns `{}` when empty.
Venue lists are sorted by name and include only valid status files.
GET/HEAD `/venues/<name>-overview.png`, `-profile.scn`, `-metrics.json` and
`-status.txt` serve the corresponding data with explicit content types.
