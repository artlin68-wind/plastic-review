"""Boss 柱檢查模組"""
import numpy as np


def analyze(mesh_data: dict, rules: dict) -> dict:
    try:
        import trimesh

        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        face_normals = mesh.face_normals
        face_areas = mesh.area_faces
        tri_centers = mesh.triangles_center

        n_faces = len(faces)
        face_colors = np.full((n_faces, 3), [0.75, 0.75, 0.75])  # 預設灰色

        horiz_mask = np.abs(face_normals[:, 2]) < 0.2
        horiz_faces = np.where(horiz_mask)[0]

        if len(horiz_faces) < 6:
            return {
                'status': 'pass',
                'bosses': [],
                'fail_count': 0,
                'warning_count': 0,
                'face_colors': face_colors,
                'summary': '未偵測到 Boss 柱特徵',
            }

        adj = mesh.face_adjacency
        groups = _group_cylindrical_faces(horiz_faces, adj, face_normals, face_areas, tri_centers)

        bosses = []
        for group in groups:
            pts = tri_centers[group]
            center_xy = pts[:, :2].mean(axis=0)
            dists_from_center = np.linalg.norm(pts[:, :2] - center_xy, axis=1)
            outer_r = float(dists_from_center.max())
            inner_r = float(dists_from_center.min())

            if outer_r < 1.0:
                continue

            if inner_r < 0.5:
                inner_r = outer_r * 0.35

            ratio = outer_r / inner_r if inner_r > 0 else 0
            height = float(pts[:, 2].max() - pts[:, 2].min())

            r_pass = rules['boss_design']['outer_inner_ratio_pass']
            r_warn = rules['boss_design']['outer_inner_ratio_warn']

            if ratio < r_warn:
                b_status = 'fail'
                color = [0.95, 0.15, 0.1]   # 紅
            elif ratio < r_pass:
                b_status = 'warning'
                color = [1.0, 0.85, 0.0]    # 黃
            else:
                b_status = 'pass'
                color = [0.2, 0.7, 0.3]     # 綠

            for fi in group:
                face_colors[fi] = color

            bosses.append({
                'outer_radius': round(outer_r, 2),
                'inner_radius': round(inner_r, 2),
                'ratio': round(ratio, 2),
                'height': round(height, 2),
                'status': b_status,
                'center': [round(center_xy[0], 2), round(center_xy[1], 2)],
                'face_ids': group.tolist(),
            })

        fail_count = sum(1 for b in bosses if b['status'] == 'fail')
        warn_count = sum(1 for b in bosses if b['status'] == 'warning')

        if fail_count > 0:
            status = 'fail'
        elif warn_count > 0:
            status = 'warning'
        else:
            status = 'pass'

        summary = (
            f"偵測 Boss 柱：{len(bosses)} 個｜"
            f"縮水風險高：{fail_count} 個｜"
            f"警告：{warn_count} 個"
        )

        return {
            'status': status,
            'bosses': bosses,
            'fail_count': fail_count,
            'warning_count': warn_count,
            'face_colors': face_colors,
            'summary': summary,
        }

    except Exception as e:
        n = len(mesh_data.get('faces', []))
        return {
            'status': 'warning',
            'bosses': [],
            'fail_count': 0,
            'warning_count': 0,
            'face_colors': np.full((n, 3), [0.75, 0.75, 0.75]) if n else np.zeros((0, 3)),
            'summary': f'Boss 柱檢查發生錯誤：{e}',
        }


def _group_cylindrical_faces(face_ids, adjacency, normals, areas, centers) -> list:
    id_set = set(face_ids.tolist())
    visited = set()
    groups = []

    adj_dict: dict = {}
    for a, b in adjacency:
        for x, y in [(a, b), (b, a)]:
            if x not in adj_dict:
                adj_dict[x] = []
            adj_dict[x].append(y)

    for fid in face_ids:
        if fid in visited:
            continue
        group = []
        stack = [fid]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            if cur in id_set:
                group.append(cur)
                for nb in adj_dict.get(cur, []):
                    if nb not in visited and nb in id_set:
                        stack.append(nb)
        if len(group) >= 6 and areas[group].sum() > 2.0:
            n_xy = normals[group, :2]
            n_xy_norm = n_xy / (np.linalg.norm(n_xy, axis=1, keepdims=True) + 1e-9)
            mean_abs = np.abs(n_xy_norm.mean(axis=0)).max()
            if mean_abs < 0.5:
                groups.append(np.array(group))

    return groups
