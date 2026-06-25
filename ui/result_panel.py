"""結果面板 UI"""
import streamlit as st


STATUS_ICON = {'pass': '✅', 'warning': '⚠️', 'fail': '❌'}
STATUS_COLOR = {'pass': 'green', 'warning': 'orange', 'fail': 'red'}
STATUS_LABEL = {'pass': '通過', 'warning': '警告', 'fail': '失敗'}


def render_overview(results: dict):
    """渲染整體通過率與各項狀態總覽卡片列。"""
    st.subheader("📊 檢查結果總覽")

    # 統計
    statuses = [v.get('status') for v in results.values() if isinstance(v, dict)]
    pass_n = statuses.count('pass')
    warn_n = statuses.count('warning')
    fail_n = statuses.count('fail')
    total = len(statuses)
    pass_rate = int(pass_n / total * 100) if total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("整體通過率", f"{pass_rate}%")
    col2.metric("✅ 通過", pass_n)
    col3.metric("⚠️ 警告", warn_n)
    col4.metric("❌ 失敗", fail_n)

    st.divider()

    # 各項狀態橫列
    items = [
        ('draft_angle', '拔模角'),
        ('wall_thickness', '壁厚'),
        ('fillet', '圓角'),
        ('rib', '肋條'),
        ('boss', 'Boss 柱'),
        ('undercut', '倒扣'),
        ('parting_line', '分模線'),
        ('hole', '孔洞方向'),
        ('ejection', '頂出'),
        ('mold_direction', '開模方向'),
    ]

    cols = st.columns(5)
    for idx, (key, label) in enumerate(items):
        res = results.get(key, {})
        status = res.get('status', 'warning') if res else 'warning'
        icon = STATUS_ICON.get(status, '⚠️')
        color = STATUS_COLOR.get(status, 'gray')

        with cols[idx % 5]:
            st.markdown(
                f"""<div style="border:1px solid {color}; border-radius:8px;
                    padding:8px; text-align:center; margin:4px 0;
                    background-color: rgba(0,0,0,0.1);">
                    <div style="font-size:1.4em">{icon}</div>
                    <div style="font-size:0.85em; font-weight:bold">{label}</div>
                    <div style="color:{color}; font-size:0.8em">{STATUS_LABEL.get(status,'N/A')}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def render_detail_cards(results: dict):
    """渲染每項可展開的詳細結果卡片。"""
    st.subheader("📋 詳細分析報告")

    sections = [
        ('draft_angle', '1. 拔模角分析', _render_draft_angle),
        ('wall_thickness', '2. 壁厚均勻性分析', _render_wall_thickness),
        ('fillet', '3. 圓角檢查', _render_fillet),
        ('rib', '4. 肋條設計檢查', _render_rib),
        ('boss', '5. Boss 柱檢查', _render_boss),
        ('undercut', '6. 倒扣/底切偵測', _render_undercut),
        ('parting_line', '7. 分模線建議', _render_parting),
        ('hole', '8. 孔洞方向檢查', _render_hole),
        ('ejection', '9. 頂出面積評估', _render_ejection),
        ('mold_direction', '10. 整體開模方向分析', _render_mold_dir),
    ]

    for key, title, render_fn in sections:
        res = results.get(key, {})
        if not res:
            continue

        status = res.get('status', 'warning')
        icon = STATUS_ICON.get(status, '⚠️')

        with st.expander(f"{icon} {title} — {STATUS_LABEL.get(status, 'N/A')}", expanded=(status == 'fail')):
            render_fn(res)


def _status_badge(status: str) -> str:
    color = STATUS_COLOR.get(status, 'gray')
    label = STATUS_LABEL.get(status, 'N/A')
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:0.85em">{label}</span>'


def _render_draft_angle(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("最小拔模角", f"{res.get('min_angle', 0):.2f}°")
    c2.metric("不足面積比", f"{res.get('fail_ratio', 0)*100:.1f}%")
    c3.metric("警告面積比", f"{res.get('warning_ratio', 0)*100:.1f}%")
    if res['status'] != 'pass':
        st.warning("建議：增加拔模角至 1.0° 以上，避免脫模困難。")


def _render_wall_thickness(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最小壁厚", f"{res.get('min_thickness', 0):.2f} mm")
    c2.metric("最大壁厚", f"{res.get('max_thickness', 0):.2f} mm")
    c3.metric("平均壁厚", f"{res.get('avg_thickness', 0):.2f} mm")
    c4.metric("厚薄比", f"{res.get('thickness_ratio', 0):.1f}:1")
    if res['status'] == 'fail':
        st.error("建議：避免壁厚突變，厚薄比應控制在 2:1 以內。")
    elif res['status'] == 'warning':
        st.warning("建議：壁厚接近臨界值，建議調整設計。")


def _render_fillet(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("最小圓角 R", f"{res.get('min_radius', 0):.3f} mm")
    c2.metric("不足圓角數", res.get('fail_count', 0))
    c3.metric("警告圓角數", res.get('warning_count', 0))
    if res['status'] != 'pass':
        st.warning("建議：內凹角應加圓角（R ≥ 壁厚 × 0.5），避免應力集中。")


def _render_rib(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("偵測肋條數", len(res.get('ribs', [])))
    c2.metric("設計不良", res.get('fail_count', 0))
    c3.metric("警告", res.get('warning_count', 0))
    ribs = res.get('ribs', [])
    if ribs:
        st.dataframe(
            [{'肋厚(mm)': r['thickness'], '肋高(mm)': r['height'],
              '厚度比': r['thickness_ratio'], '高度比': r['height_ratio'],
              '狀態': STATUS_LABEL.get(r['status'], 'N/A')} for r in ribs],
            use_container_width=True,
        )


def _render_boss(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("偵測 Boss 數", len(res.get('bosses', [])))
    c2.metric("縮水風險", res.get('fail_count', 0))
    c3.metric("警告", res.get('warning_count', 0))
    bosses = res.get('bosses', [])
    if bosses:
        st.dataframe(
            [{'外徑(mm)': b['outer_radius'], '內徑(mm)': b['inner_radius'],
              '外/內比': b['ratio'], '高度(mm)': b['height'],
              '狀態': STATUS_LABEL.get(b['status'], 'N/A')} for b in bosses],
            use_container_width=True,
        )


def _render_undercut(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("倒扣面數", res.get('undercut_count', 0))
    c2.metric("倒扣面積比", f"{res.get('undercut_area_ratio', 0)*100:.1f}%")
    if res['status'] == 'fail':
        st.error("建議：需增加側向滑塊或斜銷，或重新設計避免倒扣。")
    elif res['status'] == 'warning':
        st.warning("建議：倒扣面積小，可考慮使用斜銷解決。")


def _render_parting(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("建議分模高度(Z)", f"{res.get('parting_z', 0):.2f} mm")
    c2.metric("上模面積比", f"{res.get('upper_ratio', 0)*100:.1f}%")
    c3.metric("下模面積比", f"{res.get('lower_ratio', 0)*100:.1f}%")


def _render_hole(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("偵測孔洞數", len(res.get('holes', [])))
    c2.metric("需滑塊", res.get('fail_count', 0))
    c3.metric("警告", res.get('warning_count', 0))
    holes = res.get('holes', [])
    if holes:
        st.dataframe(
            [{'孔徑(mm)': h['radius']*2, '偏斜角(°)': h['angle_deg'],
              '狀態': STATUS_LABEL.get(h['status'], 'N/A')} for h in holes],
            use_container_width=True,
        )


def _render_ejection(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("可頂出面積比", f"{res.get('ejection_ratio', 0)*100:.1f}%")
    pts = res.get('suggested_points', [])
    c2.metric("建議頂針位置數", len(pts))
    if res['status'] == 'fail':
        st.error("建議：增加頂針數量或面積，避免頂出不均造成變形。")
    elif res['status'] == 'warning':
        st.warning("建議：頂出面積偏低，建議重新評估頂針配置。")


def _render_mold_dir(res: dict):
    st.markdown(f"**狀態：** {_status_badge(res['status'])}", unsafe_allow_html=True)
    scores = res.get('direction_scores', {})
    best = res.get('best_direction_name', 'N/A')
    st.metric("建議開模方向", best)
    if scores:
        cols = st.columns(len(scores))
        for idx, (dir_name, score) in enumerate(scores.items()):
            cols[idx].metric(dir_name, f"{score}%")
