import json
import os
from collections import Counter
from urllib.parse import urlparse

def get_analytics(college_name):
    file_path = os.path.join("data", f"{college_name}.json")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    pages = data.get("pages", [])
    downloads = data.get("downloads", [])
    
    # URL Groups
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
    
    # Download types
    download_types = Counter()
    for d in downloads:
        ext = os.path.splitext(d.get("fileName", ""))[1].lower()
        if not ext: ext = "unknown"
        download_types[ext] += 1
        
    return {
        "totalPages": len(pages),
        "totalDownloads": len(downloads),
        "crawlDurationSeconds": data.get("crawlDurationSeconds", 0),
        "urlGroups": dict(groups.most_common(15)),
        "depthDistribution": dict(depths),
        "avgBodyLength": avg_body_length,
        "downloadTypes": dict(download_types)
    }
print(get_analytics("vitap"))
