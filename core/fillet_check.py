"""圓角檢查模組 — 使用 face_adjacency（相容 trimesh 4.x）"""
import numpy as np


def analyze(mesh_data: dict, rules: dict) -> dict:
    try:
        import trimesh

        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        n_faces = len(faces)
        face_colors = np.full((n_faces, 3), [0.75, 0.75, 0.75])  # 預設灰色

        adj_pairs = mesh.face_adjacency
        adj_edges = mesh.face_adjacency_edges

        if len(adj_pairs) == 0:
            return _no_edge_result(face_colors)

        normals_a = mesh.face_normals[adj_pairs[:, 0]]
        normals_b = mesh.face_normals[adj_pairs[:, 1]]

        cos_angle = np.clip(np.sum(normals_a * normals_b, axis=1), -1, 1)
        dihedral_deg = np.degrees(np.arccos(cos_angle))

        edge_vecs = vertices[adj_edges[:, 1]] - vertices[adj_edges[:, 0]]
        cross = np.cross(normals_a, normals_b)
        sign = np.sign(np.sum(cross * edge_vecs, axis=1))
        concave_mask = sign < 0

        if concave_mask.sum() == 0:
            return _no_edge_result(face_colors)

        edge_lengths = np.linalg.norm(
            vertices[adj_edges[concave_mask, 1]] - vertices[adj_edges[concave_mask, 0]],
            axis=1
        )
        half_angle = np.radians(dihedral_deg[concave_mask] / 2.0)
        sin_half = np.sin(half_angle)
        valid = sin_half > 1e-4
        radii = np.full(len(edge_lengths), np.inf)
        radii[valid] = edge_lengths[valid] / (2.0 * sin_half[valid])
        radii_finite = radii[radii < 100.0]

        if len(radii_finite) == 0:
            return _no_edge_result(face_colors)

        r_pass = rules['fillet']['min_radius']
        r_warn = rules['fillet']['warning_radius']

        # 找出每條凹邊對應的面並著色
        concave_pair_indices = np.where(concave_mask)[0]
        finite_mask_in_concave = radii < 100.0
        for idx_in_concave, (pair_idx, r) in enumerate(
                zip(concave_pair_indices[finite_mask_in_concave],
                    radii_finite)):
            fa, fb = adj_pairs[pair_idx]
            if r < r_warn:
                color = [0.95, 0.15, 0.1]   # 紅：嚴重不足
            elif r < r_pass:
                color = [1.0, 0.85, 0.0]    # 黃：警告
            else:
                color = [0.2, 0.7, 0.3]     # 綠：OK
            face_colors[fa] = color
            face_colors[fb] = color

        fail_mask = radii_finite < r_warn
        warn_mask = (radii_finite >= r_warn) & (radii_finite < r_pass)

        fail_count = int(fail_mask.sum())
        warn_count = int(warn_mask.sum())
        min_r = float(radii_finite.min())

        if fail_count > 0:
            status = 'fail'
        elif warn_count > 0:
            status = 'warning'
        else:
            status = 'pass'

        summary = (
            f"内凹邊數：{len(radii_finite)} 條｜"
            f"不足 R（<{r_warn}mm）：{fail_count} 條｜"
            f"警告：{warn_count} 條｜"
            f"最小 R：{min_r:.3f}mm"
        )

        return {
            'status': status,
            'edge_radii': radii_finite.tolist(),
            'fail_count': fail_count,
            'warning_count': warn_count,
            'min_radius': min_r,
            'total_concave_edges': len(radii_finite),
            'face_colors': face_colors,
            'summary': summary,
        }

    except Exception as e:
        n = len(mesh_data.get('faces', []))
        fc = np.full((n, 3), [0.75, 0.75, 0.75]) if n else np.zeros((0, 3))
        return {
            'status': 'warning',
            'edge_radii': [],
            'fail_count': 0,
            'warning_count': 0,
            'min_radius': 0.0,
            'total_concave_edges': 0,
            'face_colors': fc,
            'summary': f'圓角檢查錯誤：{e}',
        }


def _no_edge_result(face_colors) -> dict:
    return {
        'status': 'pass',
        'edge_radii': [],
        'fail_count': 0,
        'warning_count': 0,
        'min_radius': float('inf'),
        'total_concave_edges': 0,
        'face_colors': face_colors,
        'summary': '無內凹邊，無需圓角檢查',
    }
