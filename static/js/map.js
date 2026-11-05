/**
 * Interactive Botanical Garden Map (Leaflet.js)
 * Visualizes zones, POIs, plant locations, Dijkstra walking paths, and simulated GPS navigation.
 */

let gardenMap = null;
let plantMarkers = {};
let poiMarkers = {};
let zoneLayers = [];
let routePolyline = null;
let visitorMarker = null;
let animationTimer = null;

const ZONE_COLORS = {
  "zone_tropical": "#059669",
  "zone_rose": "#f43f5e",
  "zone_aquatic": "#0284c7",
  "zone_succulent": "#f97316",
  "zone_zen": "#d97706",
  "zone_meadow": "#eab308",
  "zone_medicinal": "#8b5cf6",
  "zone_orchid": "#ec4899",
  "zone_entrance": "#10b981"
};

async function initGardenMap() {
  if (gardenMap) return;

  // Initialize Leaflet map
  gardenMap = L.map('gardenMap', {
    center: [51.4788, -0.2970],
    zoom: 17,
    minZoom: 15,
    maxZoom: 19
  });

  // Base map tiles (CartoDB Positron for clean botanical contrast)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(gardenMap);

  try {
    const res = await fetch('/api/garden/map');
    const data = await res.json();

    // 1. Render Garden Zones
    if (data.zones) {
      data.zones.forEach(zone => {
        const polygon = L.polygon(zone.coordinates, {
          color: zone.color || '#10b981',
          fillColor: zone.color || '#10b981',
          fillOpacity: 0.16,
          weight: 2,
          dashArray: '4, 4'
        }).addTo(gardenMap);

        polygon.bindTooltip(`<b>${zone.name}</b><br><span style="font-size:11px;color:#555;">${zone.description}</span>`, {
          sticky: true,
          className: 'zone-tooltip'
        });

        zoneLayers.push(polygon);
      });
    }

    // 2. Render Points of Interest (POIs)
    if (data.points_of_interest) {
      data.points_of_interest.forEach(poi => {
        const poiIcon = L.divIcon({
          className: 'poi-custom-marker',
          html: `<div style="background:#1e293b; color:#fff; border-radius:50%; width:26px; height:26px; display:flex; align-items:center; justify-content:center; font-size:13px; border:2px solid #fff; box-shadow:0 2px 4px rgba(0,0,0,0.3);">📍</div>`,
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });

        const marker = L.marker([poi.coords.lat, poi.coords.lng], { icon: poiIcon }).addTo(gardenMap);
        marker.bindPopup(`<b>${poi.name}</b><br><span style="text-transform:capitalize;font-size:11px;color:#64748b;">${poi.type} Point of Interest</span>`);
        poiMarkers[poi.id] = marker;
      });
    }

    // 3. Render Botanical Plants
    if (data.plants) {
      data.plants.forEach(plant => {
        const zoneColor = ZONE_COLORS[plant.zone_id] || '#059669';
        const plantIcon = L.divIcon({
          className: 'plant-map-icon',
          html: `<div style="background:${zoneColor}; color:#fff; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:15px; border:2px solid #ffffff; box-shadow:0 3px 6px rgba(0,0,0,0.25); cursor:pointer;">🌿</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16]
        });

        const marker = L.marker([plant.garden_coords.lat, plant.garden_coords.lng], { icon: plantIcon }).addTo(gardenMap);

        const popupContent = `
          <div style="font-family:system-ui; min-width:180px;">
            <div style="font-weight:700; color:#064e3b; font-size:14px;">${plant.common_name}</div>
            <div style="font-style:italic; font-size:12px; color:#047857;">${plant.scientific_name}</div>
            <div style="font-size:11px; color:#64748b; margin:4px 0;">Zone: <b>${plant.zone_name}</b></div>
            <div style="margin-top:8px;">
              <button onclick="navigateDirectTo('${plant.id}')" style="background:#059669; color:#fff; border:none; padding:4px 10px; border-radius:4px; font-size:11px; font-weight:600; cursor:pointer; width:100%;">
                📍 Navigate Here
              </button>
            </div>
          </div>
        `;
        marker.bindPopup(popupContent);
        plantMarkers[plant.id] = marker;
      });

      // Populate destination dropdown
      populateDestinationSelect(data.plants);
    }

  } catch (err) {
    console.error("Failed to load garden map data:", err);
  }
}

function populateDestinationSelect(plants) {
  const sel = document.getElementById('destPlantSelect');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Choose Target Plant --</option>';
  plants.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = `${p.common_name} (${p.zone_name})`;
    sel.appendChild(opt);
  });
}

async function navigateDirectTo(plantId) {
  // Switch to map tab if not already on it
  window.switchTab('map');
  const sel = document.getElementById('destPlantSelect');
  if (sel) sel.value = plantId;
  await requestRouteToPlant(plantId);
}

async function requestRouteToPlant(plantId) {
  if (!plantId) return;

  const startNode = document.getElementById('startNodeSelect')?.value || 'N_ENTRANCE';
  try {
    const res = await fetch(`/api/navigate?plant_id=${plantId}&start_node=${startNode}`);
    const routeData = await res.json();
    renderNavigationRoute(routeData);
  } catch (err) {
    alert("Could not calculate route: " + err.message);
  }
}

function renderNavigationRoute(routeData) {
  if (!gardenMap) return;

  // Clear existing polyline & animations
  if (routePolyline) gardenMap.removeLayer(routePolyline);
  if (animationTimer) clearInterval(animationTimer);
  if (visitorMarker) gardenMap.removeLayer(visitorMarker);

  const coords = routeData.path_coords_latlng;
  if (!coords || coords.length === 0) return;

  // Draw walking route with lush glowing emerald polyline
  routePolyline = L.polyline(coords, {
    color: '#059669',
    weight: 6,
    opacity: 0.85,
    dashArray: '10, 8',
    lineJoin: 'round'
  }).addTo(gardenMap);

  // Fit map bounds to show full route
  gardenMap.fitBounds(routePolyline.getBounds(), { padding: [50, 50] });

  // Add animated Visitor Pin at start
  const startCoord = coords[0];
  const visitorIcon = L.divIcon({
    className: 'visitor-icon',
    html: `<div style="background:#2563eb; color:#fff; border-radius:50%; width:30px; height:30px; display:flex; align-items:center; justify-content:center; font-size:15px; border:3px solid #fff; box-shadow:0 0 10px rgba(37,99,235,0.7);">🚶</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15]
  });
  visitorMarker = L.marker(startCoord, { icon: visitorIcon }).addTo(gardenMap);

  // Update UI stats & step directions
  document.getElementById('routeDistance').textContent = `${routeData.total_distance_meters} m`;
  document.getElementById('routeTime').textContent = `${routeData.estimated_minutes} min`;
  document.getElementById('routeTargetName').textContent = routeData.target_plant.common_name;

  const stepsList = document.getElementById('stepInstructions');
  if (stepsList) {
    stepsList.innerHTML = '';
    routeData.turn_instructions.forEach(step => {
      const li = document.createElement('li');
      li.textContent = step.instruction;
      stepsList.appendChild(li);
    });
  }

  const routeCard = document.getElementById('routeInfoBox');
  if (routeCard) routeCard.style.display = 'block';

  // Setup simulate walk button
  const simBtn = document.getElementById('btnSimulateWalk');
  if (simBtn) {
    simBtn.onclick = () => simulateWalkingAnimation(coords);
  }
}

function simulateWalkingAnimation(coords) {
  if (!visitorMarker || coords.length < 2) return;
  if (animationTimer) clearInterval(animationTimer);

  let stepIdx = 0;
  visitorMarker.setLatLng(coords[0]);

  animationTimer = setInterval(() => {
    stepIdx++;
    if (stepIdx >= coords.length) {
      clearInterval(animationTimer);
      return;
    }
    visitorMarker.setLatLng(coords[stepIdx]);
  }, 600);
}

// Make accessible to window
window.navigateDirectTo = navigateDirectTo;
window.requestRouteToPlant = requestRouteToPlant;
window.renderNavigationRoute = renderNavigationRoute;
