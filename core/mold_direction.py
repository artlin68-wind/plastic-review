"""整體開模方向分析模組"""
import numpy as np


def analyze(mesh_data: dict) -> dict:
    """
    分析最佳開模方向：計算各候選方向可正常脫模的面積比例。

    回傳:
        {
          'status': 'pass',
          'best_direction': ndarray (3,),
          'direction_scores': dict,   # 各方向分數
          'summary': str
        }
    """
    normals = mesh_data['face_normals']

    candidates = {
        '+Z': np.array([0, 0, 1]),
        '-Z': np.array([0, 0, -1]),
        '+X': np.array([1, 0, 0]),
        '-X': np.array([-1, 0, 0]),
        '+Y': np.array([0, 1, 0]),
        '-Y': np.array([0, -1, 0]),
    }

    scores = {}
    for name, direction in candidates.items():
        dot = normals @ direction
        # 可脫模面（法向量與開模方向夾角 ≤ 90°）
        demoldable_ratio = float((dot >= 0).sum()) / len(normals)
        scores[name] = round(demoldable_ratio * 100, 1)

    best_name = max(scores, key=scores.__getitem__)
    best_direction = candidates[best_name]

    summary = (
        f"建議開模方向：{best_name}｜"
        f"可脫模面積：{scores[best_name]:.1f}%｜"
        f"各方向：" + "、".join([f"{k}={v}%" for k, v in scores.items()])
    )

    return {
        'status': 'pass',
        'best_direction': best_direction,
        'direction_scores': scores,
        'best_direction_name': best_name,
        'summary': summary,
    }
