"""Download real HDFS inputs, run local Spark, compare business results.

Outputs only under deploy; no edits to jobs or production data. Not Spark RPC I/O.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

from hdfs_sync import WebHDFS

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def compare(left, right, path='$', differences=None):
    if differences is None:
        differences = []
    if isinstance(left, dict) and isinstance(right, dict):
        if left.keys() != right.keys():
            differences.append(path + ': keys differ')
        for key in left.keys() & right.keys():
            compare(left[key], right[key], path + '.' + key, differences)
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            differences.append(path + ': lengths differ')
        # Spark unordered groupBy results may arrive in a different row order.
        def row_key(row):
            if isinstance(row, dict):
                return json.dumps({k: v for k, v in row.items() if isinstance(v, (str, int))}, sort_keys=True, ensure_ascii=False)
            return json.dumps(row, sort_keys=True, ensure_ascii=False)
        for index, (a, b) in enumerate(zip(sorted(left, key=row_key), sorted(right, key=row_key))):
            compare(a, b, f'{path}[{index}]', differences)
    elif isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(left, bool) and not isinstance(right, bool):
        if not math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-8):
            differences.append(f'{path}: {left} != {right}')
    elif left != right:
        differences.append(f'{path}: values differ')
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://192.168.203.128:9870')
    parser.add_argument('--remote-source', default='/evcharge-stage2/ods')
    parser.add_argument('--baseline', type=Path, default=PROJECT / 'data/ads/dashboard.json')
    parser.add_argument('--resume-comparison', type=Path, help='Recompare an already completed demo directory without rerunning Spark')
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work = args.resume_comparison or Path(__file__).parent / 'hdfs-demo' / stamp
    if args.resume_comparison:
        baseline = json.loads((work / 'baseline.json').read_text(encoding='utf-8'))
    else:
        work.mkdir(parents=True)
        (work / 'baseline.json').write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
    client = WebHDFS(args.endpoint)
    hashes = {}
    for name in ['nvv2t.csv', 'nvv2t_md_end.csv', 'dsv13r2.csv']:
        hashes[name] = client.download(args.remote_source.rstrip('/') + '/' + name, work / 'input' / name)
    if hashes != baseline['meta']['source_sha256']:
        raise RuntimeError('HDFS input hashes differ from the local reference run')
    if not args.resume_comparison:
        from jobs.pipeline import run
        run(work / 'input', work / 'output', train=True)
    # Compare serialized artifacts on both sides: in-memory date/Decimal objects
    # must not be compared directly with JSON strings/numbers.
    result = json.loads((work / 'output/ads/dashboard.json').read_text(encoding='utf-8'))
    differences = []
    for section in ['kpis', 'charts', 'quality', 'model']:
        compare(baseline[section], result[section], section, differences)
    for field in ['source_sha256', 'range_start', 'range_end', 'spark_version']:
        compare(baseline['meta'][field], result['meta'][field], 'meta.' + field, differences)
    report = {'passed': not differences, 'execution': 'Windows local Spark; inputs downloaded from Ubuntu HDFS via WebHDFS',
              'spark_direct_hdfs_rpc': False, 'endpoint': args.endpoint, 'remote_source': args.remote_source,
              'baseline_run_id': baseline['meta']['run_id'], 'hdfs_input_run_id': result['meta']['run_id'],
              'input_sha256': hashes, 'compared_sections': ['kpis', 'charts', 'quality', 'model'],
              'ignored_metadata': ['run_id', 'updated_at'], 'numeric_tolerance': {'relative': 1e-9, 'absolute': 1e-8},
              'array_order': 'rows compared after sorting by string/integer identity fields',
              'differences': differences, 'note': 'Parquet/model binary bytes across independent runs are not required to match; synced files are separately byte-verified.'}
    (work / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'report': str(work / 'comparison.json')}, ensure_ascii=False), flush=True)
    if differences:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
