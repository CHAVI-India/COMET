/** Ambient declarations for vtk.js modules that lack complete .d.ts files. */
declare module '@kitware/vtk.js/Filters/General/ImageMarchingCubes' {
  const vtkImageMarchingCubes: {
    newInstance: (initialValues?: any) => any;
    extend: (publicAPI: object, model: object, initialValues?: any) => void;
  };
  export default vtkImageMarchingCubes;
}

declare module '@kitware/vtk.js/Filters/General/WindowedSincPolyDataFilter' {
  const vtkWindowedSincPolyDataFilter: {
    newInstance: (initialValues?: any) => any;
    extend: (publicAPI: object, model: object, initialValues?: any) => void;
  };
  export default vtkWindowedSincPolyDataFilter;
}

declare module '@kitware/vtk.js/Interaction/Style/InteractorStyleManipulator' {
  const vtkInteractorStyleManipulator: {
    newInstance: (initialValues?: any) => any;
  };
  export default vtkInteractorStyleManipulator;
}

declare module '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballPanManipulator' {
  const vtkMouseCameraTrackballPanManipulator: {
    newInstance: (initialValues?: any) => any;
  };
  export default vtkMouseCameraTrackballPanManipulator;
}

declare module '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballZoomManipulator' {
  const vtkMouseCameraTrackballZoomManipulator: {
    newInstance: (initialValues?: any) => any;
  };
  export default vtkMouseCameraTrackballZoomManipulator;
}

declare module '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballZoomToMouseManipulator' {
  const vtkMouseCameraTrackballZoomToMouseManipulator: {
    newInstance: (initialValues?: any) => any;
  };
  export default vtkMouseCameraTrackballZoomToMouseManipulator;
}

declare module '@kitware/vtk.js/Interaction/Style/InteractorStyleImage' {
  const vtkInteractorStyleImage: {
    newInstance: (initialValues?: any) => any;
  };
  export default vtkInteractorStyleImage;
}

declare module '@itk-wasm/dicom/dist/pipelines-base-url.js' {
  export function setPipelinesBaseUrl(url: string): void;
  export function getPipelinesBaseUrl(): string;
}

declare module '@itk-wasm/dicom/dist/pipeline-worker-url.js' {
  export function setPipelineWorkerUrl(url: string): void;
  export function getPipelineWorkerUrl(): string | null;
}
