# mcr.microsoft.com/playwright (the Node-focused variant) ships Chromium and
# all the apt-level browser deps already installed at /ms-playwright. We add
# Python on top and install the playwright Python package, which finds the
# pre-installed browser via PLAYWRIGHT_BROWSERS_PATH (set in the base image).
#
# We tried two simpler bases first and rejected them:
#   * mcr.microsoft.com/playwright/python:v1.49.0-jammy — installs the
#     `playwright` Python package only under the non-root `pwuser` so root
#     (which we need for cookies.txt write perms) gets ModuleNotFoundError.
#   * python:3.12-slim — Debian-based, so `playwright install --with-deps`
#     fails on Ubuntu-only fonts (ttf-ubuntu-font-family, ttf-unifont).
FROM mcr.microsoft.com/playwright:v1.49.0-jammy

# Python + tini. tini so SIGTERM from `docker compose down` cuts through the
# long sleep in the entrypoint loop.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv tini ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pin playwright to match the Chromium revision shipped in the base image.
RUN pip3 install --no-cache-dir 'playwright==1.49.0' 'redis>=5.0,<6'

WORKDIR /app
COPY refresh.py /app/refresh.py

# Image already runs as root by default; keep it that way explicitly so a
# future base-image change doesn't silently downgrade us and break the
# host-mount writes to secrets/cookies.txt.
USER root

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "/app/refresh.py"]
