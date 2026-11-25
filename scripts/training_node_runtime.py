"""Fetch a portable official Node 22 executable and verify its published SHA-256."""
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import tarfile
from urllib.request import urlopen
import zipfile


def obtain(destination: Path):
    system={"Darwin":"darwin","Windows":"win"}.get(platform.system())
    arch={"arm64":"arm64","aarch64":"arm64","x86_64":"x64","AMD64":"x64"}.get(platform.machine())
    if not system or not arch: raise RuntimeError("Build the desktop runtime on supported macOS or Windows")
    extension="zip" if system=="win" else "tar.gz"
    version="v22.23.5"
    base=f"https://nodejs.org/dist/{version}/"
    with urlopen(base+"SHASUMS256.txt",timeout=30) as response:
        lines=response.read().decode().splitlines()
    pattern=rf"node-{re.escape(version)}-{system}-{arch}\.{re.escape(extension)}"
    candidates=[line.split() for line in lines if len(line.split())==2 and re.fullmatch(pattern,line.split()[1])]
    if len(candidates)!=1: raise RuntimeError("Official Node runtime checksum entry is ambiguous or missing")
    expected,filename=candidates[0]
    with urlopen(base+filename,timeout=60) as response: archive=response.read()
    actual=hashlib.sha256(archive).hexdigest()
    if actual!=expected: raise RuntimeError("Official Node runtime checksum mismatch")
    if extension=="zip":
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            binary=source.read(filename[:-4]+"/node.exe")
    else:
        with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as source:
            binary=source.extractfile(filename[:-7]+"/bin/node").read()
    destination.unlink(missing_ok=True)
    destination.write_bytes(binary);destination.chmod(0o755)
    destination.with_name("node-source.json").write_text(json.dumps({"url":base+filename,"archive_sha256":actual,"executable_sha256":hashlib.sha256(binary).hexdigest()},indent=2)+"\n")
