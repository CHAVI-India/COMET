"""Helpers for collecting and serving DICOM series files for ITK-Wasm."""
from pathlib import Path
from typing import List, Dict

from pydicom import dcmread
import numpy as np

from django.conf import settings

from app.models import DICOMInstance


def _slice_position(ds) -> float:
    """Compute physical position of a DICOM slice along the slice normal."""
    try:
        iop = [float(x) for x in ds.ImageOrientationPatient]
    except Exception:
        return 0.0
    # Row and column direction cosines
    row_dir = np.array(iop[0:3])
    col_dir = np.array(iop[3:6])
    slice_dir = np.cross(row_dir, col_dir)
    try:
        ipp = [float(x) for x in ds.ImagePositionPatient]
    except Exception:
        return 0.0
    return float(np.dot(slice_dir, ipp))


def get_ordered_dicom_files(series) -> List[Dict]:
    """
    Return an ordered list of DICOM file descriptors for a series.
    Each descriptor contains the instance id, SOP UID, instance number,
    and an authenticated URL the browser can fetch.

    The list is sorted by physical slice position (ImagePositionPatient projected
    onto the slice normal) so that the order matches SimpleITK / GDCM and rt-utils.
    """
    instances = DICOMInstance.objects.filter(series=series)
    files = []
    for inst in instances:
        if not inst.instance_file_path:
            continue
        path = Path(inst.instance_file_path)
        if not path.is_absolute():
            path = Path(settings.MEDIA_ROOT) / path
        if not path.exists():
            continue
        try:
            ds = dcmread(str(path), stop_before_pixels=True)
            position = _slice_position(ds)
        except Exception:
            position = 0.0
        files.append(
            {
                "instance_id": inst.id,
                "sop_instance_uid": inst.sop_instance_uid,
                "instance_number": inst.instance_number,
                "position": position,
                "url": f"/segmentation/api/file/{inst.id}/",
            }
        )
    # Sort by physical slice position ascending, matching GDCM/SimpleITK/rt-utils
    files.sort(key=lambda x: x["position"])
    return files


def get_series_dicom_dir(series) -> Path:
    """
    Return the on-disk directory containing the DICOM files for a series.
    Raises ValueError if no files are found.
    """
    first = (
        DICOMInstance.objects.filter(series=series, instance_file_path__isnull=False)
        .exclude(instance_file_path="")
        .first()
    )
    if not first or not first.instance_file_path:
        raise ValueError("Source series has no DICOM files")
    path = Path(first.instance_file_path)
    if not path.is_absolute():
        path = Path(settings.MEDIA_ROOT) / path
    if not path.exists():
        raise ValueError(f"DICOM file not found on disk: {path}")
    return path.parent
