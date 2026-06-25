"""塑膠件開模前幾何設計檢查工具 — Streamlit 主程式"""
import os
import sys
import tempfile
import streamlit as st
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="塑膠件開模前幾何設計檢查",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-title { font-size: 1.8em; font-weight: bold; color: #00d2ff; }
</style>
""", unsafe_allow_html=True)


# ===== 功能函數 =====

def _render_fig_to_png(fig, width=800, height=450) -> bytes | None:
    """將 Plotly figure 轉成 PNG bytes，失敗時回傳 None。
    相容 kaleido 0.2.x（Streamlit Cloud）與 1.x（本機）。
    """
    try:
        import plotly.io as pio
        return pio.to_image(fig, format='png', width=width, height=height, scale=1.5)
    except Exception:
        try:
            return fig.to_image(format='png', width=width, height=height)
        except Exception:
            return None


def _build_figures(results: dict, mesh_data: dict) -> dict:
    """
    為各分析項目產生 Plotly 截圖，回傳 {key: PNG bytes}。
    只對有 face_colors / sample_points 的項目截圖。
    """
    from ui.viewer import render_mesh, render_points_overlay, render_direction_radar
    figs = {}

    # 1. 拔模角（用角度值 scalar heat map，RdYlBu：紅=問題 藍=OK）
    r = results.get('draft_angle', {})
    if r and 'face_angles' in r:
        import numpy as _np
        angles = _np.array(r['face_angles'])
        fig = render_mesh(
            mesh_data,
            scalar_values=angles,
            colorscale='RdYlBu',
            title='Draft Angle Heat Map  Red(<0.2deg)=FAIL / Blue(>1.5deg)=OK',
            colorbar_title='deg',
            cmin=0.0,
            cmax=10.0,   # 固定 0-10° 色階，紅色問題區更明顯
        )
        png = _render_fig_to_png(fig)
        if png:
            figs['draft_angle'] = png

    # 2. 壁厚
    r = results.get('wall_thickness', {})
    if r and 'sample_points' in r and len(r.get('sample_points', [])) > 0:
        fig = render_points_overlay(mesh_data, r['sample_points'],
                                    r.get('thickness_values'), 'Wall Thickness Distribution')
        png = _render_fig_to_png(fig)
        if png:
            figs['wall_thickness'] = png

    # 3. 圓角（fillet）
    r = results.get('fillet', {})
    if r and 'face_colors' in r:
        import numpy as _np2
        fc = _np2.array(r['face_colors'])
        fig = render_mesh(mesh_data, fc,
                          'Fillet Check (Red=R too small / Yellow=Warn / Green=OK / Gray=Other)')
        png = _render_fig_to_png(fig)
        if png:
            figs['fillet'] = png

    # 4. 肋條（rib）
    r = results.get('rib', {})
    if r and 'face_colors' in r:
        import numpy as _np3
        fc = _np3.array(r['face_colors'])
        fig = render_mesh(mesh_data, fc,
                          'Rib Design (Red=Fail / Yellow=Warn / Green=OK / Gray=Non-rib)')
        png = _render_fig_to_png(fig)
        if png:
            figs['rib'] = png

    # 5. Boss 柱
    r = results.get('boss', {})
    if r and 'face_colors' in r:
        import numpy as _np4
        fc = _np4.array(r['face_colors'])
        fig = render_mesh(mesh_data, fc,
                          'Boss Check (Red=OD/ID ratio fail / Green=OK / Gray=Non-boss)')
        png = _render_fig_to_png(fig)
        if png:
            figs['boss'] = png

    # 6. 倒扣
    r = results.get('undercut', {})
    if r and 'face_colors' in r:
        import numpy as _np5
        fc = _np5.array(r['face_colors'])
        fig = render_mesh(mesh_data, fc,
                          'Undercut Detection (Red=Undercut / Blue=OK)')
        png = _render_fig_to_png(fig)
        if png:
            figs['undercut'] = png

    # 7. 開模方向雷達
    r = results.get('mold_direction', {})
    if r and 'direction_scores' in r:
        fig = render_direction_radar(r['direction_scores'])
        png = _render_fig_to_png(fig, width=500, height=400)
        if png:
            figs['mold_direction'] = png

    # 8. 原始模型（封面用）
    fig = render_mesh(mesh_data, title='Part Overview')
    png = _render_fig_to_png(fig)
    if png:
        figs['overview'] = png

    return figs


def _make_pdf(results: dict, filename: str, material: str,
              figures: dict = None) -> bytes:
    """產生含截圖的 PDF 報告，只用 Helvetica 內建字型，全部 ASCII。"""
    from fpdf import FPDF
    from datetime import datetime
    import re
    import io

    if figures is None:
        figures = {}

    def asc(s):
        return re.sub(r'[^\x20-\x7E]', '', str(s))

    NX = 'LMARGIN'  # new_x shorthand
    NY = 'NEXT'     # new_y shorthand

    ITEMS = [
        ('draft_angle',    '1. Draft Angle'),
        ('wall_thickness', '2. Wall Thickness'),
        ('fillet',         '3. Fillet / Radius'),
        ('rib',            '4. Rib Design'),
        ('boss',           '5. Boss'),
        ('undercut',       '6. Undercut'),
        ('parting_line',   '7. Parting Line'),
        ('hole',           '8. Hole Direction'),
        ('ejection',       '9. Ejection Area'),
        ('mold_direction', '10. Mold Direction'),
    ]
    STATUS_COLOR = {
        'pass':    (200, 240, 200),
        'warning': (255, 240, 180),
        'fail':    (255, 200, 200),
    }
    STATUS_EN = {'pass': 'PASS', 'warning': 'WARN', 'fail': 'FAIL'}
    SUGGESTIONS = {
        'draft_angle':    'Increase draft angle to >= 1.5 deg (PC). Add taper to all vertical walls.',
        'wall_thickness': 'Keep wall thickness 1.5-4.0mm (PC). Avoid abrupt thickness changes (ratio <= 2:1).',
        'fillet':         'Add fillet R >= 0.5mm to all concave edges to reduce stress concentration.',
        'rib':            'Rib thickness <= 0.6x main wall. Rib height <= 3x main wall to avoid sink marks.',
        'boss':           'Boss outer diameter >= 2x inner diameter. Add gussets to prevent sinking.',
        'undercut':       'Redesign to eliminate undercuts, or add side-action sliders / lifters.',
        'parting_line':   'Review parting line placement. Ensure it follows the maximum silhouette.',
        'hole':           'Reorient holes parallel to mold open direction (< 5 deg). Side holes need sliders.',
        'ejection':       'Add ejector pins to increase ejection area to >= 30% of projected area.',
        'mold_direction': 'Consider changing mold open direction for better demold coverage.',
    }

    vals = [v for v in results.values() if isinstance(v, dict)]
    p = sum(1 for v in vals if v.get('status') == 'pass')
    w = sum(1 for v in vals if v.get('status') == 'warning')
    f = sum(1 for v in vals if v.get('status') == 'fail')
    total = p + w + f
    rate = int(p / total * 100) if total > 0 else 0

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=20)
    W = 180  # usable width = 210 - 15 - 15

    # ══════════════════════════════════════
    # 封面
    # ══════════════════════════════════════
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 22)
    pdf.ln(8)
    pdf.cell(0, 12, 'Mold Design Check Report', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(2)

    # 模型概覽圖
    if 'overview' in figures:
        img_io = io.BytesIO(figures['overview'])
        pdf.image(img_io, x=30, w=W - 20, h=90)
        pdf.ln(3)

    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 7, f'Part     : {asc(filename)}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 7, f'Material : {asc(material)}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 7, f'Date     : {datetime.now().strftime("%Y-%m-%d %H:%M")}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    # 通過率大字
    pdf.set_font('Helvetica', 'B', 16)
    color = (200, 60, 60) if rate < 60 else (220, 150, 0) if rate < 80 else (50, 150, 50)
    pdf.set_text_color(*color)
    pdf.cell(0, 10, f'Overall Pass Rate: {rate}%    Pass:{p}  Warning:{w}  Fail:{f}', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_text_color(0, 0, 0)

    # ══════════════════════════════════════
    # 摘要表
    # ══════════════════════════════════════
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 9, 'Summary Table', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    cw = [72, 20, 88]  # 72+20+88 = 180

    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(60, 60, 60)
    pdf.set_text_color(255, 255, 255)
    for txt, w_ in zip(['Check Item', 'Status', 'Key Values'], cw):
        pdf.cell(w_, 7, txt, border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

    pdf.set_font('Helvetica', '', 9)
    for key, label in ITEMS:
        res = results.get(key) or {}
        status = res.get('status', '')
        key_val = _key_values(key, res)

        rgb = STATUS_COLOR.get(status, (245, 245, 245))
        pdf.set_fill_color(*rgb)
        pdf.cell(cw[0], 6, label, border=1, fill=True)
        pdf.cell(cw[1], 6, STATUS_EN.get(status, 'N/A'), border=1, fill=True, align='C')
        pdf.cell(cw[2], 6, key_val[:42], border=1, fill=True, new_x='LMARGIN', new_y='NEXT')

    # ══════════════════════════════════════
    # 各項目詳細頁（每項獨立一頁，含截圖）
    # ══════════════════════════════════════
    for key, label in ITEMS:
        res = results.get(key) or {}
        status = res.get('status', '')
        if not status:
            continue

        pdf.add_page()

        # 標題列
        rgb = STATUS_COLOR.get(status, (245, 245, 245))
        pdf.set_fill_color(*rgb)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, f'{label}  [{STATUS_EN.get(status,"N/A")}]',
                 border=1, fill=True, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(3)

        # 截圖（如果有）
        if key in figures:
            img_io = io.BytesIO(figures[key])
            pdf.image(img_io, x=15, w=W, h=95)
            pdf.ln(4)
        elif key in ('rib', 'boss', 'hole', 'parting_line', 'ejection', 'fillet'):
            # 沒有截圖但有數值的項目：用彩色區塊代替
            pass

        # 數值區塊
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 7, 'Measurement Results', fill=True, new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 9)
        pdf.ln(1)

        for line in _detail_lines(key, res):
            pdf.cell(0, 6, f'  {line}', new_x='LMARGIN', new_y='NEXT')

        # 改善建議
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(255, 240, 200) if status == 'warning' else pdf.set_fill_color(255, 210, 210) if status == 'fail' else pdf.set_fill_color(210, 240, 210)
        pdf.cell(0, 7, 'Recommendation', fill=True, new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 9)
        pdf.ln(1)
        if status == 'pass':
            pdf.multi_cell(0, 6, '  No action required. Design meets requirements.')
        else:
            pdf.multi_cell(0, 6, f'  {SUGGESTIONS.get(key, "Please review design.")}')

    # ══════════════════════════════════════
    # 附錄
    # ══════════════════════════════════════
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(0, 9, 'Appendix: Design Rules Applied', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    pdf.ln(2)
    rules_text = [
        f'Material         : {asc(material)}',
        'Draft Angle      : >= 1.5 deg (exterior, PC)',
        'Wall Thickness   : 1.5 - 4.0 mm, ratio <= 2:1 (PC)',
        'Fillet           : R >= 0.5 mm at all concave edges',
        'Rib Thickness    : <= 0.6 x main wall',
        'Rib Height       : <= 3.0 x main wall',
        'Boss O/I Ratio   : >= 2.0',
        'Undercut Area    : < 5% (warning), >= 5% (fail)',
        'Hole Angle       : <= 5 deg (pass), 5-15 deg (warn), > 15 deg (fail)',
        'Ejection Area    : >= 30% (pass), 20-30% (warn), < 20% (fail)',
        f'Generated        : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
    ]
    for line in rules_text:
        pdf.cell(0, 6, line, new_x='LMARGIN', new_y='NEXT')

    return bytes(pdf.output())


def _key_values(key: str, res: dict) -> str:
    """產生摘要表的關鍵數值欄（純 ASCII，無錯誤訊息）。"""
    try:
        if key == 'draft_angle':
            return f'Min={res.get("min_angle",0):.2f}deg  Fail={res.get("fail_ratio",0)*100:.1f}%  Warn={res.get("warning_ratio",0)*100:.1f}%'
        elif key == 'wall_thickness':
            mn = res.get('min_thickness', 0)
            mx = res.get('max_thickness', 0)
            av = res.get('avg_thickness', 0)
            if mn == 0 and mx == 0:
                return 'Ray-cast failed - check if mesh is watertight'
            return f'Min={mn:.2f}mm  Max={mx:.2f}mm  Avg={av:.2f}mm'
        elif key == 'fillet':
            if res.get('min_radius', 0) == 0 and res.get('fail_count', 0) == 0:
                return 'Analysis error - see detail page'
            return f'MinR={res.get("min_radius",0):.3f}mm  Fail={res.get("fail_count",0)}  Warn={res.get("warning_count",0)}'
        elif key == 'rib':
            n = len(res.get('ribs', []))
            return f'Ribs={n}  Fail={res.get("fail_count",0)}  Warn={res.get("warning_count",0)}'
        elif key == 'boss':
            n = len(res.get('bosses', []))
            return f'Bosses={n}  Fail={res.get("fail_count",0)}  Warn={res.get("warning_count",0)}'
        elif key == 'undercut':
            return f'Faces={res.get("undercut_count",0)}  Area={res.get("undercut_area_ratio",0)*100:.1f}%'
        elif key == 'parting_line':
            return f'Z={res.get("parting_z",0):.2f}mm  Upper={res.get("upper_ratio",0)*100:.1f}%  Lower={res.get("lower_ratio",0)*100:.1f}%'
        elif key == 'hole':
            return f'Holes={len(res.get("holes",[]))}  Fail={res.get("fail_count",0)}  Warn={res.get("warning_count",0)}'
        elif key == 'ejection':
            return f'EjectRatio={res.get("ejection_ratio",0)*100:.1f}%  Points={len(res.get("suggested_points",[]))}'
        elif key == 'mold_direction':
            best = res.get('best_direction_name', 'N/A')
            score = res.get('direction_scores', {}).get(best, 0)
            return f'Best={best}  Score={score}%'
    except Exception:
        pass
    return ''


def _detail_lines(key: str, res: dict) -> list:
    """產生詳細數值列表。"""
    lines = []
    try:
        if key == 'draft_angle':
            lines += [
                f'Minimum draft angle : {res.get("min_angle",0):.2f} deg',
                f'Fail area (< 0.2deg): {res.get("fail_ratio",0)*100:.1f}%',
                f'Warning area        : {res.get("warning_ratio",0)*100:.1f}%',
                f'Pass threshold      : >= 1.5 deg (PC exterior)',
            ]
        elif key == 'wall_thickness':
            mn, mx, av = res.get('min_thickness',0), res.get('max_thickness',0), res.get('avg_thickness',0)
            ratio = res.get('thickness_ratio', 0)
            if mn == 0 and mx == 0:
                lines += ['Wall thickness ray-cast returned no results.',
                          'Possible causes: non-manifold mesh, open shells, or very thin walls.',
                          'Suggestion: repair STL with MeshLab or Netfabb before re-analyzing.']
            else:
                lines += [
                    f'Minimum thickness : {mn:.2f} mm',
                    f'Maximum thickness : {mx:.2f} mm',
                    f'Average thickness : {av:.2f} mm',
                    f'Thickness ratio   : {ratio:.1f} : 1  (limit: 2:1)',
                ]
        elif key == 'fillet':
            lines += [
                f'Concave edges analyzed : {res.get("total_concave_edges",0)}',
                f'Minimum radius         : {res.get("min_radius",0):.3f} mm',
                f'Fail count (R<0.3mm)   : {res.get("fail_count",0)}',
                f'Warning count (R<0.5mm): {res.get("warning_count",0)}',
                f'Requirement            : R >= 0.5 mm',
            ]
        elif key == 'rib':
            ribs = res.get('ribs', [])
            lines.append(f'Ribs detected: {len(ribs)}  Fail: {res.get("fail_count",0)}  Warning: {res.get("warning_count",0)}')
            for i, r in enumerate(ribs[:8], 1):
                lines.append(f'  Rib {i}: thickness={r["thickness"]}mm  height={r["height"]}mm  t-ratio={r["thickness_ratio"]}  h-ratio={r["height_ratio"]}  [{r["status"].upper()}]')
        elif key == 'boss':
            bosses = res.get('bosses', [])
            lines.append(f'Bosses detected: {len(bosses)}  Fail: {res.get("fail_count",0)}  Warning: {res.get("warning_count",0)}')
            for i, b in enumerate(bosses[:8], 1):
                lines.append(f'  Boss {i}: OD={b["outer_radius"]*2:.2f}mm  ID={b["inner_radius"]*2:.2f}mm  ratio={b["ratio"]:.2f}  [{b["status"].upper()}]')
        elif key == 'undercut':
            lines += [
                f'Undercut faces      : {res.get("undercut_count",0)}',
                f'Undercut area ratio : {res.get("undercut_area_ratio",0)*100:.1f}%',
                f'Limit               : < 5% (warning), >= 5% (fail)',
            ]
        elif key == 'parting_line':
            lines += [
                f'Suggested parting Z : {res.get("parting_z",0):.2f} mm',
                f'Upper (core) area   : {res.get("upper_ratio",0)*100:.1f}%',
                f'Lower (cavity) area : {res.get("lower_ratio",0)*100:.1f}%',
            ]
        elif key == 'hole':
            holes = res.get('holes', [])
            lines.append(f'Holes detected: {len(holes)}  Fail: {res.get("fail_count",0)}  Warning: {res.get("warning_count",0)}')
            for i, h in enumerate(holes[:8], 1):
                lines.append(f'  Hole {i}: dia={h["radius"]*2:.2f}mm  angle={h["angle_deg"]:.1f}deg  [{h["status"].upper()}]')
        elif key == 'ejection':
            pts = res.get('suggested_points', [])
            lines += [
                f'Ejection area ratio : {res.get("ejection_ratio",0)*100:.1f}%  (need >= 30%)',
                f'Suggested pin count : {len(pts)}',
            ]
        elif key == 'mold_direction':
            scores = res.get('direction_scores', {})
            best = res.get('best_direction_name', 'N/A')
            lines.append(f'Recommended direction: {best}')
            lines.append('Demoldable area by direction:')
            for d, s in scores.items():
                lines.append(f'  {d:4s} : {s:.1f}%  {"<-- Best" if d == best else ""}')
    except Exception as e:
        lines.append(f'Error reading detail: {e}')
    return lines


def _check_occ() -> bool:
    """檢查 pythonOCC-core 是否可用。"""
    try:
        from OCC.Core.STEPControl import STEPControl_Reader  # noqa
        return True
    except ImportError:
        return False

def _show_welcome():
    st.markdown("""
### 使用說明

1. **上傳 3D 檔案**：在左側側欄上傳 `.step` / `.stp` / `.iges` / `.igs` / `.stl`
2. **選擇材料**：選擇射出材料，系統自動套用對應設計規則
3. **設定開模方向**：預設 Z+ 方向
4. **開始分析**：點選「🚀 開始分析」
5. **查看結果**：3D Heat Map + 詳細分析報告
6. **匯出報告**：下載 PDF

### 檢查項目（10 大項）

| # | 項目 | 檢查內容 |
|---|------|---------|
| 1 | 拔模角 | 各面脫模角度（≥ 1° Pass） |
| 2 | 壁厚均勻性 | Ray casting 壁厚分佈 |
| 3 | 圓角 | 內凹邊 R 值（≥ R0.5 Pass） |
| 4 | 肋條設計 | 肋厚 ≤ 主壁厚 × 0.6 |
| 5 | Boss 柱 | 外徑 ≥ 內徑 × 2 |
| 6 | 倒扣/底切 | 遮蔽面偵測 |
| 7 | 分模線 | 最佳分模位置建議 |
| 8 | 孔洞方向 | 孔軸偏斜角（≤ 5° Pass） |
| 9 | 頂出面積 | 可頂出面積比（≥ 30% Pass） |
| 10 | 開模方向 | 最佳開模方向雷達圖 |
""")


def _execute_analysis(uploaded, material, mold_dir, rules, cache_key):
    """執行所有分析模組，結果存入 session_state。"""
    progress = st.progress(0, text="準備載入 3D 檔案...")

    suffix = '.' + uploaded.name.split('.')[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = tmp.name

    try:
        progress.progress(5, text="📂 載入 3D 檔案中...")
        from core.loader import load_file, shape_to_mesh
        shape_data = load_file(tmp_path)
        mesh_data = shape_to_mesh(shape_data)

        st.session_state['mesh_data'] = mesh_data
        st.session_state['filename'] = uploaded.name

        results = {}
        steps = [
            ('draft_angle',    10, "📐 分析拔模角..."),
            ('wall_thickness', 25, "📏 分析壁厚（需要較長時間）..."),
            ('fillet',         50, "⭕ 檢查圓角..."),
            ('rib',            58, "🔩 檢查肋條..."),
            ('boss',           65, "🔘 檢查 Boss 柱..."),
            ('undercut',       72, "⛔ 偵測倒扣..."),
            ('parting_line',   79, "✂️ 分析分模線..."),
            ('hole',           86, "🕳️ 檢查孔洞方向..."),
            ('ejection',       92, "⬆️ 評估頂出面積..."),
            ('mold_direction', 97, "🧭 分析開模方向..."),
        ]

        from core import (
            draft_angle as _da,
            wall_thickness as _wt,
            fillet_check as _fc,
            rib_check as _rc,
            boss_check as _bc,
            undercut_check as _uc,
            parting_line as _pl,
            hole_check as _hc,
            ejection_check as _ec,
            mold_direction as _md,
        )

        analysis_fns = {
            'draft_angle':    lambda: _da.analyze(mesh_data, mold_dir, rules),
            'wall_thickness': lambda: _wt.analyze(mesh_data, rules),
            'fillet':         lambda: _fc.analyze(mesh_data, rules),
            'rib':            lambda: _rc.analyze(mesh_data, rules),
            'boss':           lambda: _bc.analyze(mesh_data, rules),
            'undercut':       lambda: _uc.analyze(mesh_data, mold_dir, rules),
            'parting_line':   lambda: _pl.analyze(mesh_data, mold_dir),
            'hole':           lambda: _hc.analyze(mesh_data, mold_dir, rules),
            'ejection':       lambda: _ec.analyze(mesh_data, mold_dir, rules),
            'mold_direction': lambda: _md.analyze(mesh_data),
        }

        for key, pct, msg in steps:
            progress.progress(pct, text=msg)
            try:
                results[key] = analysis_fns[key]()
            except Exception as e:
                results[key] = {'status': 'warning', 'summary': f'模組錯誤：{e}'}

        progress.progress(100, text="✅ 分析完成！")
        progress.empty()

        st.session_state.update({
            'results': results,
            'material': material,
            'mold_dir': mold_dir,
            'cache_key': cache_key,
            'analysis_done': True,
        })

    except Exception as e:
        progress.empty()
        st.error(f"❌ 分析失敗：{e}")
        st.info(
            "常見問題：\n"
            "- STEP/IGES 需要 pythonOCC-core：`conda install -c conda-forge pythonocc-core`\n"
            "- STL 需要 trimesh：`pip install trimesh`\n"
            "- 確認模型為水密（Manifold）網格"
        )
        return
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    _display_results()


def _display_results():
    """從 session_state 讀取並顯示分析結果。"""
    results = st.session_state.get('results', {})
    mesh_data = st.session_state.get('mesh_data', {})
    filename = st.session_state.get('filename', '未知檔案')
    material = st.session_state.get('material', 'ABS')

    if not results or not mesh_data:
        st.warning("無分析結果，請重新上傳並分析。")
        return

    from ui.result_panel import render_overview, render_detail_cards
    from ui.viewer import render_mesh, render_points_overlay, render_direction_radar

    render_overview(results)
    st.divider()

    # 3D 視覺化
    st.subheader("🎨 3D 視覺化")
    tabs = st.tabs(["📐 拔模角", "📏 壁厚", "⛔ 倒扣", "🧭 方向雷達", "🔵 原始模型"])

    with tabs[0]:
        r = results.get('draft_angle', {})
        if r and 'face_angles' in r:
            import numpy as _np
            angles = _np.array(r['face_angles'])
            # 水平面（>75°）設為 90 統一灰化，其他用角度值
            fig = render_mesh(
                mesh_data,
                scalar_values=angles,
                colorscale='RdYlBu',
                title='拔模角 Heat Map（紅=不足<0.2° / 藍=足夠>1.5° / 色階固定 0-10°）',
                colorbar_title='deg',
                cmin=0.0,
                cmax=10.0,
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(r.get('summary', ''))
            st.info("💡 灰色區域（水平面/頂底面）與開模方向垂直，不需拔模角，已排除統計。")

    with tabs[1]:
        r = results.get('wall_thickness', {})
        if r and 'sample_points' in r and len(r['sample_points']) > 0:
            fig = render_points_overlay(mesh_data, r['sample_points'],
                                        r.get('thickness_values'), '壁厚分佈')
        else:
            fig = render_mesh(mesh_data, title='壁厚分佈（取樣點不足）')
        st.plotly_chart(fig, use_container_width=True)
        if r:
            st.caption(r.get('summary', ''))

    with tabs[2]:
        r = results.get('undercut', {})
        if r and 'face_colors' in r:
            st.plotly_chart(
                render_mesh(mesh_data, r['face_colors'], '倒扣偵測（紅=倒扣區域）'),
                use_container_width=True
            )
            st.caption(r.get('summary', ''))

    with tabs[3]:
        r = results.get('mold_direction', {})
        if r and 'direction_scores' in r:
            st.plotly_chart(
                render_direction_radar(r['direction_scores']),
                use_container_width=True
            )
            st.caption(r.get('summary', ''))

    with tabs[4]:
        st.plotly_chart(
            render_mesh(mesh_data, title=f'原始模型 — {filename}'),
            use_container_width=True
        )

    st.divider()
    render_detail_cards(results)
    st.divider()

    # PDF 匯出
    st.subheader("📄 匯出 PDF 報告")
    col_pdf1, col_pdf2 = st.columns(2)

    with col_pdf1:
        if st.button("產生 PDF（含 3D 截圖）", type="primary"):
            try:
                prog = st.progress(10, text="正在產生 3D 截圖（需要 Chrome，約 20 秒）...")
                figures = _build_figures(results, mesh_data)
                n_figs = len(figures)
                prog.progress(70, text=f"截圖 {n_figs} 張完成，組合 PDF...")
                pdf_bytes = _make_pdf(results, filename, material, figures)
                prog.progress(100, text="完成！")
                prog.empty()
                if n_figs == 0:
                    st.warning("截圖未成功（kaleido 可能需要安裝 Chrome），已產生不含截圖的報告。")
                else:
                    st.success(f"PDF 完成（含 {n_figs} 張截圖）")
                st.download_button(
                    label="⬇️ 下載 PDF（含截圖）",
                    data=pdf_bytes,
                    file_name=f"mold_check_{filename.rsplit('.', 1)[0]}.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                import traceback
                st.error(f"PDF 失敗：{e}")
                st.code(traceback.format_exc(), language='text')

    with col_pdf2:
        if st.button("產生 PDF（純文字，較快）", type="secondary"):
            try:
                pdf_bytes = _make_pdf(results, filename, material, figures={})
                st.success("PDF 完成")
                st.download_button(
                    label="⬇️ 下載 PDF（純文字）",
                    data=pdf_bytes,
                    file_name=f"mold_check_{filename.rsplit('.', 1)[0]}_text.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                import traceback
                st.error(f"PDF 失敗：{e}")
                st.code(traceback.format_exc(), language='text')


# ===== 主程式入口 =====

if 'analysis_done' not in st.session_state:
    st.session_state['analysis_done'] = False

from ui.sidebar import render_sidebar
params = render_sidebar()

st.markdown('<div class="main-title">🔧 塑膠件開模前幾何設計自動檢查工具</div>', unsafe_allow_html=True)
st.caption("支援 STEP / IGES / STL｜10 大射出成型設計規則自動檢查")

# 格式支援狀態
_occ_available = _check_occ()
if not _occ_available:
    st.warning(
        "⚠️ **STEP/IGES 支援未啟用**（需要 pythonOCC-core，目前 Python 3.14 無法安裝）\n\n"
        "**目前只支援 STL 格式。** 請先將 STEP 檔轉換為 STL：\n"
        "- 線上轉換：[CAD Exchanger](https://cadexchanger.com/)、"
        "[FreeCAD](https://www.freecad.org/)（免費桌面軟體）、"
        "SolidWorks / CATIA 另存為 STL",
        icon="⚠️"
    )

st.divider()

if params['uploaded_file'] is None:
    _show_welcome()
elif params['run_analysis']:
    cache_key = f"{params['uploaded_file'].name}_{params['material']}_{list(params['mold_direction'])}"
    _execute_analysis(
        params['uploaded_file'],
        params['material'],
        params['mold_direction'],
        params['rules'],
        cache_key,
    )
elif st.session_state.get('analysis_done'):
    _display_results()
else:
    st.info("✅ 檔案已上傳，請點選左側「🚀 開始分析」按鈕")
