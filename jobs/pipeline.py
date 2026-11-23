"""Run with python -m jobs.pipeline. All business cleaning/aggregation uses Spark."""
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from pyspark.sql import functions as F
from jobs.runtime import ROOT, spark_session
from jobs.cleaning import PERIOD_HOURS, clean_stations, clean_telemetry, enrich_sessions, session_reasons

def json_default(value):
    if isinstance(value, Decimal): return float(value)
    if hasattr(value, 'isoformat'): return value.isoformat()
    raise TypeError(type(value).__name__)

def records(df):
    return [r.asDict(recursive=True) for r in df.collect()]

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default, allow_nan=False), encoding='utf-8')
    temp.replace(path)

def run(source, output, train=True):
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    ods = output/'ods'/run_id
    ods.mkdir(parents=True)
    hashes={}
    for filename in ['nvv2t.csv','nvv2t_md_end.csv','dsv13r2.csv']:
        src=source/filename
        shutil.copy2(src, ods/filename)
        hashes[filename]=hashlib.sha256(src.read_bytes()).hexdigest()
    spark=spark_session()
    try:
        load=lambda filename:spark.read.option('header',True).option('mode','FAILFAST').csv(str(ods/filename))
        raw=load('nvv2t.csv'); station_raw=load('nvv2t_md_end.csv'); telemetry_raw=load('dsv13r2.csv')
        before={'sessions':raw.count(),'stations':station_raw.count(),'telemetry':telemetry_raw.count()}
        rules=[]
        def rule(code,issue,count,action):
            rules.append(dict(id=code,issue=issue,count=int(count),action=action))
        dup=raw.count()-raw.dropDuplicates().count()
        rule('R01','完全重复会话',dup,'全字段相同才去重；不同内容的同ID记录隔离核查')
        df=raw.dropDuplicates()
        for c in df.columns: df=df.withColumn(c,F.trim(F.col(c)))
        df=(df.withColumn('created_raw',F.col('created')).withColumn('ended_raw',F.col('ended'))
            .withColumn('created',F.try_to_timestamp(F.regexp_replace('created',r'^00(\d{2})-',r'20$1-')))
            .withColumn('ended',F.try_to_timestamp(F.regexp_replace('ended',r'^00(\d{2})-',r'20$1-'))))
        rule('R02','年份0014/0015规范化',df.filter(F.col('created_raw').rlike('^00')).count(),
             '依据星期、小时和时长一致性解释为2014/2015；保留原值，不宣称外部来源已确认')
        for c in ['kwhTotal','chargeTimeHrs']: df=df.withColumn(c,F.expr(f'try_cast(`{c}` as double)'))
        df=df.withColumn('charging_fees',F.expr('try_cast(charging_fees as decimal(14,4))'))
        df=df.withColumn('platform',F.lower('platform'))
        rule('R05','零电量会话',df.filter('kwhTotal = 0').count(),'隔离到rejected，不纳入有效订单和平均值')
        rule('R06','零费用会话',df.filter('charging_fees = 0').count(),'有效订单标记免费；按开始/结束时段分别统计免费、付费次数及费用')
        rule('R07','连接时长超过24小时',df.filter('chargeTimeHrs > 24').count(),'按教师需求隔离到rejected，不纳入有效订单和时长均值')
        df=df.withColumn('reason',session_reasons())
        invalid=F.col('reason')!=''
        invalid_ids=df.groupBy('sessionId').count().filter('count > 1').select('sessionId')
        rejected=df.filter(invalid)
        conflict=df.join(invalid_ids,'sessionId','inner').filter(~invalid).withColumn('reason',F.lit('主键内容冲突'))
        rejected=rejected.unionByName(conflict).dropDuplicates()
        rule('R03','关键字段与主键冲突',rejected.count(),'隔离到rejected，不静默修补目标值')
        df=df.filter(~invalid).join(invalid_ids,'sessionId','left_anti').drop('reason')
        duration_check=F.abs((F.unix_timestamp('ended')-F.unix_timestamp('created'))/3600-F.col('chargeTimeHrs'))>1/60
        weekday=F.element_at(F.array(*[F.lit(v) for v in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']]),F.dayofweek('created'))
        consistency=duration_check | (weekday!=F.col('weekday')) | (F.hour('created')!=F.col('startTime').cast('int')) | (F.hour('ended')!=F.col('endTime').cast('int'))
        rule('R04','日期衍生字段不一致',df.filter(consistency).count(),'保留标记；日期年份解释必须通过交叉校验')
        if df.filter(consistency).count(): raise ValueError('日期解释未通过星期/时长/小时交叉校验')
        station_clean,station_rejected=clean_stations(station_raw,rule)
        stations=station_clean.select(F.col('stationId').alias('station_id'),F.col('locationId').alias('location_master'),
            F.col('facilityType').alias('facility_master'),F.col('station_name').alias('name'),F.col('address').alias('address'),
            'device_count','facility_type_name','station_name_missing','address_missing')
        if stations.count()!=stations.select('station_id').distinct().count(): raise ValueError('站点主键不唯一')
        unavailable=df.join(station_clean.select('stationId'),'stationId','left_anti').withColumn('reason',F.lit('站点缺失或未运营'))
        rejected=rejected.unionByName(unavailable)
        rule('C16','站点缺失或未运营的会话',unavailable.count(),'隔离会话，保留站点及会话拒绝记录')
        df=df.join(station_clean.select('stationId'),'stationId','left_semi')
        df=df.withColumnRenamed('stationId','station_id').join(stations,'station_id','left')
        bad_join=df.filter(F.col('name').isNull() | (F.col('locationId')!=F.col('location_master')) | (F.col('facilityType')!=F.col('facility_master'))).count()
        rule('R08','站点关联缺失或口径冲突',bad_join,'以唯一站点键关联，冲突则停止发布')
        if bad_join: raise ValueError('站点关联校验失败')
        df=enrich_sessions(df)
        rule('C09','开始/结束小时转时段',df.count(),'新增start_period/end_period；采用公开的教学时段划分，不用于真实计费')
        rule('C10','会话设施编码映射',df.count(),'1交流、2直流、3交直流一体；保留原编码和未知编码')
        df=(df.withColumn('date',F.to_date('created')).withColumn('hour',F.hour('created'))
            .withColumn('day_type',F.when(F.dayofweek('created').isin(1,7),'周末').otherwise('工作日'))
            .withColumn('zero_energy',F.col('kwhTotal')==0).withColumn('long_session',F.col('chargeTimeHrs')>24)
            .withColumn('duration_bucket',F.when(F.col('chargeTimeHrs')<1,'0–1小时').when(F.col('chargeTimeHrs')<2,'1–2小时')
              .when(F.col('chargeTimeHrs')<4,'2–4小时').when(F.col('chargeTimeHrs')<8,'4–8小时').otherwise('8小时以上')).cache())
        q1,q3=df.approxQuantile('chargeTimeHrs',[.25,.75],.001)
        iqr_count=df.filter((F.col('chargeTimeHrs')<q1-1.5*(q3-q1)) | (F.col('chargeTimeHrs')>q3+1.5*(q3-q1))).count()
        rule('R09','时长IQR候选异常',iqr_count,'统计异常不等于错误；保留并公开阈值，模型单独评估')
        time_distinct=telemetry_raw.select('record_time').distinct().count()
        rule('R10','电池采样时间精度丢失',before['telemetry'] if time_distinct==1 else 0,'保留原始科学计数法文本，不恢复伪造时间，不绘制连续充电曲线')
        rule('R11','没有电池记录的会话',df.join(telemetry_raw,df.sessionId==telemetry_raw.esd,'left_anti').count(),'不为会话补造电池记录；电池字段不进入预测')
        telemetry,telemetry_rejected=clean_telemetry(telemetry_raw,rule)
        rule('R12','电池字段单位/符号口径',before['telemetry'],'按教师需求负电流不进入有效充电采样；保留原件，kw字段不换算、不参与核心电量指标')
        dwd=output/'dwd'/run_id
        df.write.mode('errorifexists').parquet(str(dwd/'sessions'))
        stations.write.mode('errorifexists').parquet(str(dwd/'stations'))
        rejected.write.mode('errorifexists').parquet(str(dwd/'rejected'))
        station_rejected.write.mode('errorifexists').parquet(str(dwd/'stations_rejected'))
        telemetry.write.mode('errorifexists').parquet(str(dwd/'telemetry'))
        telemetry_rejected.write.mode('errorifexists').parquet(str(dwd/'telemetry_rejected'))
        # Raw telemetry is retained separately: structural linkage is not proof of measurement chronology.
        telemetry_raw.write.mode('errorifexists').parquet(str(dwd/'telemetry_unverified'))
        count=df.count()
        if count+rejected.count()+dup!=before['sessions']: raise AssertionError('会话行数不守恒')
        if telemetry.count()+telemetry_rejected.count()!=before['telemetry']: raise AssertionError('电池行数不守恒')
        if stations.count()+station_rejected.count()!=before['stations']: raise AssertionError('站点行数不守恒')
        def aggregate(keys):
            return df.groupBy(*keys).agg(F.count('*').alias('sessions'),F.round(F.sum('kwhTotal'),4).alias('energy_kwh'),F.round(F.avg('chargeTimeHrs'),4).alias('avg_duration_h'))
        daily=aggregate(['date']).orderBy('date')
        charts={
            'daily':records(daily),
            'hourly':records(aggregate(['hour']).orderBy('hour')),
            'weekday':records(aggregate(['weekday'])),
            'stations':records(aggregate(['station_id','name']).orderBy(F.desc('energy_kwh'))),
            'locations':records(aggregate(['locationId','address']).withColumnRenamed('locationId','location_id').withColumnRenamed('address','name').orderBy(F.desc('energy_kwh'))),
            'facility':records(aggregate(['facilityType','facility_type_name']).withColumnRenamed('facilityType','facility_code').withColumnRenamed('facility_type_name','facility_type').orderBy('facility_code')),
            'platform':records(aggregate(['platform']).orderBy('platform')),
            'vehicle':records(aggregate(['managerVehicle']).withColumnRenamed('managerVehicle','manager_vehicle')),
            'users':records(aggregate(['userId']).withColumnRenamed('userId','user_id').orderBy(F.desc('sessions'))),
            'duration':records(aggregate(['duration_bucket']).withColumnRenamed('duration_bucket','bucket').orderBy('bucket')),
            'station_hour':records(aggregate(['station_id','name','hour']).orderBy('station_id','hour')),
            'platform_daytype':records(df.groupBy('platform','day_type').agg(F.count('*').alias('sessions'),F.round(F.avg('kwhTotal'),4).alias('avg_energy_kwh'))),
            'energy_duration':records(df.select(F.col('sessionId').alias('session_id'),F.col('chargeTimeHrs').alias('duration_h'),F.col('kwhTotal').alias('energy_kwh')).orderBy('session_id')),
        }
        totals=df.agg(F.count('*').alias('sessions'),F.round(F.sum('kwhTotal'),4).alias('energy_kwh'),F.countDistinct('station_id').alias('stations'),
            F.countDistinct('userId').alias('users'),F.avg('chargeTimeHrs').alias('avg_duration_h'),F.sum('charging_fees').alias('fees'),
            F.min('date').alias('range_start'),F.max('date').alias('range_end')).first().asDict()
        for key in ['daily','hourly','weekday','stations','locations','facility','platform','vehicle','users','duration']:
            if sum(r['sessions'] for r in charts[key])!=count: raise AssertionError(f'{key}会话数不守恒')
            if abs(sum(r['energy_kwh'] for r in charts[key])-totals['energy_kwh'])>.1: raise AssertionError(f'{key}电量不守恒')
        fee_by_period={column:records(df.groupBy(column,'fee_type').agg(F.count('*').alias('sessions'),
            F.sum('charging_fees').alias('fees'),F.avg('charging_fees').alias('avg_fee')).orderBy(column,'fee_type'))
            for column in ['start_period','end_period']}
        quality={'before':before,'after':{'sessions':count,'stations':stations.count(),'telemetry':telemetry.count()},'rules':rules,
                 'summary':'按教师清洗需求筛选有效订单、站点和电池采样；原始数据及拒绝原因保留。免费订单单独标记，设施编码中文化，时段采用教学假设。',
                 'rejected':{'sessions':rejected.count(),'stations':station_rejected.count(),'telemetry':telemetry_rejected.count()},
                 'time_period_definition':{'basis':'教学假设；按数据集本地小时划分，非实际电价政策；仅按开始/结束小时分类，不拆分跨时段电量或费用','hours':PERIOD_HOURS},
                 'fee_by_period':fee_by_period,
                 'duration_iqr':{'q1':q1,'q3':q3,'lower':q1-1.5*(q3-q1),'upper':q3+1.5*(q3-q1)},
                 'reconciliation':{'dimensions_checked':10,'all_session_totals_match':True,'all_energy_totals_match':True},
                 'limitations':['没有外部来源证据，不能声称采集准确性已得到验证','历史教学数据不能反映当前站点运营状态','费用币种未知；设施编码4等未定义值保留未知标签','负电流按教师需求隔离；有效电池数据为空时不生成电池统计','时段划分是教学假设，免费不等于零电量，零费用不改变总费用求和']}
        model={}
        if train:
            from jobs.forecast import fit_forecast
            model=fit_forecast(spark,daily,output/'models'/run_id)
        payload={'meta':{'run_id':run_id,'source':'老师提供的04.数据集最终版（单一来源）','range_start':str(totals.pop('range_start')),
                        'range_end':str(totals.pop('range_end')),'updated_at':datetime.now(timezone.utc).isoformat(),'source_sha256':hashes,
                        'currency':'原始费用单位（未标明币种）','storage_mode':'local','spark_version':spark.version},
                 'kpis':totals,'charts':charts,'quality':quality,'model':model}
        write_json(output/'ads'/run_id/'dashboard.json',payload)
        write_json(output/'ads'/'dashboard.json',payload)
        write_json(output/'reports'/f'{run_id}-quality.json',quality)
        print(json.dumps({'status':'success','run_id':run_id,'sessions':count,'dimensions':10,'model':model.get('selected_model'),'output':str(output/'ads'/'dashboard.json')},ensure_ascii=False),flush=True)
        return payload
    finally:
        spark.stop()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path(os.getenv('BIGDATA_SOURCE', str(ROOT/'datasets/teacher'))))
    parser.add_argument('--output',type=Path,default=ROOT/'data')
    parser.add_argument('--skip-model',action='store_true')
    args=parser.parse_args()
    run(args.source,args.output,not args.skip_model)
