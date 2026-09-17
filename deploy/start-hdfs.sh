#!/bin/bash
set -euo pipefail
exec > /tmp/evcharge-stage2-start.txt 2>&1
export JAVA_HOME=/opt/module/jdk1.8.0_261
export HADOOP_HOME=/opt/module/hadoop-3.2.1
export PATH="$JAVA_HOME/bin:$HADOOP_HOME/bin:$PATH"
# Existing storage only. Never initialize a namespace.
test -s "$HADOOP_HOME/data/namenode/current/VERSION"
test -s "$HADOOP_HOME/data/datanode/current/VERSION"
cat "$HADOOP_HOME/data/namenode/current/VERSION"
for daemon in namenode datanode secondarynamenode; do
  if ! hdfs --daemon status "$daemon"; then hdfs --daemon start "$daemon"; fi
done
timeout 60 hdfs dfsadmin -safemode wait
hdfs dfsadmin -report
hdfs dfs -ls /
hdfs dfs -mkdir -p /evcharge-stage2/ods /evcharge-stage2/dwd /evcharge-stage2/ads /evcharge-stage2/models
hdfs dfs -ls /evcharge-stage2
ip -br addr
jps
ss -lnt
