"""Build a standalone zipapp from the local package, using only Python stdlib."""

from pathlib import Path
import shutil
import tempfile
import zipapp

root = Path(__file__).resolve().parents[1]
source = root / "src"
output = root / "dist" / "revenuepilot.pyz"
output.parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    stage = Path(temp)
    shutil.copytree(source / "revenuepilot", stage / "revenuepilot")
    zipapp.create_archive(stage, target=output, main="revenuepilot.app:serve", compressed=True)
print(f"BUILD PASS: {output.relative_to(root)} ({output.stat().st_size} bytes)")
