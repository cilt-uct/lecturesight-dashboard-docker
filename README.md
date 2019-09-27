# LectureSight Dashboard in Docker
Simple dashboard for LectureSight overview images (Dockerized)

## Images

1. `web` [nginx:latest]: runs on port `5000` and uses the code defined in `/code`.
2. `php` [php:7-fpm]: runs all the php in `web`.
3. `cron` [alpine:3.10]: is defined in `/cron` and does a periodic call to `web/status/index.php`.

## Install

1. Clone the repository to a folder.
```
git clone https://github.com/cilt-uct/lecturesight-dashboard-docker
```
2. Configure apache or nginx to point to `http://127.0.0.1:5000`, making sure that only the appropriate IP's have access to `http://127.0.0.1:5000/status/`.
3. Configure LectureSight status update to use the enpoint as configured above.

NOTE: If you get access denied for updating the venues, then re-create the `/code/venues` folder.
