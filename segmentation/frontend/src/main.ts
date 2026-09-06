/** Entry point for the COMET segmentation editor. */
import '@kitware/vtk.js/Rendering/Profiles/Volume';
import { fetchSeriesFileList, loadDicomSeries, type ItkImage } from './dicomLoader';
import { createSliceViewer, type SliceViewer } from './vtkViewer';
import { RoiCollection, type ROI } from './labelmap/RoiCollection';
import { LabelmapVolume } from './labelmap/LabelmapVolume';
import { applyBrush, type BrushOptions } from './tools/BrushTool';
import { fillPolygon2D } from './tools/LassoTool';
import { fillRectangle2D } from './tools/RectangleTool';
import { fillEllipse2D } from './tools/EllipseTool';
import { applyThreshold } from './tools/ThresholdTool';
import { applyRegionGrowing } from './tools/RegionGrowingTool';
import { interpolateBetweenSlices } from './tools/InterpolateTool';
import { saveSegmentation, type RoiPayload } from './apiClient';

declare global {
  interface Window {
    SEG_SERIES_ID?: number;
  }
}

interface EditorState {
  viewer: SliceViewer;
  itkImage: ItkImage;
  rois: RoiCollection;
  seriesId: number;
  activeTool: string;
  brushRadius: number;
  eraseMode: boolean;
  isDrawing: boolean;
  lassoPoints: Array<[number, number]>;
  polyPoints: Array<[number, number]>;
  rectStart: [number, number] | null;
  ellipseStart: [number, number] | null;
}

const TOOLS: Array<[string, string, string]> = [
  ['brush', 'Brush', 'pencil'],
  ['erase', 'Erase', 'eraser'],
  ['lasso', 'Lasso', 'pen'],
  ['polygon', 'Polygon', 'pentagon'],
  ['rectangle', 'Rectangle', 'square'],
  ['ellipse', 'Ellipse', 'circle'],
  ['threshold', 'Threshold', 'graph-up'],
  ['regionGrowing', 'Region Growing', 'moisture'],
  ['interpolate', 'Interpolate', 'arrows-angle-expand'],
];

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4, 6, 8];

async function main() {
  const seriesId = window.SEG_SERIES_ID;
  if (!seriesId) {
    console.error('No SEG_SERIES_ID found');
    return;
  }

  const container = document.getElementById('seg-viewer');
  if (!container) {
    console.error('No #seg-viewer container');
    return;
  }

  container.innerHTML = '<div style="color:white;padding:20px;">Loading DICOM series...</div>';

  try {
    const urls = await fetchSeriesFileList(seriesId);
    if (urls.length === 0) {
      container.innerHTML = '<div style="color:white;padding:20px;">No DICOM files found for this series.</div>';
      return;
    }

    const itkImage = await loadDicomSeries(urls);
    container.innerHTML = '';

    const dims = itkImage.size as [number, number, number];
    const viewer = createSliceViewer(container, itkImage);
    const rois = new RoiCollection(dims);
    rois.add('ROI 1');

    const state: EditorState = {
      viewer,
      itkImage,
      rois,
      seriesId,
      activeTool: 'brush',
      brushRadius: 5,
      eraseMode: false,
      isDrawing: false,
      lassoPoints: [],
      polyPoints: [],
      rectStart: null,
      ellipseStart: null,
    };

    buildLayout(container, state, dims);
    setupViewerInteractions(container, state, dims);
    setupKeyboardShortcuts(state);
  } catch (err) {
    console.error(err);
    container.innerHTML = '<div style="color:red;padding:20px;">Error loading series: ' + String(err) + '</div>';
  }
}

function buildLayout(viewerContainer: HTMLElement, state: EditorState, dims: [number, number, number]) {
  const parent = viewerContainer.parentElement!;
  parent.style.display = 'flex';
  parent.style.height = '600px';
  parent.style.overflow = 'hidden';

  // Left tool palette
  const leftPanel = document.createElement('div');
  leftPanel.id = 'seg-left-panel';
  leftPanel.className = 'seg-panel';
  leftPanel.style.cssText = 'width:220px; display:flex; flex-direction:column; background:#1e1e1e; color:#fff; border-right:1px solid #333;';

  // Tool palette
  leftPanel.innerHTML = `
    <div style="padding:10px; border-bottom:1px solid #333; font-weight:600; font-size:13px; background:#2a2a2a;">Segmentation Tools</div>
    <div id="seg-tools" style="padding:8px; display:flex; flex-direction:column; gap:4px;">
      ${TOOLS.map(([id, label, icon]) => `
        <button class="seg-tool-btn" data-tool="${id}" style="text-align:left; padding:8px; background:#333; color:#fff; border:1px solid #444; border-radius:4px; cursor:pointer; display:flex; align-items:center; gap:8px;">
          <i class="bi bi-${icon}"></i> ${label}
        </button>
      `).join('')}
    </div>
    <div id="seg-tool-options" style="padding:10px; border-top:1px solid #333; font-size:12px;">
      <label style="display:flex; justify-content:space-between; align-items:center; gap:8px;">Brush radius
        <input id="ctrl-radius" type="range" min="1" max="30" value="${state.brushRadius}" style="width:90px;">
        <span id="ctrl-radius-val">${state.brushRadius}</span>
      </label>
      <div id="seg-threshold-controls" style="display:none; margin-top:10px;">
        <div style="margin-bottom:6px;">Threshold range</div>
        <label style="display:flex; justify-content:space-between; gap:4px;">Lower <input id="ctrl-thresh-lower" type="number" style="width:60px;" value="0"></label>
        <label style="display:flex; justify-content:space-between; gap:4px; margin-top:4px;">Upper <input id="ctrl-thresh-upper" type="number" style="width:60px;" value="0"></label>
        <button id="btn-apply-threshold" style="margin-top:8px; width:100%; padding:6px; background:#28a745; border:none; border-radius:4px; color:#fff; cursor:pointer;">Apply Threshold</button>
      </div>
    </div>
    <div style="margin-top:auto; padding:10px; border-top:1px solid #333; display:flex; gap:8px;">
      <button id="btn-undo" class="seg-btn" style="flex:1; padding:8px; background:#444; border:1px solid #555; border-radius:4px; color:#fff; cursor:pointer;">Undo</button>
      <button id="btn-redo" class="seg-btn" style="flex:1; padding:8px; background:#444; border:1px solid #555; border-radius:4px; color:#fff; cursor:pointer;">Redo</button>
    </div>
  `;

  // Center viewer area
  viewerContainer.style.flex = '1';
  viewerContainer.style.position = 'relative';
  viewerContainer.style.background = '#000';
  viewerContainer.style.minWidth = '0';

  // Right ROI panel
  const rightPanel = document.createElement('div');
  rightPanel.id = 'seg-right-panel';
  rightPanel.className = 'seg-panel';
  rightPanel.style.cssText = 'width:240px; display:flex; flex-direction:column; background:#1e1e1e; color:#fff; border-left:1px solid #333;';
  rightPanel.innerHTML = `
    <div style="padding:10px; border-bottom:1px solid #333; font-weight:600; font-size:13px; background:#2a2a2a; display:flex; justify-content:space-between; align-items:center;">
      <span>ROIs</span>
      <button id="btn-add-roi" style="padding:2px 8px; background:#28a745; border:none; border-radius:3px; color:#fff; cursor:pointer; font-size:12px;">+ Add</button>
    </div>
    <div id="seg-roi-list" style="flex:1; overflow-y:auto; padding:8px;"></div>
    <div style="padding:10px; border-top:1px solid #333;">
      <button id="btn-save" style="width:100%; padding:8px; background:#28a745; border:none; border-radius:4px; color:#fff; cursor:pointer; font-weight:600;">Save RTSTRUCT</button>
    </div>
  `;

  // Bottom control bar
  const bottomBar = document.createElement('div');
  bottomBar.id = 'seg-bottom-bar';
  bottomBar.style.cssText = 'width:100%; padding:8px 12px; background:#222; color:#fff; border-top:1px solid #333; display:flex; gap:16px; align-items:center; flex-wrap:wrap; font-size:12px;';
  bottomBar.innerHTML = `
    <div style="display:flex; align-items:center; gap:8px; min-width:220px;">
      <button id="btn-slice-prev" style="padding:2px 8px; background:#444; border:1px solid #555; border-radius:3px; color:#fff; cursor:pointer;"><i class="bi bi-chevron-left"></i></button>
      <input id="ctrl-slice" type="range" min="0" max="${dims[2] - 1}" value="${state.viewer.getSlice()}" style="flex:1;">
      <button id="btn-slice-next" style="padding:2px 8px; background:#444; border:1px solid #555; border-radius:3px; color:#fff; cursor:pointer;"><i class="bi bi-chevron-right"></i></button>
      <span id="ctrl-slice-val" style="min-width:60px; font-variant-numeric:tabular-nums;">${state.viewer.getSlice()}/${dims[2] - 1}</span>
    </div>
    <div style="display:flex; align-items:center; gap:8px;">
      <label>Zoom
        <select id="ctrl-zoom" style="background:#333; color:#fff; border:1px solid #555; border-radius:3px; padding:2px 6px; margin-left:4px;">
          ${ZOOM_STEPS.map((z) => `<option value="${z}" ${z === 1 ? 'selected' : ''}>${Math.round(z * 100)}%</option>`).join('')}
        </select>
      </label>
      <button id="btn-reset-view" style="padding:2px 8px; background:#444; border:1px solid #555; border-radius:3px; color:#fff; cursor:pointer;">Reset View</button>
    </div>
    <div style="display:flex; align-items:center; gap:8px; margin-left:auto;">
      <label style="display:flex; align-items:center; gap:4px;">W <input id="ctrl-width" type="range" min="1" max="${Math.ceil(state.viewer.getWindowLevel().width)}" value="${Math.ceil(state.viewer.getWindowLevel().width)}" style="width:100px;"></label>
      <label style="display:flex; align-items:center; gap:4px;">L <input id="ctrl-level" type="range" min="0" max="${Math.ceil(state.viewer.getWindowLevel().center * 2)}" value="${Math.ceil(state.viewer.getWindowLevel().center)}" style="width:100px;"></label>
    </div>
  `;

  // Reorder DOM: we need a wrapper for viewer + bottom bar, then flex row for left/parent/right
  const centerWrapper = document.createElement('div');
  centerWrapper.style.cssText = 'flex:1; display:flex; flex-direction:column; min-width:0;';
  centerWrapper.appendChild(viewerContainer);
  centerWrapper.appendChild(bottomBar);

  // Add all panels to the document BEFORE wiring event listeners, otherwise
  // querySelector/getElementById calls below will find nothing.
  parent.appendChild(leftPanel);
  parent.appendChild(centerWrapper);
  parent.appendChild(rightPanel);

  wireUI(state, dims);
  renderRoiList(state);
  updateToolOptions(state);
}

function wireUI(state: EditorState, dims: [number, number, number]) {
  // Tool selection
  document.querySelectorAll('.seg-tool-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tool = (btn as HTMLButtonElement).dataset.tool!;
      selectTool(state, tool);
    });
  });
  selectTool(state, 'brush');

  // Radius
  const radiusInput = document.getElementById('ctrl-radius') as HTMLInputElement;
  const radiusVal = document.getElementById('ctrl-radius-val')!;
  radiusInput.addEventListener('input', () => {
    state.brushRadius = parseInt(radiusInput.value);
    radiusVal.textContent = String(state.brushRadius);
  });

  // Slice slider
  const sliceInput = document.getElementById('ctrl-slice') as HTMLInputElement;
  const sliceVal = document.getElementById('ctrl-slice-val')!;
  const updateSliceDisplay = (s: number) => {
    sliceInput.value = String(Math.round(s));
    sliceVal.textContent = `${Math.round(s)}/${dims[2] - 1}`;
  };
  sliceInput.addEventListener('input', () => {
    state.viewer.setSlice(parseInt(sliceInput.value));
  });
  state.viewer.onSliceChange((s) => updateSliceDisplay(s));
  updateSliceDisplay(state.viewer.getSlice());

  document.getElementById('btn-slice-prev')!.addEventListener('click', () => state.viewer.setSlice(state.viewer.getSlice() - 1));
  document.getElementById('btn-slice-next')!.addEventListener('click', () => state.viewer.setSlice(state.viewer.getSlice() + 1));

  // Zoom
  const zoomSelect = document.getElementById('ctrl-zoom') as HTMLSelectElement;
  zoomSelect.addEventListener('change', () => {
    state.viewer.zoom(parseFloat(zoomSelect.value));
  });
  document.getElementById('btn-reset-view')!.addEventListener('click', () => {
    state.viewer.resetView();
    zoomSelect.value = '1';
  });

  // Window/level
  const widthInput = document.getElementById('ctrl-width') as HTMLInputElement;
  const levelInput = document.getElementById('ctrl-level') as HTMLInputElement;
  const updateWL = () => state.viewer.setWindowLevel(parseInt(levelInput.value), parseInt(widthInput.value));
  widthInput.addEventListener('input', updateWL);
  levelInput.addEventListener('input', updateWL);

  // Threshold
  const threshLower = document.getElementById('ctrl-thresh-lower') as HTMLInputElement;
  const threshUpper = document.getElementById('ctrl-thresh-upper') as HTMLInputElement;
  const dataRange = state.viewer.imageData.getPointData().getScalars().getRange() as [number, number];
  threshLower.min = threshUpper.min = String(Math.floor(dataRange[0]));
  threshLower.max = threshUpper.max = String(Math.ceil(dataRange[1]));
  threshLower.value = String(Math.floor(dataRange[0]));
  threshUpper.value = String(Math.ceil(dataRange[1]));
  document.getElementById('btn-apply-threshold')!.addEventListener('click', () => {
    const roi = state.rois.getActive();
    if (!roi) return;
    state.rois.snapshotActive();
    applyThreshold(state.itkImage.data as Float32Array, roi.labelmap, parseInt(threshLower.value), parseInt(threshUpper.value));
    state.viewer.render();
  });

  // Interpolate
  document.querySelector('[data-tool="interpolate"]')!.addEventListener('click', () => {
    const roi = state.rois.getActive();
    if (!roi) return;
    state.rois.snapshotActive();
    interpolateBetweenSlices(roi.labelmap);
    state.viewer.render();
  });

  // Undo / Redo
  document.getElementById('btn-undo')!.addEventListener('click', () => {
    state.rois.undoActive();
    state.viewer.render();
  });
  document.getElementById('btn-redo')!.addEventListener('click', () => {
    state.rois.redoActive();
    state.viewer.render();
  });

  // Add ROI
  document.getElementById('btn-add-roi')!.addEventListener('click', () => {
    const name = prompt('ROI name:', 'ROI ' + (state.rois.rois.length + 1));
    if (name === null) return;
    state.rois.add(name || undefined as unknown as string);
    renderRoiList(state);
  });

  // Save
  document.getElementById('btn-save')!.addEventListener('click', () => handleSave(state));
}

function selectTool(state: EditorState, tool: string) {
  state.activeTool = tool;
  state.eraseMode = tool === 'erase';
  document.querySelectorAll('.seg-tool-btn').forEach((b) => {
    const btn = b as HTMLButtonElement;
    const isActive = btn.dataset.tool === tool;
    btn.style.background = isActive ? '#007bff' : '#333';
    btn.style.borderColor = isActive ? '#007bff' : '#444';
  });
  const threshControls = document.getElementById('seg-threshold-controls')!;
  threshControls.style.display = tool === 'threshold' ? 'block' : 'none';
  updateOverlayCursor(state);
}

function updateOverlayCursor(state: EditorState) {
  const overlay = document.getElementById('seg-overlay') as HTMLCanvasElement | null;
  if (!overlay) return;
  const tool = state.activeTool;
  if (tool === 'brush' || tool === 'erase') overlay.style.cursor = 'crosshair';
  else if (tool === 'regionGrowing') overlay.style.cursor = 'cell';
  else overlay.style.cursor = 'default';
}

function updateToolOptions(state: EditorState) {
  // Initial threshold defaults already set in wireUI
}

function renderRoiList(state: EditorState) {
  const list = document.getElementById('seg-roi-list')!;
  const active = state.rois.getActive();
  list.innerHTML = state.rois.rois
    .map(
      (roi) => `
      <div class="seg-roi-item" data-id="${roi.id}" style="padding:8px; margin-bottom:6px; background:${active?.id === roi.id ? '#2a4a6b' : '#2a2a2a'}; border:1px solid ${active?.id === roi.id ? '#007bff' : '#444'}; border-radius:4px; cursor:pointer;">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:6px;">
          <div style="display:flex; align-items:center; gap:6px; flex:1; min-width:0;">
            <span style="display:inline-block; width:12px; height:12px; border-radius:2px; background:rgb(${roi.color.join(',')}); flex-shrink:0;"></span>
            <span class="seg-roi-name" style="font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(roi.name)}</span>
          </div>
          <div style="display:flex; gap:4px;">
            <button class="seg-roi-visible" data-id="${roi.id}" style="padding:2px 4px; background:transparent; border:none; color:#fff; cursor:pointer;" title="Toggle visibility"><i class="bi bi-eye${roi.visible ? '' : '-slash'}"></i></button>
            <button class="seg-roi-delete" data-id="${roi.id}" style="padding:2px 4px; background:transparent; border:none; color:#dc3545; cursor:pointer;" title="Delete"><i class="bi bi-trash"></i></button>
          </div>
        </div>
      </div>
    `
    )
    .join('');

  list.querySelectorAll('.seg-roi-item').forEach((el) => {
    el.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).closest('.seg-roi-visible, .seg-roi-delete')) return;
      const id = (el as HTMLElement).dataset.id!;
      state.rois.setActive(id);
      renderRoiList(state);
      state.viewer.render();
    });
  });
  list.querySelectorAll('.seg-roi-visible').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = (btn as HTMLElement).dataset.id!;
      const roi = state.rois.get(id)!;
      state.rois.setVisible(id, !roi.visible);
      renderRoiList(state);
      state.viewer.render();
    });
  });
  list.querySelectorAll('.seg-roi-delete').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = (btn as HTMLElement).dataset.id!;
      if (confirm('Delete ROI ' + state.rois.get(id)?.name + '?')) {
        state.rois.remove(id);
        renderRoiList(state);
        state.viewer.render();
      }
    });
  });
  list.querySelectorAll('.seg-roi-name').forEach((nameEl) => {
    nameEl.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      const id = (nameEl.closest('.seg-roi-item') as HTMLElement).dataset.id!;
      const roi = state.rois.get(id)!;
      const newName = prompt('Rename ROI:', roi.name);
      if (newName !== null) {
        state.rois.rename(id, newName);
        renderRoiList(state);
      }
    });
  });
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function setupViewerInteractions(container: HTMLElement, state: EditorState, dims: [number, number, number]) {
  // Overlay canvas sits on top of the vtk render but only captures pointer events during tool use
  const canvas = document.createElement('canvas');
  canvas.id = 'seg-overlay';
  canvas.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:auto; cursor:crosshair; z-index:10;';
  container.appendChild(canvas);

  const resizeCanvas = () => {
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
  };
  resizeCanvas();
  new ResizeObserver(resizeCanvas).observe(container);

  const ctx = canvas.getContext('2d', { willReadFrequently: false })!;
  let previewRect: { x: number; y: number; w: number; h: number } | null = null;
  let previewEllipse: { cx: number; cy: number; rx: number; ry: number } | null = null;

  // Offscreen buffer at the native labelmap resolution. We composite all visible
  // ROIs into it and then draw it scaled to the viewer canvas.
  const sliceCanvas = document.createElement('canvas');
  sliceCanvas.width = dims[0];
  sliceCanvas.height = dims[1];
  const sliceCtx = sliceCanvas.getContext('2d')!;
  const sliceImageData = sliceCtx.createImageData(dims[0], dims[1]);
  const slicePixels = sliceImageData.data;

  function screenToVoxel(sx: number, sy: number): [number, number] {
    const rect = canvas.getBoundingClientRect();
    const px = sx - rect.left;
    const py = sy - rect.top;
    return state.viewer.screenToVoxel(px, py, canvas.width, canvas.height);
  }

  function currentSlice(): number {
    return state.viewer.getSlice();
  }

  function renderSliceToBuffer() {
    const z = currentSlice();
    // Clear buffer
    slicePixels.fill(0);
    // Draw visible ROIs; active ROI is drawn last so it appears on top.
    const active = state.rois.getActive();
    const ordered = active
      ? state.rois.visibleRois().sort((a) => (a.id === active.id ? 1 : 0))
      : state.rois.visibleRois();
    for (const roi of ordered) {
      const [r, g, b] = roi.color;
      for (let y = 0; y < dims[1]; y++) {
        for (let x = 0; x < dims[0]; x++) {
          if (roi.labelmap.get(x, y, z)) {
            const idx = (y * dims[0] + x) * 4;
            slicePixels[idx] = r;
            slicePixels[idx + 1] = g;
            slicePixels[idx + 2] = b;
            slicePixels[idx + 3] = 160; // alpha
          }
        }
      }
    }
    sliceCtx.putImageData(sliceImageData, 0, 0);
  }

  function drawBrushCursor(vx: number, vy: number) {
    const r = state.brushRadius;
    // Convert voxel center to screen pixel
    const [px, py] = state.viewer.voxelToScreen(vx, vy, canvas.width, canvas.height);
    // Convert voxel + radius to screen pixel to get the brush radius in screen pixels
    const [px2] = state.viewer.voxelToScreen(vx + r, vy, canvas.width, canvas.height);
    const pr = Math.abs(px2 - px);
    ctx.strokeStyle = 'rgba(255,255,255,0.9)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(px, py, pr, 0, Math.PI * 2);
    ctx.stroke();
  }

  function redrawOverlay() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    renderSliceToBuffer();

    // Compute an affine transform from labelmap (voxel) coordinates to screen pixels
    // using the same voxelToScreen conversion that the cursor uses. This keeps the
    // overlay exactly aligned with the zoomed/panned image, regardless of axis flips.
    const [sx0, sy0] = state.viewer.voxelToScreen(0, 0, canvas.width, canvas.height);
    const [sxW, syW] = state.viewer.voxelToScreen(dims[0] - 1, 0, canvas.width, canvas.height);
    const [sxH, syH] = state.viewer.voxelToScreen(0, dims[1] - 1, canvas.width, canvas.height);
    // x' = a*x + b*y + c ; y' = d*x + e*y + f
    const a = (sxW - sx0) / (dims[0] - 1);
    const b = (sxH - sx0) / (dims[1] - 1);
    const c = sx0;
    const d = (syW - sy0) / (dims[0] - 1);
    const e = (syH - sy0) / (dims[1] - 1);
    const f = sy0;

    ctx.save();
    ctx.imageSmoothingEnabled = false;
    // Canvas setTransform(a,b,c,d,e,f) maps x' = a*x + c*y + e, y' = b*x + d*y + f
    ctx.setTransform(a, d, b, e, c, f);
    ctx.drawImage(sliceCanvas, 0, 0);
    ctx.restore();

    // Draw shape previews (these are already in screen coordinates)
    if (previewRect) {
      ctx.strokeStyle = 'rgba(255,255,255,0.8)';
      ctx.lineWidth = 1;
      ctx.strokeRect(previewRect.x, previewRect.y, previewRect.w, previewRect.h);
    }
    if (previewEllipse) {
      ctx.strokeStyle = 'rgba(255,255,255,0.8)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(previewEllipse.cx, previewEllipse.cy, previewEllipse.rx, previewEllipse.ry, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  function redrawOverlayWithCursorAt(sx: number, sy: number) {
    redrawOverlay();
    const [vx, vy] = screenToVoxel(sx, sy);
    if (state.activeTool === 'brush' || state.activeTool === 'erase') {
      drawBrushCursor(vx, vy);
    }
  }

  // Bind pointer events on the container in CAPTURE phase. The vtk.js
  // RenderWindowInteractor also binds pointer events on this container (bubble
  // phase) and calls container.setPointerCapture() during pointerdown, which
  // steals subsequent pointermove/pointerup events from the overlay canvas.
  // By listening in capture phase we see the event first, handle drawing tools
  // ourselves and stop propagation before vtk.js can capture the pointer.
  // Right/middle buttons are left untouched so vtk.js zoom/pan still work.
  const eventTarget = container;
  function isDrawingEvent(e: PointerEvent): boolean {
    // For pointerdown/pointerup, e.button indicates which button changed.
    // For pointermove during a drag, e.button is -1 (no change) and e.buttons
    // is a bitmask of currently held buttons (bit 0 = left).
    const leftButtonChanged = e.button === 0;
    const leftButtonHeld = (e.buttons & 1) !== 0;
    const isLeftButton = e.type === 'pointermove' ? leftButtonHeld : leftButtonChanged;
    return isLeftButton && ['brush', 'erase', 'lasso', 'polygon', 'rectangle', 'ellipse', 'regionGrowing'].includes(state.activeTool);
  }
  function handlePointerDown(e: PointerEvent) {
    if (!isDrawingEvent(e)) return;
    e.preventDefault();
    e.stopPropagation();
    try { eventTarget.setPointerCapture(e.pointerId); } catch {}

    const [vx, vy] = screenToVoxel(e.clientX, e.clientY);
    const z = currentSlice();
    const roi = state.rois.getActive();
    if (!roi) return;

    state.isDrawing = true;
    const tool = state.activeTool;
    if (tool === 'brush' || tool === 'erase') {
      state.rois.snapshotActive();
      const opts: BrushOptions = { radius: state.brushRadius, is3D: false, erase: state.eraseMode };
      applyBrush(roi.labelmap, [vx, vy, z], opts);
      redrawOverlayWithCursorAt(e.clientX, e.clientY);
    } else if (tool === 'lasso') {
      state.lassoPoints = [[vx, vy]];
    } else if (tool === 'polygon') {
      state.polyPoints.push([vx, vy]);
    } else if (tool === 'rectangle') {
      state.rectStart = [vx, vy];
    } else if (tool === 'ellipse') {
      state.ellipseStart = [vx, vy];
    } else if (tool === 'regionGrowing') {
      state.rois.snapshotActive();
      applyRegionGrowing(state.itkImage.data as Float32Array, dims, [vx, vy, z], 50, roi.labelmap);
      redrawOverlayWithCursorAt(e.clientX, e.clientY);
      state.viewer.render();
    }
  }
  function handlePointerMove(e: PointerEvent) {
    if (!state.isDrawing) {
      redrawOverlayWithCursorAt(e.clientX, e.clientY);
      return;
    }
    // Only consume move events if this pointer is currently drawing
    if (!isDrawingEvent(e)) return;
    e.preventDefault();
    e.stopPropagation();

    const tool = state.activeTool;
    const [vx, vy] = screenToVoxel(e.clientX, e.clientY);
    const z = currentSlice();
    const roi = state.rois.getActive();
    if (!roi) return;

    if (tool === 'brush' || tool === 'erase') {
      const opts: BrushOptions = { radius: state.brushRadius, is3D: false, erase: state.eraseMode };
      applyBrush(roi.labelmap, [vx, vy, z], opts);
      redrawOverlayWithCursorAt(e.clientX, e.clientY);
    } else if (tool === 'lasso') {
      state.lassoPoints.push([vx, vy]);
    } else if (tool === 'rectangle' && state.rectStart) {
      const [sx, sy] = state.rectStart;
      const [x1, y1] = [Math.min(sx, vx), Math.min(sy, vy)];
      const [x2, y2] = [Math.max(sx, vx), Math.max(sy, vy)];
      // Convert voxel corners to screen pixels for the preview
      const [px1, py1] = state.viewer.voxelToScreen(x1, y1, canvas.width, canvas.height);
      const [px2, py2] = state.viewer.voxelToScreen(x2, y2, canvas.width, canvas.height);
      previewRect = {
        x: Math.min(px1, px2),
        y: Math.min(py1, py2),
        w: Math.abs(px2 - px1),
        h: Math.abs(py2 - py1),
      };
      redrawOverlay();
    } else if (tool === 'ellipse' && state.ellipseStart) {
      const [sx, sy] = state.ellipseStart;
      const [cx, cy] = state.viewer.voxelToScreen((sx + vx) / 2, (sy + vy) / 2, canvas.width, canvas.height);
      const [ex, ey] = state.viewer.voxelToScreen(sx + Math.abs(vx - sx) / 2, sy, canvas.width, canvas.height);
      const [ey2] = state.viewer.voxelToScreen(sx, sy + Math.abs(vy - sy) / 2, canvas.width, canvas.height);
      previewEllipse = {
        cx,
        cy,
        rx: Math.abs(ex - cx),
        ry: Math.abs(ey2 - cy),
      };
      redrawOverlay();
    }
  }
  function handlePointerUp(e: PointerEvent) {
    if (!state.isDrawing) return;
    try { eventTarget.releasePointerCapture(e.pointerId); } catch {}
    if (!isDrawingEvent(e)) return;
    e.preventDefault();
    e.stopPropagation();

    const tool = state.activeTool;
    const [vx, vy] = screenToVoxel(e.clientX, e.clientY);
    const z = currentSlice();
    const roi = state.rois.getActive();
    if (!roi) return;

    if (tool === 'lasso' && state.lassoPoints.length >= 3) {
      state.rois.snapshotActive();
      fillPolygon2D(roi.labelmap, state.lassoPoints, z, 1);
    } else if (tool === 'rectangle' && state.rectStart) {
      state.rois.snapshotActive();
      fillRectangle2D(roi.labelmap, state.rectStart[0], state.rectStart[1], vx, vy, z, 1);
    } else if (tool === 'ellipse' && state.ellipseStart) {
      state.rois.snapshotActive();
      fillEllipse2D(roi.labelmap, state.ellipseStart[0], state.ellipseStart[1], vx, vy, z, 1);
    }
    state.isDrawing = false;
    state.lassoPoints = [];
    state.rectStart = null;
    state.ellipseStart = null;
    previewRect = null;
    previewEllipse = null;
    redrawOverlayWithCursorAt(e.clientX, e.clientY);
  }

  eventTarget.addEventListener('pointerdown', handlePointerDown, { capture: true });
  eventTarget.addEventListener('pointermove', handlePointerMove, { capture: true });
  eventTarget.addEventListener('pointerup', handlePointerUp, { capture: true });
  eventTarget.addEventListener('pointercancel', handlePointerUp, { capture: true });

  // Close polygon with a double click on the container
  eventTarget.addEventListener('dblclick', (e) => {
    if (state.activeTool !== 'polygon') return;
    e.preventDefault();
    e.stopPropagation();
    const roi = state.rois.getActive();
    if (!roi) return;
    if (state.polyPoints.length >= 3) {
      state.rois.snapshotActive();
      fillPolygon2D(roi.labelmap, state.polyPoints, currentSlice(), 1);
      state.polyPoints = [];
      redrawOverlay();
    }
  });

  // Redraw overlay on slice change and render events
  state.viewer.onSliceChange(() => redrawOverlay());
  state.viewer.renderWindow.getInteractor().onRenderEvent(() => redrawOverlay());
}

function setupKeyboardShortcuts(state: EditorState) {
  document.addEventListener('keydown', (e) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
    if (e.key === 'ArrowUp' || e.key === 'ArrowRight' || e.key === 'PageUp') {
      e.preventDefault();
      state.viewer.setSlice(state.viewer.getSlice() + 1);
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'PageDown') {
      e.preventDefault();
      state.viewer.setSlice(state.viewer.getSlice() - 1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      state.viewer.setSlice(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      state.viewer.setSlice(state.viewer.maxSlice);
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
      e.preventDefault();
      if (e.shiftKey) {
        state.rois.redoActive();
      } else {
        state.rois.undoActive();
      }
      state.viewer.render();
    }
  });
}

async function handleSave(state: EditorState) {
  const saveBtn = document.getElementById('btn-save') as HTMLButtonElement;
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';
  try {
    const dims = state.itkImage.size as [number, number, number];
    const rois: RoiPayload[] = state.rois.visibleRois().map((roi) => ({
      roi_name: roi.name,
      labelmap: roi.labelmap.data,
      color: roi.color,
      shape: [dims[2], dims[1], dims[0]],
    }));
    if (rois.length === 0) {
      alert('No visible ROIs to save.');
      return;
    }
    const result = await saveSegmentation(state.seriesId, rois);
    if (result.success) {
      alert('Saved RTSTRUCT with ' + (result.segmentation_ids?.length || 0) + ' ROI(s).');
    } else {
      alert('Save failed: ' + (result.error || 'unknown error'));
    }
  } catch (err) {
    alert('Save error: ' + String(err));
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save RTSTRUCT';
  }
}

main().catch(console.error);
