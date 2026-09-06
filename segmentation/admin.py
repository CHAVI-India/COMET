from django.contrib import admin
from segmentation.models import SegmentationSession, UserSegmentation


@admin.register(SegmentationSession)
class SegmentationSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "image_series", "created_at", "modified_at")
    list_filter = ("user",)
    search_fields = ("user__username", "image_series__series_instance_uid")


@admin.register(UserSegmentation)
class UserSegmentationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "roi_name",
        "finalized",
        "rtstruct_instance",
        "created_at",
        "modified_at",
    )
    list_filter = ("finalized",)
    search_fields = ("roi_name", "session__user__username")
