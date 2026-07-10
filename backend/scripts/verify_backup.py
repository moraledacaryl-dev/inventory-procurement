import argparse, gzip, hashlib, pathlib, sqlite3, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('path'); parser.add_argument('--sha256'); args=parser.parse_args()
    path=pathlib.Path(args.path)
    if not path.exists() or not path.is_file(): raise SystemExit('Backup file does not exist')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if args.sha256 and digest.lower()!=args.sha256.lower(): raise SystemExit('Checksum mismatch')
    if path.suffix=='.gz':
        with gzip.open(path,'rb') as handle:
            head=handle.read(4096).lower()
            if b'create table' not in head and b'postgresql database dump' not in head and b'set statement_timeout' not in head: raise SystemExit('Compressed backup does not resemble a PostgreSQL dump')
    elif path.suffix=='.db':
        connection=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
        try:
            result=connection.execute('PRAGMA integrity_check').fetchone()[0]
            if result!='ok': raise SystemExit(f'SQLite integrity check failed: {result}')
        finally: connection.close()
    else: raise SystemExit('Unsupported backup format')
    print(f'Backup verification passed: {path.name} sha256={digest}')
if __name__=='__main__': main()
