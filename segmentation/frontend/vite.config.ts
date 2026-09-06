import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  base: '/static/segmentation/bundle/',
  build: {
    outDir: path.resolve(__dirname, '../static/segmentation/bundle'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'segmentation-editor.js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name][extname]',
      },
    },
  },
  optimizeDeps: {
    exclude: ['@itk-wasm/dicom', '@itk-wasm/image-io'],
  },
});
