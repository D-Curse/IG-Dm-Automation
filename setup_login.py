"""Create/reset the single dashboard administrator without exposing a password in arguments."""
import getpass
import json
import os
from pathlib import Path
from werkzeug.security import generate_password_hash

def main():
    username = input('Dashboard username: ').strip()
    if not username or len(username) > 100:
        raise SystemExit('Enter a username between 1 and 100 characters.')
    password = getpass.getpass('Password (at least 14 characters): ')
    if len(password) < 14 or len(password) > 256:
        raise SystemExit('Use a password or passphrase between 14 and 256 characters.')
    if password != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords do not match. Nothing changed.')
    directory = Path(__file__).parent / 'instance'
    directory.mkdir(exist_ok=True)
    target = directory / 'dashboard-auth.json'
    temporary = directory / 'dashboard-auth.json.tmp'
    temporary.write_text(json.dumps({'username': username, 'password_hash': generate_password_hash(password, method='scrypt')}))
    os.replace(temporary, target)
    print('Dashboard login saved. Existing sessions are invalidated. Open /login to sign in.')

if __name__ == '__main__':
    main()
