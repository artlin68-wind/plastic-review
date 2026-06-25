"""壁厚均勻性分析模組（ray casting 方法）"""
import numpy as np


def analyze(mesh_data: dict, rules: dict, n_samples: int = 2000) -> dict:
    """
    使用 ray casting 估算壁厚分佈。
    從表面取樣點，沿內法線投射 ray，與對面交點距離即為局部壁厚。

    回傳:
        {
          'status': 'pass'|'warning'|'fail',
          'sample_points': ndarray (M,3),
          'thickness_values': ndarray (M,),
          'point_colors': ndarray (M,3),
          'min_thickness': float,
          'max_thickness': float,
          'avg_thickness': float,
          'fail_ratio': float,
          'summary': str
        }
    """
    try:
        import trimesh

        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        # 表面取樣
        points, face_ids = trimesh.sample.sample_surface(mesh, n_samples)
        normals = mesh.face_normals[face_ids]

        # 沿負法向量 (向內) 投射 ray
        ray_origins = points - normals * 0.01
        ray_directions = -normals

        locations, index_ray, _ = mesh.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_directions,
            multiple_hits=False,
        )

        if len(locations) == 0:
            return _empty_result(rules)

        dists = np.linalg.norm(locations - ray_origins[index_ray], axis=1)
        sample_pts = points[index_ray]

    except ImportError:
        raise ImportError("trimesh 未安裝，無法進行壁厚分析")
    except Exception:
        # 回退：用幾何邊界框估算
        return _fallback_result(mesh_data, rules)

    t_min = rules['wall_thickness']['min']
    t_max = rules['wall_thickness']['max']
    w_min = rules['wall_thickness']['warning_min']
    w_max = rules['wall_thickness']['warning_max']
    ratio_pass = rules['wall_thickness']['thickness_ratio_pass']
    ratio_warn = rules['wall_thickness']['thickness_ratio_warn']

    fail_mask = (dists < w_min) | (dists > w_max)
    warn_mask = ~fail_mask & ((dists < t_min) | (dists > t_max))
    pass_mask = (dists >= t_min) & (dists <= t_max)

    # 厚薄比
    if dists.max() > 0 and dists.min() > 0:
        ratio = dists.max() / dists.min()
    else:
        ratio = 0

    if ratio > ratio_warn:
        ratio_status = 'fail'
    elif ratio > ratio_pass:
        ratio_status = 'warning'
    else:
        ratio_status = 'pass'

    fail_ratio = np.sum(fail_mask) / len(dists)
    warn_ratio = np.sum(warn_mask) / len(dists)

    colors = np.zeros((len(dists), 3))
    colors[pass_mask] = [0.2, 0.7, 0.2]
    colors[warn_mask] = [1.0, 0.85, 0.0]
    colors[fail_mask] = [0.9, 0.1, 0.1]

    if fail_ratio > 0.05 or ratio_status == 'fail':
        status = 'fail'
    elif fail_ratio > 0 or warn_ratio > 0.1 or ratio_status == 'warning':
        status = 'warning'
    else:
        status = 'pass'

    summary = (
        f"最小壁厚：{dists.min():.2f}mm｜"
        f"最大壁厚：{dists.max():.2f}mm｜"
        f"平均壁厚：{dists.mean():.2f}mm｜"
        f"厚薄比：{ratio:.1f}"
    )

    return {
        'status': status,
        'sample_points': sample_pts,
        'thickness_values': dists,
        'point_colors': colors,
        'min_thickness': float(dists.min()),
        'max_thickness': float(dists.max()),
        'avg_thickness': float(dists.mean()),
        'thickness_ratio': float(ratio),
        'fail_ratio': fail_ratio,
        'warning_ratio': warn_ratio,
        'summary': summary,
    }


def _empty_result(rules: dict) -> dict:
    return {
        'status': 'warning',
        'sample_points': np.zeros((0, 3)),
        'thickness_values': np.array([]),
        'point_colors': np.zeros((0, 3)),
        'min_thickness': 0.0,
        'max_thickness': 0.0,
        'avg_thickness': 0.0,
        'thickness_ratio': 0.0,
        'fail_ratio': 0.0,
        'warning_ratio': 0.0,
        'summary': '壁厚分析無法取得射線交點，請檢查模型是否為水密網格',
    }


def _fallback_result(mesh_data: dict, rules: dict) -> dict:
    verts = mesh_data['vertices']
    bbox = verts.max(axis=0) - verts.min(axis=0)
    estimated = float(bbox.min()) / 2
    return {
        'status': 'warning',
        'sample_points': np.zeros((0, 3)),
        'thickness_values': np.array([estimated]),
        'point_colors': np.zeros((0, 3)),
        'min_thickness': estimated,
        'max_thickness': estimated,
        'avg_thickness': estimated,
        'thickness_ratio': 1.0,
        'fail_ratio': 0.0,
        'warning_ratio': 1.0,
        'summary': f'壁厚分析使用邊界框估算（{estimated:.2f}mm），建議確認模型是否為水密網格',
    }
