/** Undo/redo stack for labelmap snapshots. */
import { LabelmapVolume } from '../labelmap/LabelmapVolume';

export class UndoStack {
  private stack: LabelmapVolume[] = [];
  private pos = -1;
  private limit = 50;

  push(vol: LabelmapVolume): void {
    this.stack = this.stack.slice(0, this.pos + 1);
    this.stack.push(vol.clone());
    if (this.stack.length > this.limit) this.stack.shift();
    this.pos = this.stack.length - 1;
  }

  undo(): LabelmapVolume | null {
    if (this.pos <= 0) return null;
    this.pos--;
    return this.stack[this.pos].clone();
  }

  redo(): LabelmapVolume | null {
    if (this.pos >= this.stack.length - 1) return null;
    this.pos++;
    return this.stack[this.pos].clone();
  }

  canUndo(): boolean {
    return this.pos > 0;
  }

  canRedo(): boolean {
    return this.pos < this.stack.length - 1;
  }
}
