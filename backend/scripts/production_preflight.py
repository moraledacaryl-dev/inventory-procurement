import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings

def main():
    errors=[]
    if settings.app_env=='production':
        if len(settings.jwt_secret)<32 or any(x in settings.jwt_secret.lower() for x in ['change','development','secret']): errors.append('JWT_SECRET must be a strong production secret')
        if settings.bootstrap_owner_password=='change-this-password-now' or len(settings.bootstrap_owner_password)<12: errors.append('Bootstrap owner password must be changed and contain at least 12 characters')
        if any(x.startswith('http://') for x in settings.cors_origins): errors.append('Production CORS origins must use HTTPS')
        if '*' in settings.cors_origins: errors.append('Wildcard production CORS is forbidden')
        if settings.database_url.startswith('sqlite'): errors.append('Production must use PostgreSQL')
        if '*' in settings.trusted_hosts or 'testserver' in settings.trusted_hosts: errors.append('Production TRUSTED_HOSTS must contain only deployed hostnames')
        if settings.max_request_bytes>52_428_800: errors.append('MAX_REQUEST_BYTES must not exceed 50 MB')
        if settings.backup_max_age_hours>168: errors.append('BACKUP_MAX_AGE_HOURS must not exceed seven days')
    if errors:
        print('\n'.join(f'ERROR: {x}' for x in errors)); sys.exit(1)
    print('Production preflight passed')
if __name__=='__main__': main()
