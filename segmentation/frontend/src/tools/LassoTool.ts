/** Freehand lasso — fill a closed contour on a single slice. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

export function fillPolygon2D(
  labelmap: LabelmapVolume,
  points: Array<[number, number]>,
  sliceZ: number,
  value: number
): void {
  if (points.length < 3) return;
  const [w, h] = [labelmap.dims[0], labelmap.dims[1]];
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  ctx.beginPath();
  ctx.moveTo(points[0][0], points[0][1]);
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
  ctx.closePath();
  ctx.fillStyle = '#fff';
  ctx.fill();
  const imageData = ctx.getImageData(0, 0, w, h).data;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (imageData[(y * w + x) * 4] > 0) labelmap.set(x, y, sliceZ, value);
    }
  }
}
