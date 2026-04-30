"""
sfa_csv_importer.py — SFA PMI BOM Report CSV 自動導入器
=========================================================
功能：
  1. 讀取 SFA_PMI_BOM_Report.csv
  2. 解析每條公差標註：類型、數值、特徵面、基準面
  3. 透過 ontology 的組裝接觸關係，自動建構公差分析路徑 (editorPathData)
  4. 輸出可直接傳入 analysis_service.py 的 JSON

使用方式：
  from sfa_csv_importer import SfaCsvImporter
  importer = SfaCsvImporter('data/ontology_export.csv')
  path_data = importer.build_path_from_csv('1-SFA_PMI_BOM_Report.csv', axis='Z')
"""

import re
import pandas as pd
from collections import defaultdict


# ═══════════════════════════════════════════════════════════
# 公差類型映射
# ═══════════════════════════════════════════════════════════
TOLERANCE_TYPES = {
    'dat': 'datum',    # 基準面（不進入分析路徑）
    'dis': 'dis',      # 距離公差 → spatial + feature
    'dia': 'dia',      # 直徑公差 → feature（公稱尺寸用）
    'fla': 'fla',      # 平面度 → feature
    'par': 'par',      # 平行度 → feature（角度類，需 dist）
    'per': 'per',      # 垂直度 → feature（角度類，需 dist）
    'co':  'co',       # 同心度 → feature
    'cyl': 'cyl',      # 圓柱度 → feature
    'cir': 'cir',      # 圓度 → feature
    'run': 'run',      # 跳動 → feature（角度類）
    'tot': 'tot',      # 全跳動 → feature（角度類）
    'pos': 'pos',      # 位置度 → feature
    'ang': 'ang',      # 角度公差 → feature（角度類）
    'sym': 'sym',      # 對稱度 → feature
}

# 角度類公差（需要轉換距離）
ANGULAR_TYPES = {'par', 'per', 'run', 'tot', 'ang'}


class SfaRow:
    """代表 CSV 中的一條 PMI 標註"""

    def __init__(self, row: dict):
        self.raw = row
        self.code       = str(row.get('公差代號', '')).strip()
        self.geo_type   = str(row.get('名稱/幾何類型', '')).strip()
        self.pmi_text   = str(row.get('公差標註(PMI)', '')).strip()
        self.nominal    = self._parse_float(row.get('公稱尺寸'))
        self.it_grade   = str(row.get('IT等級', '')).strip() or None
        self.tol_value  = self._parse_float(row.get('公差數值'))
        self.features   = self._parse_features(row.get('特徵代號', ''))
        self.face_ids   = self._parse_ids(row.get('Face ID', ''))
        self.checked    = '✓' in str(row.get('是否勾選', ''))
        self.is_feature_only = '★特徵面' in self.pmi_text  # 無公差的純幾何特徵面

        # 特徵面(無公差)的「公差數值」欄位無意義，清零
        if self.is_feature_only:
            self.tol_value = None

        # 解析公差代號
        # 新格式：「工作臺心軸-DIS1」「軸承座-DIA2」「馬達水套-PAR1」
        # 舊格式：「3-DIS1」「1-DIA2」
        m = re.match(r'^(.+)-([A-Za-z]+)(\d+)$', self.code)
        if m:
            part_raw = m.group(1)
            self.part_name  = part_raw                    # 零件名（中文或數字）
            self.part_id    = int(part_raw) if part_raw.isdigit() else None
            self.tol_type   = m.group(2).lower()
            self.tol_index  = int(m.group(3))
        else:
            self.part_name  = ''
            self.part_id    = None
            self.tol_type   = ''
            self.tol_index  = 0

        # 解析基準面
        self.datum_refs = re.findall(r'\[([A-Z])\]', self.pmi_text)

        # 解析上下偏差
        self.upper_dev, self.lower_dev = self._parse_deviations()

    def _parse_float(self, val):
        try:
            return float(str(val).strip())
        except:
            return None

    def _parse_features(self, s):
        """解析特徵代號，支援多個（逗號分隔）"""
        s = str(s).strip().strip('"')
        return [f.strip() for f in s.split(',') if f.strip()]

    def _parse_ids(self, s):
        """解析 Face ID，支援多個"""
        s = str(s).strip().strip('"')
        ids = []
        for f in s.split(','):
            try:
                ids.append(int(f.strip()))
            except:
                pass
        return ids

    def _parse_deviations(self):
        """從 PMI 文字解析上偏差、下偏差"""
        # 格式：±0.025 → (0.025, -0.025)
        m = re.search(r'±\s*([\d.]+)', self.pmi_text)
        if m:
            v = float(m.group(1))
            return v, -v

        # 格式：+0.03 -0.05 → (0.03, -0.05)（兩個均帶符號）
        m = re.search(r'([+-][\d.]+)\s+([+-][\d.]+)', self.pmi_text)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except:
                pass

        # 格式：+0.081 0 或 +0.063 0.000（正上偏差，零下偏差）
        m = re.search(r'([+][\d.]+)\s+(0(?:\.0+)?)\b', self.pmi_text)
        if m:
            try:
                return float(m.group(1)), 0.0
            except:
                pass

        # 格式：0 -0.08 → (0, -0.08)（零上偏差，負下偏差）
        m = re.search(r'\b(0)\s+(-[\d.]+)', self.pmi_text)
        if m:
            return 0.0, float(m.group(2))

        return None, None

    @property
    def bias(self):
        """中心偏差 = (upper + lower) / 2

        說明書規定：只有距離公差（dis）才有意義的 bias；
        幾何公差（fla, per, par, cir 等）公差帶理論對稱於零，強制回傳 0。
        """
        if self.tol_type and self.tol_type != 'dis':
            return 0.0
        if self.upper_dev is not None and self.lower_dev is not None:
            return round((self.upper_dev + self.lower_dev) / 2, 6)
        return 0.0

    def is_datum(self):
        return self.tol_type == 'dat'

    def is_distance(self):
        return self.tol_type == 'dis'

    def is_angular(self):
        return self.tol_type in ANGULAR_TYPES

    def __repr__(self):
        return f"SfaRow({self.code}: {self.tol_value} on {self.features})"


class SfaCsvImporter:
    """
    SFA CSV 導入器

    核心功能：
    1. 解析 SFA_PMI_BOM_Report.csv
    2. 結合 ontology 組裝接觸，自動建構公差分析路徑
    """

    def __init__(
        self,
        ontology_csv_path: str = None,
        iso2768_geo_class: str = 'K',      # ISO 2768-2 幾何公差等級 H/K/L
        iso2768_linear_class: str = 'm',   # ISO 2768-1 尺寸公差等級 f/m/c/v
    ):
        self.ontology_path        = ontology_csv_path
        self.iso2768_geo_class    = iso2768_geo_class
        self.iso2768_linear_class = iso2768_linear_class
        self._assembly_contacts   = {}    # feature_code → [contacted_feature_code]
        self._feature_to_part     = {}    # feature_code → part_id_str
        self._datum_faces         = {}    # datum_letter → feature_code
        self._iso2768_svc         = None  # lazy-loaded

        if ontology_csv_path:
            self._load_ontology(ontology_csv_path)

    def _get_iso2768_svc(self):
        """Lazy-load ISO2768Service 避免循環 import。"""
        if self._iso2768_svc is None:
            try:
                from services.iso2768_service import ISO2768Service
                self._iso2768_svc = ISO2768Service()
            except Exception:
                pass
        return self._iso2768_svc

    def _resolve_val(self, row) -> float:
        """
        取得公差數值：
          1. CSV 中有明確值 → 直接使用
          2. 無值 → 從 ISO 2768 查表（fallback）
          3. 查表也失敗 → 回傳 0
        """
        if row.tol_value is not None:
            return row.tol_value

        svc = self._get_iso2768_svc()
        if svc is None:
            return 0.0

        val = svc.resolve_from_pmi_row(
            tol_type     = row.tol_type,
            nominal_mm   = row.nominal or 1.0,
            geo_class    = self.iso2768_geo_class,
            linear_class = self.iso2768_linear_class,
            it_grade     = row.it_grade,
        )
        if val is not None:
            print(f'  [ISO2768 fallback] {row.code} ({row.tol_type}) '
                  f'nominal={row.nominal} → {val:.4f} mm')
            return val
        return 0.0

    # ─────────────────────────────────────────────────────
    # 1. 載入 Ontology（組裝接觸關係）
    # ─────────────────────────────────────────────────────
    def _load_ontology(self, path: str):
        """從 ontology_export.csv 提取組裝接觸關係"""
        try:
            df = pd.read_csv(path, encoding='utf-8-sig')
            for _, row in df.iterrows():
                n = str(row.get('n', ''))
                r = str(row.get('r', ''))
                m = str(row.get('m', ''))

                # 提取節點 uri
                n_uri = self._extract_uri(n)
                m_uri = self._extract_uri(m)

                if not n_uri or not m_uri:
                    continue

                # 組裝接觸關係
                if '有組裝接觸' in r:
                    if n_uri not in self._assembly_contacts:
                        self._assembly_contacts[n_uri] = []
                    if m_uri not in self._assembly_contacts[n_uri]:
                        self._assembly_contacts[n_uri].append(m_uri)

                # 特徵面歸屬零件
                if '有特徵面' in r:
                    self._feature_to_part[n_uri] = m_uri

            print(f"[OK] Ontology 載入：{len(self._assembly_contacts)} 條接觸關係")
        except Exception as e:
            print(f"[WARN] Ontology 載入失敗：{e}")

    def _extract_uri(self, node_str: str) -> str:
        """從 OWL 節點字串提取 uri"""
        m = re.search(r'uri:\s*([^,}\s]+)', node_str)
        return m.group(1).strip('}').strip() if m else ''

    # ─────────────────────────────────────────────────────
    # 2. 解析 CSV
    # ─────────────────────────────────────────────────────
    def load_csv(self, csv_path: str) -> list:
        """讀取 SFA_PMI_BOM_Report.csv，返回 SfaRow 列表"""
        rows = []
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            for _, row in df.iterrows():
                r = SfaRow(row.to_dict())
                if r.code and r.tol_type:
                    rows.append(r)
        except Exception as e:
            print(f"[ERROR] CSV 讀取失敗：{e}")
        return rows

    # ─────────────────────────────────────────────────────
    # 3. 建立特徵面字典
    # ─────────────────────────────────────────────────────
    def build_feature_dict(self, rows: list) -> dict:
        """
        以特徵代號為 key，彙整該特徵面的所有公差

        返回：
        {
          "3-P-4": {
            "face_id": 2869,
            "geo_type": "PLANE",
            "tolerances": [SfaRow, ...],
            "dis_to": {"3-P-3": SfaRow, "3-P-5": SfaRow},  # 此面參與的距離公差
          }
        }
        """
        feat_dict = defaultdict(lambda: {
            "face_id": None,
            "geo_type": "",
            "tolerances": [],
            "dis_to": {},
        })

        for row in rows:
            if row.is_datum():
                continue

            for i, feat in enumerate(row.features):
                fd = feat_dict[feat]
                if not fd["face_id"] and i < len(row.face_ids):
                    fd["face_id"] = row.face_ids[i]
                if not fd["geo_type"]:
                    fd["geo_type"] = row.geo_type

                fd["tolerances"].append(row)

                # 距離公差：記錄「此面到那個面」
                if row.is_distance() and len(row.features) == 2:
                    other = row.features[1 - i]  # 另一個面
                    fd["dis_to"][other] = row

        return dict(feat_dict)

    # ─────────────────────────────────────────────────────
    # 4. 自動建構公差分析路徑
    # ─────────────────────────────────────────────────────
    def build_path_from_csv(
        self,
        csv_path: str,
        axis: str = 'Z',
        include_types: set = None,
        nominal_dist: float = None,
    ) -> list:
        """
        從 CSV 自動建構 editorPathData（供 analysis_service.py 使用）

        策略：
        1. 收集所有距離公差（DIS）→ 建立位移段落
        2. 每個 DIS 之後，加上該特徵面上的形狀公差（FLA, PAR, PER, CIR 等）
        3. 組裝接觸面的公差也加入

        Args:
            csv_path:      CSV 檔案路徑
            axis:          分析軸向（'X', 'Y', 'Z'）
            include_types: 要包含的公差類型（None=全部）
            nominal_dist:  整體名義尺寸（若 CSV 沒有）

        Returns:
            list of path items for analysis_service.py
        """
        rows = self.load_csv(csv_path)
        if not rows:
            return []

        # 分類
        dat_rows = [r for r in rows if r.is_datum()]
        dis_rows = [r for r in rows if r.is_distance()]
        other_rows = [r for r in rows if not r.is_datum() and not r.is_distance()]

        # 建立特徵面字典
        feat_dict = self.build_feature_dict(rows)

        # 建立基準面映射
        datum_map = {}  # letter → SfaRow（DAT）
        for row in dat_rows:
            for feat in row.features:
                for letter in re.findall(r'\[([A-Z])\]', row.pmi_text):
                    datum_map[letter] = feat

        path = []
        added_shape_tols = set()  # 防止形狀公差重複加入

        # ── 加入距離公差段落（DIS）──
        # 按 DIS 序號排序
        dis_sorted = sorted(dis_rows, key=lambda r: r.tol_index)
        for dis_row in dis_sorted:
            if include_types and 'dis' not in include_types:
                continue

            # 位移（nominal）
            nominal = dis_row.nominal or 0
            path.append({
                "type": "spatial",
                "axis": axis,
                "val": nominal,
                "bias": dis_row.bias or 0,
                "dist": "",
                "nominal_size": nominal,
            })

            # 距離公差本身
            path.append({
                "type": "feature",
                "name": dis_row.code,
                "val": self._resolve_val(dis_row),
                "bias": dis_row.bias or 0,
                "dist": "",
                "nominal_size": nominal,
                "it_grade": dis_row.it_grade,
                "tol_type": "dis",
                "features": dis_row.features,
                "face_ids": dis_row.face_ids,
            })

            # ── 在此 DIS 的 「起點面」 加入形狀公差（FLA, PAR, PER 等）
            # 只取 features[0]（起點），避免終點在下一個 DIS 重複
            primary_feat = dis_row.features[0] if dis_row.features else None
            if primary_feat:
                fd = feat_dict.get(primary_feat, {})
                for tol_row in fd.get("tolerances", []):
                    if tol_row.is_datum() or tol_row.is_distance():
                        continue
                    if include_types and tol_row.tol_type not in include_types:
                        continue
                    if tol_row.code in added_shape_tols:
                        continue  # 去重

                    added_shape_tols.add(tol_row.code)
                    entry = {
                        "type": "feature",
                        "name": tol_row.code,
                        "val": self._resolve_val(tol_row),
                        "bias": tol_row.bias or 0,
                        "dist": nominal if tol_row.is_angular() else "",
                        "nominal_size": tol_row.nominal or nominal,
                        "it_grade": tol_row.it_grade,
                        "tol_type": tol_row.tol_type,
                        "features": tol_row.features,
                        "face_ids": tol_row.face_ids,
                    }
                    path.append(entry)

        # ── 加入非距離、且未在 DIS 路徑中加入的公差（孤立的 DIA, CO 等）
        added_codes = {item.get('name') for item in path}
        for row in other_rows:
            if row.code in added_codes:
                continue
            if include_types and row.tol_type not in include_types:
                continue

            feat = row.features[0] if row.features else ""
            nominal = row.nominal or 0

            path.append({
                "type": "feature",
                "name": row.code,
                "val": self._resolve_val(row),
                "bias": row.bias or 0,
                "dist": nominal if row.is_angular() else "",
                "nominal_size": nominal,
                "it_grade": row.it_grade,
                "tol_type": row.tol_type,
                "features": row.features,
                "face_ids": row.face_ids,
            })

        return path

    # ─────────────────────────────────────────────────────
    # 5. 跨零件路徑（透過 ontology 接觸關係串聯）
    # ─────────────────────────────────────────────────────
    def build_assembly_path(self, csv_files: list, axis: str = 'Z') -> list:
        """
        從多個零件 CSV 建構整個組合件的公差分析路徑

        Args:
            csv_files: [(csv_path, part_name), ...]  按零件順序
            axis: 分析軸向

        Returns:
            完整的多零件 editorPathData
        """
        full_path = []

        for csv_path, part_name in csv_files:
            print(f"[Importing] {part_name} from {csv_path}")
            part_path = self.build_path_from_csv(csv_path, axis=axis)

            # 加入零件分隔標記（spatial 0 位移 = 零件邊界）
            if full_path:
                full_path.append({
                    "type": "spatial",
                    "axis": axis,
                    "val": 0,
                    "bias": 0,
                    "dist": "",
                    "_comment": f"組裝接觸 → {part_name}",
                })

            full_path.extend(part_path)

        return full_path

    # ─────────────────────────────────────────────────────
    # 6. 輸出摘要
    # ─────────────────────────────────────────────────────
    def print_summary(self, rows: list):
        """印出解析結果摘要"""
        by_type = defaultdict(list)
        for r in rows:
            by_type[r.tol_type].append(r)

        print(f"\n{'='*50}")
        first = rows[0] if rows else None
        part_label = first.part_name or first.part_id if first else '?'
        print(f"零件: {part_label}")
        print(f"共 {len(rows)} 條 PMI 標註")
        print(f"{'='*50}")

        for ttype, trows in sorted(by_type.items()):
            print(f"\n  [{ttype.upper()}] {len(trows)} 條:")
            for r in trows:
                feats = ', '.join(r.features)
                print(f"    {r.code}: tol={r.tol_value}, nominal={r.nominal}, feats=[{feats}]")

        print(f"\n{'='*50}")


# ═══════════════════════════════════════════════════════════
# 使用範例
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    import json

    # 初始化（連接 ontology）
    importer = SfaCsvImporter(
        ontology_csv_path='data/ontology_export.csv'
    )

    # 讀取並解析 Part 3 (蝸輪)
    rows = importer.load_csv(r'C:\test0402\1\3-SFA_PMI_BOM_Report.csv')
    importer.print_summary(rows)

    # 建構分析路徑（沿 Z 軸）
    path = importer.build_path_from_csv(
        r'C:\test0402\1\3-SFA_PMI_BOM_Report.csv',
        axis='Z',
        include_types={'dis', 'fla', 'par', 'per'}  # 只取距離+形狀公差
    )

    print(f"\n建構路徑：{len(path)} 個路徑段")
    for item in path:
        if item['type'] == 'spatial':
            print(f"  [空間] {item['axis']} = {item['val']} mm")
        else:
            print(f"  [公差] {item['name']}: {item['val']} mm  ({item.get('tol_type','')})")
