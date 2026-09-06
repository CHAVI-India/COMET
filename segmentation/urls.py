from django.urls import path
from segmentation import views

urlpatterns = [
    # Editor page
    path("editor/<int:series_id>/", views.segmentation_editor, name="seg_editor"),
    # DICOM serving API for ITK-Wasm
    path(
        "api/series/<int:series_id>/dicom-files/",
        views.series_dicom_files,
        name="seg_series_dicom_files",
    ),
    path(
        "api/file/<int:instance_id>/",
        views.serve_dicom_file,
        name="seg_serve_dicom_file",
    ),
    # Save labelmap -> RTSTRUCT
    path(
        "api/series/<int:series_id>/save-segmentation/",
        views.save_segmentation,
        name="seg_save_segmentation",
    ),
    # Server-side tool endpoints
    path(
        "api/series/<int:series_id>/tool/smooth/",
        views.tool_smooth,
        name="seg_tool_smooth",
    ),
    path(
        "api/series/<int:series_id>/tool/margin/",
        views.tool_margin,
        name="seg_tool_margin",
    ),
    path(
        "api/series/<int:series_id>/tool/hollow/",
        views.tool_hollow,
        name="seg_tool_hollow",
    ),
    path(
        "api/series/<int:series_id>/tool/islands/",
        views.tool_islands,
        name="seg_tool_islands",
    ),
    path(
        "api/series/<int:series_id>/tool/interpolate/",
        views.tool_interpolate,
        name="seg_tool_interpolate",
    ),
    path(
        "api/series/<int:series_id>/tool/logical/",
        views.tool_logical,
        name="seg_tool_logical",
    ),
    # Mesh decimation (segmentation-scoped)
    path(
        "api/segmentation/<int:segmentation_id>/mesh-decimate/",
        views.tool_mesh_decimate,
        name="seg_tool_mesh_decimate",
    ),
    # Mesh -> labelmap rasterization (series-scoped)
    path(
        "api/series/<int:series_id>/tool/mesh-rasterize/",
        views.tool_mesh_rasterize,
        name="seg_tool_mesh_rasterize",
    ),
    # Segmentation management UI
    path(
        "sessions/",
        views.segmentation_sessions_list,
        name="seg_sessions_list",
    ),
    path(
        "sessions/<int:session_id>/",
        views.segmentation_session_detail,
        name="seg_session_detail",
    ),
    # Segmentation management API
    path(
        "api/segmentation/<int:segmentation_id>/rename/",
        views.rename_segmentation,
        name="seg_rename",
    ),
    path(
        "api/segmentation/<int:segmentation_id>/delete/",
        views.delete_segmentation,
        name="seg_delete",
    ),
    path(
        "api/segmentation/<int:segmentation_id>/duplicate/",
        views.duplicate_segmentation,
        name="seg_duplicate",
    ),
    path(
        "api/segmentation/<int:segmentation_id>/export/rtstruct/",
        views.export_rtstruct,
        name="seg_export_rtstruct",
    ),
    path(
        "api/segmentation/<int:segmentation_id>/export/nifti/",
        views.export_nifti,
        name="seg_export_nifti",
    ),
]
