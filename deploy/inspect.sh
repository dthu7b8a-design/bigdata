#!/bin/bash
exec > /tmp/evcharge-stage2-inspect.txt 2>&1
date -Is
id
ip -br addr
ip route
ls -ld /opt/module/*
pgrep -af 'NameNode|DataNode|ResourceManager|NodeManager|SecondaryNameNode'
for f in /opt/module/hadoop-3.2.1/etc/hadoop/{core-site,hdfs-site,hadoop-env}.xml; do
  test ! -f "$f" || cat "$f"
done
grep -E 'JAVA_HOME|HADOOP' /opt/module/hadoop-3.2.1/etc/hadoop/hadoop-env.sh
find /opt/module -maxdepth 6 -name VERSION -print
ss -lnt
nmcli device status
sudo -n true && echo SUDO_NOPASS_AVAILABLE
exit 0
