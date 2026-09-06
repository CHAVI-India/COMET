/** Load a DICOM series from authenticated URLs using ITK-Wasm. */
import { readImageDicomFileSeries } from '@itk-wasm/dicom';

// Configure ITK-Wasm to use locally bundled pipeline files instead of CDN.
// We import the internal modules via relative path to bypass package export restrictions.
(async () => {
  try {
    const pipelinesModule = await import(
      /* @vite-ignore */ '../node_modules/@itk-wasm/dicom/dist/pipelines-base-url.js'
    );
    pipelinesModule.setPipelinesBaseUrl('/static/segmentation/bundle/pipelines');
    const workerModule = await import(
      /* @vite-ignore */ '../node_modules/@itk-wasm/dicom/dist/pipeline-worker-url.js'
    );
    workerModule.setPipelineWorkerUrl(
      '/static/segmentation/bundle/assets/itk-wasm-pipeline.worker-B0gp24qu.js'
    );
  } catch (e) {
    console.warn('Could not set local pipeline URLs, using CDN fallback', e);
  }
})();

export interface ItkImage {
  imageType: {
    dimension: number;
    componentType: string;
    pixelType: string;
    components: number;
  };
  name: string;
  origin: number[];
  spacing: number[];
  direction: number[];
  size: number[];
  data: Float32Array | Uint8Array | Int16Array | Uint16Array;
}

export async function loadDicomSeries(urls: string[]): Promise<ItkImage> {
  const files = await Promise.all(
    urls.map(async (url) => {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Failed to fetch ${url}: ${resp.status}`);
      const blob = await resp.blob();
      const name = url.split('/').pop() || 'slice.dcm';
      return new File([blob], name, { type: 'application/dicom' });
    })
  );

  console.log(`ITK-Wasm: loading ${files.length} DICOM files`);

  try {
    const { outputImage, webWorkerPool } = await readImageDicomFileSeries({
      inputImages: files,
      singleSortedSeries: true,
    });
    webWorkerPool?.terminateWorkers();
    console.log('ITK-Wasm: series loaded successfully', outputImage.size);
    return outputImage as unknown as ItkImage;
  } catch (err) {
    console.error('ITK-Wasm: readImageDicomFileSeries failed', err);
    throw err;
  }
}

export async function fetchSeriesFileList(seriesId: number): Promise<string[]> {
  const resp = await fetch(`/segmentation/api/series/${seriesId}/dicom-files/`);
  if (!resp.ok) throw new Error(`Failed to fetch series metadata: ${resp.status}`);
  const body = await resp.json();
  return body.files.map((f: { url: string }) => f.url);
}
