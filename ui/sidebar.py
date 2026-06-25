"""側欄參數設定 UI"""
import streamlit as st
import numpy as np
import yaml
from pathlib import Path


def render_sidebar() -> dict:
    """
    渲染 Streamlit 側欄，回傳使用者設定參數字典。

    回傳:
        {
          'material': str,
          'mold_direction': ndarray (3,),
          'rules': dict,
          'uploaded_file': UploadedFile | None,
          'run_analysis': bool
        }
    """
    st.sidebar.title("⚙️ 分析參數設定")

    # 檔案上傳
    st.sidebar.subheader("📁 上傳 3D 檔案")

    # 偵測 OCC 是否可用，決定接受哪些格式
    _occ_ok = _check_occ_available()
    if _occ_ok:
        accept_types = ['step', 'stp', 'iges', 'igs', 'stl']
        help_text = "支援 STEP / IGES / STL 格式"
    else:
        accept_types = ['stl']
        help_text = "目前只支援 STL（STEP/IGES 需要 pythonOCC-core）"

    uploaded = st.sidebar.file_uploader(
        "拖拉或點選上傳",
        type=accept_types,
        help=help_text,
    )

    st.sidebar.divider()

    # 材料選擇
    st.sidebar.subheader("🧪 材料選擇")
    materials = ['ABS', 'PC', 'PP', 'PA66', 'POM', 'PC+ABS']
    material = st.sidebar.selectbox("選擇材料", materials, index=0)

    # 載入設計規則
    rules = _load_rules(material)

    with st.sidebar.expander("查看材料壁厚規格", expanded=False):
        wt = rules['wall_thickness']
        st.write(f"- 合格範圍：{wt['min']} ~ {wt['max']} mm")
        st.write(f"- 警告範圍：{wt['warning_min']} ~ {wt['warning_max']} mm")
        st.write(f"- 合格厚薄比：≤ {wt['thickness_ratio_pass']}:1")

    st.sidebar.divider()

    # 開模方向
    st.sidebar.subheader("🔧 開模方向")
    direction_options = {
        '+Z（預設）': np.array([0, 0, 1]),
        '-Z': np.array([0, 0, -1]),
        '+X': np.array([1, 0, 0]),
        '-X': np.array([-1, 0, 0]),
        '+Y': np.array([0, 1, 0]),
        '-Y': np.array([0, -1, 0]),
        '自訂': None,
    }
    dir_choice = st.sidebar.selectbox("開模方向", list(direction_options.keys()))

    if dir_choice == '自訂':
        col1, col2, col3 = st.sidebar.columns(3)
        dx = col1.number_input('X', value=0.0, format="%.2f")
        dy = col2.number_input('Y', value=0.0, format="%.2f")
        dz = col3.number_input('Z', value=1.0, format="%.2f")
        vec = np.array([dx, dy, dz])
        if np.linalg.norm(vec) < 1e-6:
            vec = np.array([0, 0, 1])
        mold_direction = vec / np.linalg.norm(vec)
    else:
        mold_direction = direction_options[dir_choice]

    st.sidebar.divider()

    # 進階規則調整
    with st.sidebar.expander("🔩 進階規則調整", expanded=False):
        da_min = st.slider(
            "最小拔模角（外觀面）",
            min_value=0.0, max_value=5.0,
            value=float(rules['draft_angle']['exterior_min']),
            step=0.1, format="%.1f°"
        )
        rules['draft_angle']['exterior_min'] = da_min

        wt_min = st.slider(
            "最小壁厚",
            min_value=0.5, max_value=3.0,
            value=float(rules['wall_thickness']['min']),
            step=0.1, format="%.1f mm"
        )
        rules['wall_thickness']['min'] = wt_min

    st.sidebar.divider()

    # 開始分析按鈕
    run = st.sidebar.button(
        "🚀 開始分析",
        type="primary",
        use_container_width=True,
        disabled=(uploaded is None),
    )

    if uploaded is None:
        st.sidebar.info("請先上傳 3D 檔案")

    return {
        'material': material,
        'mold_direction': mold_direction,
        'rules': rules,
        'uploaded_file': uploaded,
        'run_analysis': run,
    }


def _check_occ_available() -> bool:
    try:
        from OCC.Core.STEPControl import STEPControl_Reader  # noqa
        return True
    except ImportError:
        return False


def _load_rules(material: str) -> dict:
    """從 YAML 載入設計規則，回傳指定材料的規則字典。"""
    config_path = Path(__file__).parent.parent / 'config' / 'design_rules.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        mat_rules = config['materials'].get(material, config['materials']['ABS'])
        rules = dict(mat_rules)
        rules['rib_design'] = config['rib_design']
        rules['boss_design'] = config['boss_design']
        rules['undercut'] = config['undercut']
        rules['hole_direction'] = config['hole_direction']
        rules['ejection'] = config['ejection']
        return rules

    except Exception:
        return _default_rules()


def _default_rules() -> dict:
    return {
        'wall_thickness': {
            'min': 1.5, 'max': 3.5,
            'warning_min': 1.2, 'warning_max': 4.5,
            'thickness_ratio_pass': 2.0, 'thickness_ratio_warn': 3.0,
        },
        'draft_angle': {'exterior_min': 1.0, 'interior_min': 0.5, 'warning_min': 0.2},
        'fillet': {'min_radius': 0.5, 'warning_radius': 0.3},
        'rib_design': {
            'thickness_ratio_pass': 0.6, 'thickness_ratio_warn': 0.7,
            'height_ratio_pass': 3.0, 'height_ratio_warn': 4.0,
        },
        'boss_design': {'outer_inner_ratio_pass': 2.0, 'outer_inner_ratio_warn': 1.7},
        'undercut': {'area_ratio_warning': 0.05},
        'hole_direction': {'angle_pass_deg': 5.0, 'angle_warn_deg': 15.0},
        'ejection': {'area_ratio_pass': 0.30, 'area_ratio_warn': 0.20},
    }
