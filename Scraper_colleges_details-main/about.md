# About Scraper CMS (v2.0)

Scraper CMS is a robust, production-ready deep recursive website scraper and content management system designed to intelligently extract, organize, and manage massive amounts of website data, documents, and media.

## 🚀 What's New in v2.0
- **Seamless Auto-Resume**: The crawler saves state every 5 pages. If a job is stopped or crashes, it can instantly resume exactly where it left off, avoiding duplicate work.
- **Granular Page Archiving**: Each scraped page is instantly saved as an individual JSON file, improving stability and performance.
- **One-Click Markdown Export**: An entire college's crawled data (text, URLs, and local document links) can be exported into a perfectly formatted, indexed directory of Markdown (`.md`) files.
- **Files & Pages Archive**: A dedicated CMS tab that provides a searchable, real-time view of every scraped page file and downloaded document.
- **Production Hardening**: Features dynamic UI updates (Vue v-for), non-blocking toast notifications, bulletproof try/catch safety across all scraper tabs, and path traversal security.

## 🛠️ Technology Stack

**Backend**
- **Python 3.10+**: Core programming language.
- **FastAPI**: High-performance asynchronous web framework used for the CMS backend API.
- **Uvicorn**: ASGI web server implementation.
- **Playwright (Async)**: Headless browser automation for rendering JavaScript-heavy websites and Single Page Applications (SPAs).
- **BeautifulSoup4**: HTML parsing and DOM manipulation for extracting clean text and links.
- **aiohttp**: Asynchronous HTTP client used for fast, concurrent document downloading (with automatic retries).

**Frontend**
- **Vue.js 3**: Progressive JavaScript framework used via CDN for reactive, componentless UI management.
- **Tailwind CSS**: Utility-first CSS framework for rapid UI styling and responsive design.
- **Chart.js**: Client-side charting library for the analytics dashboard.

## ✨ Core Features

- **Deep Recursive Crawling**: Uses Breadth-First Search (BFS) to map and crawl entire domains, constrained to specific allowed domains to prevent infinite external looping. Safely capped at 2,000 pages per domain to prevent infinite crawls.
- **Stealth Browsing**: Employs Playwright Stealth to bypass basic anti-bot protections.
- **Smart DOM Parsing**: Intelligently identifies and strips out boilerplate content like headers, footers, sidebars, and navigation menus to ensure only the primary article/body text is saved.
- **Document Extraction**: Automatically detects links to `.pdf`, `.doc`, `.xlsx`, and other documents, downloads them locally, and maps them to the exact section and page they were found on.
- **Bulk Scraping**: Queue up multiple domains at once. The crawler processes them sequentially in the background.
- **Visual Analytics Dashboard**: Provides real-time insights into crawl depths, storage usage, page distribution across URL paths, and file type breakdowns.
- **Background Task Management**: Scrape jobs run as background subprocesses, providing live log tails and status polling without blocking the UI.
- **Trash & Restore**: Soft-deletion system for pages, with a garbage-collection mechanism that safely removes orphaned document files from the disk when changes are committed.

## ⚙️ How It Works

1. **Initialization**: You provide a `CollegeName` and a list of `SeedURLs`.
2. **Crawl Phase**: Playwright spins up multiple concurrent browser tabs (8 max). It blocks images, CSS, and fonts at the network level to massively speed up page rendering.
3. **Extraction**: For every page, it extracts the DOM. It performs two passes:
   - *Pass 1 (Navigation)*: Finds all `<a>` tags to populate the BFS queue with new internal URLs.
   - *Pass 2 (Content)*: Cleans the HTML of boilerplate, extracts the raw body text, and finds document links.
4. **Downloading**: Document links are intercepted by `aiohttp` and downloaded asynchronously to the `downloads/` folder.
5. **Storage**: Individual pages are instantly saved to `data/pages/<college>/`. A master checkpoint is updated every 5 pages.
6. **Management**: The FastAPI backend serves this data to the Vue.js frontend, allowing you to edit text, export to Markdown, delete pages, and monitor live crawls.
