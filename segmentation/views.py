"""Views for the segmentation app: editor page, DICOM serving, save, tools, management."""
import os
import json
import base64
import gzip
import logging
from typing import List

import numpy as np
import SimpleITK as sitk
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.db import transaction

from app.models import DICOMSeries, DICOMInstance, RTStructROI
from segmentation.models import SegmentationSession, UserSegmentation
from segmentation.utils.dicom_volume import get_ordered_dicom_files, get_series_dicom_dir
from segmentation.utils.rtstruct_exporter import create_rtstruct_from_masks, _read_reference_image
from segmentation.utils.tools.morphology import (
    gaussian_smooth,
    median_smooth,
    apply_margin,
    hollow,
    keep_largest_island,
    remove_small_islands,
    logical_operation,
    mask_volume,
    interpolate_between_slices,
)
from segmentation.utils.tools.mesh_decimate import decimate_mesh
from segmentation.utils.tools.mesh_rasterize import mesh_to_labelmap

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Editor page
# ---------------------------------------------------------------------------

@login_required
def segmentation_editor(request, series_id):
    """Render the segmentation editor page for a source DICOM series."""
    series = get_object_or_404(DICOMSeries, id=series_id)
    return render(
        request,
        "segmentation/segmentation_editor.html",
        {
            "series": series,
            "patient": series.study.patient,
            "study": series.study,
        },
    )


# ---------------------------------------------------------------------------
# DICOM serving API for ITK-Wasm
# ---------------------------------------------------------------------------

@login_required
def series_dicom_files(request, series_id):
    """Return a JSON list of authenticated DICOM file URLs for a series."""
    series = get_object_or_404(DICOMSeries, id=series_id)
    files = get_ordered_dicom_files(series)
    return JsonResponse(
        {
            "series_instance_uid": series.series_instance_uid,
            "modality": series.modality,
            "files": files,
            "count": len(files),
        }
    )


@login_required
def serve_dicom_file(request, instance_id):
    """Stream a raw DICOM file to the authenticated browser."""
    instance = get_object_or_404(DICOMInstance, id=instance_id)
    if not instance.instance_file_path or not os.path.exists(instance.instance_file_path):
        return JsonResponse({"error": "DICOM file not found"}, status=404)
    return FileResponse(
        open(instance.instance_file_path, "rb"),
        content_type="application/dicom",
    )


# ---------------------------------------------------------------------------
# Helpers for decoding labelmaps from the browser
# ---------------------------------------------------------------------------

def _decode_labelmap(roi_data: dict) -> np.ndarray:
    """Decode a base64+gzip labelmap + shape into a numpy array."""
    shape = tuple(roi_data["shape"])  # (z, y, x)
    compressed = base64.b64decode(roi_data["labelmap"])
    raw = gzip.decompress(compressed)
    return np.frombuffer(raw, dtype=np.uint8).reshape(shape)


def _labelmap_to_sitk(mask: np.ndarray, reference_image: sitk.Image) -> sitk.Image:
    """Wrap a numpy mask (z, y, x) as a SimpleITK image with reference geometry."""
    img = sitk.GetImageFromArray(mask.astype(np.uint8))
    img.CopyInformation(reference_image)
    return img


def _sitk_to_labelmap_bytes(img: sitk.Image) -> dict:
    """Serialize a SimpleITK labelmap to base64 + shape for the browser."""
    arr = sitk.GetArrayFromImage(img).astype(np.uint8)
    return {
        "labelmap": base64.b64encode(arr.tobytes()).decode("ascii"),
        "shape": list(arr.shape),
    }


# ---------------------------------------------------------------------------
# Save labelmap -> RTSTRUCT
# ---------------------------------------------------------------------------

@login_required
@require_POST
def save_segmentation(request, series_id):
    """Save one or more browser-produced ROI labelmaps as a single DICOM RTSTRUCT."""
    try:
        image_series = get_object_or_404(DICOMSeries, id=series_id)
        data = json.loads(request.body)
        rois_data = data.get("rois", [])
        if not rois_data:
            return JsonResponse(
                {"success": False, "error": "No ROIs provided"}, status=400
            )

        roi_inputs = []
        seen_names = set()
        for roi in rois_data:
            name = str(roi.get("roi_name", "")).strip()
            if not name:
                return JsonResponse(
                    {"success": False, "error": "Every ROI must have a name"}, status=400
                )
            if name in seen_names:
                return JsonResponse(
                    {"success": False, "error": f"Duplicate ROI name: {name}"}, status=400
                )
            seen_names.add(name)
            labelmap = _decode_labelmap(roi)
            color = roi.get("color", [255, 0, 0])
            roi_inputs.append((labelmap, name, color))

        session, _ = SegmentationSession.objects.get_or_create(
            user=request.user, image_series=image_series
        )

        from pydicom import dcmread

        rtstruct_path = create_rtstruct_from_masks(roi_inputs, image_series)

        ds = dcmread(str(rtstruct_path))
        series_uid = str(ds.SeriesInstanceUID)
        sop_uid = str(ds.SOPInstanceUID)

        with transaction.atomic():
            rtstruct_series, _ = DICOMSeries.objects.get_or_create(
                series_instance_uid=series_uid,
                defaults={
                    "study": image_series.study,
                    "modality": "RTSTRUCT",
                },
            )
            instance, _ = DICOMInstance.objects.update_or_create(
                sop_instance_uid=sop_uid,
                defaults={
                    "series": rtstruct_series,
                    "instance_file_path": str(rtstruct_path),
                    "referenced_series_instance_uid": image_series,
                },
            )
            segmentations = []
            for _, name, _ in roi_inputs:
                segmentation, _ = UserSegmentation.objects.update_or_create(
                    session=session,
                    roi_name=name,
                    defaults={
                        "rtstruct_instance": instance,
                        "finalized": True,
                    },
                )
                segmentations.append(segmentation)
                RTStructROI.objects.update_or_create(
                    instance=instance,
                    roi_name=name,
                    defaults={
                        "roi_segmentation_username_id": request.user,
                        "roi_description": f"User segmentation by {request.user.username}",
                        "roi_generation_algorithm": "ITK-Wasm + vtk.js labelmap editor",
                    },
                )

        return JsonResponse(
            {
                "success": True,
                "segmentation_ids": [seg.id for seg in segmentations],
                "rtstruct_instance_id": instance.id,
                "rtstruct_path": str(rtstruct_path),
            }
        )
    except Exception as e:
        logger.exception("save_segmentation failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# Server-side tool endpoints
# ---------------------------------------------------------------------------

def _run_tool(request, series_id, fn):
    """Common boilerplate: decode labelmap, run a SimpleITK tool, return result."""
    try:
        series = get_object_or_404(DICOMSeries, id=series_id)
        data = json.loads(request.body)
        mask_arr = _decode_labelmap(data)
        params = data.get("params", {})

        ref = _read_reference_image(series)
        sitk_mask = _labelmap_to_sitk(mask_arr, ref)
        result = fn(sitk_mask, **params)
        return JsonResponse(_sitk_to_labelmap_bytes(result))
    except Exception as e:
        logger.exception("tool failed")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def tool_smooth(request, series_id):
    return _run_tool(request, series_id, lambda m, **p: (
        gaussian_smooth(m, p.get("sigma_mm", 1.0)) if p.get("method", "gaussian") == "gaussian"
        else median_smooth(m, p.get("radius", 1))
    ))


@login_required
@require_POST
def tool_margin(request, series_id):
    return _run_tool(request, series_id, lambda m, **p: apply_margin(m, p.get("margin_mm", 2.0)))


@login_required
@require_POST
def tool_hollow(request, series_id):
    return _run_tool(request, series_id, lambda m, **p: hollow(m, p.get("thickness_voxels", 1)))


@login_required
@require_POST
def tool_islands(request, series_id):
    def _islands(m, **p):
        if p.get("mode", "keep_largest") == "keep_largest":
            return keep_largest_island(m)
        return remove_small_islands(m, p.get("min_voxel_count", 100))
    return _run_tool(request, series_id, _islands)


@login_required
@require_POST
def tool_interpolate(request, series_id):
    return _run_tool(request, series_id, lambda m, **p: interpolate_between_slices(m, p.get("axis", 2)))


@login_required
@require_POST
def tool_logical(request, series_id):
    try:
        series = get_object_or_404(DICOMSeries, id=series_id)
        data = json.loads(request.body)
        shape = tuple(data["shape"])
        mask_a = np.frombuffer(base64.b64decode(data["labelmap"]), dtype=np.uint8).reshape(shape)
        mask_b = np.frombuffer(base64.b64decode(data["labelmap_b"]), dtype=np.uint8).reshape(shape)
        op = data.get("op", "union")
        ref = _read_reference_image(series)
        sitk_a = _labelmap_to_sitk(mask_a, ref)
        sitk_b = _labelmap_to_sitk(mask_b, ref)
        result = logical_operation(sitk_a, sitk_b, op)
        return JsonResponse(_sitk_to_labelmap_bytes(result))
    except Exception as e:
        logger.exception("logical tool failed")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def tool_mesh_decimate(request, segmentation_id):
    """Server-side mesh decimation using Python VTK."""
    try:
        data = json.loads(request.body)
        vertices = data["vertices"]
        triangles = data["triangles"]
        target_reduction = data.get("target_reduction", 0.5)
        out_verts, out_tris = decimate_mesh(vertices, triangles, target_reduction)
        return JsonResponse({"vertices": out_verts, "triangles": out_tris})
    except Exception as e:
        logger.exception("mesh decimate failed")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def tool_mesh_rasterize(request, series_id):
    """Convert an edited surface mesh back into a labelmap."""
    try:
        series = get_object_or_404(DICOMSeries, id=series_id)
        data = json.loads(request.body)
        vertices = data["vertices"]
        triangles = data["triangles"]
        ref = _read_reference_image(series)
        sitk_label = mesh_to_labelmap(vertices, triangles, ref)
        return JsonResponse(_sitk_to_labelmap_bytes(sitk_label))
    except Exception as e:
        logger.exception("mesh rasterize failed")
        return JsonResponse({"error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# Segmentation management UI and API
# ---------------------------------------------------------------------------

@login_required
def segmentation_sessions_list(request):
    """List all segmentation sessions for the logged-in user."""
    sessions = SegmentationSession.objects.filter(
        user=request.user
    ).select_related("image_series__study__patient").order_by("-modified_at")
    return render(
        request,
        "segmentation/segmentation_list.html",
        {"sessions": sessions},
    )


@login_required
def segmentation_session_detail(request, session_id):
    """Show all segmentations within a session."""
    session = get_object_or_404(
        SegmentationSession, id=session_id, user=request.user
    )
    segmentations = session.segmentations.all().order_by("-modified_at")
    return render(
        request,
        "segmentation/segmentation_detail.html",
        {"session": session, "segmentations": segmentations},
    )


@login_required
@require_POST
def rename_segmentation(request, segmentation_id):
    """Rename a user segmentation's ROI."""
    seg = get_object_or_404(
        UserSegmentation, id=segmentation_id, session__user=request.user
    )
    try:
        data = json.loads(request.body)
        new_name = data.get("roi_name", "").strip()
        if not new_name:
            return JsonResponse(
                {"success": False, "error": "ROI name required"}, status=400
            )
        seg.roi_name = new_name
        seg.save()
        if seg.rtstruct_instance:
            RTStructROI.objects.filter(
                instance=seg.rtstruct_instance, roi_name__isnull=False
            ).update(roi_name=new_name)
        return JsonResponse({"success": True, "roi_name": new_name})
    except Exception as e:
        logger.exception("rename failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_POST
def delete_segmentation(request, segmentation_id):
    """Delete a user segmentation and its RTSTRUCT file."""
    seg = get_object_or_404(
        UserSegmentation, id=segmentation_id, session__user=request.user
    )
    try:
        # Delete the RTSTRUCT file on disk
        if seg.rtstruct_instance and seg.rtstruct_instance.instance_file_path:
            if os.path.exists(seg.rtstruct_instance.instance_file_path):
                os.remove(seg.rtstruct_instance.instance_file_path)
            seg.rtstruct_instance.delete()
        seg.delete()
        return JsonResponse({"success": True})
    except Exception as e:
        logger.exception("delete failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_POST
def duplicate_segmentation(request, segmentation_id):
    """Duplicate a user segmentation within the same session."""
    seg = get_object_or_404(
        UserSegmentation, id=segmentation_id, session__user=request.user
    )
    try:
        new_seg = UserSegmentation.objects.create(
            session=seg.session,
            roi_name=f"{seg.roi_name} (copy)",
            labelmap_data=seg.labelmap_data,
            labelmap_shape=seg.labelmap_shape,
            finalized=seg.finalized,
        )
        return JsonResponse({"success": True, "segmentation_id": new_seg.id})
    except Exception as e:
        logger.exception("duplicate failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def export_rtstruct(request, segmentation_id):
    """Download the RTSTRUCT DICOM file for a segmentation."""
    seg = get_object_or_404(
        UserSegmentation, id=segmentation_id, session__user=request.user
    )
    if not seg.rtstruct_instance or not seg.rtstruct_instance.instance_file_path:
        return JsonResponse({"error": "No RTSTRUCT file"}, status=404)
    path = seg.rtstruct_instance.instance_file_path
    if not os.path.exists(path):
        return JsonResponse({"error": "RTSTRUCT file not found on disk"}, status=404)
    resp = FileResponse(open(path, "rb"), content_type="application/dicom")
    resp["Content-Disposition"] = (
        f'attachment; filename="RTSTRUCT_{seg.roi_name}.dcm"'
    )
    return resp


@login_required
def export_nifti(request, segmentation_id):
    """Generate and download a NIfTI mask from the segmentation's RTSTRUCT."""
    import nibabel as nib
    import tempfile

    seg = get_object_or_404(
        UserSegmentation, id=segmentation_id, session__user=request.user
    )
    if not seg.rtstruct_instance or not seg.rtstruct_instance.instance_file_path:
        return JsonResponse({"error": "No RTSTRUCT file"}, status=404)

    try:
        from dcmrtstruct2nii import Dcmrtstruct2nii

        # Get the source DICOM directory
        ref_series = seg.rtstruct_instance.referenced_series_instance_uid
        if not ref_series:
            return JsonResponse({"error": "No source series referenced"}, status=400)
        dicom_dir = get_series_dicom_dir(ref_series)

        tmp_dir = tempfile.mkdtemp(prefix="nifti_export_")
        converter = Dcmrtstruct2nii()
        converter.convert_from_file(
            seg.rtstruct_instance.instance_file_path, str(dicom_dir), tmp_dir
        )

        # Find the generated mask file
        import glob

        mask_files = glob.glob(os.path.join(tmp_dir, "*.nii.gz"))
        if not mask_files:
            return JsonResponse({"error": "NIfTI conversion produced no files"}, status=500)

        with open(mask_files[0], "rb") as f:
            content = f.read()

        # Clean up temp dir
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)

        resp = HttpResponse(content, content_type="application/gzip")
        resp["Content-Disposition"] = (
            f'attachment; filename="{seg.roi_name}.nii.gz"'
        )
        return resp
    except Exception as e:
        logger.exception("NIfTI export failed")
        return JsonResponse({"error": str(e)}, status=500)

