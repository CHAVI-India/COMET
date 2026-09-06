/** Multi-ROI collection: each ROI owns its own binary labelmap, name, color, and undo stack. */
import { LabelmapVolume } from './LabelmapVolume';
import { UndoStack } from '../tools/UndoStack';

export interface ROI {
  id: string;
  name: string;
  color: [number, number, number];
  visible: boolean;
  labelmap: LabelmapVolume;
  undoStack: UndoStack;
}

const PALETTE: [number, number, number][] = [
  [255, 0, 0],
  [0, 255, 0],
  [0, 0, 255],
  [255, 255, 0],
  [255, 0, 255],
  [0, 255, 255],
  [255, 128, 0],
  [128, 0, 255],
  [0, 255, 128],
  [255, 192, 203],
];

export class RoiCollection {
  rois: ROI[] = [];
  activeId: string | null = null;

  constructor(private dims: [number, number, number]) {}

  private makeId(): string {
    return 'roi_' + Math.random().toString(36).slice(2, 9);
  }

  add(name: string, color?: [number, number, number]): ROI {
    const roi: ROI = {
      id: this.makeId(),
      name: name.trim() || 'ROI ' + (this.rois.length + 1),
      color: color || PALETTE[this.rois.length % PALETTE.length],
      visible: true,
      labelmap: new LabelmapVolume(this.dims),
      undoStack: new UndoStack(),
    };
    roi.undoStack.push(roi.labelmap);
    this.rois.push(roi);
    this.activeId = roi.id;
    return roi;
  }

  remove(id: string): void {
    this.rois = this.rois.filter((r) => r.id !== id);
    if (this.activeId === id) {
      this.activeId = this.rois[0]?.id || null;
    }
  }

  setActive(id: string): void {
    if (this.rois.find((r) => r.id === id)) {
      this.activeId = id;
    }
  }

  getActive(): ROI | null {
    if (!this.activeId) return this.rois[0] || null;
    return this.rois.find((r) => r.id === this.activeId) || this.rois[0] || null;
  }

  get(id: string): ROI | null {
    return this.rois.find((r) => r.id === id) || null;
  }

  rename(id: string, name: string): void {
    const roi = this.get(id);
    if (roi) roi.name = name.trim() || roi.name;
  }

  setColor(id: string, color: [number, number, number]): void {
    const roi = this.get(id);
    if (roi) roi.color = color;
  }

  setVisible(id: string, visible: boolean): void {
    const roi = this.get(id);
    if (roi) roi.visible = visible;
  }

  snapshotActive(): void {
    const roi = this.getActive();
    if (roi) roi.undoStack.push(roi.labelmap);
  }

  undoActive(): void {
    const roi = this.getActive();
    if (!roi) return;
    const prev = roi.undoStack.undo();
    if (prev) roi.labelmap.data.set(prev.data);
  }

  redoActive(): void {
    const roi = this.getActive();
    if (!roi) return;
    const next = roi.undoStack.redo();
    if (next) roi.labelmap.data.set(next.data);
  }

  visibleRois(): ROI[] {
    return this.rois.filter((r) => r.visible);
  }
}
