// Color mapping based on asset type
const typeColors = {
    'healthcare': '#ef4444',
    'health': '#ef4444',
    'education': '#3b82f6',
    'school': '#3b82f6',
    'university': '#3b82f6',
    'utility': '#f59e0b',
    'water': '#f59e0b',
    'power': '#f59e0b',
    'electricity': '#f59e0b',
    'transport': '#8b5cf6',
    'airport': '#8b5cf6',
    'rail': '#8b5cf6',
    'bus': '#8b5cf6',
    'government': '#06b6d4',
    'financial': '#10b981',
    'bank': '#10b981',
    'atm': '#10b981'
};

// Get matching color for asset type
function getAssetColor(type) {
    if (!type) return '#10b981';
    const normalized = type.toLowerCase();
    for (const key in typeColors) {
        if (normalized.includes(key)) {
            return typeColors[key];
        }
    }
    return '#10b981'; // Default Emerald color
}

// Get matching custom SVG Leaflet icon for asset type
function getAssetIcon(type, subType) {
    const color = getAssetColor(type);
    let svgContent = '';

    const normalizedType = type ? type.toLowerCase() : '';
    const normalizedSubType = subType ? subType.toLowerCase() : '';

    if (normalizedType.includes('health')) {
        // Cross sign
        svgContent = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19"></line>
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                `;
    } else if (normalizedType.includes('education') || normalizedType.includes('school')) {
        // Graduation cap / Book
        svgContent = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
                        <path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"></path>
                    </svg>
                `;
    } else if (normalizedType.includes('utility')) {
        // Lightning bolt
        svgContent = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                `;
    } else if (normalizedType.includes('transport')) {
        if (normalizedSubType.includes('airport')) {
            // Plane
            svgContent = `
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3.5C20.5 3 18.5 3.5 17 5L13.5 8.5L5.3 6.7L4.2 7.8L11.5 12L8.5 15L5.5 14L4.5 15L8 18.5L11.5 22L12.5 21L11.5 18L14.5 15l4.2 7.2l1.1-1z"></path>
                        </svg>
                    `;
        } else {
            // Bus
            svgContent = `
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="5.5" y="3" width="13" height="16" rx="2"></rect>
                            <path d="M19 14H5"></path>
                            <path d="M19 9H5"></path>
                            <path d="M9 16h6"></path>
                            <circle cx="8" cy="19" r="1"></circle>
                            <circle cx="16" cy="19" r="1"></circle>
                        </svg>
                    `;
        }
    } else if (normalizedType.includes('government')) {
        // Civic hall/Columns icon
        svgContent = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 22h16"></path>
                        <path d="M4 11h16"></path>
                        <path d="M6 11v11"></path>
                        <path d="M10 11v11"></path>
                        <path d="M14 11v11"></path>
                        <path d="M18 11v11"></path>
                        <path d="M12 2L2 7h20L12 2z"></path>
                    </svg>
                `;
    } else if (normalizedType.includes('financial') || normalizedType.includes('bank') || normalizedType.includes('atm')) {
        // Dollar sign icon
        svgContent = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M6 4v16"></path>
                        <path d="M6 4l12 16"></path>
                        <path d="M18 4v16"></path>
                        <path d="M4 10h16"></path>
                        <path d="M4 14h16"></path>
                    </svg>
                `;
    } else {
        // Circle marker (fallback)
        svgContent = `
                    <circle cx="12" cy="12" r="10" fill="currentColor"></circle>
                `;
    }

    return L.divIcon({
        html: `<div class="marker-pin" style="background-color: ${color};">${svgContent}</div>`,
        className: 'custom-asset-marker',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -14]
    });
}

// Initialize Leaflet map
const map = L.map('map', {
    zoomControl: false // Disable to relocate it to a better position
}).setView([9.0820, 8.6753], 6);

// Add Zoom Control to the top-right
L.control.zoom({ position: 'topright' }).addTo(map);

// Define Base Maps
const lightMap = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 20,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
});

const satelliteMap = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
    maxZoom: 20,
    attribution: '&copy; Google Maps'
});

// Set default basemap
lightMap.addTo(map);

// Base maps controller
const baseMaps = {
    "Light Map": lightMap,
    "Satellite View": satelliteMap
};

L.control.layers(baseMaps, null, { position: 'topright' }).addTo(map);


// Cluster layer setup
let geojsonLayer;
const markerClusterGroup = L.markerClusterGroup({
    maxClusterRadius: 50,
    showCoverageOnHover: false,
    spiderfyOnMaxZoom: true
});
map.addLayer(markerClusterGroup);

// Handle population estimation clicks via event delegation
map.on('popupopen', function (e) {
    const popupContainer = e.popup.getElement();
    if (!popupContainer) return;
    const btn = popupContainer.querySelector('.btn-pop-query');
    if (btn) {
        btn.addEventListener('click', async function (event) {
            if (event) {
                event.stopPropagation();
                event.preventDefault();
            }
            const lat = btn.getAttribute('data-lat');
            const lon = btn.getAttribute('data-lon');
            const containerId = btn.getAttribute('data-container');
            if (lat && lon && containerId) {
                await queryWorldPop(parseFloat(lat), parseFloat(lon), containerId);
            }
        });
    }
});

// Show/hide loading indicator
function toggleLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

// Dynamically fetch and populate filters on page load
async function initializeFilters() {
    try {
        // Fetch States
        const statesRes = await fetch('/api/v1/states');
        const statesData = await statesRes.json();
        const stateSelect = document.getElementById('stateFilter');

        stateSelect.innerHTML = '<option value="">All 36 States + FCT</option>';
        if (statesData.states && statesData.states.length > 0) {
            statesData.states.forEach(state => {
                const option = document.createElement('option');
                option.value = state;
                option.textContent = state;
                stateSelect.appendChild(option);
            });
        } else {
            stateSelect.innerHTML = '<option value="">No States Found</option>';
        }

        // Fetch Asset Types
        const typesRes = await fetch('/api/v1/asset-types');
        const typesData = await typesRes.json();
        const typeSelect = document.getElementById('typeFilter');

        typeSelect.innerHTML = '<option value="">All Asset Types</option>';
        if (typesData.asset_types && typesData.asset_types.length > 0) {
            typesData.asset_types.forEach(type => {
                const option = document.createElement('option');
                option.value = type;
                option.textContent = type.charAt(0).toUpperCase() + type.slice(1);
                typeSelect.appendChild(option);
            });
        } else {
            typeSelect.innerHTML = '<option value="">No Asset Types Found</option>';
        }

    } catch (error) {
        console.error("Failed to load dynamic filter definitions:", error);
    }
}

// Fetch infrastructure assets and render on map
async function loadInfrastructureData() {
    toggleLoading(true);
    const state = document.getElementById('stateFilter').value;
    const type = document.getElementById('typeFilter').value;

    // Clean previous layers
    markerClusterGroup.clearLayers();

    // Build dynamic query
    let url = `/api/v1/infrastructure?`;
    if (state) url += `state=${encodeURIComponent(state)}&`;
    if (type) url += `type=${encodeURIComponent(type)}`;

    try {
        const response = await fetch(url);
        const geojsonData = await response.json();

        // Update counter
        const featureCount = (geojsonData.features) ? geojsonData.features.length : 0;
        document.getElementById('assetCounter').innerText = featureCount === 5000 ? '5,000 (Capped)' : featureCount.toLocaleString();

        geojsonLayer = L.geoJSON(geojsonData, {
            pointToLayer: function (feature, latlng) {
                return L.marker(latlng, {
                    icon: getAssetIcon(feature.properties.type, feature.properties.sub_type)
                });
            },
            onEachFeature: function (feature, layer) {
                const props = feature.properties;
                const badgeColor = getAssetColor(props.type);
                const containerId = `pop-wp-${props.id || Math.random().toString(36).substr(2, 9)}`;
                const coords = layer.getLatLng();

                // Construct popups with dynamic WorldPop trigger container
                layer.bindPopup(`
                            <div class="popup-header">${props.name || 'Unnamed Asset'}</div>
                            <div class="popup-detail">
                                <span class="popup-label">State:</span>
                                <span class="popup-value">${props.state || 'N/A'}</span>
                            </div>
                            <div class="popup-detail">
                                <span class="popup-label">LGA:</span>
                                <span class="popup-value">${props.lga || 'N/A'}</span>
                            </div>
                            <div class="popup-detail">
                                <span class="popup-label">Data Source:</span>
                                <span class="popup-value">${props.source || 'N/A'}</span>
                            </div>
                            <div class="badge" style="background-color: ${badgeColor}15; color: ${badgeColor}; border: 1px solid ${badgeColor}40;">
                                ${(props.type || 'other').toUpperCase()} (${props.sub_type || 'General'})
                            </div>
                            <div id="${containerId}" class="popup-detail" style="margin-top: 10px; border-top: 1px solid var(--border-color); padding-top: 8px;">
                                <button class="btn-pop-query" data-lat="${coords.lat}" data-lon="${coords.lng}" data-container="${containerId}">
                                    Estimate Pop. (1km radius)
                                </button>
                            </div>
                        `);
            }
        });

        // Add to cluster and update map
        markerClusterGroup.addLayer(geojsonLayer);

        // Dynamically fit map limits to matched items
        if (geojsonData.features && geojsonData.features.length > 0) {
            map.fitBounds(markerClusterGroup.getBounds(), { padding: [40, 40] });
        } else {
            map.setView([9.0820, 8.6753], 6);
        }
    } catch (error) {
        console.error("Failed to fetch geospatial data points:", error);
    } finally {
        toggleLoading(false);
    }
}

// Fetch surrounding population density on demand from WorldPop
async function queryWorldPop(lat, lon, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Render visual loading state inside popup
    container.innerHTML = `
                <div style="display:flex; align-items:center; gap:6px; font-size:11px; color:var(--text-secondary); margin-top:4px;">
                    <div class="spinner-small" style="width:12px; height:12px; border:2px solid rgba(16,185,129,0.15); border-top-color:var(--accent-color); border-radius:50%; animation:spin 1s infinite linear;"></div>
                    <span>Computing WorldPop stats...</span>
                </div>
            `;

    try {
        const response = await fetch(`/api/v1/population?lat=${lat}&lon=${lon}`);
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `
                        <div style="font-size:11px; color:#ef4444; margin-top:4px;">
                            Error: ${data.error}
                        </div>
                    `;
        } else {
            container.innerHTML = `
                        <div style="display:flex; flex-direction:column; gap:2px; margin-top:4px;">
                            <span class="popup-label" style="font-size:11px;">Surrounding Population (1km):</span>
                            <span class="popup-value" style="font-weight:600; color:var(--accent-color); font-size:12px;">
                                ${data.total_population.toLocaleString()} people
                            </span>
                        </div>
                    `;
        }
    } catch (error) {
        console.log(error);
        container.innerHTML = `
                    <div style="font-size:11px; color:#ef4444; margin-top:4px;">
                        Failed to calculate population.
                    </div>
                `;
    }
}

// Initialize dynamic parameters and retrieve default dataset
window.onload = async () => {
    await initializeFilters();
    await loadInfrastructureData();
};
