# ─────────────────────────────────────────────────────────
# BASE IMAGE
# ─────────────────────────────────────────────────────────
# "python:3.10-slim-bookworm" is a minimal Python image.
# "slim" means it has only the bare essentials — no extras.
# "bookworm" is the Debian 12 version (stable & compatible with Playwright).
FROM python:3.10-slim-bookworm

# ─────────────────────────────────────────────────────────
# ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────────────────
# These two lines make Python behave better inside Docker:
# PYTHONUNBUFFERED=1   → Print logs immediately (no delay)
# PYTHONDONTWRITEBYTECODE=1 → Don't create .pyc cache files (saves space)
# PLAYWRIGHT_BROWSERS_PATH → Store browser in /ms-playwright (organized location)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ─────────────────────────────────────────────────────────
# WORKING DIRECTORY
# ─────────────────────────────────────────────────────────
# All commands from here will run inside /app inside the container.
# Like doing "cd /app" permanently.
WORKDIR /app

# ─────────────────────────────────────────────────────────
# COPY REQUIREMENTS FIRST (Smart Layer Caching Trick)
# ─────────────────────────────────────────────────────────
# WHY: Docker builds images in layers (like a stack of pancakes).
# It re-uses cached layers if nothing changed.
# By copying ONLY requirements.txt first (before your code),
# Docker can reuse the pip install step every time you change
# your code — saving minutes on every rebuild!
COPY requirements.txt .

# ─────────────────────────────────────────────────────────
# INSTALL EVERYTHING IN ONE SINGLE RUN COMMAND
# ─────────────────────────────────────────────────────────
# WHY ONE BIG RUN? Each RUN creates a new "layer" in the image.
# More layers = bigger image + slower startup.
# Combining them with "&&" keeps it all in ONE layer.
#
# What each part does:
# 1. apt-get update              → Refresh the list of available packages
# 2. apt-get install curl        → Download tool (needed by Playwright)
# 3. pip install -r requirements → Install all your Python packages
# 4. playwright install chromium → Download only Chromium browser (not FFMPEG/Firefox)
#                                  We use chromium only — saves ~50MB vs full install
# 5. rm -rf /var/lib/apt/lists/* → Delete the package list cache (we don't need it after installing)
# 6. rm -rf /root/.cache/pip    → Delete pip's download cache (already installed, cache is waste)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache/pip

# ─────────────────────────────────────────────────────────
# COPY SOURCE CODE
# ─────────────────────────────────────────────────────────
# WHY COPY CODE LAST? Your code changes often.
# Putting it last means all the slow steps above (pip install,
# playwright install) are cached and DON'T re-run when you
# only change a .py file. This makes rebuilds much faster!
COPY . /app/

# Create necessary output directories
RUN mkdir -p data/pages downloads

# ─────────────────────────────────────────────────────────
# EXPOSE PORT
# ─────────────────────────────────────────────────────────
# Tell Docker that this container listens on port 8000.
# This is like labelling a door — it doesn't open it, just marks it.
EXPOSE 8000

# ─────────────────────────────────────────────────────────
# STARTUP COMMAND
# ─────────────────────────────────────────────────────────
# This is the command that runs when the container starts.
# uvicorn is the web server that serves your FastAPI (cms.py) app.
# --host 0.0.0.0 means accept connections from anywhere (needed inside Docker)
# --port 8000 is the port to listen on
CMD ["uvicorn", "cms:app", "--host", "0.0.0.0", "--port", "8000"]
