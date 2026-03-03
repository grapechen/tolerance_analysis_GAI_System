import re

with open('server/data/0213_export.csv', 'r', encoding='big5', errors='ignore') as f:
    content = f.read()

# count relations
relations = {}
for match in re.finditer(r",\[:([^\]]+)\]", content):
    rel = match.group(1).split('{')[0].strip()
    relations[rel] = relations.get(rel, 0) + 1

print("=== Relationships ===")
for r, c in sorted(relations.items(), key=lambda x: -x[1]):
    print(f"- {r}: {c}")

# count node types
nodes = {}
for match in re.finditer(r"\(:([^ {]+)", content):
    node = match.group(1).strip()
    nodes[node] = nodes.get(node, 0) + 1

print("\n=== Node Types ===")
for n, c in sorted(nodes.items(), key=lambda x: -x[1]):
    print(f"- {n}: {c}")

