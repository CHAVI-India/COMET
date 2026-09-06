"""Convert binary labelmaps into a DICOM RTStructureSet using rt-utils."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import SimpleITK as sitk
from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from rt_utils import RTStructBuilder
from rt_utils.image_helper import load_sorted_image_series

from django.conf import settings

from app.models import DICOMInstance
from app.utils.dcm_to_nifti_converter import sanitize_for_path
from segmentation.utils.dicom_volume import get_series_dicom_dir, get_ordered_dicom_files

logger = logging.getLogger(__name__)


def _read_reference_image(series) -> sitk.Image:
    """Read the source DICOM series as a SimpleITK image for geometry reference."""
    dicom_dir = get_series_dicom_dir(series)
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(str(dicom_dir))
    if not dicom_names:
        raise ValueError(f"No GDCM-readable DICOM files in {dicom_dir}")
    reader.SetFileNames(dicom_names)
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    return reader.Execute()


def ensure_mask_geometry_matches_series(
    mask_image: sitk.Image, reference_image: sitk.Image
) -> sitk.Image:
    """Resample a binary mask to the exact geometry of the reference DICOM image."""
    return sitk.Resample(
        mask_image,
        reference_image,
        sitk.Transform(),
        sitk.sitkNearestNeighbor,
        0,
        mask_image.GetPixelID(),
    )


def _load_sorted_series_data(series) -> List[Dataset]:
    """Load source DICOM series datasets in the same order as the mask z-axis."""
    dicom_dir = get_series_dicom_dir(series)
    return load_sorted_image_series(str(dicom_dir))


def _verify_sop_alignment(series, series_data: List[Dataset]) -> None:
    """
    Verify that the on-disk DICOM ordering matches the rt-utils series ordering.

    The frontend draws on a volume whose z-axis is ordered by the DICOM file list
    we provide. That list is sorted by physical slice position (same as GDCM/rt-utils).
    If the two orderings ever diverge, the SOP Instance UID references inside each
    contour would point to the wrong slice, so we raise a clear error instead.
    """
    ordered_files = get_ordered_dicom_files(series)
    if len(ordered_files) != len(series_data):
        raise ValueError(
            f"DICOM ordering mismatch: {len(ordered_files)} files in DB but "
            f"{len(series_data)} slices loaded by rt-utils"
        )
    for idx, (file_info, ds) in enumerate(zip(ordered_files, series_data)):
        if file_info["sop_instance_uid"] != ds.SOPInstanceUID:
            raise ValueError(
                f"SOP Instance UID mismatch at z={idx}: "
                f"frontend order has {file_info['sop_instance_uid']}, "
                f"rt-utils order has {ds.SOPInstanceUID}"
            )


def create_rtstruct_from_mask(
    mask: np.ndarray,
    source_series,
    structure_name: str,
    color: Optional[List[int]] = None,
) -> Path:
    """
    Build a DICOM RTSTRUCT from a single 3D binary mask aligned to the source series.

    Parameters
    ----------
    mask : np.ndarray
        3D uint8 array with the same shape as the source DICOM volume
        (SimpleITK ordering: z, y, x).
    source_series : DICOMSeries
        The image series the mask was drawn on.
    structure_name : str
        ROI name to write into the RTSTRUCT.
    color : list[int], optional
        RGB color for the ROI. Defaults to red.

    Returns
    -------
    Path
        Filesystem path of the generated RTSTRUCT DICOM file.
    """
    return create_rtstruct_from_masks(
        [(mask, structure_name, color or [255, 0, 0])], source_series
    )


def create_rtstruct_from_masks(
    rois: List[tuple],
    source_series,
) -> Path:
    """
    Build a single DICOM RTSTRUCT from multiple binary masks.

    Parameters
    ----------
    rois : list of (mask, name, color)
        Each mask is a 3D uint8 array in (z, y, x) order. Names must be unique.
        The z-axis is expected to be in the same physical-slice-position order as
        the source DICOM series (ascending), matching the ordering produced by
        GDCM/SimpleITK/rt-utils.
    source_series : DICOMSeries
        The image series the masks were drawn on.

    Returns
    -------
    Path
        Filesystem path of the generated RTSTRUCT DICOM file.
    """
    reference_image = _read_reference_image(source_series)
    ref_size = reference_image.GetSize()  # (x, y, z) in ITK order
    expected_shape = (ref_size[2], ref_size[1], ref_size[0])  # (z, y, x)

    dicom_dir = get_series_dicom_dir(source_series)
    rtstruct = RTStructBuilder.create_new(str(dicom_dir))
    # The mask order is assumed to match the physical slice position order used
    # by rt-utils. We verify this against the canonical file list we serve.
    _verify_sop_alignment(source_series, rtstruct.series_data)

    for mask, structure_name, color in rois:
        if mask.shape != expected_shape:
            raise ValueError(
                f"Mask shape {mask.shape} does not match reference volume {expected_shape}"
            )
        sitk_mask = sitk.GetImageFromArray(mask.astype(np.uint8))
        sitk_mask.CopyInformation(reference_image)
        sitk_mask = ensure_mask_geometry_matches_series(sitk_mask, reference_image)
        aligned_mask = sitk.GetArrayFromImage(sitk_mask).astype(np.uint8)
        # rt-utils expects the mask in (rows, cols, slices) = (y, x, z) order
        rtstruct_mask = np.transpose(aligned_mask, (1, 2, 0))
        rtstruct.add_roi(
            mask=rtstruct_mask.astype(bool),
            color=[int(c) for c in color],
            name=structure_name,
        )

    # Output path under MEDIA_ROOT/dicom_files/<patient>/<study>/<series>/
    patient_id = sanitize_for_path(source_series.study.patient.patient_id)
    study_uid = sanitize_for_path(source_series.study.study_instance_uid)
    series_uid = sanitize_for_path(source_series.series_instance_uid)
    out_dir = Path(settings.MEDIA_ROOT) / "dicom_files" / patient_id / study_uid / series_uid
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "RTSTRUCT_segmentation.dcm"
    rtstruct.save(str(out_path))
    logger.info("Wrote RTSTRUCT to %s with %d ROI(s)", out_path, len(rois))
    return out_path


def get_rtstruct_contour_references(rtstruct_path: Path) -> List[List[str]]:
    """Return the ReferencedSOPInstanceUID for each contour in an RTSTRUCT."""
    ds = dcmread(str(rtstruct_path))
    refs = []
    for roi_contour in ds.get("ROIContourSequence", Sequence()):
        for contour in roi_contour.get("ContourSequence", Sequence()):
            uids = [
                img.ReferencedSOPInstanceUID
                for img in contour.get("ContourImageSequence", Sequence())
            ]
            refs.append(uids)
    return refs
