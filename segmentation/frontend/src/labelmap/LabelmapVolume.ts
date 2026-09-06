/** In-memory 3D labelmap volume shared by all segmentation tools. */

export class LabelmapVolume {
  constructor(
    public dims: [number, number, number],
    public data: Uint8Array = new Uint8Array(dims[0] * dims[1] * dims[2])
  ) {}

  /** Linear index for (x, y, z) in row-major (x fastest) order. */
  idx(x: number, y: number, z: number): number {
    return z * this.dims[0] * this.dims[1] + y * this.dims[0] + x;
  }

  get(x: number, y: number, z: number): number {
    return this.data[this.idx(x, y, z)];
  }

  set(x: number, y: number, z: number, v: number): void {
    this.data[this.idx(x, y, z)] = v;
  }

  clone(): LabelmapVolume {
    return new LabelmapVolume(this.dims, new Uint8Array(this.data));
  }

  /** Count non-zero voxels. */
  count(): number {
    let n = 0;
    for (let i = 0; i < this.data.length; i++) {
      if (this.data[i]) n++;
    }
    return n;
  }
}
