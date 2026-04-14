import re

try:
    with open('server/data/ontology_export.csv', 'r', encoding='utf-8') as f:
        content = f.read()
except UnicodeDecodeError:
    with open('server/data/ontology_export.csv', 'r', encoding='utf-8-sig', errors='ignore') as f:
        content = f.read()

# Let's find anything looking like an entity name, usually in Japanese/Chinese/English ending before a quote or slash
# The format looks like: <http://www.semanticweb.org/user/ontologies/...#實體名稱>
# or rdfs__label: '實體名稱'

entities = set()

for match in re.finditer(r"#([^>']+)[>']", content):
    val = match.group(1).strip()
    # Filter out weird URL hex codes or pure English meta tags if we just want Chinese labels
    if val and len(val) < 20 and not val.startswith('http'):
        entities.add(val)

for match in re.finditer(r"rdfs__label:\s*'([^']+)'", content):
    entities.add(match.group(1).strip())
    
print(f"Total Unique Entities found in Knowledge Graph: {len(entities)}")

parts_keywords = ['零件', '件', '機台', '軸', '孔', '銷', '承', '輪', '面', '軸承', '配合']
found_parts = [e for e in entities if any(k in e for k in parts_keywords)]

if found_parts:
    print("\n📦 在知識圖譜中發現的【零件/物理特徵/配合】相關實體：")
    for p in sorted(found_parts):
        print(f"  - {p}")
else:
    print("\n❌ 在知識圖譜中沒有找到任何帶有 '零件', '軸', '孔' 等關鍵字的實體。")
    print("\n以下是隨機抽樣的 20 個實體，讓您參考裡面到底存了什麼：")
    print(list(entities)[:20])
