/** Threshold tool — set all voxels within an intensity range to the segment. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

export function applyThreshold(
  intensityVolume: Float32Array | Int16Array | Uint16Array,
  labelmap: LabelmapVolume,
  lower: number,
  upper: number
): void {
  const len = intensityVolume.length;
  for (let i = 0; i < len; i++) {
    labelmap.data[i] =
      intensityVolume[i] >= lower && intensityVolume[i] <= upper ? 1 : 0;
  }
}
