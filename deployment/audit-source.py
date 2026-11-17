"""Check tracked/staged source completeness and obvious credential leaks."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    command = ['git', '-c', f'safe.directory={ROOT.as_posix()}', 'ls-files', '-z']
    files = subprocess.check_output(command, cwd=ROOT).decode().split('\0')
    files = [name for name in files if name]
    required = ['workbuddy_optimizer.py', 'workbuddy_transport.py', 'optimizer_service.py',
                'config/request-template.json', 'desktop/agent.py', 'desktop/optimizer.ahk',
                'desktop/result_format.ahk', 'desktop/install.ps1', 'desktop/settings.example.json',
                'deployment/compose.yaml', 'deployment/Dockerfile', 'deployment/entrypoint.sh',
                'deployment/supervisord.conf', 'deployment/chromium-container',
                'deployment/prepare-server.py', 'deployment/setup-windows.ps1',
                'deployment/desktop_tunnel.py', 'deployment/verify-service.py', 'DEPLOY.md']
    failures = [f'missing: {name}' for name in required if name not in files]
    known_keys = []
    for name in ('.wenxinyiyan-api-key', '.optimizer-api-key'):
        path = ROOT / name
        if path.exists():
            known_keys.append(path.read_bytes().strip())
    forbidden = ('capture/', 'inspection/', 'official-research/', 'desktop/state/',
                 'desktop/runtime/', 'data/', '.venv/', 'deployment/tools/', 'deployment/downloads/')
    for name in files:
        if name.startswith(forbidden) or name in ('.env', '.wenxinyiyan-api-key', '.optimizer-api-key', 'desktop/settings.json'):
            failures.append(f'private/generated file tracked: {name}')
        data = (ROOT / name).read_bytes()
        if any(key and key in data for key in known_keys):
            failures.append(f'local API key found: {name}')
        if re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:OPENSSH|RSA|EC) PRIVATE KEY-----)', data):
            failures.append(f'credential-like content: {name}')
    template = json.loads((ROOT / 'config/request-template.json').read_text(encoding='utf-8'))
    if set(template) != {'headers', 'body'}:
        failures.append('template contains capture metadata')
    if any(re.search('authorization|cookie|token|secret|user.id|machine.id', key, re.I) for key in template['headers']):
        failures.append('template contains private header')
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'PASS {len(files)} tracked files; required source/config complete; no known key or private artifacts tracked')


if __name__ == '__main__':
    main()
