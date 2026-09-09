import re

with open("cms.py", "r") as f:
    content = f.read()

bulk_model = """
class BulkScrapeItem(BaseModel):
    collegeName: str
    seedUrls: List[str]

class BulkScrapeRequest(BaseModel):
    jobs: List[BulkScrapeItem]
"""

bulk_endpoint = """
@app.post("/api/scrape/bulk")
async def start_bulk_scrape(req: BulkScrapeRequest):
    \"\"\"Start the scraper in the background for multiple colleges.\"\"\"
    if not req.jobs:
        raise HTTPException(status_code=400, detail="No jobs provided")
        
    csv_path = os.path.join(DATA_DIR, "bulk_input.csv")
    import time
    timestamp = str(int(time.time()))
    csv_path = os.path.join(DATA_DIR, f"bulk_input_{timestamp}.csv")
    
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("CollegeName,SeedURL\\n")
        for job in req.jobs:
            c_name = job.collegeName.strip()
            if not c_name: continue
            
            # Write initial status
            status_file = os.path.join(DATA_DIR, f"{c_name}_status.json")
            with open(status_file, "w") as sf:
                json.dump({"status": "queued", "startedAt": time.time(), "message": "Scraper queued in bulk job..."}, sf)
                
            for url in job.seedUrls:
                if url.strip():
                    f.write(f"{c_name},{url.strip()}\\n")
                    
    # Start subprocess
    log_file = os.path.join(DATA_DIR, f"bulk_scrape_{timestamp}.log")
    
    import sys
    import subprocess
    with open(log_file, "w") as lf:
        subprocess.Popen(
            [sys.executable, "crawl.py", csv_path],
            stdout=lf,
            stderr=subprocess.STDOUT
        )
        
    return {"status": "started", "message": f"Bulk scraper launched for {len(req.jobs)} colleges."}
"""

content = content.replace("class ScrapeRequest(BaseModel):", bulk_model + "\nclass ScrapeRequest(BaseModel):")
content = content.replace("@app.get(\"/api/scrape-status", bulk_endpoint + "\n@app.get(\"/api/scrape-status")

with open("cms.py", "w") as f:
    f.write(content)
