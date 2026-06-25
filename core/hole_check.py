"""孔洞與槽口方向檢查模組"""
import numpy as np


def analyze(mesh_data: dict, mold_direction: np.ndarray, rules: dict) -> dict:
    """
    偵測孔洞特徵，計算孔軸方向與開模方向的夾角。

    回傳:
        {
          'status': 'pass'|'warning'|'fail',
          'holes': list[dict],
          'fail_count': int,
          'warning_count': int,
          'summary': str
        }
    """
    try:
        import trimesh

        vertices = mesh_data['vertices']
        faces = mesh_data['faces']
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        direction = mold_direction / np.linalg.norm(mold_direction)

        # 找邊界邊（只有一個相鄰面的邊）→ 孔洞邊界
        boundary_edges = trimesh.grouping.group_rows(
            mesh.edges_sorted, require_count=1
        )

        if len(boundary_edges) == 0:
            return {
                'status': 'pass',
                'holes': [],
                'fail_count': 0,
                'warning_count': 0,
                'summary': '未偵測到孔洞特徵',
            }

        # 對邊界邊分組（每個孔洞是一個閉合邊界環）
        boundary_verts = mesh.edges_sorted[boundary_edges]
        loops = _trace_loops(boundary_verts, vertices)

        holes = []
        angle_pass = rules['hole_direction']['angle_pass_deg']
        angle_warn = rules['hole_direction']['angle_warn_deg']

        for loop_pts in loops:
            if len(loop_pts) < 6:
                continue

            # 用 PCA 估算孔軸方向
            center = loop_pts.mean(axis=0)
            centered = loop_pts - center
            _, _, vt = np.linalg.svd(centered)
            axis = vt[-1]  # 最小方差方向即為孔軸

            # 孔軸與開模方向夾角
            cos_a = np.clip(np.abs(axis @ direction), 0, 1)
            angle_deg = float(np.degrees(np.arccos(cos_a)))
            if angle_deg > 90:
                angle_deg = 180 - angle_deg

            # 孔的近似直徑
            dists = np.linalg.norm(loop_pts - center, axis=1)
            radius = float(dists.mean())

            if angle_deg <= angle_pass:
                h_status = 'pass'
            elif angle_deg <= angle_warn:
                h_status = 'warning'
            else:
                h_status = 'fail'

            holes.append({
                'angle_deg': round(angle_deg, 1),
                'radius': round(radius, 2),
                'center': [round(center[0], 2), round(center[1], 2), round(center[2], 2)],
                'status': h_status,
            })

        fail_count = sum(1 for h in holes if h['status'] == 'fail')
        warn_count = sum(1 for h in holes if h['status'] == 'warning')

        if fail_count > 0:
            status = 'fail'
        elif warn_count > 0:
            status = 'warning'
        else:
            status = 'pass'

        summary = (
            f"偵測孔洞：{len(holes)} 個｜"
            f"需側向滑塊（>{angle_warn}°）：{fail_count} 個｜"
            f"警告：{warn_count} 個"
        )

        return {
            'status': status,
            'holes': holes,
            'fail_count': fail_count,
            'warning_count': warn_count,
            'summary': summary,
        }

    except Exception as e:
        return {
            'status': 'warning',
            'holes': [],
            'fail_count': 0,
            'warning_count': 0,
            'summary': f'孔洞方向檢查發生錯誤：{e}',
        }


def _trace_loops(boundary_edges: np.ndarray, vertices: np.ndarray) -> list:
    """追蹤邊界邊形成封閉環，回傳各環的頂點座標列表。"""
    adj: dict = {}
    for e in boundary_edges:
        a, b = int(e[0]), int(e[1])
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    visited_verts = set()
    loops = []

    for start in list(adj.keys()):
        if start in visited_verts:
            continue
        loop_ids = []
        cur = start
        prev = -1
        while True:
            visited_verts.add(cur)
            loop_ids.append(cur)
            neighbors = [n for n in adj.get(cur, []) if n != prev]
            if not neighbors or neighbors[0] in visited_verts:
                break
            prev = cur
            cur = neighbors[0]

        if len(loop_ids) >= 6:
            loops.append(vertices[loop_ids])

    return loops
