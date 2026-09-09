import asyncio
import json
import os
import sys
import time
import traceback
from crawl import crawl

def run_crawl_job(college_name: str, start_urls: list[str]):
    """
    Distributed worker task executed by RQ worker.
    Runs deep crawl for a single college, logs output, and updates status.
    """
    os.makedirs("data", exist_ok=True)
    log_file = os.path.join("data", f"{college_name}_scrape.log")
    status_file = os.path.join("data", f"{college_name}_status.json")

    # Update status to running as soon as worker picks up the job
    try:
        with open(status_file, "w", encoding="utf-8") as sf:
            json.dump({
                "status": "running",
                "startedAt": time.time(),
                "message": f"Worker processing scrape for {college_name}..."
            }, sf)
    except Exception:
        pass

    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🚀 RQ Worker picked up job for {college_name}\n")
        lf.flush()

    try:
        asyncio.run(crawl(college_name, start_urls))
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
