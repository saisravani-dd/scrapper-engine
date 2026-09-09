import re

with open("templates/index.html", "r") as f:
    content = f.read()

# Replace Data Initialization
content = content.replace("scraperForm: { collegeName: '', seedUrls: '' },", "scraperForm: { jobs: [{ collegeName: '', seedUrls: '' }] },")

# Replace openNewScrape initialization
content = content.replace("this.scraperForm = { collegeName: '', seedUrls: '' };", "this.scraperForm = { jobs: [{ collegeName: '', seedUrls: '' }] };")

# Replace startScrape method
old_start = """                async startScrape() {
                    try {
                        const urls = this.scraperForm.seedUrls.split('\\n').filter(u => u.trim());
                        const res = await fetch('/api/scrape', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                collegeName: this.scraperForm.collegeName,
                                seedUrls: urls
                            })
                        });
                        const data = await res.json();
                        if (res.ok || data.status === 'running') {
                            this.globalScraperStatus[this.scraperForm.collegeName] = 'running';
                            this.startPollingStatus(this.scraperForm.collegeName);
                        } else {
                            alert(data.message || "Failed to start scraper");
                        }
                    } catch(e) {
                        alert("Error starting scraper.");
                    }
                },"""

new_start = """                async startScrape() {
                    try {
                        const validJobs = this.scraperForm.jobs.filter(j => j.collegeName.trim() && j.seedUrls.trim());
                        if (validJobs.length === 0) return;
                        
                        const formattedJobs = validJobs.map(j => ({
                            collegeName: j.collegeName,
                            seedUrls: j.seedUrls.split('\\n').filter(u => u.trim())
                        }));
                        
                        const res = await fetch('/api/scrape/bulk', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ jobs: formattedJobs })
                        });
                        
                        const data = await res.json();
                        if (res.ok || data.status === 'started') {
                            validJobs.forEach(j => {
                                this.globalScraperStatus[j.collegeName] = 'running';
                                this.startPollingStatus(j.collegeName);
                            });
                            alert("Bulk scrape started successfully!");
                            this.scraperForm.jobs = [{ collegeName: '', seedUrls: '' }];
                        } else {
                            alert(data.message || "Failed to start scraper");
                        }
                    } catch(e) {
                        alert("Error starting scraper.");
                    }
                },"""

content = content.replace(old_start, new_start)

# Replace HTML Form
old_form = """                                <div class="mb-4">
                                    <label class="block text-sm font-bold text-gray-700 mb-2">College ID / Name</label>
                                    <input type="text" v-model="scraperForm.collegeName" placeholder="e.g. mycollege" class="w-full px-4 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none">
                                    <p class="text-xs text-gray-500 mt-1">Used for the output JSON file name. No spaces recommended.</p>
                                </div>
                                
                                <div class="mb-6">
                                    <label class="block text-sm font-bold text-gray-700 mb-2">Seed URLs (One per line)</label>
                                    <textarea v-model="scraperForm.seedUrls" rows="4" placeholder="https://college.edu/&#10;https://college.edu/academics" class="w-full px-4 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"></textarea>
                                    <p class="text-xs text-gray-500 mt-1 text-orange-600 font-medium">Note: Duplicate URLs will be automatically skipped if they already exist in the college's data.</p>
                                </div>
                                
                                <button @click="startScrape" :disabled="!scraperForm.collegeName || !scraperForm.seedUrls" class="w-full py-3 bg-gray-800 text-white font-bold rounded shadow hover:bg-gray-900 disabled:opacity-50 transition">
                                    Start Background Scrape
                                </button>"""

new_form = """                                <div v-for="(job, index) in scraperForm.jobs" :key="index" class="p-4 bg-white border rounded mb-4 shadow-sm relative">
                                    <button v-if="scraperForm.jobs.length > 1" @click="scraperForm.jobs.splice(index, 1)" class="absolute top-2 right-2 text-red-500 hover:text-red-700 p-1">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                                    </button>
                                    <h3 class="font-bold text-gray-700 mb-3 border-b pb-2">College Job [[ index + 1 ]]</h3>
                                    
                                    <div class="mb-4">
                                        <label class="block text-sm font-bold text-gray-700 mb-2">College ID / Name</label>
                                        <input type="text" v-model="job.collegeName" placeholder="e.g. mycollege" class="w-full px-4 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none">
                                    </div>
                                    
                                    <div class="mb-2">
                                        <label class="block text-sm font-bold text-gray-700 mb-2">Seed URLs (One per line)</label>
                                        <textarea v-model="job.seedUrls" rows="3" placeholder="https://college.edu/" class="w-full px-4 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"></textarea>
                                    </div>
                                </div>
                                
                                <button @click="scraperForm.jobs.push({collegeName: '', seedUrls: ''})" class="mb-6 px-4 py-2 bg-gray-200 text-gray-700 font-medium rounded hover:bg-gray-300 transition text-sm">
                                    + Add Another College
                                </button>
                                
                                <button @click="startScrape" :disabled="!scraperForm.jobs.some(j => j.collegeName && j.seedUrls)" class="w-full py-3 bg-gray-800 text-white font-bold rounded shadow hover:bg-gray-900 disabled:opacity-50 transition">
                                    Start Bulk Background Scrape
                                </button>"""

content = content.replace(old_form, new_form)

# And update the "View Scraped Data" button logic
old_view_btn = """                                <div v-if="scraperStatus.status === 'complete'" class="mt-4">
                                    <button @click="loadCollege(scraperForm.collegeName)" class="px-4 py-2 bg-green-600 text-white font-medium rounded hover:bg-green-700">
                                        View Scraped Data
                                    </button>
                                </div>"""

new_view_btn = """                                <div v-if="scraperStatus.status === 'complete'" class="mt-4">
                                    <button @click="loadCollege(selectedCollege)" class="px-4 py-2 bg-green-600 text-white font-medium rounded hover:bg-green-700">
                                        View Scraped Data
                                    </button>
                                </div>"""
content = content.replace(old_view_btn, new_view_btn)

with open("templates/index.html", "w") as f:
    f.write(content)

