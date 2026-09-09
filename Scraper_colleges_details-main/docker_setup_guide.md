# 🐳 Docker Setup Guide: Scraper CMS

This document outlines everything you need to know about containerizing the Scraper CMS. It covers the installation of Docker on macOS, how the image is optimized for a headless browser (Playwright), and the exact commands to build and run your workload.

---

## 1. Installing Docker on macOS (Apple Silicon / Intel)

To run the container, you first need the Docker engine. 

1. **Download Docker Desktop**:
   - Go to the [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/) download page.
   - Select the version for **Apple Silicon** (if you have an M1/M2/M3 Mac) or **Intel** depending on your processor.
2. **Install**:
   - Open the downloaded `.dmg` file and drag the Docker icon into your Applications folder.
3. **Start Docker**:
   - Open Docker from your Applications. 
   - Grant it the necessary system permissions when prompted.
   - You will see the Docker whale icon in your top menu bar. Wait until it says "Docker Desktop is running".
4. **Verify Installation**:
   - Open your terminal and run:
     ```bash
     docker --version
     ```
   - It should output something like `Docker version 24.0.5, build ced0996`.

---

## 2. How We Achieved a Lightweight, Headless-Browser Image

Web scraping with full headless browsers (like Chromium) usually requires massive Docker images (>2GB) because of the underlying system graphics libraries required to render web pages. 

Here is how we optimized the `Dockerfile` to be as small and fast as possible:

1. **Slim Python Base (`python:3.10-slim`)**:
   Instead of using a full Ubuntu image or the standard `python:3.10` image, we used the `-slim` variant. This strips out hundreds of megabytes of unnecessary OS utilities.
2. **Targeted System Dependencies**:
   Instead of installing a full desktop environment, we manually installed only the specific shared libraries (like `libnss3`, `libxcomposite1`, etc.) that Chromium strictly requires to run in headless mode.
3. **Chromium-Only Playwright Installation**:
   By default, `playwright install` downloads Chromium, Firefox, and WebKit, taking up massive space. We optimized this by running `playwright install chromium --with-deps`, saving ~1GB of space by ignoring browsers we don't use.
4. **.dockerignore**:
   We added a `.dockerignore` file so that your local `data/`, `downloads/`, and `.git` folders are **not** copied into the image during the build process, significantly speeding up the build and reducing image size.
5. **Non-Root User Security**:
   The Dockerfile creates a `scraperuser` and switches to it. Running browsers as root inside Docker is a security risk; this ensures production readiness.

---

## 3. Building the Docker Image

With Docker running, open your terminal, navigate to the project directory (`/Users/tejreddym/Desktop/Office/myprep`), and run:

```bash
# Build the image and tag it as 'scraper-cms'
docker build -t scraper-cms .
```

*What happens here?*
- Docker downloads the slim Python image.
- It installs the system dependencies and Python packages.
- It downloads the headless Chromium browser.
- It packages your application code into the final image.

---

## 4. Running the Containerized Scraper

When running the container, you want to **mount your local `data` and `downloads` folders**. This ensures that any colleges scraped inside the container are saved directly to your Mac's hard drive, preventing data loss when the container stops.

Run this command in your project directory:

```bash
docker run -d \
  --name scraper-app \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/downloads:/app/downloads \
  scraper-cms
```

### Breakdown of the command:
- `-d`: Runs the container in the background (detached mode).
- `--name scraper-app`: Gives the container an easy-to-remember name.
- `-p 8000:8000`: Maps port 8000 inside the container to port 8000 on your Mac so you can access the CMS.
- `-v $(pwd)/data:/app/data`: Maps your local `data` folder to the container's `data` folder.
- `-v $(pwd)/downloads:/app/downloads`: Maps your local `downloads` folder to the container's `downloads` folder.

### Accessing the CMS
Once the container is running, open your browser and navigate to:
**http://localhost:8000**

### Useful Commands

**View live server logs:**
```bash
docker logs -f scraper-app
```

**Stop the container:**
```bash
docker stop scraper-app
```

**Start it again:**
```bash
docker start scraper-app
```
