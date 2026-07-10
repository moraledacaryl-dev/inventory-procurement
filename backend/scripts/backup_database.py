import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gzip, hashlib, os, pathlib, shutil, subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import BackupRecord

def main():
    backup_dir=pathlib.Path(os.getenv('BACKUP_DIR','./backups')); backup_dir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    if settings.database_url.startswith('sqlite'):
        source=pathlib.Path(settings.database_url.replace('sqlite:///','',1)); target=backup_dir/f'inventory-{stamp}.db'; shutil.copy2(source,target)
    else:
        target=backup_dir/f'inventory-{stamp}.sql.gz'; parsed=urlparse(settings.database_url.replace('postgresql+psycopg','postgresql'))
        env={**os.environ,'PGPASSWORD':parsed.password or ''}; cmd=['pg_dump','-h',parsed.hostname or 'localhost','-p',str(parsed.port or 5432),'-U',parsed.username or 'inventory','-d',(parsed.path or '/inventory').lstrip('/')]
        raw=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout; target.write_bytes(gzip.compress(raw))
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    with SessionLocal() as db: db.add(BackupRecord(filename=target.name,size_bytes=target.stat().st_size,checksum_sha256=digest)); db.commit()
    print(target)
if __name__=='__main__': main()
