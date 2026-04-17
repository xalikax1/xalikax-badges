import os
import requests
import time
import json

# Configuration
OUTPUT_DIR = "public"
SERIES_DIR = os.path.join(OUTPUT_DIR, "series") 
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading config.json: {e}")
    return {}

def fetch_info(series_folder_name, session, config):
    series_conf = config.get(series_folder_name, {})
    if "title" in series_conf and "cover" in series_conf:
        return series_conf["title"], series_conf["cover"]

    search_term = series_folder_name.replace('_', ' ').replace('-', ' ')
    media_type = series_conf.get("type", "ANIME")
    
    query = '''
    query ($search: String, $type: MediaType) {
      Media (search: $search, type: $type) {
        title { english romaji }
        coverImage { large }
      }
    }
    '''
    url = 'https://graphql.anilist.co'
    
    attempts = 0
    while attempts < 3:
        try:
            response = session.post(url, json={'query': query, 'variables': {'search': search_term, 'type': media_type}}, timeout=15)
            if response.status_code == 429:
                wait_time = max(int(response.headers.get('Retry-After', 60)), 5)
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            data = response.json()
            if data and data.get('data'):
                media = data['data'].get('Media')
                if media:
                    t = (media.get('title') or {})
                    title = t.get('english') or t.get('romaji') or search_term
                    c = (media.get('coverImage') or {})
                    cover = c.get('large') or "https://via.placeholder.com/200x300?text=No+Cover"
                    time.sleep(0.8) 
                    return title, cover
            break
        except Exception:
            attempts += 1
            time.sleep(2)
            
    return search_term, "https://via.placeholder.com/200x300?text=No+Cover"

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    if not os.path.exists(SERIES_DIR):
        os.makedirs(SERIES_DIR)
        print(f"Created {SERIES_DIR}. Please move your series folders there!")
        return

    config = load_config()
    series_data = []
    session = requests.Session()
    valid_dirs =[d for d in os.listdir(SERIES_DIR) if os.path.isdir(os.path.join(SERIES_DIR, d)) and not d.startswith('.')]

    print(f"Found {len(valid_dirs)} folders to process...")
    for index, series in enumerate(valid_dirs, 1):
        print(f"[{index}/{len(valid_dirs)}] Processing: {series}")
        title, cover_url = fetch_info(series, session, config)
        
        current_series_path = os.path.join(SERIES_DIR, series)
        images = sorted([img for img in os.listdir(current_series_path) if img.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])
        
        grouped_images = {}
        for img in images:
            base, ext = os.path.splitext(img)
            ext = ext.lower()
            if base not in grouped_images:
                grouped_images[base] = {'static': None, 'animated': None}
            
            if ext in['.gif', '.webp']:
                grouped_images[base]['animated'] = img
            else:
                grouped_images[base]['static'] = img
                
        final_images =[]
        for base, versions in grouped_images.items():
            static = versions['static']
            animated = versions['animated']
            
            if static and not animated:
                final_images.append({'base': base, 'display': static, 'has_animated': False, 'animated': None})
            elif animated and not static:
                final_images.append({'base': base, 'display': animated, 'has_animated': False, 'animated': None})
            elif static and animated:
                final_images.append({'base': base, 'display': static, 'has_animated': True, 'animated': animated})

        final_images.sort(key=lambda x: x['base'].lower())
        series_data.append({'id': series, 'title': title, 'cover': cover_url, 'images': final_images})

    series_data.sort(key=lambda x: str(x['title']).lower())

    index_html_path = os.path.join(OUTPUT_DIR, "index.html")
    json_payload = json.dumps(series_data)
    
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>croixph's badges</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
    <style>
        :root {{ --bg: #121212; --card-bg: #1e1e1e; --accent: #007bff; --text: #e0e0e0; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 0; }}
        
        .header-container {{ padding: 60px 20px 30px 20px; background-color: #1a1a1a; border-bottom: 2px solid #333; text-align: center; }}
        h1 {{ font-size: 2.8em; margin: 0 0 10px 0; letter-spacing: -1px; }}
        
        .tabs {{ display: flex; justify-content: center; gap: 20px; margin-top: 25px; }}
        .tab-btn {{ background: none; border: none; color: #888; font-size: 1.1em; font-weight: 600; cursor: pointer; padding: 10px 20px; transition: 0.3s; border-bottom: 3px solid transparent; }}
        .tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

        #searchBar {{ width: 85%; max-width: 500px; padding: 14px 24px; margin-top: 25px; border-radius: 30px; border: 1px solid #444; background: #222; color: white; font-size: 16px; outline: none; transition: 0.3s; }}
        #searchBar:focus {{ border-color: var(--accent); box-shadow: 0 0 0 4px rgba(0,123,255,0.2); }}

        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 30px; max-width: 1300px; margin: 40px auto; padding: 0 20px; }}
        
        .img-loading-bg {{
            background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%);
            background-size: 200% 100%;
            animation: skeletonLoading 1.5s infinite linear;
        }}
        @keyframes skeletonLoading {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}

        img {{ opacity: 0; transition: opacity 0.6s ease-in-out; }}
        img.loaded {{ opacity: 1; }}

        .card {{ background: var(--card-bg); border-radius: 15px; overflow: hidden; text-decoration: none; color: inherit; transition: 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94); display: flex; flex-direction: column; cursor: pointer; border: 1px solid #2a2a2a; }}
        .card:hover {{ transform: translateY(-8px); border-color: #444; box-shadow: 0 12px 24px rgba(0,0,0,0.5); }}
        
        .card-img-container {{ width: 100%; height: 320px; border-bottom: 1px solid #2a2a2a; }}
        .card-img-container img {{ width: 100%; height: 100%; object-fit: cover; }}
        
        .card .title {{ padding: 18px; font-weight: 600; font-size: 1.05em; background: #252525; flex-grow: 1; display: flex; align-items: center; justify-content: center; text-align: center; }}
        
        .badge-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; max-width: 1300px; margin: 0 auto; padding: 40px 20px; }}
        
        .badge-container {{
            position: relative;
            width: 100%;
            min-height: 180px;
            border-radius: 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}
        .badge-container img {{ width: 100%; border-radius: 10px; transition: opacity 0.6s ease-in-out, transform 0.2s; }}
        .badge-container:hover img {{ transform: scale(1.03); }}

        .animated-badge {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: var(--accent);
            color: white;
            font-size: 11px;
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
            pointer-events: none;
            z-index: 2;
        }}
        
        .back-btn {{ position: fixed; top: 25px; left: 25px; width: 45px; height: 45px; background: rgba(50,50,50,0.8); backdrop-filter: blur(5px); border-radius: 50%; display: flex; align-items: center; justify-content: center; z-index: 100; cursor: pointer; border: 1px solid #444; color: white; transition: 0.2s; }}
        .back-btn:hover {{ background: var(--accent); border-color: var(--accent); }}

        .modal {{ position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.92); display: flex; align-items: center; justify-content: center; backdrop-filter: blur(8px); }}
        
        .modal-content {{ position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; max-width: 90%; max-height: 90%; }}
        .modal-content img {{ max-width: 100%; max-height: 75vh; border-radius: 12px; box-shadow: 0 0 50px rgba(0,0,0,0.8); opacity: 1; }}
        
        .toggle-btn {{ margin-top: 20px; padding: 10px 24px; background: var(--accent); color: white; border: none; border-radius: 25px; cursor: pointer; font-size: 15px; font-weight: bold; transition: 0.2s; box-shadow: 0 4px 10px rgba(0,0,0,0.4); }}
        .toggle-btn:hover {{ background: #0056b3; transform: scale(1.05); }}

        [v-cloak] {{ display: none; }}
    </style>
</head>
<body>
    <div id="app" v-cloak>
        <div v-if="!activeId">
            <div class="header-container">
                <h1>croixph's badges</h1>
                
                <div class="tabs">
                    <button class="tab-btn" :class="{{ active: currentTab === 'categories' }}" @click="currentTab = 'categories'">Categories</button>
                    <button class="tab-btn" :class="{{ active: currentTab === 'characters' }}" @click="currentTab = 'characters'">Characters</button>
                </div>

                <input v-if="currentTab === 'categories'" type="text" v-model="search" id="searchBar" placeholder="Search category...">
                
                <h2 v-if="currentTab === 'categories'" style="font-size: 0.8em; color: rgb(160, 160, 160); font-weight: 400; margin-top: 20px;">
                    Category names are based on the AniList ENGLISH title.<br>
                    Exceptions include collection series (e.g. Fate, Monogatari) and anything not on AniList.
                </h2>
                <h2 v-else style="font-size: 0.8em; color: rgb(160, 160, 160); font-weight: 400; margin-top: 20px;">
                    Images with a GIF tag have animated versions.
                </h2>
            </div>

            <div v-if="currentTab === 'categories'" class="grid">
                <a v-for="s in filteredSeries" :key="s.id" :href="'#' + encodeURIComponent(s.id)" class="card">
                    <div class="card-img-container img-loading-bg">
                        <img :src="s.cover" :alt="s.title" loading="lazy" @load="onImgLoad" decoding="async">
                    </div>
                    <div class="title">{{{{ s.title }}}}</div>
                </a>
            </div>

            <div v-else class="badge-grid">
                <div v-for="img in allImages" 
                     :key="img.seriesId + img.base" 
                     class="badge-container img-loading-bg"
                     @click="openModal(img, img.seriesId)">
                    <img :src="'series/' + img.seriesId + '/' + img.display" 
                         loading="lazy"
                         @load="onImgLoad"
                         decoding="async">
                    <div v-if="img.has_animated" class="animated-badge">GIF</div>
                </div>
            </div>
        </div>

        <div v-else>
            <button class="back-btn" @click="goHome">
                <svg fill="currentColor" viewBox="0 0 24 24" width="24" height="24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"></path></svg>
            </button>
            <div class="header-container">
                <h2 style="margin:0; font-size: 2em;">{{{{ currentSeries?.title || 'Loading...' }}}}</h2>
                <p style="margin-top:10px; color:#888;">{{{{ currentSeries?.images.length }}}} badges available<br><span style="font-size:0.8em;">Images with a GIF tag have animated versions</span></p>
            </div>
            <div class="badge-grid" v-if="currentSeries">
                <div v-for="img in currentSeries.images" 
                     :key="img.base" 
                     class="badge-container img-loading-bg"
                     @click="openModal(img, currentSeries.id)">
                    <img :src="'series/' + currentSeries.id + '/' + img.display" 
                         loading="lazy"
                         @load="onImgLoad"
                         decoding="async">
                    <div v-if="img.has_animated" class="animated-badge">GIF</div>
                </div>
            </div>
        </div>

        <div v-if="currentModalImg" class="modal" @click="closeModal">
            <div class="modal-content" @click.stop>
                <img v-show="!showAnimated" 
                     :src="'series/' + modalSeriesId + '/' + currentModalImg.display" 
                     decoding="async">
                     
                <img v-if="currentModalImg.has_animated" 
                     v-show="showAnimated" 
                     :src="'series/' + modalSeriesId + '/' + currentModalImg.animated" 
                     decoding="async">
                     
                <button v-if="currentModalImg.has_animated" class="toggle-btn" @click="toggleAnimated">
                    {{{{ showAnimated ? 'View Static PNG' : 'View Animated GIF' }}}}
                </button>
            </div>
        </div>
    </div>

    <script>
        const {{ createApp, ref, computed, onMounted, nextTick }} = Vue;
        const seriesData = {json_payload};

        createApp({{
            setup() {{
                const search = ref('');
                const activeId = ref('');
                const currentTab = ref('categories');
                const currentModalImg = ref(null);
                const modalSeriesId = ref('');
                const showAnimated = ref(false);
                const lastScrollPos = ref(0);

                const getHash = () => decodeURIComponent(window.location.hash.replace('#', ''));

                const filteredSeries = computed(() => 
                    seriesData.filter(s => s.title.toLowerCase().includes(search.value.toLowerCase()))
                );

                const currentSeries = computed(() => 
                    seriesData.find(s => s.id === activeId.value)
                );

                const allImages = computed(() => {{
                    let flattened = [];
                    seriesData.forEach(s => {{
                        s.images.forEach(img => {{
                            flattened.push({{ ...img, seriesId: s.id }});
                        }});
                    }});
                    return flattened;
                }});

                const onImgLoad = (e) => {{
                    e.target.classList.add('loaded');
                    const parent = e.target.closest('.img-loading-bg');
                    if (parent) {{
                        parent.classList.remove('img-loading-bg');
                        parent.style.background = 'transparent';
                    }}
                }};

                const goHome = () => {{ window.location.hash = ''; }};

                const openModal = (img, sId) => {{
                    currentModalImg.value = img;
                    modalSeriesId.value = sId;
                    showAnimated.value = false;
                }};

                const closeModal = () => {{
                    currentModalImg.value = null;
                }};

                const toggleAnimated = () => {{
                    showAnimated.value = !showAnimated.value;
                }};

                const updateRoute = () => {{
                    const newId = getHash();
                    if (activeId.value && !newId) {{
                        activeId.value = '';
                        nextTick(() => window.scrollTo(0, lastScrollPos.value));
                    }} else if (newId) {{
                        if (!activeId.value) lastScrollPos.value = window.scrollY;
                        activeId.value = newId;
                        window.scrollTo(0, 0);
                    }} else {{
                        activeId.value = '';
                    }}
                }};

                onMounted(() => {{
                    window.addEventListener('hashchange', updateRoute);
                    updateRoute();
                }});

                return {{ 
                    search, activeId, currentTab, filteredSeries, currentSeries, allImages,
                    goHome, onImgLoad, currentModalImg, modalSeriesId, showAnimated, 
                    openModal, closeModal, toggleAnimated 
                }};
            }}
        }}).mount('#app');
    </script>
</body>
</html>""")
    
    print(f"\nSuccess!")

if __name__ == "__main__":
    main()
