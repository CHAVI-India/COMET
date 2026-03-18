// Cornerstone3D Segmentation Bundle
// Import from package entry points (package.json exports field handles the path)
import * as cornerstoneCore from '@cornerstonejs/core';
import * as cornerstoneTools from '@cornerstonejs/tools';
import * as niftiVolumeLoader from '@cornerstonejs/nifti-volume-loader';

// Export all modules under a single namespace
export default {
  core: cornerstoneCore,
  tools: cornerstoneTools,
  niftiVolumeLoader: niftiVolumeLoader
};
