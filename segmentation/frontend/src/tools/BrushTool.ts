/** Paint brush tool — stamps a circle (2D) or sphere (3D) into the labelmap. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

export interface BrushOptions {
  radius: number;
  is3D: boolean;
  erase: boolean;
}

export function applyBrush(
  labelmap: LabelmapVolume,
  center: [number, number, number],
  options: BrushOptions
): void {
  const [cx, cy, cz] = center;
  const r = options.radius;
  const r2 = r * r;
  const value = options.erase ? 0 : 1;

  const zStart = options.is3D ? Math.max(0, cz - r) : cz;
  const zEnd = options.is3D ? Math.min(labelmap.dims[2] - 1, cz + r) : cz;

  for (let z = zStart; z <= zEnd; z++) {
    for (
      let y = Math.max(0, cy - r);
      y <= Math.min(labelmap.dims[1] - 1, cy + r);
      y++
    ) {
      for (
        let x = Math.max(0, cx - r);
        x <= Math.min(labelmap.dims[0] - 1, cx + r);
        x++
      ) {
        const dz = options.is3D ? z - cz : 0;
        const d2 = (x - cx) * (x - cx) + (y - cy) * (y - cy) + dz * dz;
        if (d2 <= r2) labelmap.set(x, y, z, value);
      }
    }
  }
}
