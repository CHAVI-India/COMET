# Cornerstone3D Segmentation Bundle

This directory contains the build configuration for bundling Cornerstone3D libraries for use in the Django segmentation editor.

## Build Instructions

1. Install dependencies:
```bash
cd cornerstone-build
npm install
```

2. Build the bundle:
```bash
npm run build
```

3. Copy the bundle to Django static files:
```bash
cp dist/cornerstone-segmentation.bundle.js ../static/js/
```

The bundled file will be available at `/static/js/cornerstone-segmentation.bundle.js` in your Django application.

## What's Included

- @cornerstonejs/core - Core rendering engine
- @cornerstonejs/tools - Segmentation tools (BrushTool, etc.)
- @cornerstonejs/nifti-volume-loader - NIfTI file loader

## Usage in Template

```html
<script src="{% static 'js/cornerstone-segmentation.bundle.js' %}"></script>
<script>
  const { core, tools, niftiVolumeLoader } = CornerstoneSegmentation;
  // Use the libraries...
</script>
```
