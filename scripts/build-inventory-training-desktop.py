"""Platform-native unsigned desktop build; run on the target OS in CI."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
stage = ROOT / "build/training-desktop-source"
stage.mkdir(parents=True,exist_ok=True)
for name in ("app","training"):
    shutil.copytree(ROOT/"backend"/name,stage/"backend"/name,dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__","tests","*.db","*.sqlite",".env*"))
(stage/"runtime").mkdir(exist_ok=True)
node_target=stage/"runtime"/("node.exe" if os.name=="nt" else "node")
from training_node_runtime import obtain
obtain(node_target)
web = ROOT / "frontend/.next/standalone"
if not (web/".next/static").is_dir(): raise SystemExit("Prepare the standalone training frontend first")
if not (web/"inventory-training-build.json").is_file(): raise SystemExit("Verify the training web build before packaging")
for folder in (stage,web):
    for path in folder.rglob("*"):
        if path.is_file() and (path.name.startswith(".env") or path.suffix in {".db",".sqlite"} or path.name in {"session-key","manager-key"}):
            raise SystemExit("Private runtime state must not enter a desktop build")
args=[sys.executable,"-m","PyInstaller","--noconfirm","--clean","--onedir","--name","Hidden Oasis Inventory Training",
    "--paths",str(ROOT/"backend"),"--collect-submodules","app","--collect-submodules","training",
    "--collect-submodules","uvicorn","--collect-submodules","sqlalchemy",
    "--hidden-import","passlib.handlers.pbkdf2","--hidden-import","email_validator","--collect-submodules","jose.backends",
    "--add-data",str(stage/"backend")+os.pathsep+"backend",
    "--add-data",str(stage/"runtime")+os.pathsep+"runtime",
    "--add-data",str(web)+os.pathsep+"frontend/.next/standalone"]
if sys.platform=="darwin":args.append("--windowed")
args.append(str(ROOT/"scripts/start-inventory-training.py"))
subprocess.run(args,cwd=ROOT,check=True)
print("Unsigned native build created. Signing and notarization are not configured.")
