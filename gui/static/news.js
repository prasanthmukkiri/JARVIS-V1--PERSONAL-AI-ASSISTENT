// JARVIS V1 — Global News Intelligence Dashboard

const CONFIG = {
  refreshInterval: parseInt(localStorage.getItem('refreshInterval') || '300000', 10),
  showMarkers: JSON.parse(localStorage.getItem('showMarkers') ?? 'true'),
  showStats: JSON.parse(localStorage.getItem('showStats') ?? 'true'),
};

const CAT_COLOR = {
  south: '#00e5ff', north: '#ff9100', intl: '#b0bec5', tech: '#69ff47', conflicts: '#ff1744',
};
const CAT_LABEL = {
  south: 'South India', north: 'North India', intl: 'International',
  tech: 'Tech & AI', conflicts: 'World Events',
};

// Named geo-coordinates for map markers
const GEO = {
  'Telangana': [17.12, 79.21], 'Hyderabad': [17.39, 78.49],
  'Andhra Pradesh': [15.91, 79.74], 'Visakhapatnam': [17.69, 83.22],
  'Tamil Nadu': [11.13, 78.66], 'Chennai': [13.08, 80.27],
  'Karnataka': [15.32, 75.71], 'Bangalore': [12.97, 77.59], 'Bengaluru': [12.97, 77.59],
  'Kerala': [10.85, 76.27], 'Kochi': [9.93, 76.27],
  'Delhi': [28.61, 77.21], 'Mumbai': [19.08, 72.88],
  'Punjab': [31.15, 75.34], 'Haryana': [29.06, 76.09],
  'Rajasthan': [27.02, 74.22], 'Jaipur': [26.91, 75.79],
  'Uttar Pradesh': [26.85, 80.95], 'Lucknow': [26.85, 80.95],
  'Kashmir': [34.08, 74.80], 'Jammu': [32.73, 74.87],
  'India': [20.59, 78.96],
  'Russia': [61.52, 105.32], 'Ukraine': [48.38, 31.17],
  'USA': [37.09, -95.71], 'Washington': [38.91, -77.04],
  'China': [35.86, 104.20], 'Beijing': [39.91, 116.39],
  'Pakistan': [30.38, 69.35], 'Israel': [31.05, 34.85], 'Gaza': [31.35, 34.31],
  'UK': [55.38, -3.44], 'London': [51.51, -0.13],
  'Europe': [54.53, 15.26], 'Germany': [51.17, 10.45],
  'Japan': [36.20, 138.25], 'Saudi Arabia': [23.89, 45.08],
  'Iran': [32.43, 53.69], 'France': [46.23, 2.21],
  'Sudan': [12.86, 30.22], 'Myanmar': [21.92, 95.96],
};

const COUNTRY_ALIASES = {
  'United States of America': ['United States', 'USA', 'U.S.', 'US', 'America', 'U.S.A.'],
  'United Kingdom': ['UK', 'U.K.', 'Britain', 'Great Britain'],
  'United Arab Emirates': ['UAE', 'U.A.E.', 'Emirates'],
  'Democratic Republic of the Congo': ['DR Congo', 'Congo-Kinshasa'],
  'Republic of the Congo': ['Congo-Brazzaville'],
  'Russian Federation': ['Russia'],
  'Czech Republic': ['Czechia'],
  'Cote d\'Ivoire': ['Ivory Coast'],
  'Myanmar': ['Burma'],
};

const countryCenters = new Map();

// State
let allArticles = [];
let allVideos = [];
let videosByRegion = {};
let featuredArticles = [];
let featuredIndex = 0;
let featuredTimer = null;
let refreshTimer = null;
let mapState = null;
let activeFilter = 'all';
let searchQuery = '';
let countryLabelLayer = null;
const LABEL_MIN_ZOOM = 5; // show country name labels only at or above this zoom

// ===== UTILITIES =====

function esc(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeRegExp(s) {
  return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function textHasTerm(text, term) {
  if (!text || !term) return false;
  return new RegExp(`\\b${escapeRegExp(term)}\\b`, 'i').test(text);
}

function textMatchesAny(text, terms) {
  return (terms || []).some((term) => textHasTerm(text, term));
}

function normalizeEnglishLabels() {
  const categoryLabels = {
    all: 'All',
    south: 'South India',
    north: 'North India',
    intl: 'International',
    tech: 'Tech & AI',
    conflicts: 'World Events',
  };

  document.querySelectorAll('.filter-pill[data-cat]').forEach((btn) => {
    const cat = btn.getAttribute('data-cat');
    if (cat && categoryLabels[cat]) btn.textContent = categoryLabels[cat];
  });

  document.querySelectorAll('.row-section').forEach((section) => {
    const title = section.querySelector('.row-title');
    if (!title) return;
    if (section.dataset.cat && categoryLabels[section.dataset.cat]) {
      title.textContent = categoryLabels[section.dataset.cat];
    }
  });

  const settingsTitle = document.querySelector('.settings-header h3');
  if (settingsTitle) settingsTitle.textContent = 'SETTINGS';

  const feedTitle = document.querySelector('.hud-left');
  if (feedTitle) feedTitle.textContent = 'Global Intelligence Feed';
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(val);
}

function formatAge(pubDate) {
  if (!pubDate) return '';
  try {
    const diff = Math.floor((Date.now() - new Date(pubDate)) / 60000);
    if (diff < 1) return 'Just now';
    if (diff < 60) return `${diff}m ago`;
    if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
    return new Date(pubDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  } catch { return ''; }
}

function hashString(text) {
  let hash = 0;
  const value = String(text || '');
  for (let i = 0; i < value.length; i += 1) {
    hash = ((hash << 5) - hash) + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function getFallbackCoords(article) {
  const seed = `${article.title || ''}|${article.source || ''}|${article.category || ''}`;

  // Try inferring a country from well-known source strings (deterministic)
  const s = (article.source || '').toLowerCase();
  const SOURCE_REGION_MAP = {
    'ndtv': 'India', 'times of india': 'India', 'the economic times': 'India', 'msn': 'India',
    'reuters': null, 'npr': 'United States of America', 'bbc': 'United Kingdom', 'al jazeera': 'United Arab Emirates',
    'dw.com': 'Germany', 'cnn': 'United States of America', 'fox': 'United States of America', 'msnbc': 'United States of America'
  };

  for (const k in SOURCE_REGION_MAP) {
    if (k && s.includes(k)) {
      const country = SOURCE_REGION_MAP[k];
      if (country && countryCenters.has(country)) {
        const center = countryCenters.get(country);
        const spreadLat = ((hashString(seed) % 1000) / 1000 - 0.5) * 0.9;
        const spreadLng = ((hashString(`${seed}:lng`) % 1000) / 1000 - 0.5) * 1.1;
        return [center[0] + spreadLat, center[1] + spreadLng];
      }
    }
  }

  // If we have country centers loaded, pick one deterministically from the list
  const countries = Array.from(countryCenters.keys());
  if (countries.length) {
    const idx = hashString(seed) % countries.length;
    const center = countryCenters.get(countries[idx]);
    const spreadLat = ((hashString(seed) % 1800) / 1800 - 0.5) * 1.2;
    const spreadLng = ((hashString(`${seed}:lng`) % 2400) / 2400 - 0.5) * 1.8;
    return [center[0] + spreadLat, center[1] + spreadLng];
  }

  // Fallback by category buckets (coarse global defaults)
  const bucket = article.category === 'south' ? [13.25, 80.3]
    : article.category === 'north' ? [28.4, 77.2]
    : article.category === 'tech' ? [37.4, -122.1]
    : article.category === 'conflicts' ? [31.5, 35.5]
    : [20.5, 0];
  const spreadLat = ((hashString(seed) % 1800) / 1800 - 0.5) * 6;
  const spreadLng = ((hashString(`${seed}:lng`) % 2400) / 2400 - 0.5) * 8;
  return [bucket[0] + spreadLat, bucket[1] + spreadLng];
}

function findCoords(article) {
  const text = `${article.location || ''} ${article.country || ''} ${article.region || ''} ${article.title || ''} ${article.description || ''} ${article.source || ''}`;

  if (article.lat != null && article.lng != null && isFinite(article.lat) && isFinite(article.lng)) {
    return [Number(article.lat), Number(article.lng)];
  }

  for (const k in GEO) {
    if (textHasTerm(text, k)) return GEO[k];
  }

  for (const [countryName, center] of countryCenters.entries()) {
    const aliases = COUNTRY_ALIASES[countryName] || [];
    if (textHasTerm(text, countryName) || textMatchesAny(text, aliases)) {
      return center;
    }
  }

  return getFallbackCoords(article);
}

// ===== MAP =====

function initMap() {
  const mapEl = document.getElementById('map');
  if (!mapEl || mapState) return;

  // If Leaflet is not loaded, dynamically load CSS+JS and retry initialization.
  if (typeof window.L === 'undefined') {
    if (window._leafletLoading) return; // already requested
    window._leafletLoading = true;

    // load CSS
    const lcss = document.createElement('link');
    lcss.rel = 'stylesheet';
    lcss.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(lcss);

    // load JS
    const ljs = document.createElement('script');
    ljs.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    ljs.async = true;
    ljs.onload = () => {
      try { initMap(); } catch (e) { console.error('Leaflet init retry failed', e); }
    };
    ljs.onerror = () => { console.error('Failed to load Leaflet from CDN'); };
    document.body.appendChild(ljs);
    return;
  }

  // Create Leaflet map using OpenStreetMap raster tiles for street-level detail
  mapEl.innerHTML = '';
  const map = L.map('map', { zoomControl: false, attributionControl: false }).setView([20, 0], 2);
  // Provide high-resolution OpenStreetMap tiles (detectRetina) and keep Dark layer as an alternative
  const osmStandard = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
    detectRetina: true,
    tileSize: 512,
    zoomOffset: -1
  });

  const cartoDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', {
    maxZoom: 19,
    subdomains: 'abcd',
    attribution: '&copy; OpenStreetMap contributors &copy; CartoDB',
    detectRetina: true,
    tileSize: 512,
    zoomOffset: -1
  });

  // Add OSM as default high-res base and expose a layer switcher
  osmStandard.addTo(map);
  const baseLayers = { 'OSM Standard (High-Res)': osmStandard, 'Carto Dark': cartoDark };
  L.control.layers(baseLayers, null, { position: 'topright', collapsed: true }).addTo(map);

  const markerLayer = L.layerGroup().addTo(map);

  countryLabelLayer = L.layerGroup().addTo(map);
  loadCountryLabels(map, countryLabelLayer);
  map.on('zoomend moveend', () => refreshCountryLabelVisibility(map));

  mapState = { type: 'leaflet', map, markerLayer };

  setupMapControls();
  setupMapUIControls(map);
}

async function loadCountryLabels(map, layer) {
  try {
    if (window._countryLabelsLoading) return;
    window._countryLabelsLoading = true;
    // Prefer a local copy for reliability; fallback to GitHub raw if missing
    const localUrl = '/static/data/countries.geo.json';
    let response = await fetch(localUrl).catch(() => null);
    if (!response || !response.ok) {
      try {
        response = await fetch('https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json');
      } catch (e) { response = null; }
    }
    if (!response || !response.ok) throw new Error(`Country labels fetch failed`);
    const geojson = await response.json();
    const seen = new Set();
    (geojson.features || []).forEach((feature) => {
      const name = feature?.properties?.name;
      if (!name || seen.has(name)) return;
      seen.add(name);

      const shape = L.geoJSON(feature);
      const center = shape.getBounds().getCenter();
      if (!center || !isFinite(center.lat) || !isFinite(center.lng)) return;

      countryCenters.set(name, [center.lat, center.lng]);

      const label = L.marker(center, {
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: 'country-label-icon',
          html: `<span class="country-label-text">${esc(name)}</span>`,
          iconSize: [1, 1],
          iconAnchor: [0, 0]
        })
      });
      label.countryName = name;
      label.addTo(layer);
    });
    refreshCountryLabelVisibility(map);
    if (allArticles.length) updateMapMarkers(allArticles);
  } catch (error) {
    console.warn('Country label overlay failed', error);
  }
}

function refreshCountryLabelVisibility(map) {
  if (!countryLabelLayer || !map) return;
  const zoom = map.getZoom();
  const showLabels = zoom >= LABEL_MIN_ZOOM;
  countryLabelLayer.eachLayer((marker) => {
    const el = marker.getElement && marker.getElement();
    if (!el) return;
    el.style.display = showLabels ? '' : 'none';
    el.style.opacity = zoom >= (LABEL_MIN_ZOOM + 1) ? '1' : '0.82';
  });
}

function setupMapUIControls(map) {
  try {
    // Scale control
    L.control.scale({ imperial: false, metric: true }).addTo(map);

    // Fullscreen toggle (simple CSS class toggle)
    const FullscreenControl = L.Control.extend({
      options: { position: 'topright' },
      onAdd: function () {
        const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-fullscreen');
        container.title = 'Toggle map fullscreen';
        container.innerHTML = '<a href="#" style="display:flex;align-items:center;justify-content:center;padding:6px">⤢</a>';
        L.DomEvent.on(container, 'click', L.DomEvent.stopPropagation)
                 .on(container, 'click', L.DomEvent.preventDefault)
                 .on(container, 'click', () => {
                   const mapEl = map.getContainer();
                   mapEl.classList.toggle('map-fullscreen');
                   map.invalidateSize();
                 });
        return container;
      }
    });
    map.addControl(new FullscreenControl());

    // Locate control (simple): center on user's geolocation
    const LocateControl = L.Control.extend({
      options: { position: 'topright' },
      onAdd: function () {
        const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-locate');
        container.title = 'Locate me';
        container.innerHTML = '<a href="#" style="display:flex;align-items:center;justify-content:center;padding:6px">⌖</a>';
        L.DomEvent.on(container, 'click', L.DomEvent.stopPropagation)
                 .on(container, 'click', L.DomEvent.preventDefault)
                 .on(container, 'click', () => {
                   if (!navigator.geolocation) return alert('Geolocation not available');
                   navigator.geolocation.getCurrentPosition((pos) => {
                     const lat = pos.coords.latitude, lng = pos.coords.longitude;
                     const p = L.circleMarker([lat, lng], { radius: 8, color: '#fff', fillColor: '#2b9af3', fillOpacity: 0.9 }).addTo(map);
                     map.flyTo([lat, lng], 12, { duration: 0.7 });
                     setTimeout(() => map.removeLayer(p), 6000);
                   }, (err) => console.warn('Locate error', err));
                 });
        return container;
      }
    });
    map.addControl(new LocateControl());
  } catch (e) {
    console.warn('Map UI controls failed', e);
  }
}

function setupMapControls() {
  const views = {
    'zoom-india': { lat: 22, lng: 79, z: 5 },
    'zoom-south': { lat: 13, lng: 78, z: 7 },
    'zoom-north': { lat: 28, lng: 78, z: 6 },
    'zoom-world': { lat: 20, lng: 0, z: 2 },
  };
  Object.entries(views).forEach(([id, v]) => {
    document.getElementById(id)?.addEventListener('click', () => {
      if (!mapState || mapState.type !== 'leaflet') return;
      mapState.map.flyTo([v.lat, v.lng], v.z, { duration: 0.8 });
    });
  });
}

function updateMapMarkers(articles) {
  if (!mapState || mapState.type !== 'leaflet') return;
  const layer = mapState.markerLayer;
  layer.clearLayers();
  if (!CONFIG.showMarkers) return;

  articles.forEach((article) => {
    const coords = findCoords(article);
    if (!coords) return;
    const lat = coords[0], lng = coords[1];
    if (lat == null || lng == null) return;

    const color = CAT_COLOR[article.category] || CAT_COLOR.intl;
    const colorSafe = color.replace(/"/g, '\\"');

    // Use a small fixed-size dot icon that does not scale with zoom
    const html = `<div class="news-marker-wrap" style="width:8px;height:8px;display:inline-block"><span class="news-dot" style="--mcolor:${colorSafe}"></span></div>`;
    const ico = L.divIcon({ className: 'news-marker-wrap', html, iconSize: [8, 8], iconAnchor: [4, 4] });
    const marker = L.marker([lat, lng], { icon: ico, riseOnHover: true });
    marker.article = article;
    const svUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}`;
    const thumb = article.image || article.thumbnail || (article.media && article.media.thumbnail) || (article.media && article.media.image) || '';
    const snippet = (article.description || '').substring(0, 160).replace(/"/g, '&quot;');
    const thumbHtml = thumb ? `<img src="${thumb}" class="map-popup-thumb" alt="thumb">` : '';
    const popupHtml = `<div style="max-width:360px;display:flex;gap:10px"><div class=\"map-popup-body\">${thumbHtml}<div style=\"flex:1\"><div style=\"font-weight:700;color:#e8f6ff\">${esc(article.title||'')}</div><div style=\"font-size:12px;color:#90a4ae;margin-top:6px\">${esc(article.source||'')}</div><div style=\"margin-top:6px;color:#bfcfd6;font-size:13px\">${esc(snippet)}</div><div style=\"margin-top:8px;display:flex;gap:8px\"><a href=\"${article.link||'#'}\" target=\"_blank\" rel=\"noopener\" class=\"map-popup-btn\">Open Story</a><a href=\"${svUrl}\" target=\"_blank\" rel=\"noopener\" class=\"map-popup-btn\">Street View</a></div></div></div></div>`;
    marker.bindTooltip(`<div style=\"max-width:260px;color:#e8f6ff;font-weight:700\">${esc(article.title||'')}</div>`, { direction: 'top', offset: [0, -10], opacity: 0.95 });
    marker.bindPopup(popupHtml, { maxWidth: 360 });
    marker.on('dblclick', () => openModal(article));
    layer.addLayer(marker);
  });
}

function showTooltip() { /* handled by Leaflet tooltips */ }
function hideTooltip() { /* handled by Leaflet tooltips */ }

function highlightCategory(cat) {
  if (!mapState || mapState.type !== 'leaflet') return;
  mapState.markerLayer.eachLayer((m) => {
    try {
      const art = m.article || {};
      const op = (art.category === cat) ? 1 : 0.15;
      m.setStyle && m.setStyle({ fillOpacity: op, opacity: op });
    } catch (e) {}
  });
}

function clearHighlight() {
  if (!mapState || mapState.type !== 'leaflet') return;
  mapState.markerLayer.eachLayer((m) => { try { m.setStyle && m.setStyle({ fillOpacity: 1, opacity: 1 }); } catch (e) {} });
}

// ===== FEATURED ROTATOR =====

function updateFeatured() {
  const el = document.getElementById('featured-article');
  if (!el || featuredArticles.length === 0) return;

  const art = featuredArticles[featuredIndex % featuredArticles.length];
  const color = CAT_COLOR[art.category] || CAT_COLOR.intl;
  const label = CAT_LABEL[art.category] || 'News';
  const maxDots = Math.min(featuredArticles.length, 5);

  el.classList.remove('loading');
  el.innerHTML = `
    <div class="featured-shine"></div>
    <div class="feat-cat-badge" style="color:${color};border-color:${color}">${esc(label)}</div>
    <div class="featured-content">
      <h1 class="feat-title">${esc((art.title || '').substring(0, 160))}</h1>
      <p class="feat-desc">${esc((art.description || '').substring(0, 280))}</p>
      <div class="featured-meta">
        <span class="feat-src">${esc(art.source || 'News')}</span>
        <span> · </span>
        <span class="feat-live">● LIVE</span>
        <span class="feat-src">${formatAge(art.pubDate)}</span>
      </div>
      <button class="feat-read-btn" style="border-color:${color};color:${color}" id="feat-read">View Story →</button>
    </div>
    <div class="featured-nav">
      <button class="feat-nav-btn" id="feat-prev">‹</button>
      <div class="feat-dots">
        ${Array.from({length: maxDots}, (_, i) => `<div class="feat-dot-item${i === featuredIndex % maxDots ? ' active' : ''}" data-i="${i}"></div>`).join('')}
      </div>
      <button class="feat-nav-btn" id="feat-next">›</button>
    </div>
  `;

  document.getElementById('feat-read')?.addEventListener('click', () => openModal(art));
  document.getElementById('feat-prev')?.addEventListener('click', () => { featuredIndex = (featuredIndex - 1 + featuredArticles.length) % featuredArticles.length; updateFeatured(); resetFeaturedTimer(); });
  document.getElementById('feat-next')?.addEventListener('click', () => { featuredIndex = (featuredIndex + 1) % featuredArticles.length; updateFeatured(); resetFeaturedTimer(); });
  document.querySelectorAll('.feat-dot-item').forEach((d) => d.addEventListener('click', () => { featuredIndex = parseInt(d.dataset.i, 10); updateFeatured(); resetFeaturedTimer(); }));
}

function resetFeaturedTimer() {
  if (featuredTimer) clearInterval(featuredTimer);
  featuredTimer = setInterval(() => {
    featuredIndex = (featuredIndex + 1) % Math.min(featuredArticles.length, 5);
    updateFeatured();
  }, 8000);
}

// ===== BREAKING BANNER =====

function showBreaking(article) {
  const banner = document.getElementById('breaking-banner');
  const text = document.getElementById('breaking-text');
  if (!banner || !text || !article) return;
  text.textContent = article.title || '';
  banner.classList.remove('hidden');
}

// ===== NEWS ROWS =====

function makeCard(article) {
  const color = CAT_COLOR[article.category] || CAT_COLOR.intl;
  const initial = (article.source || 'N').charAt(0).toUpperCase();
  const card = document.createElement('article');
  card.className = `card cat-${article.category || 'intl'}`;
  card.setAttribute('tabindex', '0');
  card.setAttribute('role', 'button');
  card.innerHTML = `
    <div class="card-accent-bar" style="background:${color}"></div>
    <div class="card-thumb" style="--thumb-color:${color}">
      <span class="source-initial">${esc(initial)}</span>
    </div>
    <div class="card-body">
      <h3 class="card-title">${esc(article.title || 'Untitled')}</h3>
      <div class="card-meta">
        <span class="card-src">${esc(article.source || '')}</span>
        <span class="card-time">${formatAge(article.pubDate)}</span>
      </div>
    </div>
  `;
  card.addEventListener('click', () => openModal(article));
  card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') openModal(article); });
  card.addEventListener('mouseenter', () => highlightCategory(article.category));
  card.addEventListener('mouseleave', clearHighlight);
  return card;
}

function renderNewsRows() {
  const rowMap = { south: 'row-south', north: 'row-north', intl: 'row-intl', tech: 'row-tech', conflicts: 'row-conflicts' };
  const counts = { south: 0, north: 0, intl: 0, tech: 0, conflicts: 0 };
  const query = searchQuery.toLowerCase();

  Object.values(rowMap).forEach((id) => { const el = document.getElementById(id); if (el) el.innerHTML = ''; });

  allArticles.forEach((article) => {
    if (query && !`${article.title} ${article.description} ${article.source}`.toLowerCase().includes(query)) return;
    const cat = article.category || 'intl';
    const rowEl = document.getElementById(rowMap[cat]);
    if (!rowEl) return;
    rowEl.appendChild(makeCard(article));
    counts[cat] = (counts[cat] || 0) + 1;
  });

  Object.keys(counts).forEach((k) => setEl(`count-${k}`, counts[k]));

  // Apply category filter visibility
  document.querySelectorAll('.row-section').forEach((sec) => {
    const cat = sec.dataset.cat;
    sec.style.display = (activeFilter === 'all' || activeFilter === cat) ? '' : 'none';
  });
}

// ===== MODAL =====

function openModal(article) {
  const modal = document.getElementById('article-modal');
  if (!modal) return;
  const color = CAT_COLOR[article.category] || CAT_COLOR.intl;
  const label = CAT_LABEL[article.category] || 'News';

  const catEl = document.getElementById('modal-cat');
  catEl.textContent = label;
  catEl.style.color = color;
  catEl.style.borderColor = color;

  document.getElementById('modal-title').textContent = article.title || 'Untitled';
  document.getElementById('modal-desc').textContent = article.description || 'No description available.';
  document.getElementById('modal-source').textContent = article.source || 'News';
  document.getElementById('modal-date').textContent = formatAge(article.pubDate);

  const link = document.getElementById('modal-link');
  link.href = article.link || '#';
  link.style.borderColor = color;
  link.style.color = color;
  link.style.background = `${color}14`;

  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('article-modal')?.classList.add('hidden');
  document.body.style.overflow = '';
}

function setupModal() {
  document.getElementById('modal-close')?.addEventListener('click', closeModal);
  document.getElementById('modal-backdrop')?.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
}

// ===== TICKER =====

function populateTicker() {
  const ticker = document.getElementById('map-ticker');
  if (!ticker || allArticles.length === 0) return;
  const text = allArticles.slice(0, 16).map((a) => esc(a.title || '')).join(' ◆ ');
  ticker.innerHTML = `<div class="ticker-inner"><span>${text} &nbsp;&nbsp;</span><span>${text}</span></div>`;
}

// ===== SEARCH & FILTER =====

function setupSearch() {
  const input = document.getElementById('search-input');
  const clear = document.getElementById('search-clear');
  input?.addEventListener('input', () => {
    searchQuery = input.value.trim();
    clear?.classList.toggle('hidden', !searchQuery);
    renderNewsRows();
  });
  clear?.addEventListener('click', () => {
    input.value = '';
    searchQuery = '';
    clear.classList.add('hidden');
    renderNewsRows();
  });
}

function setupCategoryFilter() {
  document.querySelectorAll('.filter-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      activeFilter = pill.dataset.cat || 'all';
      renderNewsRows();
      if (activeFilter !== 'all') {
        document.querySelector(`.row-section[data-cat="${activeFilter}"]`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

function setupScrollButtons() {
  document.querySelectorAll('.scroll-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const row = document.getElementById(btn.dataset.row);
      row?.scrollBy({ left: parseInt(btn.dataset.dir, 10) * 380, behavior: 'smooth' });
    });
  });
}

// ===== SETTINGS =====

function initSettings() {
  const toggle = document.getElementById('settings-toggle');
  const panel = document.getElementById('settings-panel');
  toggle?.addEventListener('click', () => panel?.classList.toggle('hidden'));
  document.getElementById('settings-close')?.addEventListener('click', () => panel?.classList.add('hidden'));

  const tm = document.getElementById('toggle-markers');
  if (tm) {
    tm.checked = CONFIG.showMarkers;
    tm.addEventListener('change', (e) => { CONFIG.showMarkers = e.target.checked; localStorage.setItem('showMarkers', JSON.stringify(CONFIG.showMarkers)); updateMapMarkers(allArticles); });
  }

  const ts = document.getElementById('toggle-stats');
  if (ts) {
    ts.checked = CONFIG.showStats;
    ts.addEventListener('change', (e) => {
      CONFIG.showStats = e.target.checked;
      localStorage.setItem('showStats', JSON.stringify(CONFIG.showStats));
      const card = document.getElementById('stats-card');
      if (card) card.style.display = CONFIG.showStats ? 'flex' : 'none';
    });
    const card = document.getElementById('stats-card');
    if (card && !CONFIG.showStats) card.style.display = 'none';
  }

  const ri = document.getElementById('refresh-interval');
  if (ri) {
    ri.value = String(CONFIG.refreshInterval);
    ri.addEventListener('change', (e) => { CONFIG.refreshInterval = parseInt(e.target.value, 10); localStorage.setItem('refreshInterval', String(CONFIG.refreshInterval)); scheduleRefresh(); });
  }
}

// ===== STATISTICS =====

function updateStatistics() {
  const cats = new Set(allArticles.map((a) => a.category).filter(Boolean));
  setEl('stat-total', allArticles.length);
  setEl('stat-regions', cats.size);
  setEl('stat-videos', allVideos.length);
  setEl('stat-updated', new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }));
  setEl('count-videos', allVideos.length);
  setEl('footer-time', new Date().toLocaleTimeString('en-IN', { hour12: false }));
}

// ===== TRENDING =====

function updateTrending() {
  const list = document.getElementById('trending-list');
  if (!list) return;
  const STOP = new Set(['about', 'after', 'their', 'while', 'which', 'today', 'india', 'says', 'from', 'with', 'over', 'into', 'will', 'amid', 'news', 'latest', 'breaking', 'report', 'hours', 'were', 'have', 'this', 'that', 'more', 'also', 'been']);
  const freq = {};
  allArticles.forEach((a) => {
    (a.title || '').toLowerCase().replace(/[^a-z\s]/g, '').split(/\s+/).forEach((w) => {
      if (w.length > 4 && !STOP.has(w)) freq[w] = (freq[w] || 0) + 1;
    });
  });
  const trending = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([w]) => w);
  list.innerHTML = trending.map((t) => `<button class="trending-tag" data-tag="${esc(t)}">#${esc(t)}</button>`).join('');
  list.querySelectorAll('.trending-tag').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tag = btn.dataset.tag;
      const inp = document.getElementById('search-input');
      if (inp) inp.value = tag;
      searchQuery = tag;
      document.getElementById('search-clear')?.classList.remove('hidden');
      renderNewsRows();
      document.querySelector('.rows-area')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

// ===== VIDEOS =====

function regionBadge(region) {
  const labels = { south_india: 'South India', india: 'India', international: 'World' };
  const colors = { south_india: '#00e5ff', india: '#ff9100', international: '#b0bec5' };
  const r = region || 'india';
  return `<span style="background:${colors[r]}22;color:${colors[r]};border:1px solid ${colors[r]}44;padding:2px 8px;border-radius:4px;font-size:0.72rem;font-family:'Orbitron',monospace;letter-spacing:0.06em">${labels[r] || r}</span>`;
}

function renderVideos(videos) {
  const grid = document.getElementById('news-videos');
  if (!grid) return;
  if (!videos || videos.length === 0) {
    grid.innerHTML = '<div class="video-loading"><p>No news videos available at this time</p></div>';
    return;
  }
  const regionOrder = ['south_india', 'india', 'international'];
  const picked = regionOrder.map((r) => (videosByRegion[r] || [])[0]).filter(Boolean);
  const display = picked.length > 0 ? picked : videos.slice(0, 3);
  grid.innerHTML = display.map((v) => `
    <div class="video-card">
      <div class="video-region-badge">${regionBadge(v.region)}</div>
      <div class="frame">
        <iframe src="${v.embed_url}" title="${esc(v.title || 'Video')}" frameborder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen loading="lazy"></iframe>
      </div>
      <div class="video-meta">
        <h3>${esc((v.title || '').substring(0, 80))}</h3>
        <p>${esc(v.channel || 'YouTube')}</p>
      </div>
    </div>
  `).join('');
}

// ===== LOAD & RENDER =====

async function loadAndRender() {
  try {
    const resp = await fetch('/api/news');
    const data = await resp.json();

    const tag = (arr, cat) => (arr || []).map((a) => ({ ...a, category: cat })).filter((a) => a.title);
    allArticles = [
      ...tag(data.south_india, 'south'),
      ...tag(data.north_india, 'north'),
      ...tag(data.international, 'intl'),
      ...tag(data.tech, 'tech'),
      ...tag(data.conflicts, 'conflicts'),
    ];

    // One featured article per category, best-effort
    featuredArticles = ['conflicts', 'tech', 'south', 'north', 'intl']
      .map((c) => allArticles.find((a) => a.category === c))
      .filter(Boolean);
    featuredIndex = 0;

    const breakingArt = allArticles.find((a) => a.category === 'conflicts') || allArticles[0];
    if (breakingArt) showBreaking(breakingArt);

    try {
      const vresp = await fetch('/api/news/videos');
      const vdata = await vresp.json();
      allVideos = vdata.videos || [];
      videosByRegion = vdata.videos_by_region || {};
    } catch {
      allVideos = [];
      videosByRegion = {};
    }

    updateMapMarkers(allArticles);
    updateStatistics();
    updateFeatured();
    resetFeaturedTimer();
    updateTrending();
    populateTicker();
    renderNewsRows();
    renderVideos(allVideos);

    document.getElementById('error-container').style.display = 'none';
  } catch (e) {
    const box = document.getElementById('error-container');
    const msg = document.getElementById('error-message');
    if (box && msg) { msg.textContent = `Failed to load news: ${e.message || e}`; box.style.display = 'flex'; }
  }
}

function updateClock() {
  setEl('live-clock', new Date().toLocaleTimeString('en-IN', { hour12: false }) + ' IST');
}

function scheduleRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(loadAndRender, CONFIG.refreshInterval);
}

function setupRefreshButton() {
  const btn = document.getElementById('refresh-videos');
  btn?.addEventListener('click', async () => {
    btn.style.transform = 'rotate(360deg)';
    btn.style.transition = 'transform 0.4s';
    try {
      const resp = await fetch('/api/news/videos');
      const data = await resp.json();
      allVideos = data.videos || [];
      videosByRegion = data.videos_by_region || {};
      renderVideos(allVideos);
      updateStatistics();
    } finally {
      setTimeout(() => { btn.style.transform = ''; btn.style.transition = ''; }, 500);
    }
  });
}

function setupBreakingClose() {
  document.getElementById('breaking-close')?.addEventListener('click', () => {
    document.getElementById('breaking-banner')?.classList.add('hidden');
  });
}

// ===== BOOT =====

function initializeApp() {
  normalizeEnglishLabels();
  initSettings();
  setupSearch();
  setupCategoryFilter();
  setupScrollButtons();
  setupModal();
  setupBreakingClose();
  try { initMap(); } catch (e) { console.error('Map init failed:', e); }
  loadAndRender();
  updateClock();
  setInterval(updateClock, 1000);
  scheduleRefresh();
  setupRefreshButton();
}

let booted = false;
function boot() {
  if (booted) return;
  booted = true;
  setTimeout(initializeApp, 40);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true });
} else {
  boot();
}
window.addEventListener('load', boot, { once: true });
