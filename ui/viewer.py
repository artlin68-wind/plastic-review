"""3D 互動視覺化元件"""
import numpy as np
import plotly.graph_objects as go


def render_mesh(mesh_data: dict, face_colors: np.ndarray = None,
                title: str = "3D 模型",
                scalar_values: np.ndarray = None,
                colorscale: str = None,
                colorbar_title: str = '',
                cmin: float = None,
                cmax: float = None) -> go.Figure:
    """
    使用 Plotly 渲染 3D 網格。

    face_colors: (N,3) RGB float (0~1)，用於倒扣等二值顏色
    scalar_values: (N,) float，用於連續 heat map（如拔模角角度）
    若兩者都提供，優先用 scalar_values。
    """
    vertices = mesh_data['vertices']
    faces = mesh_data['faces']

    x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]
    i, j, k = faces[:, 0], faces[:, 1], faces[:, 2]

    if scalar_values is not None:
        # per-face scalar → per-vertex（取平均）
        vert_vals = np.zeros(len(vertices))
        vert_cnt  = np.zeros(len(vertices))
        for fi, (vi, vj, vk) in enumerate(faces):
            if fi < len(scalar_values):
                v = float(scalar_values[fi])
                for vid in (vi, vj, vk):
                    vert_vals[vid] += v
                    vert_cnt[vid]  += 1
        mask = vert_cnt > 0
        vert_vals[mask] /= vert_cnt[mask]

        cs = colorscale or 'RdYlBu'
        mesh_trace = go.Mesh3d(
            x=x, y=y, z=z, i=i, j=j, k=k,
            intensity=vert_vals,
            colorscale=cs,
            cmin=cmin,
            cmax=cmax,
            showscale=True,
            colorbar=dict(title=colorbar_title, thickness=15),
            name=title,
            hovertemplate='X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>',
        )

    elif face_colors is not None:
        # per-face RGB → per-vertex RGB 字串（精確還原顏色）
        vert_rgb = np.zeros((len(vertices), 3))
        vert_cnt = np.zeros(len(vertices))
        for fi, (vi, vj, vk) in enumerate(faces):
            if fi < len(face_colors):
                c = face_colors[fi]
                for vid in (vi, vj, vk):
                    vert_rgb[vid] += c
                    vert_cnt[vid] += 1
        mask = vert_cnt > 0
        vert_rgb[mask] /= vert_cnt[mask, np.newaxis]

        # 轉換為 hex 字串
        def to_hex(rgb):
            r = int(np.clip(rgb[0], 0, 1) * 255)
            g = int(np.clip(rgb[1], 0, 1) * 255)
            b = int(np.clip(rgb[2], 0, 1) * 255)
            return f'#{r:02x}{g:02x}{b:02x}'

        vertex_color_strs = [to_hex(vert_rgb[vi]) for vi in range(len(vertices))]

        mesh_trace = go.Mesh3d(
            x=x, y=y, z=z, i=i, j=j, k=k,
            vertexcolor=vertex_color_strs,
            showscale=False,
            name=title,
            hovertemplate='X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>',
        )

    else:
        mesh_trace = go.Mesh3d(
            x=x, y=y, z=z, i=i, j=j, k=k,
            color='lightblue', opacity=0.9, name=title,
        )

    fig = go.Figure(data=[mesh_trace])
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)',
            aspectmode='data',
            bgcolor='#1a1a2e',
            xaxis=dict(backgroundcolor='#16213e', gridcolor='#444', color='white'),
            yaxis=dict(backgroundcolor='#16213e', gridcolor='#444', color='white'),
            zaxis=dict(backgroundcolor='#16213e', gridcolor='#444', color='white'),
        ),
        paper_bgcolor='#0f3460',
        font=dict(color='white'),
        margin=dict(l=0, r=0, t=40, b=0),
        height=500,
    )
    return fig


def render_heat_map(mesh_data: dict, scalar_values: np.ndarray,
                    colorscale: str = 'RdYlBu', title: str = "Heat Map",
                    unit: str = '') -> go.Figure:
    """渲染標量 Heat Map（如壁厚分佈）。"""
    vertices = mesh_data['vertices']
    faces = mesh_data['faces']

    x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]
    i, j, k = faces[:, 0], faces[:, 1], faces[:, 2]

    # per-face scalar → per-vertex
    vertex_vals = np.zeros(len(vertices))
    vertex_cnt = np.zeros(len(vertices))
    for fi, (vi, vj, vk) in enumerate(faces):
        if fi < len(scalar_values):
            v = scalar_values[fi]
            for vid in [vi, vj, vk]:
                vertex_vals[vid] += v
                vertex_cnt[vid] += 1

    mask = vertex_cnt > 0
    vertex_vals[mask] /= vertex_cnt[mask]

    mesh_trace = go.Mesh3d(
        x=x, y=y, z=z,
        i=i, j=j, k=k,
        intensity=vertex_vals,
        colorscale=colorscale,
        showscale=True,
        colorbar=dict(title=unit, thickness=15),
        name=title,
    )

    fig = go.Figure(data=[mesh_trace])
    fig.update_layout(
        title=title,
        scene=dict(aspectmode='data', bgcolor='#1a1a2e'),
        paper_bgcolor='#0f3460',
        font=dict(color='white'),
        margin=dict(l=0, r=0, t=40, b=0),
        height=500,
    )
    return fig


def render_points_overlay(mesh_data: dict, points: np.ndarray,
                          point_values: np.ndarray = None,
                          title: str = "點雲疊加") -> go.Figure:
    """在網格上疊加點雲（如壁厚取樣點）。"""
    fig = render_mesh(mesh_data, title=title)

    if len(points) > 0:
        scatter = go.Scatter3d(
            x=points[:, 0],
            y=points[:, 1],
            z=points[:, 2],
            mode='markers',
            marker=dict(
                size=3,
                color=point_values if point_values is not None else 'yellow',
                colorscale='RdYlGn',
                showscale=point_values is not None,
                colorbar=dict(title='mm', x=1.1) if point_values is not None else None,
            ),
            name='取樣點',
        )
        fig.add_trace(scatter)

    return fig


def render_direction_radar(scores: dict) -> go.Figure:
    """渲染各開模方向的可脫模比例雷達圖。"""
    directions = list(scores.keys())
    values = list(scores.values())
    values.append(values[0])
    directions.append(directions[0])

    fig = go.Figure(go.Scatterpolar(
        r=values,
        theta=directions,
        fill='toself',
        line=dict(color='#00d2ff'),
        fillcolor='rgba(0, 210, 255, 0.3)',
        name='可脫模比例 (%)',
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100]),
            bgcolor='#16213e',
        ),
        paper_bgcolor='#0f3460',
        font=dict(color='white'),
        title='各方向可脫模比例',
        height=400,
    )
    return fig


