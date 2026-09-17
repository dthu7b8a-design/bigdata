"""Spark cleaning rules from 数据清洗需求表.xlsx; originals stay in ODS."""
from pyspark.sql import functions as F


# Teaching assumption, not a local electricity tariff or billing rule.
PERIOD_HOURS = {
    '低谷': [0, 1, 2, 3, 4, 5, 6, 23],
    '平时': [7, 8, 9, 12, 13, 14, 15, 16],
    '高峰': [10, 11, 17, 18, 21, 22],
    '尖峰': [19, 20],
}


def nonfinite(column):
    value = F.col(column)
    return value.isNull() | F.isnan(value) | (F.abs(value) == float('inf'))


def facility_name(column):
    value = F.trim(F.col(column))
    return (F.when(value == '1', '交流').when(value == '2', '直流')
            .when(value == '3', '交直流一体')
            .otherwise(F.concat(F.lit('未知类型（'), F.coalesce(value, F.lit('空')), F.lit('）'))))


def period_name(column):
    hour = F.col(column)
    return (F.when(hour.isin(PERIOD_HOURS['低谷']), '低谷')
            .when(hour.isin(PERIOD_HOURS['平时']), '平时')
            .when(hour.isin(PERIOD_HOURS['高峰']), '高峰')
            .when(hour.isin(PERIOD_HOURS['尖峰']), '尖峰').otherwise('未知时段'))


def session_reasons():
    return F.concat_ws('；',
        F.when(F.col('sessionId').isNull() | (F.col('sessionId') == ''), '会话ID缺失'),
        F.when(F.col('created').isNull() | F.col('ended').isNull() |
               (F.col('ended') < F.col('created')), '起止时间无效'),
        F.when(nonfinite('kwhTotal') | (F.col('kwhTotal') <= 0), '充电量须大于0'),
        F.when(nonfinite('chargeTimeHrs') | (F.col('chargeTimeHrs') <= 0) |
               (F.col('chargeTimeHrs') > 24), '充电时长须大于0且不超过24小时'),
        F.when(nonfinite('charging_fees') | (F.col('charging_fees') < 0), '费用无效'))


def enrich_sessions(df):
    return (df.withColumn('facility_type_name', facility_name('facilityType'))
            .withColumn('start_period', period_name('startTime'))
            .withColumn('end_period', period_name('endTime'))
            .withColumn('is_free', F.col('charging_fees') == 0)
            .withColumn('fee_type', F.when(F.col('is_free'), '免费').otherwise('付费')))


def clean_stations(raw, rule):
    df = raw
    for column in df.columns:
        df = df.withColumn(column, F.trim(F.col(column)))
    df = df.withColumn('device_count_raw', F.col('device_count'))
    df = df.withColumn('device_count', F.expr('try_cast(device_count as int)'))
    invalid = (F.col('device_count').isNull() | (F.col('device_count') <= 0) |
               F.col('stationId').isNull() | (F.col('stationId') == ''))
    rejected = df.filter(invalid).withColumn('reason', F.lit('站点ID缺失或设备数不是正整数'))
    rule('C12', '站点设备数/主键无效', rejected.count(), '隔离非运营或无效站点；关联会话不进入有效订单')
    df = df.filter(~invalid)
    blank_name = F.col('station_name').isNull() | (F.col('station_name') == '')
    blank_address = F.col('address').isNull() | (F.col('address') == '')
    rule('C13', '站名为空', df.filter(blank_name).count(), '补为未命名站点（站点ID），保留缺失标记')
    rule('C14', '地址为空', df.filter(blank_address).count(), '补为地址未知；不伪造地理位置')
    rule('C15', '站点设施编码映射', df.count(), '1交流、2直流、3交直流一体；其余保留未知类型及原编码')
    df = (df.withColumn('station_name_missing', blank_name).withColumn('address_missing', blank_address)
          .withColumn('station_name', F.when(blank_name, F.concat(F.lit('未命名站点（'), F.col('stationId'), F.lit('）'))).otherwise(F.col('station_name')))
          .withColumn('address', F.when(blank_address, '地址未知').otherwise(F.col('address')))
          .withColumn('facility_type_name', facility_name('facilityType')))
    return df, rejected


def clean_telemetry(raw, rule):
    columns = ['charge_current (A)', 'soc', 'max_temperature (℃)', 'min_temperature (℃)',
               'available_energy (kw)', 'available_capacity (Ah)', 'pack_voltage (V)']
    df = raw
    for column in columns:
        df = df.withColumn(column + '_raw', F.col(column))
        df = df.withColumn(column, F.expr(f'try_cast(`{column}` as double)'))
    checks = [
        ('C01', '充电电流为负或无效', nonfinite(columns[0]) | (F.col(columns[0]) < 0)),
        ('C02', 'SOC不在0至100内或无效', nonfinite('soc') | ~F.col('soc').between(0, 100)),
        ('C03', '温度不在-40至85℃内或无效',
         nonfinite(columns[2]) | nonfinite(columns[3]) |
         ~F.col(columns[2]).between(-40, 85) | ~F.col(columns[3]).between(-40, 85)),
        ('C04', '剩余能量/容量为负或无效',
         nonfinite(columns[4]) | nonfinite(columns[5]) | (F.col(columns[4]) < 0) | (F.col(columns[5]) < 0)),
        ('C05', '电池包电压非正或无效', nonfinite(columns[6]) | (F.col(columns[6]) <= 0)),
    ]
    counts = df.agg(*[F.sum(F.when(condition, 1).otherwise(0)).alias(code) for code, _, condition in checks]).first()
    for code, issue, _ in checks:
        rule(code, issue, counts[code] or 0, '按教师需求隔离，保留原始字段和逐条原因；不取绝对值或填造测量值')
    df = df.withColumn('reason', F.concat_ws('；', *[F.when(condition, issue) for _, issue, condition in checks]))
    return df.filter(F.col('reason') == '').drop('reason'), df.filter(F.col('reason') != '')
