"""Convert an edited surface mesh back into a binary labelmap.

Uses VTK's vtkPolyDataToImageStencil to voxelize the mesh, then
resamples the result to match the reference DICOM geometry via SimpleITK.
"""
from __future__ import annotations

import logging
from typing import List

import numpy as np
import SimpleITK as sitk
import vtk
from vtk.util.numpy_support import numpy_to_vtk

logger = logging.getLogger(__name__)


def mesh_to_labelmap(
    vertices: List[List[float]],
    triangles: List[List[int]],
    reference_image: sitk.Image,
) -> sitk.Image:
    """
    Voxelize a closed surface mesh into a binary labelmap matching the
    geometry of ``reference_image``.

    Parameters
    ----------
    vertices : list of [x, y, z] in world coordinates (mm).
    triangles : list of [i, j, k] (0-indexed).
    reference_image : sitk.Image
        The source DICOM volume whose geometry the labelmap must match.

    Returns
    -------
    sitk.Image — binary labelmap (uint8) with the same geometry as reference_image.
    """
    # Build vtkPolyData from vertices/triangles
    points = vtk.vtkPoints()
    for v in vertices:
        points.InsertNextPoint(v[0], v[1], v[2])

    cells = vtk.vtkCellArray()
    for t in triangles:
        cells.InsertNextCell(3, [t[0], t[1], t[2]])

    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)

    # Ensure the mesh is closed (triangulate + clean)
    triangulate = vtk.vtkTriangleFilter()
    triangulate.SetInputData(poly)
    triangulate.Update()

    # Set up the stencil image matching the reference geometry
    ref_size = reference_image.GetSize()  # (x, y, z)
    ref_spacing = reference_image.GetSpacing()
    ref_origin = reference_image.GetOrigin()

    stencil_image = vtk.vtkImageData()
    stencil_image.SetDimensions(ref_size[0], ref_size[1], ref_size[2])
    stencil_image.SetSpacing(ref_spacing[0], ref_spacing[1], ref_spacing[2])
    stencil_image.SetOrigin(ref_origin[0], ref_origin[1], ref_origin[2])
    stencil_image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)

    # Voxelize: fill inside the mesh
    pol2stenc = vtk.vtkPolyDataToImageStencil()
    pol2stenc.SetInputConnection(triangulate.GetOutputPort())
    pol2stenc.SetOutputOrigin(ref_origin[0], ref_origin[1], ref_origin[2])
    pol2stenc.SetOutputSpacing(ref_spacing[0], ref_spacing[1], ref_spacing[2])
    pol2stenc.SetOutputWholeExtent(
        0, ref_size[0] - 1, 0, ref_size[1] - 1, 0, ref_size[2] - 1
    )

    imgstenc = vtk.vtkImageStencil()
    imgstenc.SetInputData(stencil_image)
    imgstenc.SetStencilConnection(pol2stenc.GetOutputPort())
    imgstenc.SetReverseStencil(0)  # fill inside
    imgstenc.SetBackgroundValue(0)
    imgstenc.Update()

    result = imgstenc.GetOutput()

    # Convert vtkImageData -> numpy array -> SimpleITK image
    dims = result.GetDimensions()  # (x, y, z)
    arr = vtk_to_numpy(result.GetPointData().GetScalars())
    # vtk stores data in Fortran (x-fastest) order; reshape to (z, y, x) for SimpleITK
    arr = arr.reshape(dims[2], dims[1], dims[0]).astype(np.uint8)

    sitk_label = sitk.GetImageFromArray(arr)
    sitk_label.CopyInformation(reference_image)
    return sitk_label
