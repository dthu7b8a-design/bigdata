#!/bin/bash
set -euo pipefail
export JAVA_HOME=/opt/module/jdk1.8.0_261
export HADOOP_HOME=/opt/module/hadoop-3.2.1
for daemon in secondarynamenode datanode namenode; do
  "$HADOOP_HOME/bin/hdfs" --daemon stop "$daemon"
done
