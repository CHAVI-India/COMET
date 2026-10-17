"""
Regression tests for the CSRF-token-resolution bug.

Root cause
----------
Several templates read the CSRF token from ``document.cookie`` using the
hard-coded name ``csrftoken``. This project sets a custom
``CSRF_COOKIE_NAME = 'spatialmetrics_csrftoken'``, so those readers returned
``null`` / ``''`` and the ``X-CSRFToken`` header was empty. Django's
``CsrfViewMiddleware`` then rejected the AJAX POST with a 403 (the 403 body is
HTML, which is why the browser surfaced it as a cryptic ``JSON.parse`` error).

These tests prove, using a CSRF-enforced client:

* a POST carrying the token the front-end resolves  -> 200
* a POST with an empty ``X-CSRFToken`` header (the old bug) -> 403

and that the token the shared JS helper will actually use is non-empty on every
previously-broken page.
"""

import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from app.models import DICOMSeries, DICOMStudy, Patient
from segmentation.models import SegmentationSession, UserSegmentation


def _js_extract_token(html: str) -> str:
    """Return the CSRF token the shared ``window.getCsrfToken`` helper will use
    for this rendered page, mirroring its resolution order exactly:

      1. the server-rendered hidden ``csrfmiddlewaretoken`` input, then
      2. the server-rendered ``{{ csrf_token }}`` value (base.html helper).

    It never relies on a cookie name.
    """
    m = re.search(
        r'<input[^>]*name="csrfmiddlewaretoken"[^>]*value="([^"]+)"', html
    )
    if m:
        return m.group(1)
    m = re.search(r'var\s+rendered\s*=\s*"([^"]*)";', html)
    return m.group(1) if m else ""


class CsrfAjaxRegressionTest(TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username="csrfuser", password="p4ssw0rd!xyz"
        )
        # CSRF-enforced client: mimics a real browser enforcing CSRF checks.
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

        # Minimal DICOM hierarchy so the segmentation pages render.
        self.patient = Patient.objects.create(patient_id="P-0001")
        self.study = DICOMStudy.objects.create(
            study_instance_uid="1.2.3.4.5", patient=self.patient
        )
        self.series = DICOMSeries.objects.create(
            study=self.study,
            series_instance_uid="1.2.3.4.5.6",
            modality="CT",
        )
        self.session = SegmentationSession.objects.create(
            user=self.user, image_series=self.series
        )
        self.seg = UserSegmentation.objects.create(
            session=self.session, roi_name="GTV"
        )

    # ---- Diagnosis proof: 200 with a resolved token, 403 with an empty one ----
    def test_resolved_token_200_vs_empty_token_403(self):
        page = self.client.get(reverse("spatial_overlap_metrics"))
        self.assertEqual(page.status_code, 200)
        token = _js_extract_token(page.content.decode())
        self.assertTrue(token, "JS could not resolve a CSRF token on metrics page")

        ok = self.client.post(
            reverse("compute_overlap_metrics"),
            data={"roi_pairs": ""},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(ok.status_code, 200)  # CSRF accepted (JSON body, not 403 HTML)

        bad = self.client.post(
            reverse("compute_overlap_metrics"),
            data={"roi_pairs": ""},
            HTTP_X_CSRFTOKEN="",
        )
        self.assertEqual(bad.status_code, 403)  # empty header rejected

    def test_broken_rename_endpoint_200_vs_403(self):
        # Exact endpoint the (previously broken) segmentation_detail.html AJAX
        # hit with an empty token.
        page = self.client.get(reverse("seg_session_detail", args=[self.session.id]))
        self.assertEqual(page.status_code, 200)
        token = _js_extract_token(page.content.decode())
        self.assertTrue(
            token, "JS could not resolve a CSRF token on segmentation detail page"
        )

        ok = self.client.post(
            reverse("seg_rename", args=[self.seg.id]),
            data='{"roi_name": "GTV-renamed"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(ok.status_code, 200)

        bad = self.client.post(
            reverse("seg_rename", args=[self.seg.id]),
            data='{"roi_name": "GTV-renamed"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN="",
        )
        self.assertEqual(bad.status_code, 403)

    # ---- Rendered-token checks for every previously-broken page ----
    def test_metrics_page_token_nonempty(self):
        page = self.client.get(reverse("spatial_overlap_metrics"))
        self.assertTrue(_js_extract_token(page.content.decode()))

    def test_seg_detail_page_token_nonempty(self):
        page = self.client.get(reverse("seg_session_detail", args=[self.session.id]))
        self.assertTrue(_js_extract_token(page.content.decode()))

    def test_seg_editor_page_token_nonempty(self):
        page = self.client.get(reverse("seg_editor", args=[self.series.id]))
        self.assertEqual(page.status_code, 200)
        self.assertTrue(_js_extract_token(page.content.decode()))

    # ---- The {{ csrf_token }} fallback (context processor) is not empty ----
    def test_base_csrf_context_processor_rendered_nonempty(self):
        page = self.client.get(reverse("spatial_overlap_metrics"))
        html = page.content.decode()
        m = re.search(r'var\s+rendered\s*=\s*"([^"]*)";', html)
        self.assertIsNotNone(
            m,
            "shared getCsrfToken helper with {{ csrf_token }} not found in base.html",
        )
        self.assertTrue(m.group(1).strip(), "{{ csrf_token }} rendered empty")
