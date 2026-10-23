# LectureSight Dashboard in Docker
Simple dashboard for LectureSight overview images, served by Python.

## Runtime

One non-root container runs Flask with Gunicorn on `127.0.0.1:5000`.
Pillow validates PNG uploads. These are the only direct dependencies, pinned in
`requirements.txt`. PHP, nginx and cron containers are no longer needed:
`/venues.json` is generated on each request, so updates appear immediately.

## Install

Requires Docker with Compose v2.

1. Clone the repository and enter its directory.
2. Make the persistent venue directory writable by the container's UID/GID 33.
   For an existing installation, back up this directory first; its files are reused.

```sh
sudo chown -R 33:33 code/venues
sudo chmod -R u+rwX code/venues
bash start.sh
```

3. Configure your host reverse proxy to forward to `http://127.0.0.1:5000`.
   Use HTTPS and restrict **both** `/status/` and `/status/index.php` to trusted
   LectureSight senders. Preserve the trailing-slash routes or the legacy `.php`
   URLs; these are Python routes, not PHP files.
4. Configure LectureSight to POST to `/status/` (existing `/status/index.php`
   configurations continue to work).

`bash start.sh` builds the image and removes the obsolete PHP/cron services.
`bash stop.sh` stops the dashboard without deleting venue data. Only `code/venues`
is mounted writable; application code is baked into the image and requires a rebuild
after changes. Old `code/venues.json` files are no longer used.

### Troubleshooting storage permissions

If uploads fail with `Permission denied: '/app/code/venues/tmp...'`, check the
running identity and bind-mount directory:

```sh
sudo docker compose exec web id
stat -c '%a %u:%g %n' code/venues
```

The container should report UID/GID `33:33`, and that identity needs write and
execute permission on the directory, not just write permission on existing files:
uploads create a temporary file there and atomically replace the destination.
The bind mount hides the directory ownership set during the image build.
After backing up existing venue data, apply the ownership and permission commands
in the install steps above, then rebuild and recreate the service:

```sh
sudo chown -R 33:33 code/venues
sudo chmod -R u+rwX code/venues

sudo docker compose up -d --build --force-recreate web
sudo docker compose logs --tail=50 web
```

Recreating is necessary after changing the image's `USER`; restarting an existing
container does not apply it. Do not remove `read_only` or run the service as root
to work around venue permissions.

## Security

Uploads require a venue name of 1–30 ASCII letters, digits, underscores or hyphens,
a valid PNG (maximum 16 million pixels), and at most 8 MiB per request.
Optional text fields are limited to 256 KiB each; status and metrics are validated
before any files are written. Uploaded filenames are ignored, writes use atomic
replacement, and only known venue file types and dashboard assets are served.
The container runs as UID/GID 33 with a read-only root filesystem and no capabilities.
Gunicorn's optional control socket is disabled so it does not try to create
`$HOME/.gunicorn` on that filesystem. Worker temporary files use writable `/tmp`.

For clients that support an Authorization header, set `STATUS_TOKEN` in the
deployment environment and use HTTP bearer authentication with every POST.
Use a long randomly generated token and do not commit it. Leave it unset only
when trusted-sender restrictions are enforced by the reverse proxy; legacy
LectureSight clients may not support this header. There is no built-in login or
rate limiter: protect uploads with proxy rate limits and monitor persistent disk
usage. Request limits do not cap the number of distinct venues.
Browser-originated uploads are rejected to prevent cross-site form submissions;
updates are a server-to-server interface.

Read endpoints expose venue images, status, profiles and metrics without
authentication, matching the original dashboard. Restrict the whole dashboard at
the reverse proxy if that information is private. Do not publish port 8000 directly.

## Development

Use Python 3.13 (3.12 is also supported):

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
gunicorn --bind 127.0.0.1:5000 app:app
```

`VENUES_DIR` can override the storage directory; it must already exist and be writable.
No separate lint configuration is provided.
