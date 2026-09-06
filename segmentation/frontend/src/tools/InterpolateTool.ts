/** Fill between slices — interpolate masks on empty slices between annotated ones. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

/**
 * Simple binary interpolation: for each empty slice between two non-empty
 * slices along the Z axis, set voxels that are foreground in both bounding
 * slices (logical AND of the two nearest annotated slices). This is a
 * conservative shape-preserving interpolation.
 */
export function interpolateBetweenSlices(
  labelmap: LabelmapVolume,
  axis: number = 2
): void {
  const [w, h, d] = labelmap.dims;
  if (axis !== 2) return; // currently only Z-axis interpolation

  // Find annotated slices (slices with at least one foreground voxel)
  const annotated: number[] = [];
  for (let z = 0; z < d; z++) {
    let hasFg = false;
    for (let y = 0; y < h && !hasFg; y++) {
      for (let x = 0; x < w && !hasFg; x++) {
        if (labelmap.get(x, y, z)) hasFg = true;
      }
    }
    if (hasFg) annotated.push(z);
  }

  if (annotated.length < 2) return;

  for (let i = 0; i < annotated.length - 1; i++) {
    const zA = annotated[i];
    const zB = annotated[i + 1];
    if (zB - zA <= 1) continue;

    for (let z = zA + 1; z < zB; z++) {
      const t = (z - zA) / (zB - zA);
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const va = labelmap.get(x, y, zA);
          const vb = labelmap.get(x, y, zB);
          // Linear interpolation with threshold at 0.5
          const v = va * (1 - t) + vb * t;
          labelmap.set(x, y, z, v >= 0.5 ? 1 : 0);
        }
      }
    }
  }
}
