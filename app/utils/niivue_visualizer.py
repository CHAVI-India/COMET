"""
NiiVue WebGL Visualization Module

This module provides functionality to prepare NIfTI files for WebGL-based visualization
using the niivue library. Unlike the matplotlib-based visualizer, this approach:
- Uses GPU-accelerated rendering in the browser
- Provides instant slice navigation without pre-rendering
- Supports real-time windowing and overlay adjustments
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict
import json
from django.conf import settings

logger = logging.getLogger(__name__)


def prepare_niivue_data(
    image_series_id: int,
    roi_names: Optional[List[str]] = None,
    include_staple: bool = True
) -> Dict:
    """
    Prepare NIfTI file paths and metadata for niivue visualization.
    
    This function doesn't generate any images - it just prepares the file paths
    and metadata that the browser-based niivue viewer will use to load and render
    the volumes directly using WebGL.
    
    Args:
        image_series_id: ID of the image series (CT/MR)
        roi_names: List of ROI names to visualize (if None, visualize all)
        include_staple: Whether to include STAPLE contours
        
    Returns:
        Dictionary containing:
        - base_image: Path to the base NIfTI image
        - overlays: List of overlay NIfTI files with metadata
        - metadata: Additional information (modality, windowing defaults, etc.)
    """
    from app.models import DICOMSeries, DICOMInstance
    from app.utils.dcm_to_nifti_converter import sanitize_for_path
    
    try:
        # Get the image series
        image_series = DICOMSeries.objects.select_related(
            'study', 'study__patient'
        ).get(id=image_series_id)
        
        # Check if NIfTI file exists
        if not image_series.nifti_file_path:
            raise ValueError(f"No NIfTI file found for series {image_series_id}")
        
        image_path = Path(settings.MEDIA_ROOT) / image_series.nifti_file_path
        
        # For image series (CT/MR), nifti_file_path is the .nii.gz file itself
        # Ensure the path exists and has the correct extension
        if not image_path.exists():
            raise ValueError(f"NIfTI file not found: {image_path}")
        
        # Ensure the URL includes the .nii.gz extension for niivue to detect file type
        if image_path.is_file():
            base_image_url = str(Path(image_series.nifti_file_path))
        else:
            # If it's a directory, this shouldn't happen for image series, but handle it
            raise ValueError(f"Expected NIfTI file but got directory: {image_path}")
        
        # Set default windowing for CT
        window_center = None
        window_width = None
        if image_series.modality == 'CT':
            window_center = 40
            window_width = 400
        
        # Find all RTStruct series that reference this image series
        rtstruct_series = DICOMSeries.objects.filter(
            modality='RTSTRUCT',
            dicominstance__referenced_series_instance_uid=image_series,
            nifti_file_path__isnull=False
        ).exclude(nifti_file_path='').distinct()
        
        # Collect all available ROIs
        all_rois = {}
        for rtstruct in rtstruct_series:
            nifti_dir = Path(settings.MEDIA_ROOT) / rtstruct.nifti_file_path
            metadata_path = nifti_dir / "rtstruct_metadata.json"
            
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    for roi in metadata.get('rois', []):
                        roi_name = roi['name']
                        if roi_names is None or roi_name in roi_names:
                            if roi_name not in all_rois:
                                all_rois[roi_name] = []
                            
                            # Check if mask file exists
                            safe_roi_name = sanitize_for_path(roi_name)
                            mask_path = nifti_dir / f"{safe_roi_name}.nii.gz"
                            
                            if mask_path.exists():
                                relative_mask_path = mask_path.relative_to(settings.MEDIA_ROOT)
                                all_rois[roi_name].append({
                                    'path': str(relative_mask_path),
                                    'series_uid': rtstruct.series_instance_uid
                                })
        
        # Colors for different structure sets - RGB values for niivue
        colors = [
            [255, 0, 0],      # red
            [0, 255, 0],      # green
            [0, 0, 255],      # blue
            [255, 255, 0],    # yellow
            [0, 255, 255],    # cyan
            [255, 0, 255],    # magenta
            [255, 165, 0],    # orange
            [128, 0, 255],    # purple
        ]
        
        # Prepare overlay list
        overlays = []
        global_color_idx = 0
        
        for roi_name, mask_infos in all_rois.items():
            if mask_infos:
                for idx, mask_info in enumerate(mask_infos):
                    # Label with structure set number if multiple
                    if len(mask_infos) > 1:
                        label = f"{roi_name} (SS{idx+1})"
                    else:
                        label = roi_name
                    
                    # Assign color
                    color = colors[global_color_idx % len(colors)]
                    
                    overlays.append({
                        'url': mask_info['path'],
                        'name': label,
                        'colormap': 'custom',
                        'color': color,
                        'opacity': 0.5,
                        'roi_name': roi_name
                    })
                    global_color_idx += 1
                    logger.info(f"Added overlay for ROI: {label}")
            
            # Check for STAPLE contour from database
            if include_staple:
                from app.models import StapleROI, RTStructROI
                
                # Find RTStructROI records with this roi_name that have a staple_roi
                # First, try without the series filter to see if any exist
                all_matching = RTStructROI.objects.filter(
                    roi_name=roi_name,
                    staple_roi__isnull=False
                ).select_related('staple_roi', 'instance').distinct()
                
                logger.info(f"Found {all_matching.count()} RTStructROI records with roi_name={roi_name} and staple_roi set")
                
                # Now filter by the image series
                rtstruct_rois = all_matching.filter(
                    instance__referenced_series_instance_uid=image_series
                )
                
                logger.info(f"After filtering by image series, found {rtstruct_rois.count()} matching records")
                
                for rtstruct_roi in rtstruct_rois:
                    staple_roi = rtstruct_roi.staple_roi
                    logger.info(f"Checking STAPLE ROI with file path: {staple_roi.staple_roi_file_path}")
                    
                    if staple_roi and staple_roi.staple_roi_file_path:
                        staple_path = Path(settings.MEDIA_ROOT) / staple_roi.staple_roi_file_path
                        logger.info(f"Full STAPLE path: {staple_path}, exists: {staple_path.exists()}")
                        
                        if staple_path.exists():
                            relative_staple_path = staple_path.relative_to(settings.MEDIA_ROOT)
                            overlays.append({
                                'url': str(relative_staple_path),
                                'name': f'⭐ STAPLE {roi_name}',
                                'colormap': 'custom',
                                'color': [255, 215, 0],  # gold
                                'opacity': 0.6,
                                'roi_name': roi_name
                            })
                            logger.info(f"Added STAPLE overlay for ROI: {roi_name}")
                            break  # Only add one STAPLE per ROI
        
        # Prepare result
        result = {
            'base_image': {
                'url': base_image_url,
                'name': f"{image_series.modality} Image"
            },
            'overlays': overlays,
            'metadata': {
                'patient_id': image_series.study.patient.patient_id,
                'patient_name': image_series.study.patient.patient_name or '',
                'modality': image_series.modality,
                'series_uid': image_series.series_instance_uid,
                'window_center': window_center,
                'window_width': window_width,
                'total_overlays': len(overlays)
            }
        }
        
        logger.info(f"Prepared niivue data: base image + {len(overlays)} overlays")
        return result
        
    except Exception as e:
        logger.error(f"Error in prepare_niivue_data: {e}")
        raise


def get_available_rois(image_series_id: int) -> List[Dict]:
    """
    Get list of available ROIs for an image series.
    
    Args:
        image_series_id: ID of the image series
        
    Returns:
        List of dictionaries with ROI information
    """
    from app.models import DICOMSeries
    from app.utils.dcm_to_nifti_converter import sanitize_for_path
    
    try:
        image_series = DICOMSeries.objects.select_related(
            'study', 'study__patient'
        ).get(id=image_series_id)
        
        # Find all RTStruct series that reference this image series
        rtstruct_series = DICOMSeries.objects.filter(
            modality='RTSTRUCT',
            dicominstance__referenced_series_instance_uid=image_series,
            nifti_file_path__isnull=False
        ).exclude(nifti_file_path='').distinct()
        
        # Collect all available ROIs
        all_rois = {}
        for rtstruct in rtstruct_series:
            nifti_dir = Path(settings.MEDIA_ROOT) / rtstruct.nifti_file_path
            metadata_path = nifti_dir / "rtstruct_metadata.json"
            
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    for roi in metadata.get('rois', []):
                        roi_name = roi['name']
                        if roi_name not in all_rois:
                            all_rois[roi_name] = {
                                'name': roi_name,
                                'structure_sets': [],
                                'has_staple': False
                            }
                        
                        all_rois[roi_name]['structure_sets'].append({
                            'series_id': rtstruct.id,
                            'series_uid': rtstruct.series_instance_uid
                        })
        
        # Check for STAPLE contours
        patient_id = sanitize_for_path(image_series.study.patient.patient_id)
        study_uid = sanitize_for_path(image_series.study.study_instance_uid)
        series_uid = sanitize_for_path(image_series.series_instance_uid)
        staple_dir = Path(settings.MEDIA_ROOT) / "nifti_files" / patient_id / study_uid / series_uid / "staple"
        
        if staple_dir.exists():
            for roi_name in all_rois.keys():
                safe_roi_name = sanitize_for_path(roi_name)
                staple_path = staple_dir / f"staple_{safe_roi_name}.nii.gz"
                if staple_path.exists():
                    all_rois[roi_name]['has_staple'] = True
        
        # Sort ROIs by name
        rois_list = sorted(all_rois.values(), key=lambda x: x['name'])
        return rois_list
        
    except Exception as e:
        logger.error(f"Error getting available ROIs: {e}")
        raise
