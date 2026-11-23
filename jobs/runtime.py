import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def spark_session(name='evcharge-stage2'):
    if os.name == 'nt':
        # Spark's .cmd launcher round-trips its command through the console encoding.
        # Use an ASCII virtualenv path, or explicitly provide BIGDATA_PYTHON_HOME.
        runtime = Path(os.getenv('BIGDATA_PYTHON_HOME', sys.prefix))
        os.environ.setdefault('SPARK_HOME', str(runtime / 'Lib/site-packages/pyspark'))
        os.environ.setdefault('PYSPARK_PYTHON', str(runtime / 'Scripts/python.exe'))
        bins = [str(Path(os.environ[key]) / 'bin') for key in ('JAVA_HOME', 'HADOOP_HOME') if os.environ.get(key)]
        os.environ['PATH'] = os.pathsep.join([*bins, os.environ['PATH']])
    else:
        os.environ.setdefault('PYSPARK_PYTHON', sys.executable)
    os.environ.setdefault('SPARK_LOCAL_IP', '127.0.0.1')
    os.environ.setdefault('PYTHONUTF8', '1')
    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.master(os.getenv('SPARK_MASTER', 'local[2]'))
             .appName(name).config('spark.ui.enabled', 'false')
             .config('spark.sql.shuffle.partitions', '4')
             .config('spark.sql.session.timeZone', 'UTC')
             .config('spark.sql.warehouse.dir', os.getenv('BIGDATA_SPARK_WAREHOUSE', (ROOT/'data/warehouse').as_uri()))
             .getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    return spark
