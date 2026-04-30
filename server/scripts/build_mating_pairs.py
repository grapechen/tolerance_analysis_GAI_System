"""
Extract H↔S (cylindrical hole ↔ cylindrical shaft) mating pairs from
ras400_ontology_contacts.csv and merge with hand-curated nominal_dia /
function_desc / priority drafts to produce ras400_mating_pairs.csv.

This file is the canonical Plan 1 input: each row is one mating pair
the recommender must assign a tolerance fit to.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONTACTS_CSV = DATA_DIR / "ras400_ontology_contacts.csv"
OUT_CSV = DATA_DIR / "ras400_mating_pairs.csv"

URI_RE = re.compile(r"\{uri:\s*([^}]+?)\}")
TYPE_RE = re.compile(r"ns0__(內圓柱面|外圓柱面|平面|錐面)")
ASSEMBLY_REL = "有組裝接觸"

# Hand-curated draft values keyed by (part_a, feat_a, part_b, feat_b).
# 對應 c:/Tolerance_Project/server/data/ras400_ontology_contacts.csv（簡化編碼器版）
# 簡化編碼器後：原「分流座 ↔ 編碼器」H↔S 配合消失（改為 H↔P 平面接觸），剩 11 對。
DRAFT: dict[tuple[str, str, str, str], dict] = {
    ("軸承", "S-3", "軸承座", "H-1"): {
        "nominal_dia": 47,
        "function_desc": "軸承外圈固定於軸承座，承受徑向負載",
        "priority": "high",
    },
    ("軸承", "H-4", "工作臺心軸", "S-1"): {
        "nominal_dia": 25,
        "function_desc": "軸承內圈隨心軸旋轉，過盈固定",
        "priority": "high",
    },
    ("工作臺", "H-2", "工作臺心軸", "S-3"): {
        "nominal_dia": 30,
        "function_desc": "工作臺定位於心軸頂部，需精密定位且可組裝",
        "priority": "high",
    },
    ("工作臺心軸", "S-4", "轉動軸", "H-1"): {
        "nominal_dia": 22,
        "function_desc": "轉動軸與心軸對接，傳遞旋轉扭矩",
        "priority": "high",
    },
    ("馬達", "H-5", "轉動軸", "S-2"): {
        "nominal_dia": 18,
        "function_desc": "馬達輸出端與轉動軸連接，傳遞扭矩",
        "priority": "high",
    },
    ("馬達", "S-1", "馬達水套", "H-1"): {
        "nominal_dia": 80,
        "function_desc": "水套套於馬達外殼，承擔冷卻與密封定位",
        "priority": "medium",
    },
    ("馬達水套", "S-2", "軸承座", "H-2"): {
        "nominal_dia": 60,
        "function_desc": "水套與軸承座定位連接",
        "priority": "medium",
    },
    ("馬達座", "H-2", "分流座", "S-1"): {
        "nominal_dia": 35,
        "function_desc": "分流座定位於馬達座（第一段）",
        "priority": "medium",
    },
    ("馬達座", "H-2", "分流座", "S-3"): {
        "nominal_dia": 30,
        "function_desc": "分流座定位於馬達座（第二段）",
        "priority": "medium",
    },
    ("編碼器", "H-1", "編碼器心軸", "S-2"): {
        "nominal_dia": 8,
        "function_desc": "編碼器讀取心軸角度，要求高旋轉精度",
        "priority": "high",
    },
    ("工作臺心軸", "H-4", "編碼器心軸", "S-4"): {
        "nominal_dia": 10,
        "function_desc": "兩心軸對接，傳遞旋轉訊號",
        "priority": "high",
    },
}


def parse_node(node: str) -> tuple[str | None, str | None]:
    """Return (feature_type, feature_uri) e.g. ('內圓柱面', '軸承座-H-5')."""
    type_m = TYPE_RE.search(node)
    uri_m = URI_RE.search(node)
    feat_type = type_m.group(1) if type_m else None
    uri = uri_m.group(1).strip() if uri_m else None
    return feat_type, uri


def split_feature(uri: str) -> tuple[str, str]:
    """'軸承座-H-5' -> ('軸承座', 'H-5'). Last hyphen-prefixed token is feature."""
    idx = uri.rfind("-")
    # feature suffix is two tokens separated by '-', e.g. H-5, S-3
    # so search back two hyphens
    second = uri.rfind("-", 0, idx)
    if second == -1:
        return uri, ""
    return uri[:second], uri[second + 1:]


def extract_pairs() -> list[dict]:
    rows: list[dict] = []
    with CONTACTS_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 3:
                continue
            n, r, m = row[0], row[1], row[2]
            if ASSEMBLY_REL not in r:
                continue
            t1, u1 = parse_node(n)
            t2, u2 = parse_node(m)
            if not (u1 and u2 and t1 and t2):
                continue
            # only keep 內圓柱面 ↔ 外圓柱面 (H ↔ S)
            types = {t1, t2}
            if types != {"內圓柱面", "外圓柱面"}:
                continue
            # decide hole / shaft
            if t1 == "內圓柱面":
                hole_uri, shaft_uri = u1, u2
            else:
                hole_uri, shaft_uri = u2, u1
            hole_part, hole_feat = split_feature(hole_uri)
            shaft_part, shaft_feat = split_feature(shaft_uri)

            # draft lookup tries both orderings of the original contact
            key1 = (
                *split_feature(u1), *split_feature(u2),
            )
            key2 = (
                *split_feature(u2), *split_feature(u1),
            )
            draft = DRAFT.get(key1) or DRAFT.get(key2) or {}

            rows.append({
                "hole_part": hole_part,
                "hole_feature": hole_feat,
                "shaft_part": shaft_part,
                "shaft_feature": shaft_feat,
                "nominal_dia": draft.get("nominal_dia", ""),
                "function_desc": draft.get("function_desc", ""),
                "priority": draft.get("priority", ""),
            })
    return rows


def main() -> None:
    rows = extract_pairs()
    # stable ordering: by hole_part then hole_feature
    rows.sort(key=lambda r: (r["hole_part"], r["hole_feature"], r["shaft_part"], r["shaft_feature"]))
    fieldnames = [
        "pair_id", "hole_part", "hole_feature",
        "shaft_part", "shaft_feature",
        "nominal_dia", "function_desc", "priority",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(rows, start=1):
            r["pair_id"] = f"MP{i:02d}"
            writer.writerow(r)
    print(f"Wrote {len(rows)} mating pairs to {OUT_CSV}")
    missing = [r for r in rows if not r.get("function_desc")]
    if missing:
        print(f"WARNING: {len(missing)} pair(s) missing draft values:")
        for r in missing:
            print(f"  {r['hole_part']}-{r['hole_feature']} <-> {r['shaft_part']}-{r['shaft_feature']}")


if __name__ == "__main__":
    main()
