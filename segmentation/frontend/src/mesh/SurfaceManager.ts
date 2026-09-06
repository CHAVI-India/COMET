/** SurfaceManager — generate a 3D surface mesh from the labelmap using marching cubes. */
import '@kitware/vtk.js/Rendering/Profiles/Volume';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray';
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData';
import vtkImageMarchingCubes from '@kitware/vtk.js/Filters/General/ImageMarchingCubes';
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper';
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import type { LabelmapVolume } from '../labelmap/LabelmapVolume';

export interface SurfaceActor {
  actor: ReturnType<typeof vtkActor.newInstance>;
  mc: ReturnType<typeof vtkImageMarchingCubes.newInstance>;
  mapper: ReturnType<typeof vtkMapper.newInstance>;
  update: (labelmap: LabelmapVolume) => void;
}

export function createSurfaceFromLabelmap(
  labelmap: LabelmapVolume,
  spacing: [number, number, number],
  origin: [number, number, number]
): SurfaceActor {
  const imageData = vtkImageData.newInstance();
  imageData.setDimensions(labelmap.dims[0], labelmap.dims[1], labelmap.dims[2]);
  imageData.setSpacing(spacing);
  imageData.setOrigin(origin);

  const scalars = vtkDataArray.newInstance({
    name: 'labelmap',
    numberOfComponents: 1,
    values: labelmap.data,
  });
  imageData.getPointData().setScalars(scalars);

  const mc = vtkImageMarchingCubes.newInstance();
  mc.setInputData(imageData);
  mc.setContourValue(0.5);
  mc.setComputeNormals(true);
  mc.setMergePoints(true);

  const mapper = vtkMapper.newInstance();
  mapper.setInputConnection(mc.getOutputPort());

  const actor = vtkActor.newInstance();
  actor.setMapper(mapper);
  actor.getProperty().setColor(1, 0.5, 0.2);
  actor.getProperty().setOpacity(0.8);

  const update = (newLabelmap: LabelmapVolume) => {
    const newScalars = vtkDataArray.newInstance({
      name: 'labelmap',
      numberOfComponents: 1,
      values: newLabelmap.data,
    });
    imageData.getPointData().setScalars(newScalars);
    mc.modified();
  };

  return { actor, mc, mapper, update };
}
