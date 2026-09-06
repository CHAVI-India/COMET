/** vtk.js-based 2D slice viewer with window/level, slice navigation, zoom/pan.
 *  Follows the official vtk.js manipulator pattern: right-drag zoom, middle-drag pan,
 *  scroll wheel slice, left mouse free for tool canvas overlay. */
import '@kitware/vtk.js/Rendering/Profiles/Volume';
import vtkGenericRenderWindow from '@kitware/vtk.js/Rendering/Misc/GenericRenderWindow';
import vtkImageMapper from '@kitware/vtk.js/Rendering/Core/ImageMapper';
import vtkImageSlice from '@kitware/vtk.js/Rendering/Core/ImageSlice';
import vtkITKHelper from '@kitware/vtk.js/Common/DataModel/ITKHelper';
import vtkInteractorStyleManipulator from '@kitware/vtk.js/Interaction/Style/InteractorStyleManipulator';
import vtkMouseCameraTrackballPanManipulator from '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballPanManipulator';
import vtkMouseCameraTrackballZoomManipulator from '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballZoomManipulator';
import vtkMouseCameraTrackballZoomToMouseManipulator from '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballZoomToMouseManipulator';
import { SlicingMode } from '@kitware/vtk.js/Rendering/Core/ImageMapper/Constants';
import type { ItkImage } from './dicomLoader';

export interface SliceViewer {
  renderWindow: any;
  renderer: any;
  mapper: any;
  actor: any;
  imageData: any;
  maxSlice: number;
  setSlice: (index: number) => void;
  getSlice: () => number;
  setWindowLevel: (center: number, width: number) => void;
  getWindowLevel: () => { center: number; width: number };
  zoom: (factor: number) => void;
  resetView: () => void;
  render: () => void;
  onSliceChange: (cb: (slice: number) => void) => void;
  /** Convert screen pixel coordinates (top-left origin) to voxel indices. */
  screenToVoxel: (sx: number, sy: number, canvasWidth: number, canvasHeight: number) => [number, number];
  /** Convert voxel indices to screen pixel coordinates (top-left origin). */
  voxelToScreen: (vx: number, vy: number, canvasWidth: number, canvasHeight: number) => [number, number];
  /** Get the on-screen pixel rect and flip flags where the image slice is rendered. */
  getImageScreenRect: (canvasWidth: number, canvasHeight: number) => { x: number; y: number; w: number; h: number; flipX: boolean; flipY: boolean };
}

export function createSliceViewer(container: HTMLElement, itkImage: ItkImage): SliceViewer {
  const genericRenderWindow = vtkGenericRenderWindow.newInstance();
  genericRenderWindow.setContainer(container);
  genericRenderWindow.resize();

  const renderWindow = genericRenderWindow.getRenderWindow();
  const renderer = genericRenderWindow.getRenderer();

  const vtkImage = vtkITKHelper.convertItkToVtkImage(itkImage as any);

  const mapper = vtkImageMapper.newInstance();
  mapper.setInputData(vtkImage);
  mapper.setSlicingMode(SlicingMode.Z);
  mapper.setSliceAtFocalPoint(true);

  const actor = vtkImageSlice.newInstance();
  actor.setMapper(mapper);

  // Default window/level
  const dataRange = vtkImage.getPointData().getScalars().getRange();
  const width = dataRange[1] - dataRange[0];
  const center = (dataRange[1] + dataRange[0]) / 2;
  actor.getProperty().setColorWindow(width);
  actor.getProperty().setColorLevel(center);

  renderer.addActor(actor);

  const dims = vtkImage.getDimensions();
  const spacing = vtkImage.getSpacing();
  const origin = vtkImage.getOrigin();
  const maxSlice = dims[2] - 1;
  const initialSlice = Math.floor(maxSlice / 2);
  mapper.setSlice(initialSlice);

  renderer.getActiveCamera().setParallelProjection(true);
  renderer.resetCamera();
  // DICOM row origin is top-left; vtk world Y is up.
  renderer.getActiveCamera().setViewUp(0, -1, 0);
  renderWindow.render();

  // Custom interactor style: right drag zoom, middle drag pan, scroll zoom,
  // left mouse free for tool overlay. No left mouse manipulator added.
  const interactorStyle = vtkInteractorStyleManipulator.newInstance();
  const panManipulator = vtkMouseCameraTrackballPanManipulator.newInstance();
  panManipulator.setButton(2); // middle mouse
  interactorStyle.addMouseManipulator(panManipulator);

  const zoomManipulator = vtkMouseCameraTrackballZoomToMouseManipulator.newInstance();
  zoomManipulator.setButton(2); // right mouse
  zoomManipulator.setScrollEnabled(false);
  interactorStyle.addMouseManipulator(zoomManipulator);

  const scrollZoomManipulator = vtkMouseCameraTrackballZoomManipulator.newInstance();
  scrollZoomManipulator.setDragEnabled(false);
  scrollZoomManipulator.setScrollEnabled(true);
  interactorStyle.addMouseManipulator(scrollZoomManipulator);

  renderWindow.getInteractor().setInteractorStyle(interactorStyle);

  // Slice change callbacks
  const sliceChangeCallbacks: ((slice: number) => void)[] = [];
  const worldZToSliceIndex = (worldZ: number) =>
    Math.max(0, Math.min(maxSlice, Math.round((worldZ - origin[2]) / spacing[2])));
  let lastSlice = worldZToSliceIndex(mapper.getSlice());

  const checkSliceChange = () => {
    const current = worldZToSliceIndex(mapper.getSlice());
    if (current !== lastSlice) {
      lastSlice = current;
      sliceChangeCallbacks.forEach((cb) => cb(current));
    }
  };
  renderWindow.getInteractor().onRenderEvent(checkSliceChange);

  function changeSlice(sliceIndex: number) {
    const clamped = Math.max(0, Math.min(maxSlice, Math.round(sliceIndex)));
    const current = worldZToSliceIndex(mapper.getSlice());
    if (clamped === current) return;

    const targetZ = origin[2] + clamped * spacing[2];
    const cam = renderer.getActiveCamera();
    const focal = cam.getFocalPoint();
    const pos = cam.getPosition();
    const dz = targetZ - focal[2];
    cam.setFocalPoint(focal[0], focal[1], targetZ);
    cam.setPosition(pos[0], pos[1], pos[2] + dz);
    renderWindow.render();
    lastSlice = clamped;
    sliceChangeCallbacks.forEach((cb) => cb(clamped));
  }

  // Resize observer
  const resizeObserver = new ResizeObserver(() => {
    genericRenderWindow.resize();
    renderWindow.render();
  });
  resizeObserver.observe(container);

  return {
    renderWindow,
    renderer,
    mapper,
    actor,
    imageData: vtkImage,
    maxSlice,
    setSlice(index: number) {
      changeSlice(index);
    },
    getSlice() {
      // With setSliceAtFocalPoint(true), mapper.getSlice() returns the world
      // Z coordinate of the camera focal point, not a slice index. Convert it
      // back to a slice index using the image origin and spacing.
      const worldZ = mapper.getSlice();
      const sliceIndex = Math.round((worldZ - origin[2]) / spacing[2]);
      return Math.max(0, Math.min(maxSlice, sliceIndex));
    },
    setWindowLevel(center: number, width: number) {
      actor.getProperty().setColorWindow(width);
      actor.getProperty().setColorLevel(center);
      renderWindow.render();
    },
    getWindowLevel() {
      return {
        width: actor.getProperty().getColorWindow(),
        center: actor.getProperty().getColorLevel(),
      };
    },
    zoom(factor: number) {
      const cam = renderer.getActiveCamera();
      cam.zoom(factor);
      renderWindow.render();
    },
    resetView() {
      renderer.resetCamera();
      renderer.getActiveCamera().setViewUp(0, -1, 0);
      changeSlice(initialSlice);
      renderWindow.render();
    },
    render() {
      renderWindow.render();
    },
    onSliceChange(cb: (slice: number) => void) {
      sliceChangeCallbacks.push(cb);
    },
    screenToVoxel(sx, sy, canvasWidth, canvasHeight) {
      // Convert screen pixel (top-left origin) to normalized display (0..1, bottom-left origin)
      const ndx = sx / canvasWidth;
      const ndy = 1.0 - sy / canvasHeight;
      const aspect = canvasWidth / canvasHeight;
      // Normalized display to world coordinates
      const world = renderer.normalizedDisplayToWorld(ndx, ndy, 0, aspect);
      // World to voxel index
      const vx = Math.round((world[0] - origin[0]) / spacing[0]);
      const vy = Math.round((world[1] - origin[1]) / spacing[1]);
      return [
        Math.max(0, Math.min(dims[0] - 1, vx)),
        Math.max(0, Math.min(dims[1] - 1, vy)),
      ];
    },
    voxelToScreen(vx, vy, canvasWidth, canvasHeight) {
      // Voxel to world
      const wx = origin[0] + vx * spacing[0];
      const wy = origin[1] + vy * spacing[1];
      const wz = origin[2] + worldZToSliceIndex(mapper.getSlice()) * spacing[2];
      const aspect = canvasWidth / canvasHeight;
      // World to normalized display
      const nd = renderer.worldToNormalizedDisplay(wx, wy, wz, aspect);
      // Normalized display (bottom-left origin) to screen pixel (top-left origin)
      const sx = nd[0] * canvasWidth;
      const sy = (1.0 - nd[1]) * canvasHeight;
      return [sx, sy];
    },
    getImageScreenRect(canvasWidth, canvasHeight) {
      // Compute the on-screen rectangle where the full image slice is rendered,
      // including any axis flips caused by the camera viewUp direction.
      const z = worldZToSliceIndex(mapper.getSlice());
      const wz = origin[2] + z * spacing[2];
      const aspect = canvasWidth / canvasHeight;
      // Convert voxel (0, 0) and voxel (W-1, H-1) to screen pixels
      const ndTL = renderer.worldToNormalizedDisplay(origin[0], origin[1], wz, aspect);
      const ndBR = renderer.worldToNormalizedDisplay(
        origin[0] + (dims[0] - 1) * spacing[0],
        origin[1] + (dims[1] - 1) * spacing[1],
        wz,
        aspect
      );
      const sxTL = ndTL[0] * canvasWidth;
      const syTL = (1.0 - ndTL[1]) * canvasHeight;
      const sxBR = ndBR[0] * canvasWidth;
      const syBR = (1.0 - ndBR[1]) * canvasHeight;
      // Detect flips: if voxel (0,0) is to the right of voxel (W-1, H-1) in X,
      // the image is flipped horizontally. Similarly for Y.
      const flipX = sxTL > sxBR;
      const flipY = syTL > syBR;
      return {
        x: Math.min(sxTL, sxBR),
        y: Math.min(syTL, syBR),
        w: Math.abs(sxBR - sxTL),
        h: Math.abs(syBR - syTL),
        flipX,
        flipY,
      };
    },
  };
}
