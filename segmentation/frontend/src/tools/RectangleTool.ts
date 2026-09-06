/** Rectangle ROI — fill a 2D rectangle on a single slice. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

export function fillRectangle2D(
  labelmap: LabelmapVolume,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  sliceZ: number,
  value: number
): void {
  const xmin = Math.max(0, Math.min(x1, x2));
  const xmax = Math.min(labelmap.dims[0] - 1, Math.max(x1, x2));
  const ymin = Math.max(0, Math.min(y1, y2));
  const ymax = Math.min(labelmap.dims[1] - 1, Math.max(y1, y2));
  for (let y = ymin; y <= ymax; y++) {
    for (let x = xmin; x <= xmax; x++) labelmap.set(x, y, sliceZ, value);
  }
}
