"""Offline training-state recovery for qualified administrators only.

No business backup-status row is created. The archive contains private local
session/trainer keys and employee history; it is never a distribution package.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile

MARKER={"application":"hidden-oasis-inventory-training","schema":1}
FIXED={"training-only.json","session-key","manager-key","progress.sqlite"}
ATTEMPT=re.compile(r"attempt-[a-f0-9-]{36}\.sqlite")
FORMAT="hidden-oasis-training-recovery-v1"


def private(path,mode):
    if os.name=="posix":path.chmod(mode)


def files(root):
    if root.is_symlink() or root.name!="inventory-training" or not root.is_dir():
        raise ValueError("Choose an existing dedicated training directory")
    marker=root/"training-only.json"
    if marker.is_symlink() or json.loads(marker.read_text())!=MARKER:
        raise ValueError("Recovery accepts only marked isolated training state")
    result={}
    for path in root.iterdir():
        if path.name in FIXED or ATTEMPT.fullmatch(path.name):
            if path.is_symlink() or not path.is_file():raise ValueError("Training state cannot contain links or directories")
            result[path.name]=path
    if not FIXED<=result.keys():raise ValueError("Training recovery needs registry and both private keys")
    return result


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_state(root):
    rows=files(root)
    for name,path in rows.items():
        if name.endswith(".sqlite"):
            with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as db:
                if db.execute("PRAGMA integrity_check").fetchone()!=("ok",):raise ValueError("Training database integrity check failed")
                if db.execute("PRAGMA foreign_key_check").fetchone():raise ValueError("Training database relationship check failed")
    with sqlite3.connect((root/"progress.sqlite").as_uri()+"?mode=ro",uri=True) as db:
        for (id,) in db.execute("SELECT id FROM attempts"):
            if f"attempt-{id}.sqlite" not in rows:raise ValueError("A saved practice database is missing; repair before backing up")
    if len((root/"session-key").read_text().strip())<64 or len((root/"manager-key").read_text().strip())<32:raise ValueError("Private training keys are incomplete")
    return rows


def backup(root:Path,archive:Path,*,stopped=False):
    if not stopped:raise ValueError("Stop training before making a recovery copy")
    root=root.absolute();archive=archive.absolute()
    if archive.exists() or archive.is_symlink() or root==archive or root in archive.parents:
        raise ValueError("Choose a new private backup file outside the training directory")
    rows=validate_state(root)
    before={name:digest(path) for name,path in rows.items()}
    # Create only a fresh file; failed or concurrently changed snapshots are
    # removed, never replacing an earlier administrator recovery copy.
    archive.parent.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,"wb") as stream,zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as out:
            for name,path in sorted(rows.items()):out.write(path,name)
            out.writestr("recovery-manifest.json",json.dumps({"format":FORMAT,"files":before},sort_keys=True))
        after={name:digest(path) for name,path in files(root).items()}
        if before!=after or any((root/(name+suffix)).exists() for name in rows if name.endswith(".sqlite") for suffix in ("-wal","-journal")):
            raise ValueError("Training state changed or has an unfinished journal; stop training and retry")
        private(archive,0o600)
        return {"files":len(rows),"sha256":digest(archive)}
    except BaseException:
        archive.unlink(missing_ok=True)
        raise


def restore(archive:Path,target:Path,*,stopped=False):
    if not stopped:raise ValueError("Stop training before restoring a recovery copy")
    target=target.absolute()
    if target.name!="inventory-training" or target.exists() or target.is_symlink():
        raise ValueError("Restore only into a new, absent inventory-training directory; preserve the previous installation")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="training-restore-",dir=target.parent) as temporary:
        stage=Path(temporary)/"inventory-training";stage.mkdir(mode=0o700)
        with zipfile.ZipFile(archive) as source:
            names=source.namelist()
            if len(names)!=len(set(names)) or "recovery-manifest.json" not in names:raise ValueError("Recovery manifest is missing or duplicated")
            manifest=json.loads(source.read("recovery-manifest.json"))
            hashes=manifest.get("files",{})
            if manifest.get("format")!=FORMAT or not isinstance(hashes,dict) or set(names)!=set(hashes)|{"recovery-manifest.json"}:raise ValueError("Invalid training recovery manifest")
            for name,expected in hashes.items():
                if name not in FIXED and not ATTEMPT.fullmatch(name):raise ValueError("Recovery archive contains an unexpected path")
                entry=source.getinfo(name)
                if entry.file_size>512*1024*1024 or (entry.external_attr>>16)&0o170000==0o120000:raise ValueError("Invalid training recovery file")
                payload=source.read(name)
                if hashlib.sha256(payload).hexdigest()!=expected:raise ValueError("Recovery file checksum does not match")
                path=stage/name;path.write_bytes(payload);private(path,0o600)
        rows=validate_state(stage)
        # Reserve a fresh target exclusively before replacing our own empty
        # placeholder atomically on this filesystem. Existing data is refused.
        if os.name=="nt":stage.rename(target)  # Windows rename refuses any existing destination.
        else:
            target.mkdir(mode=0o700)
            stage.replace(target)
        private(target,0o700)
        return {"files":len(rows),"sha256":digest(archive)}


def require_closed_ports():
    import socket
    for port in (3400,8400):
        with socket.socket() as probe:
            if os.name!="nt":probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            elif hasattr(socket,"SO_EXCLUSIVEADDRUSE"):probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            try:probe.bind(("127.0.0.1",port))
            except OSError:raise ValueError("Close the training application and its services before recovery")


def main():
    parser=argparse.ArgumentParser(description="Offline recovery of isolated Inventory Training; archive contains private keys and learner history")
    parser.add_argument("operation",choices=("backup","restore"))
    parser.add_argument("--data",required=True,type=Path)
    parser.add_argument("--archive",required=True,type=Path)
    parser.add_argument("--training-is-stopped",required=True,action="store_true")
    args=parser.parse_args();require_closed_ports()
    result=backup(args.data,args.archive,stopped=True) if args.operation=="backup" else restore(args.archive,args.data,stopped=True)
    print(json.dumps({"operation":args.operation,**result}))


if __name__=="__main__":main()
