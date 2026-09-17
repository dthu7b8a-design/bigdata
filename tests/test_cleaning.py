"""Synthetic boundary cases exercise teacher rules even if today's CSV has no errors."""
from datetime import datetime
import pytest
from pyspark.sql import functions as F
from jobs.cleaning import clean_stations, clean_telemetry, enrich_sessions, period_name, session_reasons
from jobs.runtime import spark_session


@pytest.fixture(scope='module')
def spark():
    session = spark_session('teacher-cleaning-tests')
    yield session
    session.stop()


def test_battery_thresholds_and_reasons(spark):
    columns = ['charge_current (A)', 'soc', 'max_temperature (℃)', 'min_temperature (℃)',
               'available_energy (kw)', 'available_capacity (Ah)', 'pack_voltage (V)']
    baseline = ['1', '50', '30', '20', '1', '1', '330']
    cases = [('valid', baseline)]
    for name, index, value in [('negative_current', 0, '-22.5'), ('soc_low', 1, '-0.1'),
            ('soc_high', 1, '100.1'), ('hot', 2, '85.1'), ('cold', 3, '-40.1'),
            ('energy', 4, '-1'), ('capacity', 5, '-1'), ('voltage_zero', 6, '0'),
            ('voltage_negative', 6, '-1'), ('nan', 1, 'NaN'), ('infinite', 0, 'Infinity'),
            ('missing', 2, None), ('nonnumeric', 5, 'bad')]:
        row = baseline.copy()
        row[index] = value
        cases.append((name, row))
    cases += [('lower_edges', ['0', '0', '-40', '-40', '0', '0', '0.1']),
              ('upper_edges', ['1', '100', '85', '85', '1', '1', '330'])]
    raw = spark.createDataFrame([(name, *values) for name, values in cases], ['id', *columns])
    rules = []
    clean, rejected = clean_telemetry(raw, lambda *args: rules.append(args))
    assert {r.id for r in clean.collect()} == {'valid', 'lower_edges', 'upper_edges'}
    rejected_rows = rejected.collect()
    assert len(rejected_rows) == 13
    assert all(r.reason for r in rejected_rows)
    assert next(r for r in rejected_rows if r.id == 'negative_current')['charge_current (A)_raw'] == '-22.5'
    assert {r[0] for r in rules} == {'C01', 'C02', 'C03', 'C04', 'C05'}


def test_stations_missing_values_and_nonoperating(spark):
    raw = spark.createDataFrame([
        ('s1', 'a', '1', '1', '站点一', '地址一'),
        ('s2', 'a', '4', '2', '  ', None),
        ('s3', 'a', '2', '0', '站点三', '地址三'),
        ('s4', 'a', '3', '-1', '站点四', '地址四'),
        ('s5', 'a', '3', 'bad', '站点五', '地址五'),
        ('s6', 'a', '3', '1.5', '站点六', '地址六'),
    ], ['stationId', 'locationId', 'facilityType', 'device_count', 'station_name', 'address'])
    clean, rejected = clean_stations(raw, lambda *args: None)
    rows = {r.stationId: r for r in clean.collect()}
    assert set(rows) == {'s1', 's2'}
    assert rows['s1'].facility_type_name == '交流'
    assert rows['s2'].facility_type_name == '未知类型（4）'
    assert rows['s2'].station_name == '未命名站点（s2）'
    assert rows['s2'].address == '地址未知'
    assert rows['s2'].station_name_missing and rows['s2'].address_missing
    assert rejected.count() == 4


def test_session_numeric_boundaries_and_free_labels(spark):
    cases = [('valid', 1., 1., 1.), ('free', 1., 24., 0.), ('zero_energy', 0., 1., 0.),
             ('negative_energy', -1., 1., 0.), ('long', 1., 24.01, 1.),
             ('zero_duration', 1., 0., 0.), ('negative_duration', 1., -1., 1.),
             ('nan', float('nan'), 1., 0.), ('negative_fee', 1., 1., -1.)]
    df = spark.createDataFrame(cases, ['sessionId', 'kwhTotal', 'chargeTimeHrs', 'charging_fees'])
    df = (df.withColumn('created', F.lit(datetime(2024, 1, 1)))
          .withColumn('ended', F.lit(datetime(2024, 1, 2))).withColumn('reason', session_reasons()))
    assert {r.sessionId for r in df.filter("reason = ''").collect()} == {'valid', 'free'}
    enriched = enrich_sessions(df.withColumn('facilityType', F.lit('2'))
                               .withColumn('startTime', F.lit(19)).withColumn('endTime', F.lit(23)))
    free = enriched.filter("sessionId = 'free'").first()
    assert free.is_free and free.fee_type == '免费'
    assert free.start_period == '尖峰' and free.end_period == '低谷'
    assert free.facility_type_name == '直流'


def test_period_labels_cover_24_hours_and_boundaries(spark):
    df = spark.createDataFrame([(hour,) for hour in range(-1, 25)], ['hour'])
    result = {r.hour: r.period for r in df.withColumn('period', period_name('hour')).collect()}
    expected = ['低谷'] * 7 + ['平时'] * 3 + ['高峰'] * 2 + ['平时'] * 5 + ['高峰'] * 2 + ['尖峰'] * 2 + ['高峰'] * 2 + ['低谷']
    assert [result[h] for h in range(24)] == expected
    assert result[-1] == result[24] == '未知时段'
