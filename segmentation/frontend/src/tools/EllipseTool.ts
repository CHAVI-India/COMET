/** Ellipse ROI — fill a 2D ellipse on a single slice. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

export function fillEllipse2D(
  labelmap: LabelmapVolume,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  sliceZ: number,
  value: number
): void {
  const cx = (x1 + x2) / 2;
  const cy = (y1 + y2) / 2;
  const rx = Math.abs(x2 - x1) / 2;
  const ry = Math.abs(y2 - y1) / 2;
  if (rx === 0 || ry === 0) return;
  for (let y = 0; y < labelmap.dims[1]; y++) {
    for (let x = 0; x < labelmap.dims[0]; x++) {
      if (((x - cx) * (x - cx)) / (rx * rx) + ((y - cy) * (y - cy)) / (ry * ry) <= 1)
        labelmap.set(x, y, sliceZ, value);
    }
  }
}
