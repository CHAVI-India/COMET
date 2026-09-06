from django.db import models
from django.contrib.auth.models import User
from app.models import DICOMSeries, DICOMInstance


class SegmentationSession(models.Model):
    """
    A per-user segmentation workspace tied to a source DICOM image series.
    Multiple users can independently segment the same series; each gets
    their own session.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image_series = models.ForeignKey(
        DICOMSeries,
        on_delete=models.CASCADE,
        related_name="segmentation_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "image_series")
        ordering = ["-modified_at"]

    def __str__(self):
        return f"Session(user={self.user.username}, series={self.image_series.id})"


class UserSegmentation(models.Model):
    """
    A single ROI/segment produced within a session. The authoritative
    persisted artifact is the RTSTRUCT DICOM instance; the optional
    labelmap_data field stores a compressed draft for re-editing.
    """
    session = models.ForeignKey(
        SegmentationSession,
        on_delete=models.CASCADE,
        related_name="segmentations",
    )
    roi_name = models.CharField(max_length=255)
    labelmap_data = models.BinaryField(null=True, blank=True)
    labelmap_shape = models.JSONField(null=True, blank=True)
    rtstruct_instance = models.ForeignKey(
        DICOMInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_segmentations",
    )
    finalized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-modified_at"]

    def __str__(self):
        return f"UserSegmentation(roi={self.roi_name}, session={self.session.id})"
