"""Tests for the DICOM series serving API."""
import os
import tempfile

from django.test import TestCase, Client
from django.contrib.auth.models import User

from app.models import Patient, DICOMStudy, DICOMSeries, DICOMInstance


class DicomVolumeApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", password="x")
        self.client = Client()
        self.client.login(username="tester", password="x")
        patient = Patient.objects.create(patient_id="P1")
        study = DICOMStudy.objects.create(patient=patient, study_instance_uid="S1")
        self.series = DICOMSeries.objects.create(
            study=study, series_instance_uid="SER1", modality="CT"
        )

    def test_series_dicom_files_empty(self):
        response = self.client.get(
            f"/segmentation/api/series/{self.series.id}/dicom-files/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_series_dicom_files_requires_auth(self):
        anon = Client()
        response = anon.get(
            f"/segmentation/api/series/{self.series.id}/dicom-files/"
        )
        # login_required redirects to /accounts/login/ by default
        self.assertIn(response.status_code, (302, 401, 403))

    def test_series_dicom_files_with_instance(self):
        # Create a temp DICOM file on disk
        tmp = tempfile.NamedTemporaryFile(suffix=".dcm", delete=False)
        tmp.write(b"DICOMTEST")
        tmp.close()
        try:
            DICOMInstance.objects.create(
                series=self.series,
                sop_instance_uid="1.2.3.4",
                instance_number=1,
                instance_file_path=tmp.name,
            )
            response = self.client.get(
                f"/segmentation/api/series/{self.series.id}/dicom-files/"
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["count"], 1)
            self.assertEqual(body["files"][0]["sop_instance_uid"], "1.2.3.4")
            self.assertTrue(body["files"][0]["url"].startswith("/segmentation/api/file/"))
        finally:
            os.unlink(tmp.name)

    def test_serve_dicom_file(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".dcm", delete=False)
        tmp.write(b"DICOMTEST")
        tmp.close()
        try:
            inst = DICOMInstance.objects.create(
                series=self.series,
                sop_instance_uid="1.2.3.5",
                instance_number=1,
                instance_file_path=tmp.name,
            )
            response = self.client.get(f"/segmentation/api/file/{inst.id}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"DICOMTEST")
        finally:
            os.unlink(tmp.name)
