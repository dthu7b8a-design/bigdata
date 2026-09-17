import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def spark_session(name='evcharge-stage2'):
    if os.name == 'nt':
        # Spark's .cmd launcher round-trips its command through the console encoding.
        # Keep executable and classpath ASCII while the PyCharm project keeps its name.
        runtime = Path(os.getenv('BIGDATA_PYTHON_HOME', 'D:/workspace/runtime/bigdata-python'))
        os.environ.setdefault('JAVA_HOME', 'D:/workspace/jdk-17')
        os.environ.setdefault('HADOOP_HOME', 'D:/workspace/hadoop-3.3.0')
        os.environ['SPARK_HOME'] = str(runtime / 'Lib/site-packages/pyspark')
        os.environ['PYSPARK_PYTHON'] = str(runtime / 'Scripts/python.exe')
        os.environ['PATH'] = os.environ['JAVA_HOME'] + '/bin;' + os.environ['HADOOP_HOME'] + '/bin;' + os.environ['PATH']
    else:
        os.environ.setdefault('PYSPARK_PYTHON', sys.executable)
    os.environ.setdefault('SPARK_LOCAL_IP', '127.0.0.1')
    os.environ.setdefault('PYTHONUTF8', '1')
    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.master(os.getenv('SPARK_MASTER', 'local[2]'))
             .appName(name).config('spark.ui.enabled', 'false')
             .config('spark.sql.shuffle.partitions', '4')
             .config('spark.sql.session.timeZone', 'UTC')
             .config('spark.sql.warehouse.dir', 'file:///D:/workspace/runtime/spark-warehouse' if os.name=='nt' else str(ROOT/'data/warehouse'))
             .getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    return spark
