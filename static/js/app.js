/**
 * AI Botanical Garden Navigator - Core Application Logic
 * Scanner, Camera, Speech Audio Guide, Visual Search, Catalog, and Tours
 */

let currentSelectedImageBase64 = null;
let currentAudioGuideText = "";
let webcamStream = null;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initScanner();
  initSampleChips();
  initVisualSearch();
  initCatalog();
  initTours();
  initAudioGuide();
});

// ----------------- TAB NAVIGATION -----------------
function initTabs() {
  const tabBtns = document.querySelectorAll('.nav-tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  // Update buttons
  document.querySelectorAll('.nav-tab-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-tab') === tabId);
  });

  // Update panes
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === `tab-${tabId}`);
  });

  // Trigger specific tab logic
  if (tabId === 'map') {
    setTimeout(() => {
      initGardenMap();
      if (gardenMap) gardenMap.invalidateSize();
    }, 100);
  } else if (tabId === 'prcv-lab') {
    loadAcademicMetrics();
    // Default inspect with current image or sample if available
    const activeImg = currentSelectedImageBase64 || '/samples/sunflower.jpg';
    inspectPRCVPipeline(activeImg);
  }
}
window.switchTab = switchTab;

// ----------------- SCANNER & PLANT IDENTIFICATION -----------------
function initScanner() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const btnScan = document.getElementById('btnScanPlant');
  const btnCamera = document.getElementById('btnStartCamera');
  const btnSnap = document.getElementById('btnSnapPhoto');
  const cameraBox = document.getElementById('cameraBox');
  const videoEl = document.getElementById('cameraVideo');

  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  btnCamera.addEventListener('click', async () => {
    if (cameraBox.style.display === 'block') {
      stopCamera();
      cameraBox.style.display = 'none';
      btnCamera.innerHTML = `<span>📷 Use Camera</span>`;
    } else {
      try {
        webcamStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        videoEl.srcObject = webcamStream;
        cameraBox.style.display = 'block';
        btnCamera.innerHTML = `<span>❌ Close Camera</span>`;
      } catch (err) {
        alert("Camera access denied or unavailable: " + err.message);
      }
    }
  });

  btnSnap.addEventListener('click', () => {
    if (!videoEl || !webcamStream) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoEl.videoWidth || 640;
    canvas.height = videoEl.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    const b64 = canvas.toDataURL('image/jpeg', 0.85);

    setImagePreview(b64);
    currentSelectedImageBase64 = b64;
    stopCamera();
    cameraBox.style.display = 'none';
    btnCamera.innerHTML = `<span>📷 Use Camera</span>`;
  });

  btnScan.addEventListener('click', () => {
    if (!currentSelectedImageBase64) {
      alert("Please upload, capture, or select a sample plant photo first.");
      return;
    }
    identifyCurrentPlant();
  });
}

function stopCamera() {
  if (webcamStream) {
    webcamStream.getTracks().forEach(t => t.stop());
    webcamStream = null;
  }
}

function handleFileSelected(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const b64 = e.target.result;
    currentSelectedImageBase64 = b64;
    setImagePreview(b64);
  };
  reader.readAsDataURL(file);
}

function setImagePreview(src) {
  const previewBox = document.getElementById('previewContainer');
  const previewImg = document.getElementById('previewImg');
  previewImg.src = src;
  previewBox.style.display = 'block';
}

async function initSampleChips() {
  try {
    const res = await fetch('/api/samples');
    const samples = await res.json();
    const chipsContainer = document.getElementById('sampleChips');
    if (!chipsContainer) return;
    chipsContainer.innerHTML = '';

    samples.forEach(s => {
      const chip = document.createElement('button');
      chip.className = 'sample-chip';
      chip.innerHTML = `<span>🌿</span> ${s.common_name}`;
      chip.addEventListener('click', async () => {
        // Fetch image as base64 or url
        setImagePreview(s.url);
        currentSelectedImageBase64 = s.url;
        // Auto-run identification on sample click
        identifyCurrentPlant();
      });
      chipsContainer.appendChild(chip);
    });
  } catch (err) {
    console.error("Failed to load sample chips:", err);
  }
}

async function identifyCurrentPlant() {
  const btnScan = document.getElementById('btnScanPlant');
  const originalText = btnScan.innerHTML;
  btnScan.innerHTML = `<span>⏳ Analyzing with PRCV Vision...</span>`;
  btnScan.disabled = true;

  const formData = new FormData();
  if (currentSelectedImageBase64.startsWith('data:')) {
    formData.append('image_base64', currentSelectedImageBase64);
  } else {
    // It's a sample URL, fetch it as blob
    try {
      const imgRes = await fetch(currentSelectedImageBase64);
      const blob = await imgRes.blob();
      formData.append('file', blob, 'sample.jpg');
    } catch {
      formData.append('image_base64', currentSelectedImageBase64);
    }
  }

  try {
    const res = await fetch('/api/identify', {
      method: 'POST',
      body: formData
    });
    const result = await res.json();
    renderIdentificationResult(result);
  } catch (err) {
    alert("Identification failed: " + err.message);
  } finally {
    btnScan.innerHTML = originalText;
    btnScan.disabled = false;
  }
}

function renderIdentificationResult(data) {
  const resultContainer = document.getElementById('idResultContainer');
  resultContainer.style.display = 'block';

  const plant = data.predicted_plant;
  if (!plant) return;

  // Basic Details
  document.getElementById('resCommonName').textContent = plant.common_name;
  document.getElementById('resScientificName').textContent = plant.scientific_name;
  document.getElementById('resFamily').textContent = plant.family;
  document.getElementById('resZone').textContent = plant.zone_name;
  document.getElementById('resSeason').textContent = plant.flowering_season;
  document.getElementById('resDescription').textContent = plant.description;
  document.getElementById('resAudioText').textContent = `"${plant.audio_guide_text}"`;
  currentAudioGuideText = plant.audio_guide_text;

  // Model Consensus Badges
  const m = data.models;
  document.getElementById('scoreSVM').textContent = `${m.svm.confidence}%`;
  document.getElementById('predSVM').textContent = m.svm.predicted_id;

  document.getElementById('scoreCNN').textContent = `${m.cnn.confidence}%`;
  document.getElementById('predCNN').textContent = m.cnn.predicted_id;

  document.getElementById('scoreKNN').textContent = `${m.knn.confidence}%`;
  document.getElementById('scoreRF').textContent = `${m.random_forest.confidence}%`;

  // Candidate probability progress bars
  const candidatesBox = document.getElementById('topCandidatesList');
  candidatesBox.innerHTML = '';
  const topList = m.ensemble?.top3 || m.cnn?.top3 || m.svm.top3 || [];
  topList.forEach(cand => {
    const row = document.createElement('div');
    row.className = 'candidate-row';
    row.innerHTML = `
      <div class="candidate-label">
        <span style="text-transform:capitalize;">${cand.plant_id.replace('_', ' ')}</span>
        <span>${cand.confidence}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width: ${Math.max(5, cand.confidence)}%;"></div>
      </div>
    `;
    candidatesBox.appendChild(row);
  });

  // Dominant color swatches
  const swatchesBox = document.getElementById('resDominantColors');
  swatchesBox.innerHTML = '';
  if (data.extracted_features_summary?.dominant_colors) {
    data.extracted_features_summary.dominant_colors.forEach(col => {
      const sw = document.createElement('span');
      sw.className = 'color-swatch';
      sw.style.backgroundColor = col;
      swatchesBox.appendChild(sw);
    });
  }

  // PRCV Texture & Shape badges
  const texture = data.extracted_features_summary?.glcm_texture || {};
  const shape = data.extracted_features_summary?.shape_metrics || {};
  document.getElementById('resTextureFeatures').textContent =
    `Contrast: ${texture.contrast_d1 || '0.12'} | Energy: ${texture.energy_d1 || '0.45'}`;
  document.getElementById('resShapeFeatures').textContent =
    `Solidity: ${shape.solidity || '0.88'} | Circularity: ${shape.circularity || '0.65'}`;

  // Hook navigation button to directly open Garden Map with calculated path
  const btnNav = document.getElementById('btnNavigateToPlant');
  btnNav.onclick = () => {
    window.navigateDirectTo(plant.id);
  };

  // Scroll smoothly to results
  resultContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ----------------- AUDIO GUIDE (SPEECH SYNTHESIS) -----------------
function initAudioGuide() {
  const btnPlay = document.getElementById('btnPlayAudioGuide');
  if (!btnPlay) return;

  btnPlay.addEventListener('click', () => {
    if (!('speechSynthesis' in window)) {
      alert("Text-to-speech is not supported by your browser.");
      return;
    }

    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      btnPlay.innerHTML = `<span>🔊 Play Audio Guide</span>`;
      return;
    }

    if (!currentAudioGuideText) return;

    const utterance = new SpeechSynthesisUtterance(currentAudioGuideText);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.onend = () => {
      btnPlay.innerHTML = `<span>🔊 Play Audio Guide</span>`;
    };

    window.speechSynthesis.speak(utterance);
    btnPlay.innerHTML = `<span>⏹ Stop Audio Guide</span>`;
  });
}

// ----------------- VISUAL PLANT SEARCH (CBIR) -----------------
function initVisualSearch() {
  const vsInput = document.getElementById('vsFileInput');
  const vsDrop = document.getElementById('vsDropzone');
  const vsBtn = document.getElementById('btnRunVisualSearch');
  let vsBase64 = null;

  if (!vsDrop) return;

  vsDrop.addEventListener('click', () => vsInput.click());
  vsInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        vsBase64 = ev.target.result;
        document.getElementById('vsPreviewImg').src = vsBase64;
        document.getElementById('vsPreviewContainer').style.display = 'block';
      };
      reader.readAsDataURL(e.target.files[0]);
    }
  });

  vsBtn.addEventListener('click', async () => {
    if (!vsBase64) {
      alert("Please upload or drop an image to search by visual similarity.");
      return;
    }

    vsBtn.disabled = true;
    vsBtn.textContent = "Comparing visual feature vectors...";

    const formData = new FormData();
    formData.append('image_base64', vsBase64);

    try {
      const res = await fetch('/api/visual-search', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      renderVisualSearchResults(data.matches);
    } catch (err) {
      alert("Visual search error: " + err.message);
    } finally {
      vsBtn.disabled = false;
      vsBtn.textContent = "🔍 Search Garden Collection";
    }
  });
}

function renderVisualSearchResults(matches) {
  const container = document.getElementById('vsResultsGrid');
  if (!container) return;
  container.innerHTML = '';

  if (!matches || matches.length === 0) {
    container.innerHTML = `<p style="color:#64748b;">No close visual matches found.</p>`;
    return;
  }

  matches.forEach((m, idx) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <span style="font-weight:700; color:#064e3b; font-size:15px;">#${idx+1} ${m.common_name}</span>
        <span class="badge-prcv">${m.similarity_score}% Match</span>
      </div>
      <div style="font-style:italic; font-size:12px; color:#047857;">${m.scientific_name}</div>
      <div style="font-size:12px; color:#64748b; margin:6px 0;">Location: <b>${m.zone_name}</b></div>
      <div class="progress-track" style="margin:8px 0;">
        <div class="progress-fill" style="width:${Math.max(5, m.similarity_score)}%;"></div>
      </div>
      <div style="margin-top:10px;">
        <button onclick="navigateDirectTo('${m.plant_id}')" class="btn btn-outline btn-sm" style="width:100%;">
          📍 Locate on Garden Map
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

// ----------------- BOTANICAL CATALOG -----------------
async function initCatalog() {
  const container = document.getElementById('catalogGrid');
  const searchInput = document.getElementById('catalogSearch');
  const zoneFilter = document.getElementById('catalogZoneFilter');
  if (!container) return;

  async function fetchAndRender() {
    const q = searchInput?.value || '';
    const zone = zoneFilter?.value || 'all';
    try {
      const res = await fetch(`/api/plants?q=${encodeURIComponent(q)}&zone_id=${zone}`);
      const plants = await res.json();
      renderCatalogCards(plants);
    } catch (err) {
      console.error("Failed to load catalog:", err);
    }
  }

  searchInput?.addEventListener('input', fetchAndRender);
  zoneFilter?.addEventListener('change', fetchAndRender);

  fetchAndRender();
}

function renderCatalogCards(plants) {
  const container = document.getElementById('catalogGrid');
  if (!container) return;
  container.innerHTML = '';

  plants.forEach(plant => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
        <div>
          <div style="font-weight:700; font-size:15px; color:#064e3b;">${plant.common_name}</div>
          <div style="font-style:italic; font-size:12px; color:#047857;">${plant.scientific_name}</div>
        </div>
        <span class="meta-tag" style="font-size:10px;">${plant.family}</span>
      </div>
      <div style="font-size:12px; color:#475569; margin:8px 0; max-height:64px; overflow:hidden; text-overflow:ellipsis;">
        ${plant.description}
      </div>
      <div style="font-size:11px; color:#64748b; margin-bottom:10px;">
        <div>📍 Zone: <b>${plant.zone_name}</b></div>
        <div>🌸 Blooms: <b>${plant.flowering_season}</b></div>
      </div>
      <div style="display:flex; gap:6px;">
        <button onclick="navigateDirectTo('${plant.id}')" class="btn btn-primary btn-sm" style="flex:1;">
          📍 Map & Route
        </button>
        <button onclick="testPlantFromCatalog('${plant.id}')" class="btn btn-outline btn-sm" title="Analyze with AI Scanner">
          🔬 Scan
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

function testPlantFromCatalog(plantId) {
  switchTab('scanner');
  const sampleUrl = `/samples/${plantId}.jpg`;
  setImagePreview(sampleUrl);
  currentSelectedImageBase64 = sampleUrl;
  identifyCurrentPlant();
}
window.testPlantFromCatalog = testPlantFromCatalog;

// ----------------- THEMED TOURS -----------------
async function initTours() {
  const container = document.getElementById('toursList');
  if (!container) return;

  try {
    const res = await fetch('/api/tours');
    const tours = await res.json();

    container.innerHTML = '';
    tours.forEach(tour => {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.display = 'flex';
      card.style.flexDirection = 'column';
      card.style.justifyContent = 'space-between';
      card.innerHTML = `
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="font-weight:700; font-size:16px; color:#064e3b;">${tour.title}</span>
            <span class="meta-tag">⏱ ${tour.duration_minutes} min</span>
          </div>
          <p style="font-size:13px; color:#475569; margin:8px 0;">${tour.description}</p>
          <div style="font-size:12px; color:#64748b; margin-bottom:10px;">
            <div>🚶 Distance: <b>${tour.distance_meters} meters</b> (${tour.stops.length} stops)</div>
            <div>♿ Accessibility: <b>${tour.accessibility}</b></div>
          </div>
        </div>
        <button onclick="startThemedTour('${tour.id}')" class="btn btn-accent btn-sm" style="width:100%; margin-top:8px;">
          🗺️ Start This Walking Tour
        </button>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Failed to load tours:", err);
  }
}

async function startThemedTour(tourId) {
  try {
    const res = await fetch(`/api/tours/${tourId}/route`);
    const tourData = await res.json();

    switchTab('map');
    renderNavigationRoute({
      path_coords_latlng: tourData.path_coords_latlng,
      total_distance_meters: tourData.total_distance_meters,
      estimated_minutes: tourData.estimated_minutes,
      target_plant: { common_name: tourData.tour_info.title },
      turn_instructions: tourData.itinerary_stops.map(s => ({
        instruction: `Stop #${s.stop_number}: Arrive at ${s.destination_name} (+${s.distance_from_prev}m)`
      }))
    });
  } catch (err) {
    alert("Could not load tour route: " + err.message);
  }
}
window.startThemedTour = startThemedTour;
