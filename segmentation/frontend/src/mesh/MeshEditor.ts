/** MeshEditor — smoothing, hole filling, and cutting on vtk.js PolyData. */
import vtkWindowedSincPolyDataFilter from '@kitware/vtk.js/Filters/General/WindowedSincPolyDataFilter';
import vtkClipClosedSurface from '@kitware/vtk.js/Filters/General/ClipClosedSurface';
import vtkFillHolesFilter from '@kitware/vtk.js/Filters/Modeling/FillHolesFilter';
import vtkPlane from '@kitware/vtk.js/Common/DataModel/Plane';

/** Smooth a polydata using the windowed sinc filter. */
export function smoothMesh(polyData: any, iterations: number = 20): any {
  const smoother = vtkWindowedSincPolyDataFilter.newInstance();
  smoother.setInputData(polyData);
  smoother.setNumberOfIterations(iterations);
  smoother.setPassBand(0.1);
  smoother.setBoundarySmoothing(0);
  smoother.setFeatureEdgeSmoothing(0);
  smoother.setNonManifoldSmoothing(1);
  smoother.setNormalizeCoordinates(1);
  smoother.update();
  return smoother.getOutputData();
}

/** Fill holes in a polydata up to a maximum hole size. */
export function fillHoles(polyData: any, holeSize: number = 1.0): any {
  const fill = vtkFillHolesFilter.newInstance();
  fill.setInputData(polyData);
  fill.setHoleSize(holeSize);
  fill.update();
  return fill.getOutputData();
}

/** Clip a closed surface with a plane. Returns the clipped polydata. */
export function cutMeshWithPlane(
  polyData: any,
  origin: [number, number, number],
  normal: [number, number, number]
): any {
  const plane = vtkPlane.newInstance();
  plane.setOrigin(origin[0], origin[1], origin[2]);
  plane.setNormal(normal[0], normal[1], normal[2]);

  const clip: any = vtkClipClosedSurface.newInstance({
    clippingPlanes: [plane],
    generateFaces: true,
    generateOutline: false,
  });
  clip.setInputData(polyData);
  clip.update();
  return clip.getOutputData();
}
