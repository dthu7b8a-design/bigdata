"""Windows local Spark + Ubuntu WebHDFS storage; Python standard library only.

Sync is additive: retain remote files absent locally; never delete or format.
Every uploaded/skipped file is downloaded and SHA256 checked.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class WebHDFS:
    def __init__(self, endpoint, user='bit'):
        self.endpoint = endpoint.rstrip('/')
        self.host = urlsplit(endpoint).hostname
        self.user = user
        self.http = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, op, method='GET', data=None, **params):
        path = str(PurePosixPath(path))
        if '..' in PurePosixPath(path).parts or not path.startswith('/evcharge-stage2/') and path != '/evcharge-stage2':
            raise ValueError('Remote path must stay within /evcharge-stage2')
        url = self.endpoint + '/webhdfs/v1' + quote(path, safe='/') + '?' + urlencode({'op': op, 'user.name': self.user, **params})
        try:
            # CREATE first asks NameNode for a redirect; body goes only to DataNode.
            return self.http.open(Request(url, data=None if op == 'CREATE' else data, method=method), timeout=120)
        except HTTPError as e:
            if e.code != 307:
                raise
            redirect = urlsplit(e.headers['Location'])
            e.close()
            # This existing single-node VM advertises localhost/bitdev to clients.
            if redirect.scheme != 'http' or redirect.port != 9864 or redirect.hostname not in {self.host, 'localhost', '127.0.0.1', 'bitdev'}:
                raise ValueError('Unexpected DataNode redirect')
            url = urlunsplit((redirect.scheme, f'{self.host}:9864', redirect.path, redirect.query, ''))
            return self.http.open(Request(url, data=data, method=method), timeout=120)

    def mkdir(self, path):
        with self.request(path, 'MKDIRS', 'PUT') as response:
            if not json.load(response)['boolean']:
                raise RuntimeError('MKDIRS returned false')

    def download(self, remote, target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.hdfs-part')
        digest = hashlib.sha256()
        with self.request(remote, 'OPEN') as response, temporary.open('wb') as output:
            while block := response.read(1024 * 1024):
                output.write(block)
                digest.update(block)
        os.replace(temporary, target)
        return digest.hexdigest()


def sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default=os.environ.get('EVCHARGE_WEBHDFS', 'http://192.168.203.128:9870'))
    parser.add_argument('--user', default='bit')
    subs = parser.add_subparsers(dest='command', required=True)
    sync = subs.add_parser('sync')
    sync.add_argument('--source', type=Path, required=True)
    sync.add_argument('--remote', default='/evcharge-stage2')
    sync.add_argument('--overwrite', action='store_true', help='Allow replacing differing existing files')
    sync.add_argument('--evidence', type=Path, default=Path(__file__).parent / 'verification')
    get = subs.add_parser('get')
    get.add_argument('--remote', required=True)
    get.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    client = WebHDFS(args.endpoint, args.user)
    if args.command == 'get':
        print(json.dumps({'remote': args.remote, 'sha256': client.download(args.remote, args.output)}))
        return
    source = args.source.resolve(strict=True)
    evidence = args.evidence.resolve()
    if evidence == source or source in evidence.parents:
        raise ValueError('Evidence must be outside source tree')
    files = sorted(p for p in source.rglob('*') if p.is_file())
    if not files:
        raise ValueError('Source contains no files')
    evidence.mkdir(parents=True, exist_ok=True)
    manifest = {'started_at': datetime.now(timezone.utc).isoformat(), 'endpoint': args.endpoint,
                'source': str(source), 'remote': args.remote, 'mode': 'local-spark-webhdfs-storage', 'files': []}
    directories = set()
    for file in files:
        relative = file.relative_to(source)
        remote = args.remote.rstrip('/') + '/' + relative.as_posix()
        parent = str(PurePosixPath(remote).parent)
        if parent not in directories:
            client.mkdir(parent)
            directories.add(parent)
        before = sha256(file)
        downloaded = evidence / 'download' / relative
        exists = True
        try:
            with client.request(remote, 'GETFILESTATUS') as response:
                json.load(response)
        except HTTPError as e:
            if e.code != 404:
                raise
            exists = False
        action = 'unchanged'
        if not exists or client.download(remote, downloaded) != before:
            if exists and not args.overwrite:
                raise RuntimeError(f'Existing file differs; pass --overwrite: {remote}')
            with file.open('rb') as data:
                # Send bytes with Content-Length (files in this dataset are small).
                with client.request(remote, 'CREATE', 'PUT', data=data.read(), overwrite=str(args.overwrite).lower()) as response:
                    if response.status != 201:
                        raise RuntimeError(f'Upload failed: {remote}')
            action = 'uploaded'
        after = client.download(remote, downloaded)
        if before != after or sha256(file) != before:
            raise RuntimeError(f'SHA256 mismatch or source changed: {remote}')
        row = {'path': relative.as_posix(), 'remote': remote, 'bytes': file.stat().st_size,
               'local_sha256': before, 'download_sha256': after, 'verified': True, 'action': action}
        manifest['files'].append(row)
        print(f'{action}: {remote} SHA256 OK', flush=True)
        (evidence / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    manifest.update(completed_at=datetime.now(timezone.utc).isoformat(), verified_count=len(files),
                    total_bytes=sum(row['bytes'] for row in manifest['files']))
    (evidence / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'PASS: {len(files)} files, {manifest["total_bytes"]} bytes; {evidence / "manifest.json"}')


if __name__ == '__main__':
    main()
