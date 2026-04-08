"""
DICOM to NIfTI Converter Module

This module provides functionality to convert DICOM image series and RTStruct files
to compressed NIfTI format using dcmrtstruct2nii library.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple, List
import SimpleITK as sitk
import numpy as np
from django.conf import settings
from django.db import transaction
from dcmrtstruct2nii.adapters.convert.rtstructcontour2mask import DcmPatientCoords2Mask
from app.utils.patched_rtstructinputadapter import (
    PatchedRtStructInputAdapter as RtStructInputAdapter,
)
from dcmrtstruct2nii.adapters.input.image.dcminputadapter import DcmInputAdapter
from dcmrtstruct2nii.adapters.output.niioutputadapter import NiiOutputAdapter
from dcmrtstruct2nii.exceptions import (
    ContourOutOfBoundsException,
    PathDoesNotExistException,
)

logger = logging.getLogger(__name__)


def sanitize_for_path(name: str) -> str:
    """Sanitize a string to be safe for use in file paths."""
    import re
    # Replace any character that's not alphanumeric, underscore, or hyphen with underscore
    sanitized = re.sub(r'[^\w\-]', '_', str(name))
    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized


def get_series_nifti_path(series) -> Path:
    """
    Generate the output directory path for NIfTI files for a given series.
    
    Args:
        series: DICOMSeries model instance
        
    Returns:
        Path object for the NIfTI output directory
    """
    patient_id = sanitize_for_path(series.study.patient.patient_id)
    study_uid = sanitize_for_path(series.study.study_instance_uid)
    series_uid = sanitize_for_path(series.series_instance_uid)
    
    nifti_base = Path(settings.MEDIA_ROOT) / "nifti_files"
    nifti_dir = nifti_base / patient_id / study_uid / series_uid
    nifti_dir.mkdir(parents=True, exist_ok=True)
    
    return nifti_dir


def get_dicom_directory_path(series) -> Optional[Path]:
    """
    Get the directory path containing DICOM files for a series.
    
    Args:
        series: DICOMSeries model instance
        
    Returns:
        Path to directory containing DICOM files, or None if not found
    """
    from app.models import DICOMInstance
    
    # Get first instance to find the directory
    instance = DICOMInstance.objects.filter(series=series).first()
    if not instance or not instance.instance_file_path:
        return None
    
    # Resolve the path
    file_path = Path(instance.instance_file_path)
    if not file_path.is_absolute():
        file_path = Path(settings.MEDIA_ROOT) / file_path
    
    # Return the parent directory
    return file_path.parent


def convert_dicom_series_to_nifti(series, progress_callback=None) -> Tuple[Optional[str], List[str]]:
    """
    Convert a DICOM image series to NIfTI format using dcmrtstruct2nii.
    
    Args:
        series: DICOMSeries model instance
        progress_callback: Optional callback function(progress_pct, message)
        
    Returns:
        Tuple of (nifti_file_path, errors)
    """
    errors = []
    
    try:
        if progress_callback:
            progress_callback(5, f"Starting conversion for series {series.series_instance_uid[:20]}...")
        
        # Get DICOM directory path
        dicom_dir = get_dicom_directory_path(series)
        if not dicom_dir or not dicom_dir.exists():
            errors.append(f"DICOM directory not found for series {series.id}")
            return None, errors
        
        if progress_callback:
            progress_callback(20, f"Reading DICOM files from {dicom_dir.name}...")
        
        # Use DcmInputAdapter to read DICOM series
        # First try with GDCM automatic series detection
        dcm_input_adapter = DcmInputAdapter()
        dicom_image = None
        
        try:
            dicom_image = dcm_input_adapter.ingest(
                str(dicom_dir),
                series_id=series.series_instance_uid
            )
        except Exception as e:
            logger.warning(f"DcmInputAdapter failed with GDCM: {e}")
            logger.info("Attempting manual DICOM file collection...")
            
            # Fallback: Manually read DICOM files using SimpleITK
            # This is needed when GDCM cannot auto-detect the series
            try:
                import pydicom
                from app.models import DICOMInstance
                
                # Get all instances for this series
                instances = DICOMInstance.objects.filter(series=series)
                
                if not instances:
                    errors.append(f"No DICOM instances found for series {series.id}")
                    return None, errors
                
                # Collect file paths with their spatial position
                dicom_files_with_position = []
                for inst in instances:
                    if not inst.instance_file_path:
                        continue
                    
                    file_path = Path(inst.instance_file_path)
                    if not file_path.is_absolute():
                        file_path = Path(settings.MEDIA_ROOT) / file_path
                    
                    if file_path.exists():
                        # Validate it's an image file and get spatial position
                        try:
                            ds = pydicom.dcmread(str(file_path), stop_before_pixels=False)
                            if hasattr(ds, 'Rows') and hasattr(ds, 'Columns'):
                                # Get ImagePositionPatient for sorting along scan direction
                                if hasattr(ds, 'ImagePositionPatient'):
                                    position = ds.ImagePositionPatient
                                    # Use Z coordinate (position[2]) for sorting
                                    # This assumes axial acquisition; for other orientations,
                                    # we'd need to consider ImageOrientationPatient
                                    z_pos = float(position[2])
                                    dicom_files_with_position.append((str(file_path), z_pos))
                                elif hasattr(ds, 'SliceLocation'):
                                    # Fallback to SliceLocation if ImagePositionPatient not available
                                    z_pos = float(ds.SliceLocation)
                                    dicom_files_with_position.append((str(file_path), z_pos))
                                else:
                                    # Last resort: use instance number
                                    z_pos = float(inst.instance_number) if inst.instance_number else 0
                                    dicom_files_with_position.append((str(file_path), z_pos))
                        except Exception as e:
                            logger.warning(f"Skipping invalid DICOM: {file_path.name} - {e}")
                
                if not dicom_files_with_position:
                    errors.append("No valid DICOM image files found")
                    return None, errors
                
                # Sort by spatial position (Z coordinate)
                dicom_files_with_position.sort(key=lambda x: x[1])
                dicom_files = [f[0] for f in dicom_files_with_position]
                
                logger.info(f"Manually collected and sorted {len(dicom_files)} DICOM files by spatial position")
                
                # Read using SimpleITK ImageSeriesReader
                reader = sitk.ImageSeriesReader()
                reader.SetFileNames(dicom_files)
                reader.MetaDataDictionaryArrayUpdateOn()
                reader.LoadPrivateTagsOn()
                dicom_image = reader.Execute()
                
                logger.info(f"Successfully read image: {dicom_image.GetSize()}")
                
            except Exception as e2:
                logger.error(f"Manual DICOM reading also failed: {e2}")
                errors.append(f"Failed to read DICOM series: {str(e2)}")
                return None, errors
        
        if progress_callback:
            progress_callback(60, "DICOM image loaded successfully")
        
        # Generate output path
        nifti_dir = get_series_nifti_path(series)
        modality = series.modality or "IMAGE"
        output_filename = f"{modality}_{series.id}"
        output_path = nifti_dir / output_filename
        
        if progress_callback:
            progress_callback(70, f"Saving to {output_filename}.nii.gz...")
        
        # Write as compressed NIfTI using NiiOutputAdapter
        nii_output_adapter = NiiOutputAdapter()
        nii_output_adapter.write(dicom_image, str(output_path), gzip=True)
        
        if progress_callback:
            progress_callback(90, "NIfTI file saved")
        
        # Update the series model with relative path
        output_file = Path(f"{output_path}.nii.gz")
        relative_path = output_file.relative_to(settings.MEDIA_ROOT)
        series.nifti_file_path = str(relative_path)
        series.save(update_fields=['nifti_file_path'])
        
        if progress_callback:
            progress_callback(100, "Conversion complete")
        
        logger.info(f"Successfully converted series {series.id} to NIfTI: {output_file}")
        return str(relative_path), errors
        
    except Exception as e:
        error_msg = f"Error converting series {series.series_instance_uid}: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        return None, errors


def convert_rtstruct_to_nifti(rtstruct_series, referenced_image_series=None, progress_callback=None) -> Tuple[Optional[str], List[str]]:
    """
    Convert an RTStruct series to NIfTI masks using dcmrtstruct2nii.
    
    Creates separate NIfTI files for each ROI as binary masks.
    
    Args:
        rtstruct_series: DICOMSeries model instance (modality='RTSTRUCT')
        referenced_image_series: DICOMSeries of the referenced image (required)
        progress_callback: Optional callback function(progress_pct, message)
        
    Returns:
        Tuple of (nifti_directory_path, errors)
    """
    errors = []
    
    try:
        if progress_callback:
            progress_callback(5, f"Starting RTStruct conversion for series {rtstruct_series.series_instance_uid[:20]}...")
        
        # Validate referenced image series
        if not referenced_image_series:
            errors.append("Referenced image series is required for RTStruct conversion")
            return None, errors
        
        # Get RTStruct file path
        from app.models import DICOMInstance
        rtstruct_instance = DICOMInstance.objects.filter(series=rtstruct_series).first()
        if not rtstruct_instance or not rtstruct_instance.instance_file_path:
            errors.append(f"RTStruct file not found for series {rtstruct_series.id}")
            return None, errors
        
        rtstruct_file_path = Path(rtstruct_instance.instance_file_path)
        if not rtstruct_file_path.is_absolute():
            rtstruct_file_path = Path(settings.MEDIA_ROOT) / rtstruct_file_path
        
        if not rtstruct_file_path.exists():
            errors.append(f"RTStruct file does not exist: {rtstruct_file_path}")
            return None, errors
        
        if progress_callback:
            progress_callback(10, "Loading referenced image series...")
        
        # Get DICOM directory for referenced image series
        dicom_dir = get_dicom_directory_path(referenced_image_series)
        if not dicom_dir or not dicom_dir.exists():
            errors.append(f"DICOM directory not found for referenced series {referenced_image_series.id}")
            return None, errors
        
        if progress_callback:
            progress_callback(20, "Reading DICOM image series...")
        
        # Load the DICOM image using DcmInputAdapter
        dcm_input_adapter = DcmInputAdapter()
        dicom_image = None
        
        try:
            dicom_image = dcm_input_adapter.ingest(
                str(dicom_dir),
                series_id=referenced_image_series.series_instance_uid
            )
        except Exception as e:
            logger.warning(f"DcmInputAdapter failed with GDCM: {e}")
            logger.info("Attempting manual DICOM file collection for RTStruct reference image...")
            
            # Fallback: Manually read DICOM files using SimpleITK
            try:
                import pydicom
                
                # Get all instances for the referenced series
                instances = DICOMInstance.objects.filter(series=referenced_image_series)
                
                if not instances:
                    errors.append(f"No DICOM instances found for referenced series {referenced_image_series.id}")
                    return None, errors
                
                # Collect file paths with their spatial position
                dicom_files_with_position = []
                for inst in instances:
                    if not inst.instance_file_path:
                        continue
                    
                    file_path = Path(inst.instance_file_path)
                    if not file_path.is_absolute():
                        file_path = Path(settings.MEDIA_ROOT) / file_path
                    
                    if file_path.exists():
                        try:
                            ds = pydicom.dcmread(str(file_path), stop_before_pixels=False)
                            if hasattr(ds, 'Rows') and hasattr(ds, 'Columns'):
                                # Get ImagePositionPatient for sorting along scan direction
                                if hasattr(ds, 'ImagePositionPatient'):
                                    position = ds.ImagePositionPatient
                                    z_pos = float(position[2])
                                    dicom_files_with_position.append((str(file_path), z_pos))
                                elif hasattr(ds, 'SliceLocation'):
                                    z_pos = float(ds.SliceLocation)
                                    dicom_files_with_position.append((str(file_path), z_pos))
                                else:
                                    z_pos = float(inst.instance_number) if inst.instance_number else 0
                                    dicom_files_with_position.append((str(file_path), z_pos))
                        except Exception as e:
                            logger.warning(f"Skipping invalid DICOM: {file_path.name} - {e}")
                
                if not dicom_files_with_position:
                    errors.append("No valid DICOM image files found for reference series")
                    return None, errors
                
                # Sort by spatial position (Z coordinate)
                dicom_files_with_position.sort(key=lambda x: x[1])
                dicom_files = [f[0] for f in dicom_files_with_position]
                
                logger.info(f"Manually collected and sorted {len(dicom_files)} DICOM files by spatial position")
                
                # Read using SimpleITK ImageSeriesReader
                reader = sitk.ImageSeriesReader()
                reader.SetFileNames(dicom_files)
                reader.MetaDataDictionaryArrayUpdateOn()
                reader.LoadPrivateTagsOn()
                dicom_image = reader.Execute()
                
                logger.info(f"Successfully read reference image: {dicom_image.GetSize()}")
                
            except Exception as e2:
                logger.error(f"Manual DICOM reading also failed: {e2}")
                errors.append(f"Failed to read DICOM image series: {str(e2)}")
                return None, errors
        
        if progress_callback:
            progress_callback(30, "Loading RTStruct file...")
        
        # Load RTStruct using RtStructInputAdapter
        rtreader = RtStructInputAdapter()
        try:
            all_rt_structs = rtreader.ingest(str(rtstruct_file_path))
        except Exception as e:
            logger.error(f"Failed to read RTStruct file: {e}")
            errors.append(f"Failed to read RTStruct file: {str(e)}")
            return None, errors
        
        if progress_callback:
            progress_callback(40, f"Found {len(all_rt_structs)} ROI structures")
        
        # Generate output directory
        nifti_dir = get_series_nifti_path(rtstruct_series)
        
        # Initialize converters
        dcm_patient_coords_to_mask = DcmPatientCoords2Mask()
        nii_output_adapter = NiiOutputAdapter()
        
        # Convert each ROI to a mask
        total_rois = len(all_rt_structs)
        converted_count = 0
        
        for idx, rtstruct in enumerate(all_rt_structs, 1):
            roi_name = rtstruct.get("name", f"ROI_{idx}")
            
            if "sequence" not in rtstruct:
                logger.info(f"Skipping mask {roi_name} - no shape/polygon found")
                continue
            
            if progress_callback:
                pct = 40 + int((idx / total_rois) * 50)
                progress_callback(pct, f"Converting ROI {idx}/{total_rois}: {roi_name}")
            
            logger.info(f"Working on mask {roi_name}")
            
            try:
                # Convert contour to mask
                mask = dcm_patient_coords_to_mask.convert(
                    rtstruct["sequence"],
                    dicom_image,
                    mask_background=0,
                    mask_foreground=255,
                )
                
                # Copy image information to mask
                mask.CopyInformation(dicom_image)
                
                # Sanitize ROI name for filename
                mask_filename = sanitize_for_path(roi_name)
                mask_output_path = nifti_dir / mask_filename
                
                # Save mask as NIfTI
                nii_output_adapter.write(mask, str(mask_output_path), gzip=True)
                logger.info(f"Saved mask at: {mask_filename}.nii.gz")
                converted_count += 1
                
            except ContourOutOfBoundsException:
                logger.warning(f"Structure {roi_name} is out of bounds, ignoring contour!")
                errors.append(f"ROI {roi_name} is out of bounds")
                continue
            except Exception as e:
                logger.error(f"Failed to convert ROI {roi_name}: {e}")
                errors.append(f"Failed to convert ROI {roi_name}: {str(e)}")
                continue
        
        if progress_callback:
            progress_callback(95, f"Converted {converted_count}/{total_rois} ROIs")
        
        # Save metadata
        import json
        rois = rtstruct_series.dicominstance_set.first().rtstructroi_set.all() if rtstruct_series.dicominstance_set.exists() else []
        roi_list = [{"number": roi.roi_number, "name": roi.roi_name} for roi in rois]
        
        metadata = {
            'series_uid': rtstruct_series.series_instance_uid,
            'rois': roi_list,
            'reference_series_uid': referenced_image_series.series_instance_uid,
            'converted_count': converted_count,
            'total_count': total_rois
        }
        
        metadata_path = nifti_dir / "rtstruct_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update the series model
        relative_path = nifti_dir.relative_to(settings.MEDIA_ROOT)
        rtstruct_series.nifti_file_path = str(relative_path)
        rtstruct_series.save(update_fields=['nifti_file_path'])
        
        if progress_callback:
            progress_callback(100, "RTStruct conversion complete")
        
        logger.info(f"Successfully processed RTStruct series {rtstruct_series.id}: {converted_count}/{total_rois} ROIs converted")
        return str(relative_path), errors
        
    except Exception as e:
        error_msg = f"Error converting RTStruct {rtstruct_series.series_instance_uid}: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        return None, errors


def convert_series_with_rtstructs(series_id: int, progress_callback=None) -> dict:
    """
    Convert a DICOM image series and all its associated RTStructs to NIfTI.
    
    If the selected series is an RTStruct, finds the referenced image series.
    
    Args:
        series_id: ID of the DICOMSeries to convert (can be image or RTStruct)
        progress_callback: Optional callback function(progress_pct, message)
        
    Returns:
        Dictionary with conversion results
    """
    from app.models import DICOMSeries, DICOMInstance
    
    result = {
        'success': False,
        'selected_series_id': series_id,
        'image_series_id': None,
        'image_nifti': None,
        'rtstruct_niftis': [],
        'errors': []
    }
    
    try:
        selected_series = DICOMSeries.objects.get(id=series_id)
        
        # Determine the image series to convert
        if selected_series.modality == 'RTSTRUCT':
            # Get the referenced image series from the RTStruct
            rtstruct_instance = DICOMInstance.objects.filter(
                series=selected_series,
                referenced_series_instance_uid__isnull=False
            ).first()
            
            if not rtstruct_instance or not rtstruct_instance.referenced_series_instance_uid:
                result['errors'].append(f"RTStruct series {series_id} has no referenced image series")
                return result
            
            image_series = rtstruct_instance.referenced_series_instance_uid
            result['image_series_id'] = image_series.id
            logger.info(f"Using referenced image series {image_series.series_instance_uid} from RTStruct {selected_series.series_instance_uid}")
        else:
            # Selected series is already an image series (CT, MR, etc.)
            image_series = selected_series
            result['image_series_id'] = image_series.id
        
        # Step 1: Convert the image series
        if progress_callback:
            progress_callback(0, f"Converting image series {image_series.modality}...")
        
        def image_progress(pct, msg):
            # Scale image progress to 0-60%
            scaled_pct = int(pct * 0.6)
            if progress_callback:
                progress_callback(scaled_pct, msg)
        
        image_path, image_errors = convert_dicom_series_to_nifti(image_series, image_progress)
        result['image_nifti'] = image_path
        result['errors'].extend(image_errors)
        
        # Step 2: Find and convert all RTStructs that reference this image series
        if progress_callback:
            progress_callback(60, "Looking for associated RTStructs...")
        
        # Find RTStructs that reference the image series
        rtstruct_instances = DICOMInstance.objects.filter(
            referenced_series_instance_uid=image_series,
            series__modality='RTSTRUCT'
        ).select_related('series')
        
        rtstruct_series_ids = set(inst.series.id for inst in rtstruct_instances)
        
        if progress_callback:
            progress_callback(65, f"Found {len(rtstruct_series_ids)} associated RTStructs")
        
        # Convert each RTStruct
        total_rtstructs = len(rtstruct_series_ids)
        for idx, rtstruct_id in enumerate(rtstruct_series_ids, 1):
            try:
                rtstruct = DICOMSeries.objects.get(id=rtstruct_id)
                
                if progress_callback:
                    base_pct = 65 + int((idx - 1) * 35 / max(total_rtstructs, 1))
                    progress_callback(base_pct, f"Converting RTStruct {idx}/{total_rtstructs}: {rtstruct.series_instance_uid[:20]}...")
                
                def rtstruct_progress(pct, msg):
                    if progress_callback:
                        base_pct = 65 + int((idx - 1) * 35 / max(total_rtstructs, 1))
                        scaled_pct = base_pct + int(pct * 35 / max(total_rtstructs, 1) / 100)
                        progress_callback(min(scaled_pct, 99), msg)
                
                rtstruct_path, rtstruct_errors = convert_rtstruct_to_nifti(
                    rtstruct, image_series, rtstruct_progress
                )
                
                result['rtstruct_niftis'].append({
                    'series_id': rtstruct_id,
                    'series_uid': rtstruct.series_instance_uid,
                    'path': rtstruct_path,
                    'errors': rtstruct_errors
                })
                result['errors'].extend(rtstruct_errors)
                
            except Exception as e:
                error_msg = f"Error processing RTStruct {rtstruct_id}: {str(e)}"
                logger.error(error_msg)
                result['errors'].append(error_msg)
        
        result['success'] = True
        
        if progress_callback:
            progress_callback(100, "All conversions complete")
            
    except DICOMSeries.DoesNotExist:
        result['errors'].append(f"Series {series_id} not found")
    except Exception as e:
        result['errors'].append(f"Unexpected error: {str(e)}")
        logger.exception("Unexpected error in convert_series_with_rtstructs")
    
    return result
