"""Chronological one-step evaluation. No future targets enter features."""
from datetime import timedelta
from pyspark.sql import functions as F, Window
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression, RandomForestRegressor
from pyspark.ml.evaluation import RegressionEvaluator

FEATURES=['lag1','lag7','mean7','weekday_n','month','trend']

def metrics(prediction):
    return {name:RegressionEvaluator(labelCol='label',predictionCol='prediction',metricName=name).evaluate(prediction)
            for name in ['mae','rmse','r2']}

def fit_forecast(spark,daily,model_dir):
    bounds=daily.agg(F.min('date'),F.max('date')).first()
    first,last=bounds[0],bounds[1]
    calendar=spark.range((last-first).days+1).select(F.date_add(F.lit(first),F.col('id').cast('int')).alias('date'))
    # Zero means no energy recorded in this supplied extract, not proof of zero real-world demand.
    series=calendar.join(daily.select('date',F.col('energy_kwh').alias('label')),'date','left').fillna({'label':0.0})
    window=Window.orderBy('date')
    prepared=(series.withColumn('lag1',F.lag('label',1).over(window)).withColumn('lag7',F.lag('label',7).over(window))
        .withColumn('mean7',F.avg('label').over(window.rowsBetween(-7,-1)))
        .withColumn('weekday_n',F.dayofweek('date').cast('double')).withColumn('month',F.month('date').cast('double'))
        .withColumn('trend',F.datediff('date',F.lit(first)).cast('double')).dropna())
    assembler=VectorAssembler(inputCols=FEATURES,outputCol='features')
    features=assembler.transform(prepared).withColumn('row_n',F.row_number().over(window)).cache()
    n=features.count(); train_end=int(n*.7); valid_end=int(n*.85)
    if n<60: raise ValueError('有效时间序列不足60天，无法进行可靠的时间切分评估')
    train=features.filter(F.col('row_n')<=train_end)
    valid=features.filter((F.col('row_n')>train_end)&(F.col('row_n')<=valid_end))
    test=features.filter(F.col('row_n')>valid_end)
    estimators={
        '线性回归':LinearRegression(featuresCol='features',labelCol='label',regParam=.1,elasticNetParam=0.0,maxIter=60),
        '随机森林':RandomForestRegressor(featuresCol='features',labelCol='label',numTrees=32,maxDepth=5,seed=20260914),
    }
    fitted={name:estimator.fit(train) for name,estimator in estimators.items()}
    validations={'同星期历史基线':metrics(valid.withColumn('prediction',F.col('lag7')))}
    validations.update({name:metrics(model.transform(valid).withColumn('prediction',F.greatest(F.lit(0.),F.col('prediction')))) for name,model in fitted.items()})
    # Select using validation RMSE only; test stays untouched by selection.
    selected=min(validations,key=lambda key:validations[key]['rmse'])
    test_results=[]
    for name in validations:
        prediction=test.withColumn('prediction',F.col('lag7')) if name=='同星期历史基线' else fitted[name].transform(test).withColumn('prediction',F.greatest(F.lit(0.),F.col('prediction')))
        test_results.append({'model':name,**metrics(prediction),'validation_rmse':validations[name]['rmse']})
    chosen=test.withColumn('prediction',F.col('lag7')) if selected=='同星期历史基线' else fitted[selected].transform(test).withColumn('prediction',F.greatest(F.lit(0.),F.col('prediction')))
    predictions=[{'date':str(r.date),'actual':r.label,'predicted':r.prediction} for r in chosen.orderBy('date').select('date','label','prediction').collect()]
    observed={r.date:float(r.label) for r in series.collect()}
    next_day=last+timedelta(days=1)
    future=[float(observed[last]),float(observed[next_day-timedelta(days=7)]),sum(observed[last-timedelta(days=i)] for i in range(7))/7,
            float((next_day.weekday()+1)%7+1),float(next_day.month),float((next_day-first).days)]
    forecast_frame=assembler.transform(spark.createDataFrame([tuple(future)],FEATURES))
    # Refit ML models on all available dates for a separately labelled next-day projection.
    model_dir.mkdir(parents=True,exist_ok=True)
    future_values={}
    for name,estimator in estimators.items():
        final_model=estimator.fit(features)
        folder='linear_regression' if name=='线性回归' else 'random_forest'
        final_model.write().save(str(model_dir/folder))
        future_values[name]=max(0.,final_model.transform(forecast_frame).first().prediction)
    future_values['同星期历史基线']=future[1]
    def period(frame):
        row=frame.agg(F.min('date'),F.max('date'),F.count('*')).first()
        return {'start':str(row[0]),'end':str(row[1]),'rows':row[2]}
    return {'target':'按会话开始日期汇总的数据集记录电量（kWh）','selected_model':selected,'selection_rule':'验证集RMSE最小；测试集不参与选择',
            'metrics':test_results,'validation_metrics':validations,'predictions':predictions,
            'forecast':[{'date':str(next_day),'predicted':future_values[selected]}],
            'ml_forecasts':[{'model':name,'date':str(next_day),'predicted':value} for name,value in future_values.items()],
            'split':{'train':period(train),'validation':period(valid),'test':period(test)},'features':FEATURES,
            'limitations':['历史教学数据的滚动单步预测，不代表当前运营需求','缺失日期置零仅表示提供的文件中无记录，不能证实实际无需求',
                           '测试使用此前已观测日的真实滞后量，属于每日更新的单步预测，不能解释为一次预测整个测试区间',
                           '模型可能不优于历史基线，报告保留全部真实评估结果','电池时间和费用等不确定字段没有进入模型']}
