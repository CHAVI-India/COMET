"""Server-side mesh decimation using Python VTK.

vtk.js does not implement vtkDecimatePro, so decimation runs here.
The browser sends vertices and triangles; we return the reduced mesh.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

import vtk
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk

logger = logging.getLogger(__name__)


def decimate_mesh(
    vertices: List[List[float]],
    triangles: List[List[int]],
    target_reduction: float = 0.5,
) -> Tuple[List[List[float]], List[List[int]]]:
    """
    Reduce triangle count using vtkDecimatePro.

    Parameters
    ----------
    vertices : list of [x, y, z]
    triangles : list of [i, j, k] (0-indexed vertex indices)
    target_reduction : float
        Fraction of triangles to remove (0.0–1.0).

    Returns
    -------
    (vertices, triangles) of the reduced mesh.
    """
    points = vtk.vtkPoints()
    for v in vertices:
        points.InsertNextPoint(v[0], v[1], v[2])

    cells = vtk.vtkCellArray()
    for t in triangles:
        cells.InsertNextCell(3, [t[0], t[1], t[2]])

    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)

    decimate = vtk.vtkDecimatePro()
    decimate.SetInputData(poly)
    decimate.SetTargetReduction(target_reduction)
    decimate.PreserveTopologyOn()
    decimate.Update()

    out = decimate.GetOutput()
    out_points = out.GetPoints()
    out_verts = []
    for i in range(out_points.GetNumberOfPoints()):
        p = out_points.GetPoint(i)
        out_verts.append([p[0], p[1], p[2]])

    out_tris = []
    for i in range(out.GetNumberOfCells()):
        cell = out.GetCell(i)
        if cell.GetCellType() == vtk.VTK_TRIANGLE:
            ids = cell.GetPointIds()
            out_tris.append([ids.GetId(0), ids.GetId(1), ids.GetId(2)])

    logger.info(
        "Decimated mesh: %d -> %d triangles (%.1f%% reduction)",
        len(triangles),
        len(out_tris),
        (1 - len(out_tris) / max(len(triangles), 1)) * 100,
    )
    return out_verts, out_tris
