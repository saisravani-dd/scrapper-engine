html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scraper CMS</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        [v-cloak] { display: none; }
        .group-header { cursor: pointer; user-select: none; }
        .locked-overlay { position: absolute; inset: 0; background: rgba(255,255,255,0.7); z-index: 50; display: flex; flex-direction: column; align-items: center; justify-content: center; backdrop-filter: blur(2px); }
    </style>
</head>
<body class="bg-gray-50 h-screen font-sans">
    <div id="app" class="flex h-full" v-cloak>
        
        <!-- Sidebar -->
        <div class="w-64 bg-white shadow-md flex flex-col h-full overflow-y-auto z-20 border-r border-gray-200 shrink-0">
            <div class="p-4 bg-gray-800 text-white font-bold text-lg flex items-center justify-between">
                <span>🏫 Scraper CMS</span>
            </div>
            
            <div class="p-4 border-b border-gray-100">
                <button @click="openNewScrape" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded shadow transition">
                    + New Scrape
                </button>
            </div>
            
            <div class="p-3 text-sm font-semibold text-gray-500 uppercase tracking-wider flex justify-between items-center">
                <span>Colleges</span>
            </div>
            
            <ul class="flex-1">
                {% for college in colleges %}
                <li>
                    <button 
                        @click="loadCollege('{{ college }}')" 
                        :class="['w-full text-left px-4 py-3 border-b hover:bg-blue-50 transition-colors flex justify-between items-center', selectedCollege === '{{ college }}' ? 'bg-blue-100 border-blue-500 text-blue-700 font-medium' : 'text-gray-700']"
                    >
                        <span>{{ college }}</span>
                        <svg v-if="globalScraperStatus['{{ college }}'] === 'running'" class="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    </button>
                </li>
                {% endfor %}
            </ul>
            
            <div class="p-4 bg-gray-50 text-xs text-gray-500 border-t">
                Global Storage:<br>
                Data: [[ formatBytes(globalStorage.dataSizeBytes) ]]<br>
                Downloads: [[ formatBytes(globalStorage.downloadsSizeBytes) ]]
            </div>
        </div>

        <!-- Main Content -->
        <div class="flex-1 flex flex-col h-full overflow-hidden relative">
            
            <!-- Global Scraper Banner -->
            <div v-if="anyScraperRunning" class="bg-blue-600 text-white px-4 py-2 text-sm font-medium flex justify-between items-center shadow-md z-30">
                <div class="flex items-center gap-2">
                    <svg class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    <span>Scraper is currently running in the background.</span>
                </div>
            </div>

            <div v-if="loading" class="absolute inset-0 bg-white/80 z-50 flex items-center justify-center backdrop-blur-sm">
                <div class="text-xl font-bold text-gray-600 animate-pulse flex flex-col items-center">
                    <svg class="animate-spin h-10 w-10 text-blue-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    Loading data...
                </div>
            </div>

            <!-- College View -->
            <template v-if="selectedCollege || activeTab === 'scraper'">
                
                <!-- Header Tabs -->
                <header class="bg-white shadow z-10 shrink-0">
                    <div class="px-6 py-4 flex justify-between items-center border-b border-gray-200">
                        <div>
                            <h1 class="text-2xl font-bold text-gray-800">
                                [[ selectedCollege || 'New Scrape' ]]
                                <span v-if="isLocked" class="ml-2 text-sm bg-orange-100 text-orange-800 px-2 py-1 rounded font-normal inline-flex items-center">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd" /></svg>
                                    Locked (Scraping)
                                </span>
                            </h1>
                        </div>
                        <div v-if="selectedCollege && activeTab !== 'scraper'">
                            <button @click="saveChanges" :disabled="saving || isLocked || !hasUnsavedChanges" :class="['px-4 py-2 rounded font-bold text-white transition', (saving || isLocked) ? 'bg-gray-400 cursor-not-allowed' : (hasUnsavedChanges ? 'bg-green-600 hover:bg-green-700' : 'bg-blue-600 hover:bg-blue-700')]">
                                [[ saving ? 'Saving...' : (hasUnsavedChanges ? 'Save Changes *' : 'Save Changes') ]]
                            </button>
                        </div>
                    </div>
                    
                    <!-- Tab Navigation -->
                    <div class="px-6 flex gap-6 bg-gray-50 pt-2" v-if="selectedCollege">
                        <button @click="activeTab = 'pages'" :class="['pb-2 px-1 border-b-2 font-medium text-sm transition-colors', activeTab === 'pages' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700']">
                            Pages ([[ pages.length ]])
                        </button>
                        <button @click="activeTab = 'dashboard'" :class="['pb-2 px-1 border-b-2 font-medium text-sm transition-colors', activeTab === 'dashboard' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700']">
                            Dashboard
                        </button>
                        <button @click="activeTab = 'scraper'" :class="['pb-2 px-1 border-b-2 font-medium text-sm transition-colors', activeTab === 'scraper' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700']">
                            Add URLs / Scraper
                        </button>
                        <button @click="activeTab = 'trash'" :class="['pb-2 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-1', activeTab === 'trash' ? 'border-red-600 text-red-600' : 'border-transparent text-gray-500 hover:text-gray-700']">
                            Trash 
                            <span v-if="trash.length > 0" class="bg-red-100 text-red-700 text-xs px-1.5 py-0.5 rounded-full">[[ trash.length ]]</span>
                        </button>
                    </div>
                </header>
                
                <div class="flex-1 overflow-hidden relative">
                    
                    <!-- TAB: PAGES -->
                    <div v-show="activeTab === 'pages'" class="h-full flex">
                        
                        <div v-if="isLocked" class="locked-overlay">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                            <h2 class="text-xl font-bold text-gray-700">College is Locked</h2>
                            <p class="text-gray-500 mt-2">The scraper is currently running for this college. Editing is disabled.</p>
                            <button @click="activeTab = 'scraper'" class="mt-4 px-4 py-2 bg-blue-100 text-blue-700 rounded hover:bg-blue-200">View Scraper Status</button>
                        </div>
                        
                        <!-- Page List -->
                        <div class="w-1/3 bg-gray-50 border-r border-gray-200 flex flex-col">
                            <!-- Toolbar -->
                            <div class="p-4 bg-white border-b border-gray-200 shadow-sm">
                                <input type="text" v-model="searchQuery" placeholder="Search URLs or titles..." class="w-full px-3 py-2 border rounded focus:outline-none focus:ring-1 focus:ring-blue-500 mb-3 text-sm">
                                
                                <div class="flex justify-between items-center mb-2">
                                    <div class="text-xs text-gray-500 font-medium">
                                        [[ selectedPageUrls.length ]] selected
                                    </div>
                                    <button @click="deleteSelected" :disabled="selectedPageUrls.length === 0" class="px-3 py-1 bg-red-100 text-red-700 text-xs font-bold rounded hover:bg-red-200 disabled:opacity-50 transition-colors flex items-center gap-1">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                                        Move to Trash
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Grouped List -->
                            <div class="overflow-y-auto flex-1">
                                <div v-for="group in groupedPages" :key="group.prefix" class="border-b border-gray-100 last:border-0">
                                    
                                    <!-- Group Header -->
                                    <div class="group-header bg-gray-100 px-3 py-2 flex items-center justify-between hover:bg-gray-200 transition-colors" @click="toggleGroup(group.prefix)">
                                        <div class="flex items-center gap-2 overflow-hidden">
                                            <svg :class="['h-4 w-4 text-gray-500 transition-transform', group.isExpanded ? 'rotate-90' : '']" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
                                            <span class="font-bold text-sm text-gray-700 truncate" :title="group.prefix">[[ group.prefix ]]</span>
                                            <span class="bg-white text-gray-500 text-xs px-1.5 py-0.5 rounded shadow-sm border font-medium">[[ group.pages.length ]]</span>
                                        </div>
                                        <div class="flex items-center" @click.stop>
                                            <input type="checkbox" :checked="group.allSelected" @change="toggleSelectAll(group)" class="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500" title="Select all in group">
                                        </div>
                                    </div>
                                    
                                    <!-- Group Items -->
                                    <div v-show="group.isExpanded" class="bg-white">
                                        <div v-for="page in group.pages" :key="page.url" 
                                             @click="selectPage(page)"
                                             :class="['p-3 border-b border-gray-50 cursor-pointer transition-colors flex items-start gap-3', selectedPage && selectedPage.url === page.url ? 'bg-blue-50 border-l-4 border-l-blue-500' : 'hover:bg-gray-50']">
                                            
                                            <div class="pt-0.5" @click.stop>
                                                <input type="checkbox" v-model="selectedPages[page.url]" class="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500">
                                            </div>
                                            
                                            <div class="overflow-hidden flex-1">
                                                <div class="font-medium text-gray-800 text-sm truncate" :title="page.title">[[ page.title || 'No Title' ]]</div>
                                                <div class="text-xs text-blue-600 truncate" :title="page.url">[[ page.url.replace(/^.*\/\/[^\/]+/, '') ]]</div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                </div>
                                <div v-if="groupedPages.length === 0" class="text-center text-gray-500 py-8 text-sm">
                                    No pages match your search.
                                </div>
                            </div>
                        </div>

                        <!-- Page Editor -->
                        <div class="w-2/3 bg-white overflow-y-auto p-6">
                            <div v-if="selectedPage">
                                <div class="mb-4">
                                    <a :href="selectedPage.url" target="_blank" class="text-blue-600 hover:underline text-lg break-all font-medium inline-flex items-center gap-1">
                                        [[ selectedPage.url ]] 
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" /><path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" /></svg>
                                    </a>
                                </div>
                                
                                <div class="mb-4">
                                    <label class="block text-sm font-semibold text-gray-700 mb-1">Title</label>
                                    <input type="text" v-model="selectedPage.title" @input="markChanged" class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500">
                                </div>

                                <div class="mb-4">
                                    <label class="block text-sm font-semibold text-gray-700 mb-1 flex justify-between">
                                        <span>Body Text Content</span>
                                        <span class="font-normal text-gray-500">[[ selectedPage.bodyText.length ]] chars</span>
                                    </label>
                                    <textarea v-model="selectedPage.bodyText" @input="markChanged" rows="15" class="w-full px-3 py-2 border border-gray-300 rounded font-mono text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"></textarea>
                                </div>
                                
                                <div class="mb-4" v-if="selectedPage.links && selectedPage.links.length > 0">
                                    <label class="block text-sm font-semibold text-gray-700 mb-2">Links on this page ([[ selectedPage.links.length ]])</label>
                                    <div class="bg-gray-50 p-4 rounded border max-h-64 overflow-y-auto">
                                        <ul class="space-y-3">
                                            <li v-for="(link, i) in selectedPage.links" :key="i" class="text-sm flex items-start gap-2 border-b border-gray-200 pb-3 last:border-0 last:pb-0">
                                                <span v-if="link.type === 'document'" class="bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded shrink-0 font-bold border border-purple-200">DOC</span>
                                                <span v-else-if="link.type === 'internal'" class="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded shrink-0 border border-blue-200">INT</span>
                                                <span v-else class="bg-gray-200 text-gray-800 text-xs px-2 py-0.5 rounded shrink-0 border border-gray-300">EXT</span>
                                                
                                                <div class="overflow-hidden">
                                                    <div class="font-medium text-gray-800" :title="link.text">[[ link.text || 'Unnamed Link' ]]</div>
                                                    <a :href="link.href" target="_blank" class="text-blue-600 hover:underline text-xs block mt-0.5 truncate" :title="link.href">[[ link.href ]]</a>
                                                    
                                                    <div v-if="link.type === 'document'" class="mt-1.5 p-2 bg-white rounded border border-gray-200 text-xs">
                                                        <div v-if="link.sectionHeading" class="text-gray-600 mb-1"><span class="font-semibold text-gray-500">Section:</span> [[ link.sectionHeading ]]</div>
                                                        <div v-if="link.localPath" class="text-green-700 font-mono"><span class="font-semibold text-gray-500 font-sans">Path:</span> [[ link.localPath ]]</div>
                                                    </div>
                                                </div>
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            <div v-else class="h-full flex flex-col items-center justify-center text-gray-400">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mb-4 text-gray-200" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                                <p>Select a page from the list to view and edit.</p>
                            </div>
                        </div>
                    </div>

                    <!-- TAB: TRASH -->
                    <div v-show="activeTab === 'trash'" class="h-full bg-gray-50 p-6 overflow-y-auto">
                        <div class="max-w-4xl mx-auto">
                            <div class="flex justify-between items-center mb-6">
                                <div>
                                    <h2 class="text-xl font-bold text-gray-800">Trash Bin</h2>
                                    <p class="text-sm text-gray-500">Pages here will be permanently deleted when you click "Save Changes".</p>
                                </div>
                                <button v-if="trash.length > 0" @click="emptyTrash" class="px-4 py-2 bg-red-100 text-red-700 font-medium rounded hover:bg-red-200 transition">
                                    Empty Trash
                                </button>
                            </div>
                            
                            <div v-if="trash.length === 0" class="bg-white rounded shadow-sm p-12 text-center text-gray-400 border border-gray-200">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mx-auto mb-4 text-gray-200" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                <p class="text-lg">Trash is empty.</p>
                            </div>
                            
                            <div v-else class="bg-white rounded shadow-sm border border-gray-200 overflow-hidden">
                                <ul class="divide-y divide-gray-200">
                                    <li v-for="page in trash" :key="page.url" class="p-4 hover:bg-gray-50 flex justify-between items-center">
                                        <div class="overflow-hidden pr-4">
                                            <div class="font-medium text-gray-800 truncate" :title="page.title">[[ page.title || 'No Title' ]]</div>
                                            <div class="text-sm text-gray-500 truncate" :title="page.url">[[ page.url ]]</div>
                                        </div>
                                        <button @click="restoreFromTrash(page)" class="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-sm font-medium rounded shadow-sm hover:bg-gray-50 shrink-0">
                                            Restore
                                        </button>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- TAB: DASHBOARD -->
                    <div v-show="activeTab === 'dashboard'" class="h-full bg-gray-100 p-6 overflow-y-auto">
                        <div class="max-w-6xl mx-auto space-y-6" v-if="analytics">
                            
                            <!-- Hero Stats -->
                            <div class="grid grid-cols-4 gap-4">
                                <div class="bg-white p-4 rounded shadow border border-gray-200 border-t-4 border-t-blue-500">
                                    <div class="text-sm text-gray-500 font-medium uppercase tracking-wide">Total Pages</div>
                                    <div class="text-3xl font-bold text-gray-800 mt-1">[[ analytics.totalPages ]]</div>
                                </div>
                                <div class="bg-white p-4 rounded shadow border border-gray-200 border-t-4 border-t-purple-500">
                                    <div class="text-sm text-gray-500 font-medium uppercase tracking-wide">Total Downloads</div>
                                    <div class="text-3xl font-bold text-gray-800 mt-1">[[ analytics.totalDownloads ]]</div>
                                </div>
                                <div class="bg-white p-4 rounded shadow border border-gray-200 border-t-4 border-t-green-500">
                                    <div class="text-sm text-gray-500 font-medium uppercase tracking-wide">Download Size</div>
                                    <div class="text-3xl font-bold text-gray-800 mt-1">[[ formatBytes(analytics.totalDownloadSize) ]]</div>
                                </div>
                                <div class="bg-white p-4 rounded shadow border border-gray-200 border-t-4 border-t-orange-500">
                                    <div class="text-sm text-gray-500 font-medium uppercase tracking-wide">Crawl Time</div>
                                    <div class="text-3xl font-bold text-gray-800 mt-1">[[ analytics.crawlDurationSeconds ]]s</div>
                                </div>
                            </div>
                            
                            <!-- Charts Row 1 -->
                            <div class="grid grid-cols-2 gap-6">
                                <div class="bg-white p-5 rounded shadow border border-gray-200">
                                    <h3 class="text-lg font-bold text-gray-700 mb-4">Pages by URL Path (Top 15)</h3>
                                    <div class="h-64 relative">
                                        <canvas id="urlGroupsChart"></canvas>
                                    </div>
                                </div>
                                <div class="bg-white p-5 rounded shadow border border-gray-200">
                                    <h3 class="text-lg font-bold text-gray-700 mb-4">Downloads by File Type</h3>
                                    <div class="h-64 relative flex justify-center">
                                        <canvas id="downloadTypesChart"></canvas>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Charts Row 2 -->
                            <div class="grid grid-cols-2 gap-6">
                                <div class="bg-white p-5 rounded shadow border border-gray-200">
                                    <h3 class="text-lg font-bold text-gray-700 mb-4">Crawl Depth Distribution</h3>
                                    <div class="h-48 relative">
                                        <canvas id="depthChart"></canvas>
                                    </div>
                                </div>
                                <div class="bg-white p-5 rounded shadow border border-gray-200">
                                    <h3 class="text-lg font-bold text-gray-700 mb-4">Storage Breakdown</h3>
                                    <div class="flex items-center justify-between mt-8">
                                        <div class="text-center">
                                            <div class="text-4xl font-bold text-gray-700">[[ formatBytes(analytics.totalBodyLength) ]]</div>
                                            <div class="text-sm text-gray-500 uppercase tracking-widest mt-2">Text Content</div>
                                        </div>
                                        <div class="text-3xl text-gray-300">VS</div>
                                        <div class="text-center">
                                            <div class="text-4xl font-bold text-purple-700">[[ formatBytes(analytics.totalDownloadSize) ]]</div>
                                            <div class="text-sm text-purple-500 uppercase tracking-widest mt-2">Downloaded Files</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                        </div>
                        <div v-else class="flex justify-center items-center h-full text-gray-400">
                            Loading analytics...
                        </div>
                    </div>

                    <!-- TAB: SCRAPER -->
                    <div v-show="activeTab === 'scraper'" class="h-full bg-white p-8 overflow-y-auto">
                        <div class="max-w-3xl mx-auto">
                            
                            <h2 class="text-2xl font-bold text-gray-800 mb-6">Run Web Scraper</h2>
                            
                            <!-- Scraper Status Panel -->
                            <div v-if="scraperStatus" class="mb-8 p-6 rounded-lg border-2 shadow-sm" 
                                :class="{
                                    'border-blue-300 bg-blue-50': scraperStatus.status === 'running',
                                    'border-green-300 bg-green-50': scraperStatus.status === 'complete',
                                    'border-red-300 bg-red-50': scraperStatus.status === 'error' || scraperStatus.status === 'failed'
                                }">
                                <div class="flex items-center gap-3 mb-4">
                                    <div v-if="scraperStatus.status === 'running'" class="relative flex h-5 w-5">
                                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                      <span class="relative inline-flex rounded-full h-5 w-5 bg-blue-500"></span>
                                    </div>
                                    <svg v-else-if="scraperStatus.status === 'complete'" class="h-6 w-6 text-green-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                                    <svg v-else class="h-6 w-6 text-red-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    
                                    <h3 class="text-xl font-bold" :class="{'text-blue-800': scraperStatus.status === 'running', 'text-green-800': scraperStatus.status === 'complete', 'text-red-800': scraperStatus.status === 'error'}">
                                        Status: [[ scraperStatus.status.toUpperCase() ]]
                                    </h3>
                                </div>
                                
                                <p class="text-gray-700 font-medium mb-4">[[ scraperStatus.message ]]</p>
                                
                                <div class="bg-gray-900 rounded p-4 font-mono text-xs text-gray-300 h-48 overflow-y-auto">
                                    <div v-for="(log, idx) in scraperStatus.logs" :key="idx" class="mb-1">[[ log ]]</div>
                                    <div v-if="!scraperStatus.logs || scraperStatus.logs.length === 0" class="text-gray-600 italic">No logs available yet...</div>
                                    <div v-if="scraperStatus.status === 'running'" class="mt-2 text-green-400 animate-pulse">_</div>
                                </div>
                                
                                <div v-if="scraperStatus.status === 'complete'" class="mt-4">
                                    <button @click="loadCollege(scraperForm.collegeName)" class="px-4 py-2 bg-green-600 text-white font-medium rounded hover:bg-green-700">
                                        View Scraped Data
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Form -->
                            <div class="bg-gray-50 p-6 rounded shadow-sm border border-gray-200" :class="{'opacity-50 pointer-events-none': scraperStatus && scraperStatus.status === 'running'}">
                                <div class="mb-4">
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
                                </button>
                            </div>
                            
                        </div>
                    </div>
                </div>
            </template>
            <div v-else-if="!loading" class="flex-1 flex flex-col items-center justify-center bg-gray-50">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-24 w-24 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <h2 class="text-2xl font-bold text-gray-500">Welcome to Scraper CMS</h2>
                <p class="text-gray-400 mt-2">Select a college from the sidebar or start a New Scrape.</p>
            </div>
        </div>
    </div>

    <script>
        const { createApp } = Vue

        createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    selectedCollege: null,
                    collegeData: null,
                    pages: [],
                    trash: [],
                    selectedPage: null,
                    loading: false,
                    saving: false,
                    hasUnsavedChanges: false,
                    searchQuery: '',
                    
                    activeTab: 'pages', // pages, trash, dashboard, scraper
                    
                    scraperForm: { collegeName: '', seedUrls: '' },
                    scraperStatus: null,
                    
                    analytics: null,
                    charts: {},
                    
                    globalStorage: { dataSizeBytes: 0, downloadsSizeBytes: 0 },
                    globalScraperStatus: {},
                    
                    expandedGroups: {},
                    selectedPages: {},
                    
                    statusPollInterval: null,
                    globalPollInterval: null
                }
            },
            computed: {
                isLocked() {
                    return this.selectedCollege && this.globalScraperStatus[this.selectedCollege] === 'running';
                },
                anyScraperRunning() {
                    return Object.values(this.globalScraperStatus).includes('running');
                },
                filteredPages() {
                    if (!this.searchQuery) return this.pages;
                    const q = this.searchQuery.toLowerCase();
                    return this.pages.filter(p => 
                        p.url.toLowerCase().includes(q) || 
                        (p.title && p.title.toLowerCase().includes(q))
                    );
                },
                groupedPages() {
                    const groups = {};
                    this.filteredPages.forEach(p => {
                        try {
                            const urlObj = new URL(p.url);
                            const pathParts = urlObj.pathname.split('/').filter(x => x);
                            const prefix = pathParts.length > 0 ? `/${pathParts[0]}/` : '/';
                            if (!groups[prefix]) groups[prefix] = [];
                            groups[prefix].push(p);
                        } catch(e) {
                            if (!groups['/']) groups['/'] = [];
                            groups['/'].push(p);
                        }
                    });
                    
                    return Object.keys(groups).sort().map(prefix => {
                        const groupPages = groups[prefix];
                        // Check if all pages in this group are selected
                        const allSelected = groupPages.length > 0 && groupPages.every(p => this.selectedPages[p.url]);
                        
                        // Default expanded state is false, unless explicitly set
                        const isExpanded = this.expandedGroups[prefix] === true;
                        
                        return {
                            prefix,
                            pages: groupPages,
                            isExpanded,
                            allSelected
                        };
                    }).sort((a,b) => b.pages.length - a.pages.length); // Sort by largest group first
                },
                selectedPageUrls() {
                    return Object.keys(this.selectedPages).filter(url => this.selectedPages[url]);
                }
            },
            mounted() {
                this.fetchStorageInfo();
                this.pollAllScraperStatuses();
                this.globalPollInterval = setInterval(this.pollAllScraperStatuses, 5000);
            },
            beforeUnmount() {
                if (this.statusPollInterval) clearInterval(this.statusPollInterval);
                if (this.globalPollInterval) clearInterval(this.globalPollInterval);
                this.destroyCharts();
            },
            watch: {
                activeTab(newTab) {
                    if (newTab === 'dashboard' && this.selectedCollege && !this.analytics) {
                        this.fetchAnalytics();
                    }
                    if (newTab === 'dashboard' && this.analytics) {
                        this.$nextTick(this.renderCharts);
                    }
                }
            },
            methods: {
                formatBytes(bytes, decimals = 2) {
                    if (!+bytes) return '0 Bytes';
                    const k = 1024;
                    const dm = decimals < 0 ? 0 : decimals;
                    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
                },
                async fetchStorageInfo() {
                    try {
                        const res = await fetch('/api/storage-info');
                        if (res.ok) this.globalStorage = await res.json();
                    } catch(e) {}
                },
                async pollAllScraperStatuses() {
                    // Quick check for all colleges in the sidebar
                    const colleges = Array.from(document.querySelectorAll('.w-64 ul button span')).map(el => el.innerText);
                    for (const c of colleges) {
                        try {
                            const res = await fetch(`/api/scrape-status/${c}`);
                            if (res.ok) {
                                const data = await res.json();
                                this.globalScraperStatus[c] = data.status;
                            }
                        } catch(e) {}
                    }
                },
                async loadCollege(collegeName) {
                    if (this.hasUnsavedChanges) {
                        if (!confirm("You have unsaved changes. Discard them?")) return;
                    }
                    
                    this.selectedCollege = collegeName;
                    this.loading = true;
                    this.selectedPage = null;
                    this.hasUnsavedChanges = false;
                    this.searchQuery = '';
                    this.trash = [];
                    this.selectedPages = {};
                    this.expandedGroups = {};
                    this.analytics = null;
                    this.activeTab = 'pages';
                    this.scraperForm.collegeName = collegeName;
                    
                    if (this.statusPollInterval) {
                        clearInterval(this.statusPollInterval);
                        this.statusPollInterval = null;
                    }
                    this.scraperStatus = null;
                    
                    // Check if running
                    await this.pollAllScraperStatuses();
                    if (this.isLocked) {
                        this.activeTab = 'scraper';
                        this.startPollingStatus(collegeName);
                    }
                    
                    try {
                        const res = await fetch(`/api/college/${collegeName}`);
                        if (res.ok) {
                            const data = await res.json();
                            this.collegeData = data;
                            this.pages = JSON.parse(JSON.stringify(data.pages || []));
                        } else {
                            if (!this.isLocked) alert("Failed to load data.");
                        }
                    } catch (e) {
                        console.error(e);
                    } finally {
                        this.loading = false;
                    }
                },
                openNewScrape() {
                    this.selectedCollege = null;
                    this.activeTab = 'scraper';
                    this.scraperForm = { collegeName: '', seedUrls: '' };
                    this.scraperStatus = null;
                    if (this.statusPollInterval) clearInterval(this.statusPollInterval);
                },
                toggleGroup(prefix) {
                    this.expandedGroups[prefix] = !this.expandedGroups[prefix];
                },
                toggleSelectAll(group) {
                    const newValue = !group.allSelected;
                    group.pages.forEach(p => {
                        this.selectedPages[p.url] = newValue;
                    });
                },
                selectPage(page) {
                    this.selectedPage = page;
                },
                deleteSelected() {
                    const urlsToDelete = this.selectedPageUrls;
                    if (urlsToDelete.length === 0) return;
                    
                    if (confirm(`Move ${urlsToDelete.length} pages to trash?`)) {
                        // Move to trash
                        const toTrash = this.pages.filter(p => urlsToDelete.includes(p.url));
                        this.trash.push(...toTrash);
                        
                        // Remove from pages
                        this.pages = this.pages.filter(p => !urlsToDelete.includes(p.url));
                        
                        // Clear selection
                        this.selectedPages = {};
                        
                        // Clear selected page if it was deleted
                        if (this.selectedPage && urlsToDelete.includes(this.selectedPage.url)) {
                            this.selectedPage = null;
                        }
                        
                        this.markChanged();
                    }
                },
                restoreFromTrash(page) {
                    this.pages.push(page);
                    this.trash = this.trash.filter(p => p.url !== page.url);
                    this.markChanged();
                },
                emptyTrash() {
                    if (confirm("Are you sure? These pages will be permanently deleted on next Save.")) {
                        this.trash = [];
                        this.markChanged();
                    }
                },
                markChanged() {
                    this.hasUnsavedChanges = true;
                },
                async saveChanges() {
                    this.saving = true;
                    try {
                        const res = await fetch(`/api/college/${this.selectedCollege}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ pages: this.pages })
                        });
                        if (res.ok) {
                            this.hasUnsavedChanges = false;
                            this.trash = []; // Trash is committed
                            alert("Changes saved successfully! Orphaned downloads have been deleted.");
                            this.fetchStorageInfo(); // refresh storage
                            if (this.analytics) this.fetchAnalytics(); // refresh analytics
                        } else {
                            alert("Failed to save changes.");
                        }
                    } catch (e) {
                        console.error(e);
                        alert("Error saving changes.");
                    } finally {
                        this.saving = false;
                    }
                },
                async startScrape() {
                    try {
                        const urls = this.scraperForm.seedUrls.split('\n').filter(u => u.trim());
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
                },
                startPollingStatus(collegeName) {
                    if (this.statusPollInterval) clearInterval(this.statusPollInterval);
                    this.pollStatus(collegeName);
                    this.statusPollInterval = setInterval(() => this.pollStatus(collegeName), 2000);
                },
                async pollStatus(collegeName) {
                    try {
                        const res = await fetch(`/api/scrape-status/${collegeName}`);
                        if (res.ok) {
                            const data = await res.json();
                            this.scraperStatus = data;
                            this.globalScraperStatus[collegeName] = data.status;
                            
                            if (data.status === 'complete' || data.status === 'error' || data.status === 'failed') {
                                clearInterval(this.statusPollInterval);
                                this.statusPollInterval = null;
                            }
                        }
                    } catch(e) {}
                },
                async fetchAnalytics() {
                    if (!this.selectedCollege) return;
                    try {
                        const res = await fetch(`/api/analytics/${this.selectedCollege}`);
                        if (res.ok) {
                            this.analytics = await res.json();
                            this.$nextTick(this.renderCharts);
                        }
                    } catch(e) {
                        console.error("Failed to load analytics");
                    }
                },
                destroyCharts() {
                    Object.values(this.charts).forEach(c => c.destroy());
                    this.charts = {};
                },
                renderCharts() {
                    if (!this.analytics) return;
                    this.destroyCharts();
                    
                    // Helper to generate colors
                    const getColors = (count) => {
                        const baseColors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#6366f1'];
                        return Array.from({length: count}).map((_, i) => baseColors[i % baseColors.length]);
                    };

                    // URL Groups Chart
                    const groupKeys = Object.keys(this.analytics.urlGroups);
                    const groupVals = Object.values(this.analytics.urlGroups);
                    if (document.getElementById('urlGroupsChart')) {
                        this.charts.urlGroups = new Chart(document.getElementById('urlGroupsChart'), {
                            type: 'bar',
                            data: {
                                labels: groupKeys.map(k => k.length > 20 ? k.substring(0,20)+'...' : k),
                                datasets: [{
                                    label: 'Pages',
                                    data: groupVals,
                                    backgroundColor: '#3b82f6',
                                    borderRadius: 4
                                }]
                            },
                            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: {display: false} } }
                        });
                    }
                    
                    // Download Types Chart
                    const dlKeys = Object.keys(this.analytics.downloadTypes);
                    const dlVals = Object.values(this.analytics.downloadTypes);
                    if (document.getElementById('downloadTypesChart') && dlKeys.length > 0) {
                        this.charts.downloadTypes = new Chart(document.getElementById('downloadTypesChart'), {
                            type: 'doughnut',
                            data: {
                                labels: dlKeys,
                                datasets: [{
                                    data: dlVals,
                                    backgroundColor: getColors(dlKeys.length),
                                    borderWidth: 0
                                }]
                            },
                            options: { responsive: true, maintainAspectRatio: false }
                        });
                    }

                    // Depth Chart
                    const depthKeys = Object.keys(this.analytics.depthDistribution).sort((a,b) => parseInt(a)-parseInt(b));
                    const depthVals = depthKeys.map(k => this.analytics.depthDistribution[k]);
                    if (document.getElementById('depthChart')) {
                        this.charts.depthChart = new Chart(document.getElementById('depthChart'), {
                            type: 'bar',
                            data: {
                                labels: depthKeys.map(k => `Depth ${k}`),
                                datasets: [{
                                    label: 'Pages',
                                    data: depthVals,
                                    backgroundColor: '#8b5cf6',
                                    borderRadius: 4
                                }]
                            },
                            options: { 
                                indexAxis: 'y', 
                                responsive: true, 
                                maintainAspectRatio: false,
                                plugins: { legend: {display: false} }
                            }
                        });
                    }
                }
            }
        }).mount('#app')
    </script>
</body>
</html>
"""
with open('templates/index.html', 'w') as f:
    f.write(html)
