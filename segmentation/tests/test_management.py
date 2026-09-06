"""Tests for the segmentation management API."""
import os
import tempfile

from django.test import TestCase, Client
from django.contrib.auth.models import User

from app.models import Patient, DICOMStudy, DICOMSeries, DICOMInstance
from segmentation.models import SegmentationSession, UserSegmentation


class ManagementApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", password="x")
        self.other = User.objects.create_user("other", password="y")
        self.client = Client()
        self.client.login(username="tester", password="x")

        patient = Patient.objects.create(patient_id="P1")
        study = DICOMStudy.objects.create(patient=patient, study_instance_uid="S1")
        self.series = DICOMSeries.objects.create(
            study=study, series_instance_uid="SER1", modality="CT"
        )
        self.session = SegmentationSession.objects.create(
            user=self.user, image_series=self.series
        )
        self.seg = UserSegmentation.objects.create(
            session=self.session, roi_name="TestROI", finalized=True
        )

    def _csrf(self):
        return self.client.cookies.get("csrftoken", "").value

    def test_sessions_list_view(self):
        response = self.client.get("/segmentation/sessions/")
        self.assertEqual(response.status_code, 200)
        # The list page shows the patient ID and modality, not ROI names
        self.assertContains(response, "P1")
        self.assertContains(response, "CT")

    def test_session_detail_view(self):
        response = self.client.get(f"/segmentation/sessions/{self.session.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TestROI")

    def test_sessions_list_requires_auth(self):
        anon = Client()
        response = anon.get("/segmentation/sessions/")
        self.assertIn(response.status_code, (302, 401, 403))

    def test_rename(self):
        response = self.client.post(
            f"/segmentation/api/segmentation/{self.seg.id}/rename/",
            data='{"roi_name": "RenamedROI"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.seg.refresh_from_db()
        self.assertEqual(self.seg.roi_name, "RenamedROI")

    def test_rename_requires_auth(self):
        anon = Client()
        response = anon.post(
            f"/segmentation/api/segmentation/{self.seg.id}/rename/",
            data='{"roi_name": "X"}',
            content_type="application/json",
        )
        self.assertIn(response.status_code, (302, 401, 403))

    def test_duplicate(self):
        response = self.client.post(
            f"/segmentation/api/segmentation/{self.seg.id}/duplicate/",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(UserSegmentation.objects.filter(session=self.session).count(), 2)

    def test_delete(self):
        response = self.client.post(
            f"/segmentation/api/segmentation/{self.seg.id}/delete/",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserSegmentation.objects.filter(id=self.seg.id).exists())

    def test_other_user_cannot_access(self):
        """A different user should not see or modify another user's segmentations."""
        other_client = Client()
        other_client.login(username="other", password="y")
        # Cannot rename another user's segmentation
        response = other_client.post(
            f"/segmentation/api/segmentation/{self.seg.id}/rename/",
            data='{"roi_name": "Hacked"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        # Cannot view another user's sessions
        response = other_client.get(f"/segmentation/sessions/{self.session.id}/")
        self.assertEqual(response.status_code, 404)
