import sys

with open('c:/Users/ardau/Desktop/tuah/engine/helioguard/data_sources.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('import ephem\nimport math\nfrom __future__', 'from __future__')
if 'import ephem' not in text:
    text = text.replace('from __future__ import annotations', 'from __future__ import annotations\nimport ephem\nimport math\n')

with open('c:/Users/ardau/Desktop/tuah/engine/helioguard/data_sources.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Imports patched")