/** Level tracing — flood-fill an iso-tolerance region on a slice and return boundary. */
export function traceLevelOnSlice(
  intensitySlice: Float32Array | Int16Array | Uint16Array,
  dims: [number, number],
  seedX: number,
  seedY: number,
  tolerance: number
): Array<[number, number]> {
  const seedValue = intensitySlice[seedY * dims[0] + seedX];
  const visited = new Uint8Array(dims[0] * dims[1]);
  const stack: Array<[number, number]> = [[seedX, seedY]];
  const region: Array<[number, number]> = [];

  while (stack.length) {
    const [x, y] = stack.pop()!;
    const idx = y * dims[0] + x;
    if (visited[idx]) continue;
    visited[idx] = 1;
    const v = intensitySlice[idx];
    if (Math.abs(v - seedValue) > tolerance) continue;
    region.push([x, y]);
    const neighbors: Array<[number, number]> = [
      [x + 1, y],
      [x - 1, y],
      [x, y + 1],
      [x, y - 1],
    ];
    for (const [nx, ny] of neighbors) {
      if (nx >= 0 && nx < dims[0] && ny >= 0 && ny < dims[1]) stack.push([nx, ny]);
    }
  }
  return region;
}
