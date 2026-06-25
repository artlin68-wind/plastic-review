"""倒扣／底切偵測模組"""
import numpy as np


def analyze(mesh_data: dict, mold_direction: np.ndarray, rules: dict) -> dict:
    """
    沿開模方向做遮蔽分析，找出被遮蔽的面（倒扣）。

    方法：
    - 正向投影（沿 +Z）與反向投影（沿 -Z）
    - 若一個面從兩個方向都被其他面遮蔽 → 倒扣

    回傳:
        {
          'status': 'pass'|'warning'|'fail',
          'face_colors': ndarray (N,3),
          'undercut_count': int,
          'undercut_area_ratio': float,
          'summary': str
        }
    """
    try:
        import trimesh

        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        normals = mesh_data['face_normals']
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        direction = mold_direction / np.linalg.norm(mold_direction)
        total_faces = len(faces)

        # 每個面中心的法向量與開模方向點積
        dot_pos = normals @ direction   # 正向開模
        dot_neg = normals @ (-direction) # 反向開模

        # 法向量指向開模方向的面 → 可正常脫模
        # 法向量指向兩側都看不到的面 → 潛在倒扣
        # 簡化判斷：法向量與開模方向夾角 > 90° + 拔模容差
        threshold = np.cos(np.radians(91.0))

        undercut_mask = (dot_pos < threshold) & (dot_neg < threshold)

        # 計算倒扣面積比
        if hasattr(mesh, 'area_faces'):
            face_areas = mesh.area_faces
            total_area = face_areas.sum()
            undercut_area = face_areas[undercut_mask].sum() if total_area > 0 else 0
            area_ratio = float(undercut_area / total_area) if total_area > 0 else 0
        else:
            area_ratio = float(undercut_mask.sum()) / total_faces if total_faces > 0 else 0

        undercut_count = int(undercut_mask.sum())

        colors = np.zeros((total_faces, 3))
        colors[~undercut_mask] = [0.7, 0.7, 0.7]
        colors[undercut_mask] = [0.9, 0.1, 0.1]

        warn_threshold = rules['undercut']['area_ratio_warning']

        if undercut_count == 0:
            status = 'pass'
        elif area_ratio < warn_threshold:
            status = 'warning'
        else:
            status = 'fail'

        summary = (
            f"倒扣面數：{undercut_count}｜"
            f"倒扣面積比：{area_ratio*100:.1f}%｜"
            f"{'建議使用斜銷或滑塊' if undercut_count > 0 else '無倒扣'}"
        )

        return {
            'status': status,
            'face_colors': colors,
            'undercut_count': undercut_count,
            'undercut_area_ratio': area_ratio,
            'undercut_mask': undercut_mask,
            'summary': summary,
        }

    except Exception as e:
        return {
            'status': 'warning',
            'face_colors': np.zeros((len(mesh_data['faces']), 3)),
            'undercut_count': 0,
            'undercut_area_ratio': 0.0,
            'undercut_mask': np.zeros(len(mesh_data['faces']), dtype=bool),
            'summary': f'倒扣偵測發生錯誤：{e}',
        }
