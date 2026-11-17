"""Validate LAN service and authentication without printing credentials."""
import argparse
import json
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--key-file', type=Path, default=ROOT / '.wenxinyiyan-api-key')
    parser.add_argument('--optimize', action='store_true', help='Uses account model quota')
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    key = args.key_file.read_text(encoding='utf-8').strip()
    base = args.url.rstrip('/')
    with opener.open(base + '/health', timeout=10) as response:
        assert json.load(response)['status'] == 'ok'
    try:
        opener.open(urllib.request.Request(base + '/optimize', data=b'{"text":"test"}',
                    headers={'Content-Type': 'application/json'}), timeout=10)
    except urllib.error.HTTPError as error:
        assert error.code == 401, f'Expected 401, got {error.code}'
    else:
        raise SystemExit('Unauthenticated optimize must fail')
    request = urllib.request.Request(base + '/ready', headers={'X-API-Key': key})
    with opener.open(request, timeout=10) as response:
        assert json.load(response)['status'] == 'discovered'
    print('PASS health, authentication and channel discovery (not proof of login)')
    if args.optimize:
        request = urllib.request.Request(base + '/optimize',
            data=json.dumps({'text': '帮我整理会议纪要'}, ensure_ascii=False).encode(),
            headers={'Content-Type': 'application/json', 'X-API-Key': key})
        with opener.open(request, timeout=70) as response:
            result = json.load(response)
        assert result['status'] == 'success' and result['optimized_text'].strip()
        print('PASS real optimization; output characters:', len(result['optimized_text']))


if __name__ == '__main__':
    main()
