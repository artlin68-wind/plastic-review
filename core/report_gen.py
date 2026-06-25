"""PDF 報告產生模組 — 使用內建 Helvetica 字型，100% ASCII 安全"""
from datetime import datetime
import re


def generate_pdf(results: dict, filename: str, material: str) -> bytes:
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 not installed. Run: pip install fpdf2")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 只用內建字型，完全不依賴系統字型
    def H(size=11):
        pdf.set_font('Helvetica', size=size)

    def HB(size=11):
        pdf.set_font('Helvetica', 'B', size=size)

    pass_n, warn_n, fail_n, total = _get_pass_count(results)
    pass_rate = int(pass_n / total * 100) if total > 0 else 0
    safe_name = _ascii(filename)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # ── 封面 ──
    pdf.add_page()
    HB(20)
    pdf.ln(20)
    pdf.cell(0, 12, 'Plastic Part Pre-Mold Geometry Check Report', ln=True, align='C')
    pdf.ln(6)
    H(12)
    pdf.cell(0, 8, f'Part: {safe_name}', ln=True, align='C')
    pdf.cell(0, 8, f'Material: {material}', ln=True, align='C')
    pdf.cell(0, 8, f'Date: {now}', ln=True, align='C')
    pdf.ln(10)
    HB(18)
    pdf.cell(0, 10, f'Overall Pass Rate: {pass_rate}%', ln=True, align='C')
    pdf.ln(4)
    H(11)
    pdf.cell(0, 7, f'Pass: {pass_n}   Warning: {warn_n}   Fail: {fail_n}', ln=True, align='C')

    # ── 摘要表 ──
    pdf.add_page()
    HB(14)
    pdf.cell(0, 10, 'Executive Summary', ln=True)
    pdf.ln(2)

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
    STATUS_EN = {'pass': 'PASS', 'warning': 'WARN', 'fail': 'FAIL'}

    H(9)
    col = [75, 24, 91]
    # 表頭
    pdf.set_fill_color(210, 210, 210)
    for txt, w in zip(['Check Item', 'Status', 'Key Values'], col):
        pdf.cell(w, 8, txt, border=1, fill=True)
    pdf.ln()

    for key, label in ITEMS:
        res = results.get(key) or {}
        status = res.get('status', '')
        summary_raw = res.get('summary', '')
        summary = _extract_numbers(summary_raw)   # 只取數字部分

        if status == 'pass':
            pdf.set_fill_color(200, 240, 200)
        elif status == 'warning':
            pdf.set_fill_color(255, 240, 180)
        elif status == 'fail':
            pdf.set_fill_color(255, 200, 200)
        else:
            pdf.set_fill_color(245, 245, 245)

        pdf.cell(col[0], 7, label, border=1, fill=True)
        pdf.cell(col[1], 7, STATUS_EN.get(status, 'N/A'), border=1, fill=True, align='C')
        pdf.cell(col[2], 7, summary[:45], border=1, fill=True, ln=True)

    # ── 詳細結果 ──
    pdf.add_page()
    HB(14)
    pdf.cell(0, 10, 'Detailed Analysis Results', ln=True)

    for key, label in ITEMS:
        res = results.get(key) or {}
        if not res:
            continue
        status = res.get('status', 'N/A')
        summary = _extract_numbers(res.get('summary', ''))

        pdf.ln(3)
        HB(11)
        pdf.cell(0, 8, label, ln=True)
        H(9)
        pdf.multi_cell(0, 6, f'Status : {STATUS_EN.get(status, status).upper()}')
        pdf.multi_cell(0, 6, f'Summary: {summary}')

        # 數值細節
        detail = _format_detail(key, res)
        if detail:
            pdf.multi_cell(0, 6, detail)

    # ── 附錄 ──
    pdf.add_page()
    HB(14)
    pdf.cell(0, 10, 'Appendix: Design Rule Parameters', ln=True)
    H(10)
    pdf.multi_cell(0, 6, f'Material        : {material}')
    pdf.multi_cell(0, 6,  'Rules source    : config/design_rules.yaml')
    pdf.multi_cell(0, 6,  'Mold direction  : User-defined (default +Z)')
    pdf.multi_cell(0, 6, f'Generated at    : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    return bytes(pdf.output())


# ── 輔助函數 ──

def _get_pass_count(results: dict) -> tuple:
    vals = [v for v in results.values() if isinstance(v, dict)]
    p = sum(1 for v in vals if v.get('status') == 'pass')
    w = sum(1 for v in vals if v.get('status') == 'warning')
    f = sum(1 for v in vals if v.get('status') == 'fail')
    return p, w, f, p + w + f


def _ascii(text: str) -> str:
    """移除非 ASCII 字元。"""
    return text.encode('ascii', errors='replace').decode('ascii')


def _extract_numbers(text: str) -> str:
    """
    從中文摘要字串中抽取數字與單位，組成英文可讀字串。
    例：'最小拔模角：0.85°｜不足面積：2.1%' → 'min=0.85deg fail=2.1%'
    """
    # 先嘗試整串都是 ASCII
    ascii_only = text.encode('ascii', errors='ignore').decode('ascii').strip()
    if ascii_only:
        return ascii_only[:100]

    # 抽取所有數字片段（含單位）
    tokens = re.findall(r'[\d]+\.?[\d]*\s*(?:mm|deg|%|°|:1)?', text)
    return '  '.join(tokens)[:100] if tokens else 'see app for details'


def _format_detail(key: str, res: dict) -> str:
    """針對各模組取出數值細節（純 ASCII）。"""
    lines = []
    if key == 'draft_angle':
        lines.append(f'  Min angle   : {res.get("min_angle", 0):.2f} deg')
        lines.append(f'  Fail ratio  : {res.get("fail_ratio", 0)*100:.1f}%')
        lines.append(f'  Warn ratio  : {res.get("warning_ratio", 0)*100:.1f}%')
    elif key == 'wall_thickness':
        lines.append(f'  Min thickness : {res.get("min_thickness", 0):.2f} mm')
        lines.append(f'  Max thickness : {res.get("max_thickness", 0):.2f} mm')
        lines.append(f'  Avg thickness : {res.get("avg_thickness", 0):.2f} mm')
        lines.append(f'  Thickness ratio: {res.get("thickness_ratio", 0):.1f}:1')
    elif key == 'fillet':
        lines.append(f'  Min radius  : {res.get("min_radius", 0):.3f} mm')
        lines.append(f'  Fail count  : {res.get("fail_count", 0)}')
        lines.append(f'  Warn count  : {res.get("warning_count", 0)}')
    elif key == 'undercut':
        lines.append(f'  Undercut faces     : {res.get("undercut_count", 0)}')
        lines.append(f'  Undercut area ratio: {res.get("undercut_area_ratio", 0)*100:.1f}%')
    elif key == 'ejection':
        lines.append(f'  Ejection ratio : {res.get("ejection_ratio", 0)*100:.1f}%')
    elif key == 'mold_direction':
        scores = res.get('direction_scores', {})
        if scores:
            lines.append('  Direction scores (%):')
            for d, s in scores.items():
                lines.append(f'    {d:4s} : {s}%')
    return '\n'.join(lines)
