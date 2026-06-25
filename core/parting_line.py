"""分模線建議模組"""
import numpy as np


def analyze(mesh_data: dict, mold_direction: np.ndarray) -> dict:
    """
    依模型最大投影輪廓線自動建議分模線位置。

    回傳:
        {
          'status': 'pass',
          'parting_z': float,        # 建議分模高度（Z 座標）
          'parting_points': ndarray, # 分模線上的點
          'upper_ratio': float,      # 上模（公模）面積比
          'lower_ratio': float,      # 下模（母模）面積比
          'summary': str
        }
    """
    try:
        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        normals = mesh_data['face_normals']

        direction = mold_direction / np.linalg.norm(mold_direction)

        # 計算每個面中心的 Z（沿開模方向）座標
        face_centers = vertices[faces].mean(axis=1)
        z_proj = face_centers @ direction

        # 法向量點積正負分類
        dot = normals @ direction
        pos_faces = dot > 0   # 朝開模方向（上模側）
        neg_faces = dot < 0   # 朝相反方向（下模側）

        # 找法向量由正轉負的 Z 位置 → 分模線
        # 取投影 Z 的直方圖，最大輪廓處為轉折區
        z_min, z_max = z_proj.min(), z_proj.max()
        bins = 100
        hist_pos, edges = np.histogram(z_proj[pos_faces], bins=bins, range=(z_min, z_max))
        hist_neg, _ = np.histogram(z_proj[neg_faces], bins=bins, range=(z_min, z_max))

        # 交叉點（兩側面積最均衡處）
        diff = np.abs(hist_pos - hist_neg)
        parting_bin = int(np.argmin(diff))
        parting_z = float((edges[parting_bin] + edges[parting_bin + 1]) / 2)

        # 上下模面積比
        upper_mask = z_proj >= parting_z
        lower_mask = z_proj < parting_z
        upper_ratio = float(upper_mask.sum()) / len(z_proj)
        lower_ratio = float(lower_mask.sum()) / len(z_proj)

        # 分模線上的頂點（接近分模 Z 的點）
        z_verts = vertices @ direction
        tol = (z_max - z_min) * 0.02
        parting_pts = vertices[np.abs(z_verts - parting_z) < tol]

        summary = (
            f"建議分模 Z 高度：{parting_z:.2f}mm｜"
            f"上模（公模）面積：{upper_ratio*100:.1f}%｜"
            f"下模（母模）面積：{lower_ratio*100:.1f}%"
        )

        return {
            'status': 'pass',
            'parting_z': parting_z,
            'parting_points': parting_pts,
            'upper_ratio': upper_ratio,
            'lower_ratio': lower_ratio,
            'summary': summary,
        }

    except Exception as e:
        return {
            'status': 'warning',
            'parting_z': 0.0,
            'parting_points': np.zeros((0, 3)),
            'upper_ratio': 0.5,
            'lower_ratio': 0.5,
            'summary': f'分模線分析發生錯誤：{e}',
        }
