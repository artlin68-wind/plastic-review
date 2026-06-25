"""拔模角分析模組"""
import numpy as np

# 拔模角 > 這個值的面視為「水平面/頂底面」，不需要拔模角，標灰色略過
_HORIZONTAL_THRESHOLD_DEG = 75.0


def analyze(mesh_data: dict, mold_direction: np.ndarray, rules: dict) -> dict:
    """
    計算每個三角面的拔模角（面法向量與開模方向的夾角）。

    定義：
      拔模角 = 面法向量與開模方向的夾角 - 90°
      即：垂直面 → 0°（最需要拔模），水平面 → 90°（不需要拔模）

    只對「側壁面」（拔模角 < HORIZONTAL_THRESHOLD）做 Pass/Warn/Fail 判定。
    水平頂底面標為灰色，不計入問題統計。
    """
    normals = mesh_data['face_normals']
    direction = mold_direction / np.linalg.norm(mold_direction)

    # 每個面法向量與開模方向的夾角（0°=平行, 90°=垂直）
    cos_vals = np.clip(np.abs(normals @ direction), 0.0, 1.0)
    # 拔模角：面與開模方向「平行程度」→ 越接近 0° 越難脫模
    # 水平面: cos≈1 → angle_with_dir≈0° → draft≈90°（不需拔模）
    # 垂直面: cos≈0 → angle_with_dir≈90° → draft≈0°（最需拔模）
    draft_angles = 90.0 - np.degrees(np.arccos(cos_vals))

    # 水平面掩碼（不需拔模，不計入統計）
    horiz_mask = draft_angles >= _HORIZONTAL_THRESHOLD_DEG
    check_mask = ~horiz_mask  # 需要檢查拔模角的側壁面

    exterior_min = rules['draft_angle']['exterior_min']
    warning_min = rules['draft_angle']['warning_min']

    # 只對側壁面做判定
    fail_mask = check_mask & (draft_angles < warning_min)
    warn_mask = check_mask & (draft_angles >= warning_min) & (draft_angles < exterior_min)
    pass_mask = check_mask & (draft_angles >= exterior_min)

    n_check = check_mask.sum()
    fail_ratio = float(fail_mask.sum() / n_check) if n_check > 0 else 0.0
    warn_ratio = float(warn_mask.sum() / n_check) if n_check > 0 else 0.0

    side_angles = draft_angles[check_mask]
    min_angle = float(side_angles.min()) if len(side_angles) > 0 else 0.0

    # 顏色：灰=水平面(不需拔模), 藍=Pass, 黃=Warning, 紅=Fail
    colors = np.zeros((len(draft_angles), 3))
    colors[horiz_mask] = [0.55, 0.55, 0.55]   # 灰色：水平面
    colors[pass_mask]  = [0.2,  0.6,  1.0]    # 藍色：拔模足夠
    colors[warn_mask]  = [1.0,  0.85, 0.0]    # 黃色：警告
    colors[fail_mask]  = [0.95, 0.15, 0.1]    # 紅色：拔模不足

    if fail_ratio > 0.05:
        status = 'fail'
    elif fail_ratio > 0 or warn_ratio > 0.1:
        status = 'warning'
    else:
        status = 'pass'

    summary = (
        f"最小拔模角（側壁）：{min_angle:.2f}°｜"
        f"側壁面數：{n_check}｜"
        f"不足（<{warning_min}°）：{fail_ratio*100:.1f}%｜"
        f"警告：{warn_ratio*100:.1f}%｜"
        f"水平面（略過）：{horiz_mask.sum()}"
    )

    return {
        'status': status,
        'face_angles': draft_angles,
        'face_colors': colors,
        'face_color_mode': 'draft_angle',   # 告知 viewer 用哪種色階
        'min_angle': min_angle,
        'fail_ratio': fail_ratio,
        'warning_ratio': warn_ratio,
        'horizontal_count': int(horiz_mask.sum()),
        'checked_count': int(n_check),
        'summary': summary,
    }
