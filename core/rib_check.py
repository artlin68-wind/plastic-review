"""肋條設計檢查模組"""
import numpy as np


def analyze(mesh_data: dict, rules: dict) -> dict:
    try:
        import trimesh

        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        bbox = mesh.bounding_box.extents
        bbox_sorted = np.sort(bbox)
        main_wall_thickness = float(bbox_sorted[0])

        face_normals = mesh.face_normals
        face_areas = mesh.area_faces

        vertical_mask = np.abs(face_normals[:, 2]) < 0.15
        vertical_faces = np.where(vertical_mask)[0]

        # 預設全部灰色（非肋條面）
        n_faces = len(faces)
        face_colors = np.full((n_faces, 3), [0.75, 0.75, 0.75])

        if len(vertical_faces) < 3:
            return {
                'status': 'pass',
                'ribs': [],
                'fail_count': 0,
                'warning_count': 0,
                'face_colors': face_colors,
                'summary': '未偵測到明顯肋條特徵',
            }

        adj = mesh.face_adjacency
        rib_groups = _group_connected_faces(vertical_faces, adj, face_areas)

        ribs = []
        for group_faces in rib_groups:
            group_pts = mesh.triangles_center[group_faces]
            group_normals = face_normals[group_faces]

            height = float(group_pts[:, 2].max() - group_pts[:, 2].min())
            mean_normal = group_normals.mean(axis=0)
            proj = group_pts @ mean_normal
            thickness = float(proj.max() - proj.min())

            if thickness < 0.1 or height < 0.5:
                continue

            t_ratio = thickness / main_wall_thickness if main_wall_thickness > 0 else 0
            h_ratio = height / main_wall_thickness if main_wall_thickness > 0 else 0

            t_pass = rules['rib_design']['thickness_ratio_pass']
            t_warn = rules['rib_design']['thickness_ratio_warn']
            h_pass = rules['rib_design']['height_ratio_pass']
            h_warn = rules['rib_design']['height_ratio_warn']

            if t_ratio > t_warn or h_ratio > h_warn:
                rib_status = 'fail'
                color = [0.95, 0.15, 0.1]   # 紅
            elif t_ratio > t_pass or h_ratio > h_pass:
                rib_status = 'warning'
                color = [1.0, 0.85, 0.0]    # 黃
            else:
                rib_status = 'pass'
                color = [0.2, 0.7, 0.3]     # 綠

            # 將此群組的面著色
            for fi in group_faces:
                face_colors[fi] = color

            ribs.append({
                'thickness': round(thickness, 2),
                'height': round(height, 2),
                'thickness_ratio': round(t_ratio, 2),
                'height_ratio': round(h_ratio, 2),
                'status': rib_status,
                'face_ids': group_faces.tolist(),
            })

        fail_count = sum(1 for r in ribs if r['status'] == 'fail')
        warn_count = sum(1 for r in ribs if r['status'] == 'warning')

        if fail_count > 0:
            status = 'fail'
        elif warn_count > 0:
            status = 'warning'
        else:
            status = 'pass'

        summary = (
            f"偵測肋條：{len(ribs)} 條｜"
            f"設計不良：{fail_count} 條｜"
            f"警告：{warn_count} 條｜"
            f"主壁厚估算：{main_wall_thickness:.2f}mm"
        )

        return {
            'status': status,
            'ribs': ribs,
            'fail_count': fail_count,
            'warning_count': warn_count,
            'face_colors': face_colors,
            'summary': summary,
        }

    except Exception as e:
        n = len(mesh_data.get('faces', []))
        return {
            'status': 'warning',
            'ribs': [],
            'fail_count': 0,
            'warning_count': 0,
            'face_colors': np.full((n, 3), [0.75, 0.75, 0.75]) if n else np.zeros((0, 3)),
            'summary': f'肋條檢查發生錯誤：{e}',
        }


def _group_connected_faces(face_ids: np.ndarray, adjacency: np.ndarray, face_areas: np.ndarray) -> list:
    id_set = set(face_ids.tolist())
    visited = set()
    groups = []

    adj_dict: dict = {}
    for a, b in adjacency:
        if a not in adj_dict:
            adj_dict[a] = []
        if b not in adj_dict:
            adj_dict[b] = []
        adj_dict[a].append(b)
        adj_dict[b].append(a)

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
        if group:
            groups.append(np.array(group))

    min_area = 1.0
    return [g for g in groups if face_areas[g].sum() > min_area]
