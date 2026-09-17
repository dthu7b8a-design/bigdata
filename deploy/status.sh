#!/bin/bash
exec > /tmp/evcharge-stage2-status.txt 2>&1
ip -br addr
ps -eo pid,etime,args | grep -E 'java|evcharge-stage2' | head -25
ss -lnt
tail -n 15 /opt/module/hadoop-3.2.1/logs/*namenode*.log
exit 0
