# LectureSight Dashboard
The LectureSight dashboard repo contains an html page to display the overview images from all running LectureSight applications and an index.php to receive the images from the LectureSight applications.

The code is based on https://github.com/cilt-uct/lecturesight-dashboard and has been simplified.

## Status (/status/index.php)

This file has a dual purpose in that if it receives a POST from a running LectureSight, it will write out the files for that venue into the venues folder. Otherwise if it gets called with a GET then it will review the venues folder and write out `venues.json` as a updated version of the current venue status. This is also what gets called by the cron image to update the venue status.

POST:
```
POST /status/index.php
Header:
    Content-Type: multipart/form-data
Body:
    overview-image [FILE] : Binary data of PNG that contains the overview image
    name    [TEXT] : name of the lecturesight venue
    profile [TEXT] : Actual profile of the configuration of this lecturesight (text/plain)
    status  [TEXT] : Status text (idle/active)
    metrics [TEXT] : Metrics coinfiguration file for the lecturesight (application/json)
```

Response:
```
HTTP/1.1 200 OK
File is valid, and was successfully uploaded.
```
```
HTTP/1.1 500 OK
Upload failed.
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
