"""頂出面積評估模組"""
import numpy as np


def analyze(mesh_data: dict, mold_direction: np.ndarray, rules: dict) -> dict:
    """
    計算底部（公模側）各面的頂出面積分佈。

    回傳:
        {
          'status': 'pass'|'warning'|'fail',
          'ejection_ratio': float,
          'suggested_points': ndarray (K,3),
          'summary': str
        }
    """
    try:
        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        normals = mesh_data['face_normals']

        direction = mold_direction / np.linalg.norm(mold_direction)
        face_centers = vertices[faces].mean(axis=1)

        # 投影到開模方向
        z_proj = face_centers @ direction
        z_min = z_proj.min()
        z_max = z_proj.max()
        z_range = z_max - z_min

        # 底部 20% 高度的面視為公模側
        bottom_threshold = z_min + z_range * 0.20
        bottom_mask = z_proj <= bottom_threshold

        if bottom_mask.sum() == 0:
            return {
                'status': 'warning',
                'ejection_ratio': 0.0,
                'suggested_points': np.zeros((0, 3)),
                'summary': '無法判斷頂出區域，請確認模型朝向',
            }

        # 計算底部朝上（朝公模方向）的面面積
        bottom_normals = normals[bottom_mask]
        bottom_centers = face_centers[bottom_mask]
        dot = bottom_normals @ (-direction)  # 朝公模方向為負開模方向
        ejectable_mask = dot > 0.1  # 面朝下（可被頂出）

        # 投影面積（XY 平面）
        try:
            import trimesh
            mesh = trimesh.Trimesh(
                vertices=vertices, faces=faces, process=False
            )
            face_areas = mesh.area_faces
            bottom_area = face_areas[bottom_mask].sum()
            ejectable_area = face_areas[bottom_mask][ejectable_mask].sum()
        except Exception:
            bottom_area = float(bottom_mask.sum())
            ejectable_area = float(ejectable_mask.sum())

        ejection_ratio = ejectable_area / bottom_area if bottom_area > 0 else 0

        # 建議頂針位置：可頂出面中心點
        suggested = bottom_centers[ejectable_mask] if ejectable_mask.any() else np.zeros((0, 3))
        # 取代表性點（均勻取樣最多 20 個）
        if len(suggested) > 20:
            idx = np.linspace(0, len(suggested) - 1, 20, dtype=int)
            suggested = suggested[idx]

        r_pass = rules['ejection']['area_ratio_pass']
        r_warn = rules['ejection']['area_ratio_warn']

        if ejection_ratio >= r_pass:
            status = 'pass'
        elif ejection_ratio >= r_warn:
            status = 'warning'
        else:
            status = 'fail'

        summary = (
            f"可頂出面積比：{ejection_ratio*100:.1f}%｜"
            f"建議頂針位置：{len(suggested)} 處｜"
            f"{'頂出充足' if status == 'pass' else '頂出不足，建議增加頂針'}"
        )

        return {
            'status': status,
            'ejection_ratio': float(ejection_ratio),
            'suggested_points': suggested,
            'summary': summary,
        }

    except Exception as e:
        return {
            'status': 'warning',
            'ejection_ratio': 0.0,
            'suggested_points': np.zeros((0, 3)),
            'summary': f'頂出評估發生錯誤：{e}',
        }
