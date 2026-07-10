import sys
from app.core.config import settings

def main():
    errors=[]
    if settings.app_env=='production':
        if len(settings.jwt_secret)<32 or 'change' in settings.jwt_secret.lower() or 'development' in settings.jwt_secret.lower(): errors.append('JWT_SECRET must be a strong production secret')
        if settings.bootstrap_owner_password=='change-this-password-now': errors.append('Default owner password is forbidden in production')
        if any(x.startswith('http://') and 'localhost' not in x for x in settings.cors_origins): errors.append('Production CORS origins must use HTTPS')
        if settings.database_url.startswith('sqlite'): errors.append('Production must use PostgreSQL')
    if errors:
        print('\n'.join(f'ERROR: {x}' for x in errors)); sys.exit(1)
    print('Production preflight passed')
if __name__=='__main__': main()
