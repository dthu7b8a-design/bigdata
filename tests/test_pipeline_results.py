"""Independent checks against immutable teacher CSV, not repeated Spark expressions."""
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.getenv('BIGDATA_SOURCE', str(ROOT/'datasets/teacher')))
RESULT=Path(os.getenv('BIGDATA_RESULT', str(ROOT/'data/ads/dashboard.json')))

@pytest.fixture(scope='module')
def result():
    return json.loads(RESULT.read_text(encoding='utf-8'))

@pytest.fixture(scope='module')
def rows():
    with (SOURCE/'nvv2t.csv').open(encoding='utf-8',newline='') as source:
        return list(csv.DictReader(source))

@pytest.fixture(scope='module')
def valid_rows(rows):
    return [r for r in rows if Decimal(r['kwhTotal'])>0 and 0<Decimal(r['chargeTimeHrs'])<=24]

def test_kpis_match_source(result,valid_rows):
    assert result['kpis']['sessions']==len(valid_rows)
    assert Decimal(str(result['kpis']['energy_kwh']))==sum(Decimal(r['kwhTotal']) for r in valid_rows)
    assert Decimal(str(result['kpis']['fees']))==sum(Decimal(r['charging_fees']) for r in valid_rows)
    assert result['kpis']['users']==len({r['userId'] for r in valid_rows})
    assert result['kpis']['stations']==len({r['stationId'] for r in valid_rows})

@pytest.mark.parametrize('chart',['daily','hourly','weekday','stations','locations','facility','platform','vehicle','users','duration','station_hour','platform_daytype'])
def test_all_views_count_same_population(result,valid_rows,chart):
    assert sum(r['sessions'] for r in result['charts'][chart])==len(valid_rows)

def test_cross_comparison_independent(result,valid_rows):
    expected=Counter()
    for row in valid_rows:
        date=datetime.fromisoformat('20'+row['created'][2:])
        expected[(row['platform'],'周末' if date.weekday()>=5 else '工作日')]+=1
    actual={(r['platform'],r['day_type']):r['sessions'] for r in result['charts']['platform_daytype']}
    assert actual==expected

def test_source_unchanged(result):
    for filename,digest in result['meta']['source_sha256'].items():
        assert hashlib.sha256((SOURCE/filename).read_bytes()).hexdigest()==digest

def test_forecast_split_and_selection(result):
    model=result['model']; split=model['split']
    assert split['train']['end']<split['validation']['start']<=split['validation']['end']<split['test']['start']
    assert len(model['predictions'])==split['test']['rows']
    assert model['forecast'][0]['date']>split['test']['end']
    assert model['selected_model']==min(model['validation_metrics'],key=lambda key:model['validation_metrics'][key]['rmse'])
    assert {r['model'] for r in model['metrics']}=={'同星期历史基线','线性回归','随机森林'}
    assert not {'label','charging_fees','ended','record_time'}.intersection(model['features'])

def test_quality_teacher_rules(result,rows,valid_rows):
    rules={r['id']:r for r in result['quality']['rules']}
    assert rules['R05']['count']==sum(float(r['kwhTotal'])==0 for r in rows)==55
    assert rules['R06']['count']==sum(float(r['charging_fees'])==0 for r in rows)==3016
    assert result['quality']['before']['sessions']==len(rows)
    assert result['quality']['after']['sessions']==len(valid_rows)
    assert result['quality']['rejected']['sessions']==len(rows)-len(valid_rows)
    assert result['quality']['after']['telemetry']==0
    assert result['quality']['rejected']['telemetry']==1594
    assert {r['facility_type'] for r in result['charts']['facility']}=={'交流','直流','交直流一体','未知类型（4）'}
    for entries in result['quality']['fee_by_period'].values():
        assert sum(r['sessions'] for r in entries)==len(valid_rows)
        assert sum(r['sessions'] for r in entries if r['fee_type']=='免费')==sum(Decimal(r['charging_fees'])==0 for r in valid_rows)
        assert sum(Decimal(str(r['fees'])) for r in entries)==sum(Decimal(r['charging_fees']) for r in valid_rows)
