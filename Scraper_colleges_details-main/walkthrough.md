# Scraper & CMS Walkthrough

We have successfully transformed the crawler into a fully-fledged Scraping Engine and Content Management System!

## 1. How to run the new Crawler
You no longer pass URLs directly in the command line. Instead, edit the `input.csv` file I created.

### The `input.csv` file
```csv
CollegeName,SeedURL,ExcludePatterns
vit-ap,https://vitap.ac.in/,"/faculty/,/gallery/,/alumni/"
srm,https://www.srmist.edu.in/,
```
- **CollegeName**: Used to group all data into `data/<collegename>.json`.
- **SeedURL**: The starting link for the crawl. You can have multiple rows with the same college name to crawl multiple portals at once!
- **ExcludePatterns**: A comma-separated list of things you want to ignore. If you want to skip all faculty pages, put `/faculty/` here.

### Running it
```bash
python3 crawl.py input.csv
```
All downloaded PDFs will be neatly organized into `downloads/<college_name>/`.

## 2. The Local Web CMS
I have built a web application using FastAPI and Vue.js that lets you view and edit your scraped data. 

**I have already started it for you in the background!**
To view the CMS, open this link in your browser:
👉 [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Features of the CMS
1. **Sidebar Navigation**: View all colleges you've scraped.
2. **Page Search**: Quickly search through all scraped pages by URL or Title.
3. **Data Editing**: You can edit the `bodyText` or `Title` directly in the browser if you spot a mistake.
4. **Bulk Deletion**: Use the **Bulk Delete by URL Slug** box to instantly remove hundreds of pages (e.g. typing `/faculty/`) at once.
5. **Smart Garbage Collection**: When you click "Save Changes", the backend automatically scans your remaining pages. Any PDFs that were only linked on the deleted pages will be permanently deleted from your hard drive to save space!
6. **Save**: Click the "Save Changes" button in the top right to instantly overwrite the `.json` file on your hard drive with your edits and trigger garbage collection.

Enjoy your new scraping platform! Let me know if you need any further adjustments.
