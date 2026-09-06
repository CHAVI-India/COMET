/** API client for saving segmentations and calling server-side tools. */

export interface RoiPayload {
  roi_name: string;
  labelmap: Uint8Array;
  color: [number, number, number];
  shape: number[];
}

export function getCsrfToken(): string {
  const cookie = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1] : '';
}

async function gzipBytes(input: Uint8Array): Promise<ArrayBuffer> {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(input);
      controller.close();
    },
  });
  const compressed = stream.pipeThrough(new CompressionStream('gzip'));
  const chunks: Uint8Array[] = [];
  const reader = compressed.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const total = chunks.reduce((acc, c) => acc + c.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    result.set(c, offset);
    offset += c.length;
  }
  return result.buffer;
}

async function encodeLabelmap(labelmap: Uint8Array): Promise<string> {
  const compressed = new Uint8Array(await gzipBytes(labelmap));
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < compressed.length; i += chunkSize) {
    binary += String.fromCharCode.apply(
      null,
      Array.from(compressed.subarray(i, i + chunkSize)) as any
    );
  }
  return btoa(binary);
}

export async function saveSegmentation(
  seriesId: number,
  rois: RoiPayload[]
): Promise<{ success: boolean; segmentation_ids?: number[]; error?: string }> {
  const body = {
    rois: await Promise.all(
      rois.map(async (roi) => ({
        roi_name: roi.roi_name,
        color: roi.color,
        labelmap: await encodeLabelmap(roi.labelmap),
        shape: roi.shape,
      }))
    ),
  };
  const resp = await fetch(
    `/segmentation/api/series/${seriesId}/save-segmentation/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(body),
    }
  );
  return resp.json();
}
