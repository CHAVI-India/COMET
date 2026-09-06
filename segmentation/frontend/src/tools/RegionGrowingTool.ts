/** Region growing — 3D flood-fill from a seed within an intensity tolerance. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

export function applyRegionGrowing(
  intensityVolume: Float32Array | Int16Array | Uint16Array,
  dims: [number, number, number],
  seed: [number, number, number],
  tolerance: number,
  labelmap: LabelmapVolume,
  value: number = 1
): void {
  const [w, h, d] = dims;
  const seedIdx = seed[2] * w * h + seed[1] * w + seed[0];
  const seedValue = intensityVolume[seedIdx];
  const visited = new Uint8Array(w * h * d);
  const stack: Array<[number, number, number]> = [seed];

  while (stack.length) {
    const [x, y, z] = stack.pop()!;
    const idx = z * w * h + y * w + x;
    if (visited[idx]) continue;
    visited[idx] = 1;

    const v = intensityVolume[idx];
    if (Math.abs(v - seedValue) > tolerance) continue;

    labelmap.set(x, y, z, value);

    const neighbors: Array<[number, number, number]> = [
      [x + 1, y, z],
      [x - 1, y, z],
      [x, y + 1, z],
      [x, y - 1, z],
      [x, y, z + 1],
      [x, y, z - 1],
    ];
    for (const [nx, ny, nz] of neighbors) {
      if (nx >= 0 && nx < w && ny >= 0 && ny < h && nz >= 0 && nz < d) {
        stack.push([nx, ny, nz]);
      }
    }
  }
}
