FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Africa/Johannesburg \
    DEBIAN_FRONTEND=noninteractive \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY code/ code/
RUN mkdir -p code/venues && chown 33:33 code/venues

USER 33:33
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-tmp-dir", "/tmp", "--no-control-socket", "--access-logfile", "-", "app:app"]
