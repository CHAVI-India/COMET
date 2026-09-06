/** Shared types for the segmentation frontend. */

export interface ToolState {
  activeTool: string;
  brushRadius: number;
  brushIs3D: boolean;
  eraseMode: boolean;
  thresholdLower: number;
  thresholdUpper: number;
  regionGrowingTolerance: number;
}
