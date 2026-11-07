"""Check local Markdown links in the project entrypoints and architecture notes."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = [root / 'README.md', root / 'PROGRESS.md', *sorted((root / 'docs/architecture').glob('*.md'))]
errors = []
for source in files:
    content = source.read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)]+)\)', content):
        if '://' in target or target.startswith('#'):
            continue
        path = target.split('#', 1)[0]
        if path and not (source.parent / path).exists():
            errors.append(f'{source.relative_to(root)} -> {target}')
if errors:
    raise SystemExit('Broken relative links:\n' + '\n'.join(errors))
print(f'PASS: relative links in {len(files)} documentation files')
