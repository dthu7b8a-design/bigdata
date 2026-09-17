"""Download latest HDFS ODS run, compute with Windows local Spark, compare results.

Default output: project/data_hdfs_roundtrip. Production data is never written.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

from hdfs_sync import WebHDFS
from hdfs_pipeline_demo import compare

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
CSV_FILES = ('nvv2t.csv', 'nvv2t_md_end.csv', 'dsv13r2.csv')


def list_status(client, path):
    with client.request(path, 'LISTSTATUS') as response:
        return json.load(response)['FileStatuses']['FileStatus']


def select_source(client, root, run_id):
    if run_id is None:
        runs = [entry['pathSuffix'] for entry in list_status(client, root)
                if entry['type'] == 'DIRECTORY'
                and re.fullmatch(r'\d{8}T\d{12}Z', entry['pathSuffix'])]
        if not runs:
            raise RuntimeError(f'No timestamped ODS run exists in {root}; sync data first')
        run_id = max(runs)
    if not re.fullmatch(r'\d{8}T\d{12}Z', run_id):
        raise ValueError('run-id must use the pipeline UTC timestamp format')
    source = root.rstrip('/') + '/' + run_id
    present = {entry['pathSuffix'] for entry in list_status(client, source) if entry['type'] == 'FILE'}
    missing = set(CSV_FILES) - present
    if missing:
        raise RuntimeError(f'Latest/selected ODS run incomplete: {source}, missing {sorted(missing)}')
    return source, run_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default=os.getenv('EVCHARGE_WEBHDFS', 'http://192.168.203.128:9870'))
    parser.add_argument('--user', default='bit')
    parser.add_argument('--remote-root', default='/evcharge-stage2/ods', help='ODS parent containing timestamped run directories')
    parser.add_argument('--run-id', help='Specific ODS run; default: latest timestamped directory on HDFS')
    parser.add_argument('--output', type=Path, default=PROJECT / 'data_hdfs_roundtrip')
    parser.add_argument('--baseline', type=Path, default=PROJECT / 'data/ads/dashboard.json')
    args = parser.parse_args()
    output = args.output.resolve()
    baseline_path = args.baseline.resolve(strict=True)
    # No output equal to, inside, or containing production/code directories.
    for protected in [PROJECT / 'data', PROJECT / 'jobs', PROJECT / 'api', PROJECT / 'frontend', PROJECT / 'docs']:
        protected = protected.resolve()
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError(f'Output overlaps protected project path: {protected}')
    if output == baseline_path or output in baseline_path.parents:
        raise ValueError('Baseline must be outside the output directory')
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    client = WebHDFS(args.endpoint, args.user)
    remote, source_run = select_source(client, args.remote_root, args.run_id)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work = output / '_hdfs_inputs' / stamp
    work.mkdir(parents=True, exist_ok=False)
    (work / 'baseline.json').write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
    hashes = {name: client.download(remote + '/' + name, work / name) for name in CSV_FILES}
    provenance = {'endpoint': args.endpoint, 'remote_source': remote, 'source_run_id': source_run,
                  'download_sha256': hashes, 'baseline': str(baseline_path),
                  'baseline_run_id': baseline['meta']['run_id'], 'downloaded_at': stamp}
    (work / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    if hashes != baseline['meta']['source_sha256']:
        raise RuntimeError('HDFS source SHA256 differs from baseline; select matching --run-id/--baseline')
    print(json.dumps({'remote_source': remote, 'output': str(output), 'input_sha256_verified': True}), flush=True)
    from jobs.pipeline import run
    computed = run(work, output, train=True)
    result_file = output / 'ads' / computed['meta']['run_id'] / 'dashboard.json'
    result = json.loads(result_file.read_text(encoding='utf-8'))
    differences = []
    for section in ['kpis', 'charts', 'quality', 'model']:
        compare(baseline[section], result[section], section, differences)
    for key in ['source_sha256', 'range_start', 'range_end', 'spark_version']:
        compare(baseline['meta'][key], result['meta'][key], 'meta.' + key, differences)
    report = {**provenance, 'passed': not differences, 'computed_run_id': result['meta']['run_id'],
              'execution': 'Windows local Spark computation + Ubuntu HDFS storage via WebHDFS',
              'spark_direct_hdfs_rpc': False, 'compared_sections': ['kpis', 'charts', 'quality', 'model'],
              'ignored_metadata': ['run_id', 'updated_at'],
              'numeric_tolerance': {'relative': 1e-9, 'absolute': 1e-8},
              'differences': differences, 'result_dashboard': str(result_file)}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    (output / 'reports' / f'{stamp}-hdfs-comparison.json').write_text(encoded, encoding='utf-8')
    temporary = output / 'comparison.json.tmp'
    temporary.write_text(encoded, encoding='utf-8')
    temporary.replace(output / 'comparison.json')
    print(json.dumps({'passed': report['passed'], 'report': str(output / 'comparison.json')}, ensure_ascii=False), flush=True)
    if differences:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
