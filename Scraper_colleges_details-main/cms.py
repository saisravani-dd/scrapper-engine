"""
Scraper CMS — FastAPI Backend
==============================
Serves the CMS frontend and provides APIs for managing scraped college data,
triggering scraper jobs, monitoring status, and exporting data.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from typing import Any, Dict, List
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# App & Configuration
# ---------------------------------------------------------------------------
app = FastAPI(title="Scraper CMS", version="2.0.0")

DATA_DIR = "data"
BASE_DOWNLOADS_DIR = "downloads"
SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs("templates", exist_ok=True)

templates = Jinja2Templates(directory="templates")

# Track running subprocess PIDs for fallback stop functionality
_running_pids: Dict[str, int] = {}

# ---------------------------------------------------------------------------
# Redis & Distributed Task Queue Setup
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = None
scrape_queue = None

try:
    from redis import Redis
    from rq import Queue
    from rq.job import Job
    from rq.command import send_stop_job_command
    import tasks

    redis_conn = Redis.from_url(REDIS_URL)
    scrape_queue = Queue("default", connection=redis_conn, default_timeout="24h")
except Exception as e:
    print(f"⚠️ Redis/RQ initialization notice: {e}")


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------
def validate_college_name(name: str) -> str:
    """Sanitize and validate college name to prevent path traversal."""
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="College name is required")
    if not SAFE_NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="College name must only contain letters, numbers, underscores, and hyphens",
        )
    return name


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class PageUpdate(BaseModel):
    url: str
    bodyText: str


class JsonUpdate(BaseModel):
    pages: List[Dict[str, Any]]


class BulkScrapeItem(BaseModel):
    collegeName: str
    seedUrls: List[str]


class BulkScrapeRequest(BaseModel):
    jobs: List[BulkScrapeItem]


class ScrapeRequest(BaseModel):
    collegeName: str
    seedUrls: List[str]


# ---------------------------------------------------------------------------
# Helper: Safe JSON Read
# ---------------------------------------------------------------------------
def safe_read_json(filepath: str, default=None):
    """Read a JSON file with error handling."""
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Error reading {filepath}: {e}")
        return default


def get_dir_size(path="."):
    """Recursively get the total size of a directory."""
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += get_dir_size(entry.path)
    except OSError:
        pass
    return total


def get_project_dir():
    """Get the absolute path to the project directory."""
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Routes: Pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main CMS page."""
    colleges = []
    for f in sorted(os.listdir(DATA_DIR)):
        if f.endswith(".json") and not f.endswith("_status.json"):
            colleges.append(f.replace(".json", ""))
    return templates.TemplateResponse("index.html", {"request": request, "colleges": colleges})


@app.get("/about", response_class=HTMLResponse)
async def read_about(request: Request):
    """Serve the About page."""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/about.md")
async def get_about_md():
    """Serve the raw about.md file."""
    if not os.path.exists("about.md"):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse("about.md")


# ---------------------------------------------------------------------------
# Routes: College Data API
# ---------------------------------------------------------------------------
@app.get("/api/colleges")
async def list_colleges():
    """Return list of all scraped colleges (for dynamic sidebar refresh)."""
    colleges = []
    for f in sorted(os.listdir(DATA_DIR)):
        if f.endswith(".json") and not f.endswith("_status.json"):
            name = f.replace(".json", "")
            file_path = os.path.join(DATA_DIR, f)
            stat = os.stat(file_path)
            colleges.append({
                "name": name,
                "sizeBytes": stat.st_size,
                "updatedAt": stat.st_mtime,
            })
    return {"colleges": colleges}


@app.get("/api/college/{college_name}")
async def get_college_data(college_name: str):
    """Get the full JSON data for a college."""
    college_name = validate_college_name(college_name)
    file_path = os.path.join(DATA_DIR, f"{college_name}.json")
    data = safe_read_json(file_path)
    if data is None:
        raise HTTPException(status_code=404, detail="College not found")
    return data


@app.post("/api/college/{college_name}")
async def update_college_data(college_name: str, data: JsonUpdate):
    """Overwrite the pages list and garbage collect unreferenced documents."""
    college_name = validate_college_name(college_name)
    file_path = os.path.join(DATA_DIR, f"{college_name}.json")
    existing_data = safe_read_json(file_path)
    if existing_data is None:
        raise HTTPException(status_code=404, detail="College not found")

    # Collect all local paths still referenced by the NEW pages list
    referenced_local_paths = set()
    for page in data.pages:
        for link in page.get("links", []):
            if link.get("type") == "document" and link.get("localPath"):
                referenced_local_paths.add(link["localPath"])

    # Garbage collect orphaned downloads
    new_downloads_list = []
    for download in existing_data.get("downloads", []):
        local_path = download.get("localPath")
        if local_path and local_path in referenced_local_paths:
            new_downloads_list.append(download)
        else:
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    print(f"🗑️ Garbage collected orphaned file: {local_path}")
                except Exception as e:
                    print(f"Failed to delete {local_path}: {e}")

    # Update pages and downloads
    existing_data["pages"] = data.pages
    existing_data["downloads"] = new_downloads_list
    existing_data["totalPages"] = len(data.pages)
    existing_data["totalDownloads"] = len(new_downloads_list)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False)

    return {
        "status": "success",
        "message": f"Updated {college_name}.json. Kept {len(new_downloads_list)} downloads.",
    }


@app.delete("/api/college/{college_name}")
async def delete_college(college_name: str):
    """Permanently delete all data, logs, individual page files, and downloads for a college."""
    college_name = validate_college_name(college_name)

    # 1. Stop / Cancel any running or queued Redis job
    if redis_conn:
        try:
            job = Job.fetch(f"scrape_{college_name}", connection=redis_conn)
            j_status = job.get_status()
            if j_status in ("queued", "deferred"):
                job.cancel()
            elif j_status == "started":
                send_stop_job_command(redis_conn, job.id)
                job.cancel()
        except Exception:
            pass

    # 2. Kill local process if present
    pid = _running_pids.pop(college_name, None)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            pass

    # 3. Remove main JSON data, status, and scrape log files
    for fname in (f"{college_name}.json", f"{college_name}_status.json", f"{college_name}_scrape.log"):
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception as e:
                print(f"Failed to remove {fpath}: {e}")

    # 4. Remove individual pages directory (data/pages/<college_name>)
    pages_dir = os.path.join(DATA_DIR, "pages", college_name)
    if os.path.exists(pages_dir):
        try:
            shutil.rmtree(pages_dir)
        except Exception as e:
            print(f"Failed to remove pages dir {pages_dir}: {e}")

    # 5. Remove downloaded documents directory (downloads/<college_name>)
    downloads_dir = os.path.join(BASE_DOWNLOADS_DIR, college_name)
    if os.path.exists(downloads_dir):
        try:
            shutil.rmtree(downloads_dir)
        except Exception as e:
            print(f"Failed to remove downloads dir {downloads_dir}: {e}")

    return {
        "status": "success",
        "message": f"College '{college_name}' and all associated files deleted permanently.",
    }


# ---------------------------------------------------------------------------
# Routes: Scraper Control
# ---------------------------------------------------------------------------
@app.post("/api/scrape")
async def start_scrape(req: ScrapeRequest):
    """Start the scraper in the background for a single college via Redis queue (or subprocess fallback)."""
    college_name = validate_college_name(req.collegeName)
    seed_urls = [u.strip() for u in req.seedUrls if u.strip()]
    if not seed_urls:
        raise HTTPException(status_code=400, detail="At least one valid seed URL is required")

    job_id = f"scrape_{college_name}"

    # 1. Distributed Queue execution with Redis + RQ
    if redis_conn and scrape_queue:
        try:
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                j_status = job.get_status()
                if j_status in ("queued", "started"):
                    return {"status": j_status, "message": f"Scraper is already {j_status} in Redis for this college."}
            except Exception:
                pass  # Job does not exist yet, which is expected

            # Write initial status file for immediate UI responsiveness
            status_file = os.path.join(DATA_DIR, f"{college_name}_status.json")
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump({"status": "queued", "startedAt": time.time(), "message": "Scraper queued in Redis..."}, f)

            job = scrape_queue.enqueue(
                tasks.run_crawl_job,
                college_name,
                seed_urls,
                job_id=job_id,
                job_timeout="24h",
                result_ttl=86400,
            )
            return {"status": "queued", "message": f"Scraper queued in Redis (Job ID: {job.id})."}
        except Exception as e:
            print(f"⚠️ Redis enqueue error, falling back to local process: {e}")

    # 2. Fallback to local subprocess if Redis is unavailable
    status_file = os.path.join(DATA_DIR, f"{college_name}_status.json")
    status = safe_read_json(status_file, {})
    if status.get("status") == "running":
        return {"status": "running", "message": "Scraper is already running for this college."}

    csv_path = os.path.join(DATA_DIR, f"{college_name}_input.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("CollegeName,SeedURL\n")
        for url in seed_urls:
            f.write(f"{college_name},{url}\n")

    with open(status_file, "w", encoding="utf-8") as f:
        json.dump({"status": "running", "startedAt": time.time(), "message": "Scraper starting..."}, f)

    log_file = os.path.join(DATA_DIR, f"{college_name}_scrape.log")
    project_dir = get_project_dir()
    env = dict(os.environ, PYTHONUNBUFFERED="1")

    with open(log_file, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [sys.executable, "-u", "crawl.py", csv_path],
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=project_dir,
            env=env,
        )
        _running_pids[college_name] = proc.pid

    return {"status": "started", "message": "Scraper launched as local process."}


@app.post("/api/scrape/bulk")
async def start_bulk_scrape(req: BulkScrapeRequest):
    """Start the scraper for multiple colleges via Redis queue (discrete jobs for 1000+ scale)."""
    if not req.jobs:
        raise HTTPException(status_code=400, detail="No jobs provided")

    # Record in master input.csv
    master_input = "input.csv"
    file_exists = os.path.exists(master_input)
    with open(master_input, "a", encoding="utf-8") as mf:
        if not file_exists:
            mf.write("CollegeName,SeedURL\n")
        for job in req.jobs:
            c_name = job.collegeName.strip()
            if not c_name:
                continue
            for url in job.seedUrls:
                if url.strip():
                    mf.write(f"{c_name},{url.strip()}\n")

    # 1. Distributed Queue with Redis
    if redis_conn and scrape_queue:
        queued_count = 0
        for job_item in req.jobs:
            c_name = job_item.collegeName.strip()
            if not c_name or not SAFE_NAME_RE.match(c_name):
                continue
            clean_urls = [u.strip() for u in job_item.seedUrls if u.strip()]
            if not clean_urls:
                continue

            job_id = f"scrape_{c_name}"
            # Check if already active
            try:
                existing_job = Job.fetch(job_id, connection=redis_conn)
                if existing_job.get_status() in ("queued", "started"):
                    continue
            except Exception:
                pass

            status_file = os.path.join(DATA_DIR, f"{c_name}_status.json")
            with open(status_file, "w", encoding="utf-8") as sf:
                json.dump(
                    {"status": "queued", "startedAt": time.time(), "message": "Queued in Redis distributed queue..."},
                    sf,
                )

            scrape_queue.enqueue(
                tasks.run_crawl_job,
                c_name,
                clean_urls,
                job_id=job_id,
                job_timeout="24h",
                result_ttl=86400,
            )
            queued_count += 1

        return {
            "status": "started",
            "message": f"Successfully queued {queued_count} college scraping jobs in Redis.",
            "queuedJobs": queued_count,
        }

    # 2. Fallback to local subprocess batch if Redis is offline
    timestamp = str(int(time.time()))
    csv_path = os.path.join(DATA_DIR, f"bulk_input_{timestamp}.csv")
    jobs_to_run = 0

    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("CollegeName,SeedURL\n")
        for job in req.jobs:
            c_name = job.collegeName.strip()
            if not c_name or not SAFE_NAME_RE.match(c_name):
                continue
            clean_urls = [u.strip() for u in job.seedUrls if u.strip()]
            if not clean_urls:
                continue
            jobs_to_run += 1

            status_file = os.path.join(DATA_DIR, f"{c_name}_status.json")
            with open(status_file, "w", encoding="utf-8") as sf:
                json.dump(
                    {"status": "queued", "startedAt": time.time(), "message": "Scraper queued in bulk job..."},
                    sf,
                )
            for url in clean_urls:
                f.write(f"{c_name},{url}\n")

    if jobs_to_run == 0:
        return {"status": "skipped", "message": "No valid colleges to scrape."}

    log_file = os.path.join(DATA_DIR, f"bulk_scrape_{timestamp}.log")
    project_dir = get_project_dir()
    env = dict(os.environ, PYTHONUNBUFFERED="1")

    with open(log_file, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [sys.executable, "-u", "crawl.py", csv_path],
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=project_dir,
            env=env,
        )
        for job in req.jobs:
            _running_pids[job.collegeName.strip()] = proc.pid

    return {"status": "started", "message": f"Bulk scraper launched locally for {jobs_to_run} colleges."}


@app.post("/api/scrape/stop/{college_name}")
async def stop_scrape(college_name: str):
    """Stop a running or queued scraper for a specific college."""
    college_name = validate_college_name(college_name)

    # 1. Cancel in Redis / RQ if present
    if redis_conn:
        job_id = f"scrape_{college_name}"
        try:
            job = Job.fetch(job_id, connection=redis_conn)
            j_status = job.get_status()
            if j_status in ("queued", "deferred"):
                job.cancel()
            elif j_status == "started":
                send_stop_job_command(redis_conn, job.id)
                job.cancel()
        except Exception:
            pass

    # 2. Cancel local subprocess if present
    pid = _running_pids.pop(college_name, None)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as e:
            return {"status": "error", "message": f"Failed to kill process: {e}"}

    # Update status file
    status_file = os.path.join(DATA_DIR, f"{college_name}_status.json")
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(
            {"status": "stopped", "message": "Scraper stopped by user.", "updatedAt": time.time()},
            f,
        )

    return {"status": "stopped", "message": f"Scraper for {college_name} has been stopped."}


# ---------------------------------------------------------------------------
# Routes: Scraper Status & Logs
# ---------------------------------------------------------------------------
@app.get("/api/scrape-status/{college_name}")
async def get_scrape_status(college_name: str):
    """Get the current status of the scraper and latest logs."""
    college_name = validate_college_name(college_name)
    status_file = os.path.join(DATA_DIR, f"{college_name}_status.json")
    log_file = os.path.join(DATA_DIR, f"{college_name}_scrape.log")

    status_data = safe_read_json(status_file, {"status": "idle"})

    # Inspect Redis RQ job status if available
    if redis_conn:
        try:
            job = Job.fetch(f"scrape_{college_name}", connection=redis_conn)
            rq_status = job.get_status()
            status_map = {
                "queued": "queued",
                "started": "running",
                "finished": "complete",
                "failed": "error",
                "canceled": "stopped",
                "stopped": "stopped",
            }
            if rq_status in status_map:
                # If disk says complete, retain complete
                if not (rq_status == "finished" and status_data.get("status") == "complete"):
                    status_data["status"] = status_map[rq_status]
        except Exception:
            pass

    # Read last lines of log
    logs = []
    if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-80:] if line.strip()]
        except Exception:
            pass

    # Fallback to newest bulk_scrape log if college log is empty
    if not logs:
        try:
            bulk_logs = [
                os.path.join(DATA_DIR, f)
                for f in os.listdir(DATA_DIR)
                if f.startswith("bulk_scrape_") and f.endswith(".log")
            ]
            if bulk_logs:
                bulk_logs.sort(key=os.path.getmtime, reverse=True)
                with open(bulk_logs[0], "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    logs = [line.strip() for line in lines[-80:] if line.strip()]
        except Exception:
            pass

    status_data["logs"] = logs
    status_data["concurrency"] = 8
    return status_data


@app.get("/api/queue-status")
async def get_queue_status():
    """Get overall Redis distributed queue metrics."""
    if not redis_conn or not scrape_queue:
        return {
            "redisEnabled": False,
            "message": "Redis is not connected. Running in fallback mode.",
        }

    try:
        from rq import Worker
        workers = Worker.all(connection=redis_conn)
        queued_jobs = scrape_queue.jobs
        return {
            "redisEnabled": True,
            "queueLength": len(scrape_queue),
            "workersTotal": len(workers),
            "workersBusy": sum(1 for w in workers if w.get_state() == "busy"),
            "workersIdle": sum(1 for w in workers if w.get_state() == "idle"),
            "queuedJobIds": [j.id for j in queued_jobs[:25]],
        }
    except Exception as e:
        return {"redisEnabled": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Routes: Analytics
# ---------------------------------------------------------------------------
@app.get("/api/analytics/{college_name}")
async def get_analytics(college_name: str):
    """Get analytics/stats for a college's scraped data."""
    college_name = validate_college_name(college_name)
    file_path = os.path.join(DATA_DIR, f"{college_name}.json")
    data = safe_read_json(file_path)
    if data is None:
        raise HTTPException(status_code=404, detail="College not found")

    pages = data.get("pages", [])
    downloads = data.get("downloads", [])

    groups = Counter()
    depths = Counter()
    total_body_length = 0

    for p in pages:
        path = urlparse(p.get("url", "")).path.strip("/")
        parts = path.split("/")
        prefix = f"/{parts[0]}/" if parts and parts[0] else "/"
        groups[prefix] += 1
        depths[str(p.get("depth", 0))] += 1
        total_body_length += len(p.get("bodyText", ""))

    avg_body_length = total_body_length / len(pages) if pages else 0

    download_types = Counter()
    total_download_size = 0
    for d in downloads:
        ext = os.path.splitext(d.get("fileName", ""))[1].lower()
        if not ext:
            ext = "unknown"
        download_types[ext] += 1
        lp = d.get("localPath")
        if lp and os.path.exists(lp):
            total_download_size += os.path.getsize(lp)

    return {
        "totalPages": len(pages),
        "totalDownloads": len(downloads),
        "crawlDurationSeconds": data.get("crawlDurationSeconds", 0),
        "urlGroups": dict(groups.most_common(15)),
        "depthDistribution": dict(depths),
        "avgBodyLength": avg_body_length,
        "totalBodyLength": total_body_length,
        "downloadTypes": dict(download_types),
        "totalDownloadSize": total_download_size,
    }


# ---------------------------------------------------------------------------
# Routes: Storage & Files
# ---------------------------------------------------------------------------
@app.get("/api/storage-info")
async def get_storage_info():
    """Get disk usage information."""
    data_size = get_dir_size("data") if os.path.exists("data") else 0
    dl_size = get_dir_size("downloads") if os.path.exists("downloads") else 0
    return {
        "dataSizeBytes": data_size,
        "downloadsSizeBytes": dl_size,
        "totalBytes": data_size + dl_size,
    }


@app.get("/api/scraped-files/{college_name}")
async def get_scraped_files(college_name: str):
    """Get list of individual scraped page files and downloaded documents."""
    college_name = validate_college_name(college_name)
    pages_dir = os.path.join(DATA_DIR, "pages", college_name)
    downloads_dir = os.path.join(BASE_DOWNLOADS_DIR, college_name)

    files = []
    if os.path.exists(pages_dir):
        for fname in sorted(os.listdir(pages_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(pages_dir, fname)
                try:
                    stat = os.stat(fpath)
                    pdata = safe_read_json(fpath, {})
                    files.append({
                        "fileName": fname,
                        "url": pdata.get("url", ""),
                        "title": pdata.get("title", ""),
                        "sizeBytes": stat.st_size,
                        "updatedAt": stat.st_mtime,
                        "linksCount": len(pdata.get("links", [])),
                        "bodyLength": len(pdata.get("bodyText", "")),
                    })
                except Exception:
                    pass

    downloads = []
    if os.path.exists(downloads_dir):
        for fname in sorted(os.listdir(downloads_dir)):
            if not fname.startswith("."):
                fpath = os.path.join(downloads_dir, fname)
                try:
                    stat = os.stat(fpath)
                    downloads.append({
                        "fileName": fname,
                        "sizeBytes": stat.st_size,
                        "updatedAt": stat.st_mtime,
                    })
                except Exception:
                    pass

    return {
        "collegeName": college_name,
        "pageFilesCount": len(files),
        "pageFiles": files,
        "downloadedFilesCount": len(downloads),
        "downloadedFiles": downloads,
        "mainJsonPath": os.path.join(DATA_DIR, f"{college_name}.json"),
    }


# ---------------------------------------------------------------------------
# Routes: Export
# ---------------------------------------------------------------------------
@app.post("/api/export/markdown/{college_name}")
async def export_to_markdown(college_name: str):
    """Export all scraped pages to clean individual markdown files."""
    college_name = validate_college_name(college_name)
    main_file = os.path.join(DATA_DIR, f"{college_name}.json")
    data = safe_read_json(main_file)
    if data is None:
        raise HTTPException(status_code=404, detail="College data not found")

    export_dir = os.path.join(DATA_DIR, "exports", college_name, "markdown")
    os.makedirs(export_dir, exist_ok=True)

    pages = data.get("pages", [])
    toc_lines = [
        f"# {college_name.upper()} - Scraped Pages Index\n\n",
        f"Total Pages: {len(pages)}\n\n",
    ]

    for idx, page in enumerate(pages, 1):
        url = page.get("url", "")
        title = page.get("title", f"Page {idx}")
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", urlparse(url).path.strip("/") or "home")[:50]
        fname = f"{idx:04d}_{slug}.md"
        fpath = os.path.join(export_dir, fname)

        depth = page.get("depth", 0)
        md_content = f"# {title}\n\n"
        md_content += f"- **URL:** [{url}]({url})\n"
        md_content += f"- **Depth:** {depth}\n\n"
        md_content += "## Page Content\n\n"
        md_content += page.get("bodyText", "") + "\n\n"

        # Document links
        doc_links = [l for l in page.get("links", []) if l.get("type") == "document"]
        if doc_links:
            md_content += "## Downloaded Documents & Resources\n\n"
            for dl in doc_links:
                dl_text = dl.get("text") or dl.get("href", "")
                dl_href = dl.get("href", "")
                section = dl.get("sectionHeading", "")
                section_str = f" *(Section: {section})*" if section else ""
                md_content += f"- [{dl_text}]({dl_href}){section_str}\n"
                lp = dl.get("localPath")
                if lp:
                    md_content += f"  - Local file: `{lp}`\n"
            md_content += "\n"

        with open(fpath, "w", encoding="utf-8") as pf:
            pf.write(md_content)

        toc_lines.append(f"{idx}. [{title}]({fname}) - `{url}`\n")

    # Write TOC
    with open(os.path.join(export_dir, "index.md"), "w", encoding="utf-8") as tf:
        tf.writelines(toc_lines)

    return {
        "status": "success",
        "message": f"Successfully exported {len(pages)} pages to {export_dir}",
        "exportPath": export_dir,
        "filesCount": len(pages) + 1,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("cms:app", host="127.0.0.1", port=8000, reload=True)
