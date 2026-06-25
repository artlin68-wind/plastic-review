# 塑膠件開模前幾何設計自動檢查工具

自動化射出成型設計規則檢查，支援 STEP / IGES / STL 格式，提供 10 大項目分析與 PDF 報告匯出。

## 安裝

### 1. 基本依賴（pip）

```bash
pip install -r requirements.txt
```

### 2. pythonOCC-core（STEP/IGES 支援，建議 conda）

```bash
conda install -c conda-forge pythonocc-core
```

> **注意**：pythonOCC 透過 pip 安裝容易有相容性問題，強烈建議使用 conda。
> 若只需分析 STL 檔案，可跳過此步驟。

### 3. 啟動 APP

```bash
cd mold_check_app
streamlit run app.py
```

瀏覽器開啟 `http://localhost:8501`

---

## 檢查項目

| # | 項目 | Pass 條件 | Warning | Fail |
|---|------|-----------|---------|------|
| 1 | 拔模角 | ≥ 1.0°（外觀面） | 0.2°~1.0° | < 0.2° |
| 2 | 壁厚（ABS） | 1.5~3.5mm，比 ≤ 2:1 | 1.2~1.5mm 或比 2~3:1 | <1.2 或 >4.5mm |
| 3 | 圓角 | R ≥ 0.5mm | R 0.3~0.5mm | R < 0.3mm |
| 4 | 肋條 | 肋厚 ≤ 0.6×主壁，高 ≤ 3×主壁 | 0.6~0.7×，3~4× | >0.7×，>4× |
| 5 | Boss 柱 | 外徑 ≥ 2×內徑 | 1.7~2.0× | < 1.7× |
| 6 | 倒扣 | 無倒扣 | 面積 < 5% | 面積 ≥ 5% |
| 7 | 分模線 | 自動建議 | — | — |
| 8 | 孔洞方向 | 偏斜 ≤ 5° | 5°~15° | > 15° |
| 9 | 頂出面積 | ≥ 30% | 20%~30% | < 20% |
| 10 | 開模方向 | 自動分析最佳方向 | — | — |

## 專案結構

```
mold_check_app/
├── app.py                  # Streamlit 主程式
├── requirements.txt
├── core/
│   ├── loader.py           # 3D 檔案載入
│   ├── draft_angle.py      # 拔模角分析
│   ├── wall_thickness.py   # 壁厚分析
│   ├── fillet_check.py     # 圓角檢查
│   ├── rib_check.py        # 肋條檢查
│   ├── boss_check.py       # Boss 柱檢查
│   ├── undercut_check.py   # 倒扣偵測
│   ├── parting_line.py     # 分模線建議
│   ├── hole_check.py       # 孔洞方向
│   ├── ejection_check.py   # 頂出評估
│   ├── mold_direction.py   # 開模方向分析
│   └── report_gen.py       # PDF 報告
├── ui/
│   ├── viewer.py           # Plotly 3D 視覺化
│   ├── result_panel.py     # 結果面板
│   └── sidebar.py          # 側欄參數
└── config/
    └── design_rules.yaml   # 設計規則（可自訂）
```

## 使用材料

支援：ABS、PC、PP、PA66、POM、PC+ABS，各有對應壁厚與拔模角規則。

## 技術架構

- **前端**：Streamlit（本地執行，無需伺服器）
- **3D 核心**：pythonOCC-core（STEP/IGES）+ trimesh（STL）
- **視覺化**：Plotly 3D（Heat Map、雷達圖）
- **報告**：fpdf2（PDF 生成，支援中文）
