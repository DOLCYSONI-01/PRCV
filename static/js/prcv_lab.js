/**
 * PRCV Research Lab & Academic Performance Inspector
 * Handles step-by-step visual filter stages, HSV histogram charts,
 * GLCM radar charts, confusion matrices, and model comparison metrics.
 */

let hsvChart = null;
let glcmChart = null;
let latencyChart = null;

async function loadAcademicMetrics() {
  try {
    const res = await fetch('/api/prcv/metrics');
    const data = await res.json();
    if (!data || !data.models) return;

    renderComparisonTable(data.comparison_table);
    renderConfusionMatrix(data);
    renderLatencyBenchmark(data.latency_benchmark);
    renderInsights(data.academic_insights);
  } catch (err) {
    console.error("Failed to load PRCV metrics:", err);
  }
}

function renderComparisonTable(rows) {
  const tbody = document.getElementById('metricsTableBody');
  if (!tbody || !rows) return;
  tbody.innerHTML = '';

  rows.forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-weight:700; color:#064e3b; padding:10px;">${r.model}</td>
      <td style="font-size:12px; color:#475569; padding:10px;">${r.features}</td>
      <td style="font-weight:700; color:#059669; padding:10px;">${r.accuracy}</td>
      <td style="padding:10px;">${r.precision}</td>
      <td style="padding:10px;">${r.recall}</td>
      <td style="font-weight:700; padding:10px;">${r.f1_score}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderConfusionMatrix(data) {
  const container = document.getElementById('confusionMatrixBox');
  if (!container || !data.models.svm) return;

  const classes = data.class_names;
  const cm = data.models.svm.confusion_matrix;

  let html = `<table class="cm-table"><thead><tr><th>True \\ Pred</th>`;
  classes.forEach(c => {
    html += `<th title="${c}">${c.substring(0, 4)}</th>`;
  });
  html += `</tr></thead><tbody>`;

  cm.forEach((row, i) => {
    html += `<tr><th title="${classes[i]}">${classes[i].substring(0, 4)}</th>`;
    row.forEach((val, j) => {
      const isDiag = (i === j);
      const cls = isDiag ? 'cm-cell-diag' : (val > 0 ? 'cm-cell-err' : '');
      html += `<td class="${cls}">${val}</td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table>`;
  container.innerHTML = html;
}

function renderLatencyBenchmark(latency) {
  const ctx = document.getElementById('latencyChartCanvas')?.getContext('2d');
  if (!ctx || !latency) return;

  if (latencyChart) latencyChart.destroy();

  latencyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Classical PRCV (SVM + Features)', 'Deep Learning (CNN)'],
      datasets: [{
        label: 'Inference Latency (milliseconds per image)',
        data: [latency.classical_svm_ms, latency.deep_cnn_ms],
        backgroundColor: ['rgba(5, 150, 105, 0.75)', 'rgba(37, 99, 235, 0.75)'],
        borderColor: ['#059669', '#2563eb'],
        borderWidth: 1.5,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Milliseconds (ms)' }
        }
      }
    }
  });
}

function renderInsights(insights) {
  const ul = document.getElementById('academicInsightsList');
  if (!ul || !insights) return;
  ul.innerHTML = '';
  insights.forEach(txt => {
    const li = document.createElement('li');
    li.style.marginBottom = '6px';
    li.textContent = txt;
    ul.appendChild(li);
  });
}

async function inspectPRCVPipeline(imageFileOrBase64) {
  const formData = new FormData();
  if (typeof imageFileOrBase64 === 'string') {
    formData.append('image_base64', imageFileOrBase64);
  } else {
    formData.append('file', imageFileOrBase64);
  }

  try {
    const res = await fetch('/api/prcv/pipeline', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    renderPipelineVisualStages(data.visual_stages);
    renderFeatureCharts(data.features);
  } catch (err) {
    console.error("PRCV pipeline error:", err);
  }
}

function renderPipelineVisualStages(stages) {
  const stageDefs = [
    { key: "step_1_original", title: "1. Standardized Input", desc: "Normalized to 256x256 RGB" },
    { key: "step_2_grayscale", title: "2. Grayscale Space", desc: "Luminance conversion Y = 0.299R + 0.587G + 0.114B" },
    { key: "step_3_clahe", title: "3. CLAHE Contrast", desc: "Adaptive histogram equalization on LAB L-channel" },
    { key: "step_4_gaussian_blur", title: "4. Gaussian Filter", desc: "5x5 kernel noise suppression" },
    { key: "step_5_otsu_mask", title: "5. Otsu Segmentation", desc: "Optimal intra-class variance threshold" },
    { key: "step_6_canny_edges", title: "6. Canny Edge Map", desc: "Gradient hysteresis (low=40, high=120)" },
    { key: "step_7_contour_tracking", title: "7. Contour & BBox", desc: "Green polygon contour & orange bounding box" },
    { key: "step_8_segmented_plant", title: "8. Masked Foreground", desc: "Background suppressed for pure feature extraction" }
  ];

  const grid = document.getElementById('pipelineVisualGrid');
  if (!grid) return;
  grid.innerHTML = '';

  stageDefs.forEach(def => {
    const card = document.createElement('div');
    card.className = 'pipeline-stage-card';
    card.innerHTML = `
      <div class="pipeline-img-wrap">
        <img src="${stages[def.key]}" alt="${def.title}">
      </div>
      <div class="pipeline-caption">
        <div class="stage-title">${def.title}</div>
        <div class="stage-desc">${def.desc}</div>
      </div>
    `;
    grid.appendChild(card);
  });
}

function renderFeatureCharts(features) {
  // 1. HSV Histogram Chart
  const hsvCtx = document.getElementById('hsvChartCanvas')?.getContext('2d');
  if (hsvCtx && features.h_hist_curve) {
    if (hsvChart) hsvChart.destroy();
    hsvChart = new Chart(hsvCtx, {
      type: 'line',
      data: {
        labels: Array.from({length: features.h_hist_curve.length}, (_, i) => i * (180 / features.h_hist_curve.length)),
        datasets: [
          {
            label: 'Hue (H) Distribution',
            data: features.h_hist_curve,
            borderColor: '#e11d48',
            backgroundColor: 'rgba(225, 29, 72, 0.1)',
            tension: 0.3,
            fill: true
          },
          {
            label: 'Saturation (S)',
            data: features.s_hist_curve,
            borderColor: '#059669',
            backgroundColor: 'rgba(5, 150, 105, 0.08)',
            tension: 0.3,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'top' }
        },
        scales: {
          x: { title: { display: true, text: 'Bin / Angle (°)' } },
          y: { title: { display: true, text: 'Normalized Density' } }
        }
      }
    });
  }

  // 2. GLCM Texture Radar Chart
  const glcmCtx = document.getElementById('glcmChartCanvas')?.getContext('2d');
  if (glcmCtx && features.glcm_stats) {
    if (glcmChart) glcmChart.destroy();
    const stats = features.glcm_stats;
    glcmChart = new Chart(glcmCtx, {
      type: 'radar',
      data: {
        labels: ['Contrast', 'Dissimilarity', 'Homogeneity', 'Energy', 'Correlation'],
        datasets: [{
          label: 'GLCM Texture Profile (d=1)',
          data: [
            Math.min(1.0, (stats.contrast_d1 || 0) / 10),
            Math.min(1.0, (stats.dissimilarity_d1 || 0) / 5),
            stats.homogeneity_d1 || 0,
            stats.energy_d1 || 0,
            Math.max(0, stats.correlation_d1 || 0)
          ],
          backgroundColor: 'rgba(16, 185, 129, 0.2)',
          borderColor: '#10b981',
          pointBackgroundColor: '#047857'
        }]
      },
      options: {
        responsive: true,
        scales: {
          r: { beginAtZero: true, max: 1.0 }
        }
      }
    });
  }

  // Display Shape Statistics (Hu Moments & Morphometrics)
  const shapeBox = document.getElementById('shapeMetricsStats');
  if (shapeBox && features.shape_stats) {
    const s = features.shape_stats;
    shapeBox.innerHTML = `
      <div style="font-size:13px; line-height:1.7;">
        <div><b>Aspect Ratio (w/h):</b> ${s.aspect_ratio}</div>
        <div><b>Extent (Area/RectArea):</b> ${s.extent}</div>
        <div><b>Solidity (Area/ConvexHull):</b> ${s.solidity}</div>
        <div><b>Circularity (\(4\\pi A/P^2\)):</b> ${s.circularity}</div>
        <div style="margin-top:6px; font-size:11px; color:#64748b;">
          <b>Hu Invariant Moments (\(-\\text{sign}(h)\\log_{10}|h|\)):</b><br>
          [${s.hu_moments ? s.hu_moments.slice(0, 4).join(', ') : ''}...]
        </div>
      </div>
    `;
  }
}

window.loadAcademicMetrics = loadAcademicMetrics;
window.inspectPRCVPipeline = inspectPRCVPipeline;
