"""Server-side segmentation tool implementations using SimpleITK."""
import numpy as np
import SimpleITK as sitk


def gaussian_smooth(mask: sitk.Image, sigma_mm: float = 1.0) -> sitk.Image:
    """Gaussian smooth a binary mask and re-threshold."""
    smoothed = sitk.SmoothingRecursiveGaussian(mask, sigma_mm)
    return sitk.BinaryThreshold(
        smoothed, lowerThreshold=0.5, upperThreshold=1.0, insideValue=1, outsideValue=0
    )


def median_smooth(mask: sitk.Image, radius: int = 1) -> sitk.Image:
    """Median smooth a binary mask."""
    return sitk.BinaryMedian(mask, [radius, radius, radius])


def apply_margin(mask: sitk.Image, margin_mm: float) -> sitk.Image:
    """
    Positive margin_mm -> dilate; negative -> erode.
    """
    spacing = mask.GetSpacing()
    kernel = [max(1, int(abs(margin_mm) / s) + 1) for s in spacing]
    if margin_mm >= 0:
        return sitk.BinaryDilate(mask, kernel)
    else:
        return sitk.BinaryErode(mask, kernel)


def hollow(mask: sitk.Image, thickness_voxels: int = 1) -> sitk.Image:
    """Create a shell of N voxels thickness from the mask surface."""
    eroded = sitk.BinaryErode(mask, [thickness_voxels] * 3)
    return mask - eroded


def keep_largest_island(mask: sitk.Image) -> sitk.Image:
    """Keep only the largest connected component."""
    components = sitk.ConnectedComponent(mask)
    labeled = sitk.RelabelComponent(components)
    return sitk.BinaryThreshold(
        labeled, lowerThreshold=1, upperThreshold=1, insideValue=1, outsideValue=0
    )


def remove_small_islands(mask: sitk.Image, min_voxel_count: int) -> sitk.Image:
    """Remove connected components smaller than min_voxel_count."""
    components = sitk.ConnectedComponent(mask)
    relabeled = sitk.RelabelComponent(components)
    stats = sitk.LabelShapeStatisticsImageFilter()
    stats.Execute(relabeled)
    keep = [
        label
        for label in stats.GetLabels()
        if stats.GetNumberOfPixels(label) >= min_voxel_count
    ]
    out = sitk.Image(mask.GetSize(), mask.GetPixelIDValue())
    out.CopyInformation(mask)
    for label in keep:
        out += sitk.BinaryThreshold(relabeled, label, label, 1, 0)
    return out


def logical_operation(a: sitk.Image, b: sitk.Image, op: str) -> sitk.Image:
    """Apply a logical operator between two binary masks."""
    if op == "union":
        return sitk.Or(a, b)
    if op == "intersection":
        return sitk.And(a, b)
    if op == "difference":
        return sitk.And(a, sitk.Not(b))
    if op == "xor":
        return sitk.Xor(a, b)
    raise ValueError(f"Unknown op: {op}")


def mask_volume(source: sitk.Image, mask: sitk.Image, fill_value: float = 0) -> sitk.Image:
    """Mask a source intensity volume with a binary mask."""
    return sitk.Mask(source, mask, outsideValue=fill_value)


def interpolate_between_slices(mask: sitk.Image, axis: int = 2) -> sitk.Image:
    """
    Interpolate masks on empty slices between annotated slices along the given axis.
    Uses linear interpolation with a 0.5 threshold.
    """
    arr = sitk.GetArrayFromImage(mask).astype(np.float32)
    if axis != 2:
        # For non-Z axes, swap so the axis of interpolation is axis 0
        arr = np.swapaxes(arr, 0, axis)

    # Find annotated slices
    annotated = [i for i in range(arr.shape[0]) if arr[i].sum() > 0]
    if len(annotated) < 2:
        if axis != 2:
            arr = np.swapaxes(arr, 0, axis)
        return sitk.GetImageFromArray(arr.astype(np.uint8))

    for i in range(len(annotated) - 1):
        zA, zB = annotated[i], annotated[i + 1]
        if zB - zA <= 1:
            continue
        for z in range(zA + 1, zB):
            t = (z - zA) / (zB - zA)
            arr[z] = (arr[zA] * (1 - t) + arr[zB] * t >= 0.5).astype(np.float32)

    if axis != 2:
        arr = np.swapaxes(arr, 0, axis)
    result = sitk.GetImageFromArray(arr.astype(np.uint8))
    result.CopyInformation(mask)
    return result
