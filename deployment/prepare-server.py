"""Download and verify the official WorkBuddy Linux package; create a local key."""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://download.codebuddy.cn/workbuddy/saas/linux-x64-deb/WorkBuddy-linux-x64-deb-5.6.2.40046327-c7b525f3.deb'
SHA256 = '12149ad8c0cd748fd5062d8f62c7827d688d8095427ada99b1ae9e7019897523'


def sha256(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind-ip', required=True, help='NAS LAN IPv4 address')
    args = parser.parse_args()
    import ipaddress
    address = ipaddress.ip_address(args.bind_ip)
    if address.version != 4 or not address.is_private or address.is_unspecified:
        raise SystemExit('Use a specific LAN IPv4 address, not 0.0.0.0/public IP')
    package = ROOT / 'deployment/downloads/WorkBuddy.deb'
    package.parent.mkdir(parents=True, exist_ok=True)
    if not package.exists() or sha256(package) != SHA256:
        temporary = package.with_suffix('.part')
        print('Downloading official WorkBuddy package (~410 MB)', flush=True)
        with urllib.request.urlopen(URL, timeout=60) as source, temporary.open('wb') as target:
            import shutil
            shutil.copyfileobj(source, target)
        if sha256(temporary) != SHA256:
            temporary.unlink()
            raise SystemExit('Package checksum mismatch; do not install')
        temporary.replace(package)
    key = ROOT / '.wenxinyiyan-api-key'
    if not key.exists():
        fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as target:
            target.write(secrets.token_urlsafe(32))
    if not key.read_text().strip():
        raise SystemExit('API key must not be empty')
    (ROOT / 'data').mkdir(exist_ok=True, mode=0o700)
    env = ROOT / '.env'
    if not env.exists():
        env.write_text(f'WENXINYIYAN_BIND_IP={address}\nWENXINYIYAN_API_PORT=18080\nWENXINYIYAN_DESKTOP_PORT=16080\n', encoding='utf-8')
    print('Verified package and initialized configuration; existing key/data/env preserved.')


if __name__ == '__main__':
    main()
