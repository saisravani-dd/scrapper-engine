import asyncio
import json
import os
import sys
import time
import traceback
from crawl import crawl

def run_crawl_job(college_name: str, start_urls: list[str], crawl_mode: str = "deep", download_media: bool = True):
    """
    Distributed worker task executed by RQ worker.
    Runs crawl (deep or specific) for a single college, logs output, and updates status.
    """
    os.makedirs("data", exist_ok=True)
    log_file = os.path.join("data", f"{college_name}_scrape.log")
    status_file = os.path.join("data", f"{college_name}_status.json")

    # Update status to running as soon as worker picks up the job
    mode_label = "Specific Links" if crawl_mode == "specific" else "Deep Crawl"
    media_label = "with Media Downloads" if download_media else "without Media Downloads"
    try:
        with open(status_file, "w", encoding="utf-8") as sf:
            json.dump({
                "status": "running",
                "crawlMode": crawl_mode,
                "downloadMedia": download_media,
                "startedAt": time.time(),
                "message": f"Worker processing {mode_label} ({media_label}) for {college_name}..."
            }, sf)
    except Exception:
        pass

    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🚀 RQ Worker picked up {mode_label} ({media_label}) job for {college_name}\n")
        lf.flush()

    try:
        asyncio.run(crawl(college_name, start_urls, crawl_mode=crawl_mode, download_media=download_media))
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ RQ Worker finished job for {college_name}\n")
    except Exception as e:
        err_details = traceback.format_exc()
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Worker error for {college_name}: {e}\n{err_details}\n")
        try:
            with open(status_file, "w", encoding="utf-8") as sf:
                json.dump({
                    "status": "error",
                    "error": str(e),
                    "updatedAt": time.time(),
                    "message": f"Scrape failed: {e}"
                }, sf)
        except Exception:
            pass
        raise e
