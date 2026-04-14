import re

with open('server/data/ontology_export.csv', 'rb') as f:
    content = f.read().decode('utf-8', errors='ignore')

entities = set()
for match in re.finditer(r"'display':\s*'([^']+)'", content):
    entities.add(match.group(1))

print(f'Total entities found: {len(entities)}')
print('Possible Parts / Components:')
for e in sorted(entities):
    if any(keyword in e for keyword in ['零件', '件', '機台', '軸', '孔', '銷', '承']):
        print(f'- {e}')
