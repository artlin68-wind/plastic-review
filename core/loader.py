"""3D 檔案載入模組：支援 STEP/IGES/STL"""
import os
import numpy as np
from pathlib import Path


def load_file(filepath: str) -> dict:
    """
    載入 3D 檔案，回傳統一格式的幾何資料字典。
    回傳:
        {
          'type': 'brep' | 'mesh',
          'shape': TopoDS_Shape (brep) | trimesh.Trimesh (mesh),
          'filename': str,
          'format': 'STEP'|'IGES'|'STL'
        }
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext in ('.step', '.stp'):
        return _load_step(filepath)
    elif ext in ('.iges', '.igs'):
        return _load_iges(filepath)
    elif ext == '.stl':
        return _load_stl(filepath)
    else:
        raise ValueError(f"不支援的檔案格式：{ext}")


def _load_step(filepath: str) -> dict:
    try:
        from OCC.Core.STEPControl import STEPControl_Reader
        from OCC.Core.IFSelect import IFSelect_RetDone

        reader = STEPControl_Reader()
        status = reader.ReadFile(filepath)
        if status != IFSelect_RetDone:
            raise IOError(f"STEP 檔案讀取失敗：{filepath}")
        reader.TransferRoots()
        shape = reader.OneShape()
        return {'type': 'brep', 'shape': shape, 'filename': os.path.basename(filepath), 'format': 'STEP'}
    except ImportError:
        raise ImportError("pythonOCC-core 未安裝。請執行：conda install -c conda-forge pythonocc-core")


def _load_iges(filepath: str) -> dict:
    try:
        from OCC.Core.IGESControl import IGESControl_Reader
        from OCC.Core.IFSelect import IFSelect_RetDone

        reader = IGESControl_Reader()
        status = reader.ReadFile(filepath)
        if status != IFSelect_RetDone:
            raise IOError(f"IGES 檔案讀取失敗：{filepath}")
        reader.TransferRoots()
        shape = reader.OneShape()
        return {'type': 'brep', 'shape': shape, 'filename': os.path.basename(filepath), 'format': 'IGES'}
    except ImportError:
        raise ImportError("pythonOCC-core 未安裝。請執行：conda install -c conda-forge pythonocc-core")


def _load_stl(filepath: str) -> dict:
    try:
        import trimesh
        mesh = trimesh.load(filepath, force='mesh')
        if not isinstance(mesh, trimesh.Trimesh):
            raise IOError("STL 載入失敗或非單一網格")
        return {'type': 'mesh', 'shape': mesh, 'filename': os.path.basename(filepath), 'format': 'STL'}
    except ImportError:
        raise ImportError("trimesh 未安裝。請執行：pip install trimesh")


def shape_to_mesh(shape_data: dict) -> dict:
    """
    將 BRep (STEP/IGES) 轉換為網格，供視覺化使用。
    回傳包含 vertices, faces, face_normals 的字典。
    """
    if shape_data['type'] == 'mesh':
        mesh = shape_data['shape']
        return {
            'vertices': np.array(mesh.vertices),
            'faces': np.array(mesh.faces),
            'face_normals': np.array(mesh.face_normals),
        }
    else:
        try:
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_FACE
            from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
            import trimesh

            shape = shape_data['shape']
            mesh_gen = BRepMesh_IncrementalMesh(shape, 0.1)
            mesh_gen.Perform()

            vertices = []
            faces = []
            offset = 0

            explorer = TopExp_Explorer(shape, TopAbs_FACE)
            while explorer.More():
                face = explorer.Current()
                location = face.Location()
                bt = BRep_Tool()
                triangulation = bt.Triangulation(face, location)
                if triangulation is not None:
                    n = triangulation.NbNodes()
                    m = triangulation.NbTriangles()
                    for i in range(1, n + 1):
                        p = triangulation.Node(i)
                        vertices.append([p.X(), p.Y(), p.Z()])
                    for i in range(1, m + 1):
                        t = triangulation.Triangle(i)
                        n1, n2, n3 = t.Get()
                        faces.append([offset + n1 - 1, offset + n2 - 1, offset + n3 - 1])
                    offset += n
                explorer.Next()

            verts = np.array(vertices, dtype=float)
            facs = np.array(faces, dtype=int)
            tm = trimesh.Trimesh(vertices=verts, faces=facs, process=False)
            return {
                'vertices': verts,
                'faces': facs,
                'face_normals': np.array(tm.face_normals),
            }
        except ImportError as e:
            raise ImportError(f"BRep 轉網格失敗：{e}")
