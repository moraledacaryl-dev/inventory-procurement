"""CI/admin native offline-recovery proof; never uploads the private archive."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    args.work.mkdir(parents=True,exist_ok=False)
    if os.name=='posix':args.work.chmod(0o700)
    executable=args.executable.resolve();data=args.data.resolve()
    archive=args.work/'private-training-recovery.zip';target=args.work/'restored'/'inventory-training'
    # Native shutdown can take a moment to release its local ports.
    import socket
    for _ in range(100):
        occupied=False
        for port in (3400,8400):
            with socket.socket() as probe:
                if os.name!='nt':probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                elif hasattr(socket,'SO_EXCLUSIVEADDRUSE'):probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                try:probe.bind(('127.0.0.1',port))
                except OSError:occupied=True
        if not occupied:break
        time.sleep(.1)
    else:raise RuntimeError('Native training has not stopped; recovery refused')
    for operation,root in [('backup',data),('restore',target)]:
        completed=subprocess.run([str(executable),'--training-recovery',operation,'--training-is-stopped','--data',str(root),'--archive',str(archive)],capture_output=True,text=True,timeout=90)
        if completed.returncode:raise RuntimeError('Native offline '+operation+' failed: '+completed.stderr[-2000:])
    with zipfile.ZipFile(archive) as source:
        manifest=json.loads(source.read('recovery-manifest.json'))
    for name,expected in manifest['files'].items():
        if hashlib.sha256((data/name).read_bytes()).hexdigest()!=expected or hashlib.sha256((target/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Native recovery did not preserve original state')
    with closing(sqlite3.connect(target/'progress.sqlite')) as db:
        attempts=db.execute('SELECT count(*) FROM attempts').fetchone()[0]
        finals=db.execute("SELECT count(*) FROM exams WHERE status='passed'").fetchone()[0]
        certificates=db.execute("SELECT count(*) FROM exams WHERE status='passed' AND module IS NULL").fetchone()[0]
    if not attempts or not finals or not certificates:raise RuntimeError('Native recovery must preserve demonstrated employee work and duty certification')
    # Only this aggregate proof is suitable for the CI artifact. Private keys,
    # participant data and the recovery archive stay in runner temporary storage.
    proof={'native_backup_restore':'passed','preserved_files':len(manifest['files']),'preserved_attempts':attempts,'preserved_passed_finals':finals,'preserved_certificates':certificates}
    Path('dist/TRAINING-RECOVERY-PROOF.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof))


if __name__=='__main__':main()
