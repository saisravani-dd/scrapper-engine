#!/usr/bin/env python3
"""
Deep Recursive Website Scraper
===============================
Takes a CSV of college names + seed URLs, recursively crawls all internal
pages using BFS with Playwright (stealth mode), extracts body text + links +
document references from each page, downloads PDFs/docs locally, and outputs
structured JSON.

Usage:
    python crawl.py input.csv
"""

import asyncio
import csv
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_CONCURRENT_TABS = 8
MAX_DEPTH = 5
MAX_PAGES = 2000
PAGE_TIMEOUT_MS = 15_000
DOWNLOAD_TIMEOUT_S = 60
DOWNLOAD_RETRIES = 2
DATA_DIR = "data"
BASE_DOWNLOADS_DIR = "downloads"

# File extensions treated as downloadable documents
DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".csv", ".rtf", ".odt", ".ods", ".odp", ".txt",
}

# Image extensions (downloadable when download_media is enabled)
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp", ".tiff",
}

# File extensions to skip entirely (media, web assets, etc.)
SKIP_EXTENSIONS = {
    # Video / Audio
    ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".flv", ".ogg", ".wav", ".webm",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # CSS / JS / Web assets
    ".css", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx",
    ".map", ".min.js", ".min.css",
    ".json", ".xml", ".rss", ".atom",
    # Other web files
    ".manifest", ".webmanifest",
    ".php", ".asp", ".aspx", ".jsp",
}


# ---------------------------------------------------------------------------
# URL Helpers
# ---------------------------------------------------------------------------
def normalize_url(url: str) -> str:
    """Strip fragment, trailing slash, and normalize for deduplication."""
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="")
    path = cleaned.path.rstrip("/") or "/"
    cleaned = cleaned._replace(path=path)
    return urlunparse(cleaned).lower()


def get_extension(url: str) -> str:
    """Extract file extension from a URL path."""
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower()


def is_allowed_domain(url: str, allowed_domains: set) -> bool:
    """Check if url belongs to any of the allowed domains, handling www. aliases."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    for d in allowed_domains:
        d_clean = (d or "").lower().lstrip("www.")
        host_clean = host.lstrip("www.")
        if host == d.lower() or host_clean == d_clean or host.endswith("." + d_clean):
            return True
    return False


def is_valid_http_url(url: str) -> bool:
    """Check if URL is http or https."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")


def slugify_url(url: str) -> str:
    """Create a safe filename from a URL."""
    path = urlparse(url).path.strip("/").replace("/", "_")
    if not path:
        path = "homepage"
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", path)
    return safe[:60]


# ---------------------------------------------------------------------------
# Document Downloader (with retries)
# ---------------------------------------------------------------------------
async def download_file(
    session: aiohttp.ClientSession,
    url: str,
    link_text: str,
    found_on_page: str,
    downloads_dir: str,
    log_fn=None,
) -> dict | None:
    """Download a document file with retry logic."""
    if log_fn is None:
        log_fn = print

    filename = os.path.basename(urlparse(url).path) or "document"
    local_path = os.path.join(downloads_dir, filename)

    # Handle filename collisions
    counter = 1
    base, ext = os.path.splitext(filename)
    while os.path.exists(local_path):
        local_path = os.path.join(downloads_dir, f"{base}_{counter}{ext}")
        counter += 1

    for attempt in range(1, DOWNLOAD_RETRIES + 2):
        try:
            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT_S)
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()
                os.makedirs(downloads_dir, exist_ok=True)
                with open(local_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)

            final_filename = os.path.basename(local_path)
            log_fn(f"    📥 Downloaded: {final_filename}")

            return {
                "originalUrl": url,
                "localPath": local_path,
                "fileName": final_filename,
                "foundOnPage": found_on_page,
                "linkText": link_text or filename,
            }
        except Exception as e:
            if attempt <= DOWNLOAD_RETRIES:
                log_fn(f"    ⚠️  Download retry {attempt}/{DOWNLOAD_RETRIES} for {filename}: {e}")
                await asyncio.sleep(1)
            else:
                log_fn(f"    ❌ Failed to download {filename} after {DOWNLOAD_RETRIES + 1} attempts: {e}")
                return None


# ---------------------------------------------------------------------------
# Page Scraper
# ---------------------------------------------------------------------------
async def scrape_page(
    page,
    url: str,
    depth: int,
    allowed_domains: set,
    visited: set,
    downloads_list: list,
    http_session: aiohttp.ClientSession,
    downloads_dir: str,
    log_fn=None,
    download_media: bool = True,
) -> tuple[dict | None, list]:
    """Visit a single page, extract content, images, and links with retry on context destruction."""
    if log_fn is None:
        log_fn = print

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)

        # Give CSR frameworks like Next.js or WordPress scripts a moment to hydrate
        await page.wait_for_timeout(500)

        # Resilient extraction of content and title (handles redirects / context destruction)
        html_content = ""
        title = ""
        for nav_retry in range(3):
            try:
                # If redirected or navigating, wait for DOM to settle
                if nav_retry > 0:
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        await asyncio.sleep(1.0)

                html_content = await page.content()
                try:
                    title = await page.title()
                except Exception:
                    pass
                break
            except Exception as e:
                err_text = str(e).lower()
                if "execution context was destroyed" in err_text or "navigation" in err_text or "navigating" in err_text:
                    if nav_retry < 2:
                        await asyncio.sleep(1.0)
                        continue
                raise e

        # Fallback to BeautifulSoup if page.title() failed or was empty
        if not title and html_content:
            raw_soup_title = BeautifulSoup(html_content, "html.parser")
            t_tag = raw_soup_title.find("title")
            title = t_tag.get_text(strip=True) if t_tag else url

        # -------------------------------------------------------------------
        # PASS 1: NAVIGATION LINKS (From Raw HTML)
        # -------------------------------------------------------------------
        raw_soup = BeautifulSoup(html_content, "html.parser")
        new_urls_to_visit = []

        for anchor in raw_soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(url, href)
            if not is_valid_http_url(full_url):
                continue

            ext = get_extension(full_url)
            if ext in SKIP_EXTENSIONS or ext in DOCUMENT_EXTENSIONS or ext in IMAGE_EXTENSIONS:
                continue

            if is_allowed_domain(full_url, allowed_domains):
                normalized = normalize_url(full_url)
                if normalized not in visited:
                    new_urls_to_visit.append((full_url, depth + 1))

        # -------------------------------------------------------------------
        # PASS 2: BODY TEXT & DOWNLOADS (From Cleaned HTML)
        # -------------------------------------------------------------------
        clean_soup = BeautifulSoup(html_content, "html.parser")

        # 1. Remove non-content tags
        for tag in clean_soup.find_all(["script", "style", "noscript", "iframe", "svg", "header", "footer", "nav"]):
            tag.decompose()

        # 2. Targeted removal of boilerplate / popup overlays (NEVER decompose body, html, or main content wrappers)
        for el in clean_soup.find_all(True):
            if el.attrs is None or el.name in ("html", "body", "main", "article"):
                continue

            el_role = el.get("role", "")
            if el_role in ["banner", "contentinfo", "navigation"] and el.name not in ("body", "main", "article"):
                el.decompose()
                continue

            el_id = (el.get("id") or "").lower()
            el_classes = " ".join(el.get("class") or []).lower()

            # Remove cookie notices, consent popups, modal overlays
            if any(k in el_id for k in ["cookie-notice", "cookie-banner", "cookie-consent", "gdpr-banner", "popup-overlay", "modal-backdrop"]) or \
               any(k in el_classes for k in ["cookie-banner", "cookie-consent", "cookie-notice", "gdpr-banner", "popup-modal", "modal-backdrop"]):
                el.decompose()
                continue

            # Remove dedicated small copyright disclaimers (< 200 chars)
            if el.name in ("div", "p", "span") and len(el.get_text(strip=True)) < 200:
                text_lower = el.get_text(strip=True).lower()
                if "all rights reserved" in text_lower and ("copyright" in text_lower or "©" in text_lower):
                    el.decompose()
                    continue

        # Extract body text
        body_text = clean_soup.get_text(separator="\n", strip=True)
        body_text = re.sub(r'\n{3,}', '\n\n', body_text).strip()

        # Extract embedded images
        images = []
        for img_tag in clean_soup.find_all("img", src=True):
            src = img_tag["src"].strip()
            if not src or src.startswith("data:"):
                continue
            full_img_url = urljoin(url, src)
            if not is_valid_http_url(full_img_url):
                continue
            img_alt = img_tag.get("alt", "").strip()
            img_entry = {
                "src": full_img_url,
                "alt": img_alt,
            }
            if download_media:
                normalized_img = normalize_url(full_img_url)
                if normalized_img not in visited:
                    visited.add(normalized_img)
                    dl_result = await download_file(
                        http_session, full_img_url, img_alt or "image", url, downloads_dir, log_fn
                    )
                    if dl_result:
                        downloads_list.append(dl_result)
                        img_entry["localPath"] = dl_result["localPath"]
            images.append(img_entry)

        # Extract links from the CLEANED body
        links = []
        for anchor in clean_soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(url, href)
            if not is_valid_http_url(full_url):
                continue

            link_text = (
                anchor.get_text(strip=True)
                or anchor.get("title", "")
                or anchor.get("aria-label", "")
            )
            if not link_text:
                img = anchor.find("img")
                if img:
                    link_text = img.get("alt", "")
            link_text = link_text or os.path.basename(urlparse(full_url).path) or full_url

            ext = get_extension(full_url)

            if ext in DOCUMENT_EXTENSIONS:
                nearest_heading = anchor.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
                section_heading = nearest_heading.get_text(strip=True) if nearest_heading else ""

                link_entry = {
                    "text": link_text,
                    "href": full_url,
                    "type": "document",
                    "sectionHeading": section_heading,
                }

                if download_media:
                    normalized = normalize_url(full_url)
                    if normalized not in visited:
                        visited.add(normalized)
                        dl_result = await download_file(
                            http_session, full_url, link_text, url, downloads_dir, log_fn
                        )
                        if dl_result:
                            downloads_list.append(dl_result)
                            link_entry["localPath"] = dl_result["localPath"]
                links.append(link_entry)

            elif ext in IMAGE_EXTENSIONS:
                link_entry = {
                    "text": link_text,
                    "href": full_url,
                    "type": "image",
                }
                if download_media:
                    normalized = normalize_url(full_url)
                    if normalized not in visited:
                        visited.add(normalized)
                        dl_result = await download_file(
                            http_session, full_url, link_text, url, downloads_dir, log_fn
                        )
                        if dl_result:
                            downloads_list.append(dl_result)
                            link_entry["localPath"] = dl_result["localPath"]
                links.append(link_entry)

            elif ext not in SKIP_EXTENSIONS:
                links.append({
                    "text": link_text,
                    "href": full_url,
                    "type": "internal" if is_allowed_domain(full_url, allowed_domains) else "external",
                })

        return {
            "url": url,
            "title": title,
            "bodyText": body_text,
            "links": links,
            "images": images,
            "depth": depth,
        }, new_urls_to_visit

    except Exception as e:
        log_fn(f"    ❌ Error scraping {url}: {e}")
        return None, []


# ---------------------------------------------------------------------------
# Main BFS Crawler
# ---------------------------------------------------------------------------
async def crawl(college_name: str, start_urls: list[str], crawl_mode: str = "deep", download_media: bool = True):
    """
    Main Crawler.
    - crawl_mode="deep": (Default) Recursively visits all internal pages up to MAX_DEPTH.
    - crawl_mode="specific": Scrapes ONLY the exact provided start_urls (no recursive link following).
    - download_media=True: Downloads linked PDFs/docs & images locally to disk.
    - download_media=False: Extracts all text & links without downloading media files to disk.
    """
    is_specific_mode = (crawl_mode == "specific")
    allowed_domains = {urlparse(u).hostname for u in start_urls if urlparse(u).hostname}

    downloads_dir = os.path.join(BASE_DOWNLOADS_DIR, college_name)
    os.makedirs(DATA_DIR, exist_ok=True)
    output_file = os.path.join(DATA_DIR, f"{college_name}.json")
    status_file = os.path.join(DATA_DIR, f"{college_name}_status.json")
    college_log_file = os.path.join(DATA_DIR, f"{college_name}_scrape.log")
    pages_dir = os.path.join(DATA_DIR, "pages", college_name)
    os.makedirs(pages_dir, exist_ok=True)

    # Initialize log file
    try:
        with open(college_log_file, "w", encoding="utf-8") as clf:
            mode_label = "Specific Links" if is_specific_mode else "Normal Deep Crawl"
            clf.write(f"🌐 Starting {mode_label} for {college_name}...\n")
    except Exception:
        pass

    def log_msg(msg: str):
        print(msg, flush=True)
        try:
            with open(college_log_file, "a", encoding="utf-8") as clf:
                clf.write(msg + "\n")
        except Exception:
            pass

    def update_status(status_msg, state="running"):
        try:
            with open(status_file, "w") as sf:
                json.dump({
                    "status": state,
                    "message": status_msg,
                    "crawlMode": crawl_mode,
                    "downloadMedia": download_media,
                    "updatedAt": time.time()
                }, sf)
        except Exception:
            pass

    # Lock for thread-safe writes to shared state
    write_lock = asyncio.Lock()

    try:
        visited = set()
        all_pages = []
        all_downloads = []

        # Load existing data to prevent duplicates and enable resume
        if os.path.exists(output_file):
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    all_pages = existing.get("pages", [])
                    all_downloads = existing.get("downloads", [])
                    for p in all_pages:
                        visited.add(normalize_url(p.get("url", "")))
                log_msg(f"♻️  Loaded {len(all_pages)} existing pages to skip duplicates.")
            except Exception as e:
                log_msg(f"⚠️  Could not load existing data: {e}")

        queue = asyncio.Queue()

        # Queue start_urls if not yet visited
        for url in start_urls:
            norm = normalize_url(url)
            if norm not in visited:
                visited.add(norm)
                await queue.put((url, 0))

        # Queue all pending unvisited links discovered in previous runs to resume (only in deep mode)
        resumed_links = 0
        if not is_specific_mode:
            for p in all_pages:
                p_depth = p.get("depth", 0)
                for link in p.get("links", []):
                    if link.get("type") == "internal":
                        href = link.get("href")
                        if href and is_allowed_domain(href, allowed_domains):
                            norm_href = normalize_url(href)
                            if norm_href not in visited:
                                link_depth = p_depth + 1
                                if link_depth <= MAX_DEPTH:
                                    visited.add(norm_href)
                                    await queue.put((href, link_depth))
                                    resumed_links += 1

        if len(all_pages) > 0 and not is_specific_mode:
            log_msg(
                f"🔄 Resuming scrape: {len(all_pages)} pages done. "
                f"Queued {resumed_links} pending links."
            )

        if is_specific_mode:
            log_msg(f"🎯 Starting Specific Links Scrape for: {college_name} ({len(start_urls)} exact target URLs, no recursive crawling)")
        else:
            log_msg(f"🌐 Starting deep crawl for: {college_name} (⚡ {MAX_CONCURRENT_TABS} tabs, depth {MAX_DEPTH}, max {MAX_PAGES} pages)")

        log_msg(f"📌 Allowed Domains: {', '.join(allowed_domains)}")
        if download_media:
            log_msg(f"📥 Media Downloads: ENABLED (PDFs, Docs & Images will be downloaded to {downloads_dir}/)")
        else:
            log_msg(f"📥 Media Downloads: DISABLED (PDFs & Images will NOT be downloaded to disk)")
        log_msg(f"📄 Output will be saved to: {output_file}")
        log_msg("=" * 60)

        start_time = time.time()
        update_status("Starting browser...")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
            )

            # Block images, CSS, fonts, media at the network level for speed
            await context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in ("image", "stylesheet", "font", "media")
                else route.continue_(),
            )

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)
            http_session = aiohttp.ClientSession()
            stealth = Stealth()  # Create once, reuse for all pages

            try:
                async def process_url(url: str, depth: int):
                    """Process a single URL — errors are caught so they don't kill the batch."""
                    async with semaphore:
                        page = await context.new_page()
                        await stealth.apply_stealth_async(page)
                        try:
                            elapsed = time.time() - start_time
                            log_msg(f"[{len(all_pages)+1:>4} pages | {elapsed:.0f}s] Depth {depth} → {url}")

                            result, new_urls = await scrape_page(
                                page, url, depth, allowed_domains, visited,
                                all_downloads, http_session, downloads_dir, log_msg,
                                download_media=download_media,
                            )

                            # If failed on the seed page (depth == 0), give it a second chance
                            if not result and depth == 0:
                                log_msg(f"    ⚠️ Seed page {url} failed; retrying once more with fresh navigation...")
                                await asyncio.sleep(2)
                                result, new_urls = await scrape_page(
                                    page, url, depth, allowed_domains, visited,
                                    all_downloads, http_session, downloads_dir, log_msg,
                                    download_media=download_media,
                                )

                            if result:
                                async with write_lock:
                                    all_pages.append(result)
                                    page_idx = len(all_pages)

                                # Save individual page file immediately
                                slug = slugify_url(url)
                                page_filename = os.path.join(pages_dir, f"page_{page_idx:04d}_{slug}.json")
                                try:
                                    with open(page_filename, "w", encoding="utf-8") as pf:
                                        json.dump(result, pf, indent=2, ensure_ascii=False)
                                except Exception:
                                    pass

                                # Checkpoint every 5 pages
                                if page_idx % 5 == 0:
                                    async with write_lock:
                                        try:
                                            checkpoint = {
                                                "collegeName": college_name,
                                                "startUrls": start_urls,
                                                "allowedDomains": list(allowed_domains),
                                                "crawledAt": datetime.now(timezone.utc).isoformat(),
                                                "crawlDurationSeconds": round(time.time() - start_time, 1),
                                                "totalPages": len(all_pages),
                                                "totalDownloads": len(all_downloads),
                                                "downloadMedia": download_media,
                                                "pages": all_pages,
                                                "downloads": all_downloads,
                                            }
                                            with open(output_file, "w", encoding="utf-8") as out_f:
                                                json.dump(checkpoint, out_f, indent=2, ensure_ascii=False)
                                        except Exception:
                                            pass

                            # Add newly discovered URLs to the queue (only in deep mode)
                            if not is_specific_mode:
                                for new_url, new_depth in (new_urls or []):
                                    if new_depth > MAX_DEPTH:
                                        continue
                                    norm = normalize_url(new_url)
                                    if norm not in visited:
                                        visited.add(norm)
                                        await queue.put((new_url, new_depth))

                        except Exception as e:
                            log_msg(f"    ❌ Unhandled error on {url}: {e}")
                        finally:
                            await page.close()

                # BFS loop
                while True:
                    # MAX_PAGES safety guard
                    if len(all_pages) >= MAX_PAGES:
                        log_msg(f"⚠️  Reached MAX_PAGES limit ({MAX_PAGES}). Stopping crawl.")
                        break

                    batch = []
                    while not queue.empty() and len(batch) < MAX_CONCURRENT_TABS:
                        try:
                            item = queue.get_nowait()
                            batch.append(item)
                        except asyncio.QueueEmpty:
                            break

                    if not batch:
                        break

                    tasks = [process_url(url, depth) for url, depth in batch]
                    await asyncio.gather(*tasks, return_exceptions=True)

                    # Update status
                    elapsed = time.time() - start_time
                    update_status(f"Scraped {len(all_pages)} pages in {elapsed:.0f}s. Queue: {queue.qsize()}")

            finally:
                # Always clean up resources
                await http_session.close()
                await browser.close()

        elapsed = time.time() - start_time

        # Build final output
        output = {
            "collegeName": college_name,
            "startUrls": start_urls,
            "allowedDomains": list(allowed_domains),
            "crawledAt": datetime.now(timezone.utc).isoformat(),
            "crawlDurationSeconds": round(elapsed, 1),
            "totalPages": len(all_pages),
            "totalDownloads": len(all_downloads),
            "downloadMedia": download_media,
            "pages": all_pages,
            "downloads": all_downloads,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        update_status("Crawl complete", "complete")

        log_msg("=" * 60)
        log_msg(f"✅ Crawl complete for {college_name}!")
        log_msg(f"   📄 Pages scraped: {len(all_pages)}")
        log_msg(f"   📥 Files downloaded: {len(all_downloads)}")
        log_msg(f"   ⏱️  Duration: {elapsed:.1f}s")
        log_msg(f"   💾 Output: {output_file}")
        if all_downloads:
            log_msg(f"   📂 Downloads: {downloads_dir}/")

    except Exception as e:
        # Catch-all: ensure status is set to "error" so CMS doesn't spin forever
        log_msg(f"💥 FATAL ERROR in crawl for {college_name}: {e}")
        log_msg(traceback.format_exc())
        update_status(f"Crawl failed: {e}", "error")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python crawl.py <input.csv> [--mode deep|specific] [--no-media]")
        print("Example: python crawl.py input.csv --mode specific --no-media")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"Error: Could not find '{csv_path}'")
        sys.exit(1)

    cli_mode = "deep"
    if "--mode" in sys.argv:
        m_idx = sys.argv.index("--mode")
        if m_idx + 1 < len(sys.argv):
            cli_mode = sys.argv[m_idx + 1].strip().lower()

    cli_media = not ("--no-media" in sys.argv or "--no-downloads" in sys.argv)

    # Parse CSV: Group by CollegeName
    colleges = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            college = row.get("CollegeName", "").strip()
            url = row.get("SeedURL", "").strip()
            mode = row.get("Mode", cli_mode).strip().lower() or cli_mode
            raw_media = row.get("DownloadMedia", "").strip().lower()
            if raw_media in ("false", "no", "0", "off"):
                media_opt = False
            elif raw_media in ("true", "yes", "1", "on"):
                media_opt = True
            else:
                media_opt = cli_media

            if not college or not url:
                continue

            if college not in colleges:
                colleges[college] = {"urls": [], "mode": mode, "download_media": media_opt}

            colleges[college]["urls"].append(url)

    for college_name, data in colleges.items():
        start_urls = list(dict.fromkeys(data["urls"]))
        c_mode = data.get("mode", cli_mode)
        c_media = data.get("download_media", cli_media)
        asyncio.run(crawl(college_name, start_urls, crawl_mode=c_mode, download_media=c_media))


if __name__ == "__main__":
    main()
