"""Tests for the RTSTRUCT exporter."""
import shutil
import tempfile
from pathlib import Path

import numpy as np
import SimpleITK as sitk
from django.test import TestCase
from pydicom import dcmread
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian

from app.models import Patient, DICOMStudy, DICOMSeries, DICOMInstance
from segmentation.utils.rtstruct_exporter import create_rtstruct_from_mask, get_rtstruct_contour_references
from segmentation.utils.dicom_volume import get_ordered_dicom_files


def _make_synthetic_ct(
    path: Path,
    instance_number: int,
    z_pos: float,
    study_uid: str,
    series_uid: str,
    sop_instance_uid: str,
):
    """Write a minimal but valid CT DICOM file with a 4x4x1 pixel array."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientID = "TESTPAT"
    ds.PatientName = "Test^Patient"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = sop_instance_uid
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.Modality = "CT"
    ds.StudyDate = "20260101"
    ds.SeriesDate = "20260101"
    ds.StudyTime = "120000"
    ds.SeriesTime = "120000"
    ds.StudyID = "1"
    ds.PatientBirthDate = ""
    ds.PatientSex = "O"
    ds.AccessionNumber = ""
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.InstanceNumber = instance_number
    ds.Rows = 4
    ds.Columns = 4
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 1.0
    ds.ImagePositionPatient = [0.0, 0.0, z_pos]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    pixel_array = np.zeros((4, 4), dtype=np.uint16)
    pixel_array[1:3, 1:3] = 100
    ds.PixelData = pixel_array.tobytes()
    ds.save_as(str(path))


class RTStructExporterTests(TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="rtstruct_test_"))
        self.dicom_dir = self.tmp_dir / "ct_series"
        self.dicom_dir.mkdir(parents=True)

        patient = Patient.objects.create(patient_id="TESTPAT")
        study_uid = str(generate_uid())
        series_uid = str(generate_uid())
        study = DICOMStudy.objects.create(
            patient=patient, study_instance_uid=study_uid
        )
        self.series = DICOMSeries.objects.create(
            study=study,
            series_instance_uid=series_uid,
            modality="CT",
        )

        # Write 3 synthetic CT slices with instance numbers deliberately NOT
        # matching physical position order, so we exercise the position-based
        # sorting used by the frontend and by rt-utils.
        slice_uids = [str(generate_uid()) for _ in range(3)]
        file_configs = [
            ("slice_0.dcm", 2, 0.0, slice_uids[0]),
            ("slice_1.dcm", 0, 1.0, slice_uids[1]),
            ("slice_2.dcm", 1, 2.0, slice_uids[2]),
        ]
        for fname, inst_num, z_pos, sop_uid in file_configs:
            _make_synthetic_ct(
                self.dicom_dir / fname,
                instance_number=inst_num,
                z_pos=z_pos,
                study_uid=study_uid,
                series_uid=series_uid,
                sop_instance_uid=sop_uid,
            )
            DICOMInstance.objects.create(
                series=self.series,
                sop_instance_uid=sop_uid,
                instance_number=inst_num,
                instance_file_path=str(self.dicom_dir / fname),
            )
        self.expected_order_by_position = [slice_uids[0], slice_uids[1], slice_uids[2]]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_dicom_files_ordered_by_physical_position(self):
        """The API must return files in ascending physical slice position order."""
        files = get_ordered_dicom_files(self.series)
        uids = [f["sop_instance_uid"] for f in files]
        self.assertEqual(uids, self.expected_order_by_position)

    def test_create_rtstruct_from_cube_mask(self):
        # Mask shape must match the volume: 3 slices, 4 rows, 4 cols (z, y, x)
        # The mask is in physical position order (z=0 is the lowest slice).
        mask = np.zeros((3, 4, 4), dtype=np.uint8)
        mask[0:2, 1:3, 1:3] = 1

        out_path = create_rtstruct_from_mask(mask, self.series, "Cube")
        self.assertTrue(out_path.exists())

        ds = dcmread(str(out_path))
        self.assertTrue(hasattr(ds, "StructureSetROISequence"))
        self.assertEqual(len(ds.StructureSetROISequence), 1)
        self.assertEqual(ds.StructureSetROISequence[0].ROIName, "Cube")

        # Each contour's ReferencedSOPInstanceUID must match the corresponding
        # physical-position slice, not the instance number order.
        contour_refs = get_rtstruct_contour_references(out_path)
        referenced_uids = {uid for refs in contour_refs for uid in refs}
        self.assertEqual(
            referenced_uids,
            {self.expected_order_by_position[0], self.expected_order_by_position[1]},
        )
        # All referenced UIDs must belong to the two segmented slices only.
        self.assertEqual(referenced_uids, {self.expected_order_by_position[0], self.expected_order_by_position[1]})
