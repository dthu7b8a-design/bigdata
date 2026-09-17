#!/bin/bash
set -euo pipefail
exec > /tmp/evcharge-stage2-final.txt 2>&1
export JAVA_HOME=/opt/module/jdk1.8.0_261
export PATH="$JAVA_HOME/bin:/opt/module/hadoop-3.2.1/bin:$PATH"
date -Is
ip -br addr
jps
cat /opt/module/hadoop-3.2.1/data/namenode/current/VERSION
hdfs dfsadmin -report
hdfs dfs -count /evcharge-stage2
hdfs fsck /evcharge-stage2
hdfs dfs -ls /evcharge-stage2/ods
