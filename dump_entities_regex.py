import re

with open('server/data/0213_export.csv', 'rb') as f:
    # Read ignoring nasty decode errors
    content = f.read().decode('utf-8', errors='ignore')

# Regex to pull out rdfs__label values from the Neo4j dump format Node(...)
entities = set()
for match in re.finditer(r"rdfs__label: '([^']+)'", content):
    entities.add(match.group(1))
    
# Also try without quotes
for match in re.finditer(r'rdfs__label: "([^"]+)"', content):
    entities.add(match.group(1))

print(f'Total labeled entities found: {len(entities)}')

parts = []
print('\n=== 所有本體論標籤 (Labels) 分析 ===')
for e in sorted(entities):
    # Print out any that sound like physical parts
    if any(keyword in e for keyword in ['零件', '件', '機台', '軸', '孔', '銷', '承', '輪', '面']):
        parts.append(e)

if parts:
    print('找到可能是零件/特徵的實體：')
    for p in parts:
        print(f'- {p}')
else:
    print('沒有找到名稱中包含 "零件/軸/孔/銷/面/承" 等字眼的標籤。')

print('\n如果您需要看全部清單，這裡抽樣 20 個：')
print(list(entities)[:20])
