# Ubuntu / HDFS 部署与开发入口

计算分工：Windows PyCharm 使用本地 Spark 4.2 / Python 3.13；Ubuntu Hadoop 3.2.1 提供真实 HDFS 存储。WebHDFS 下载输入后由本地 Spark 处理，结果可再同步回 HDFS。没有声称 Spark 经 RPC 直接读写 HDFS，也未启动 YARN/Spark 集群。

## 已定位环境

- VMware：`D:/workspace/02_BitDev虚拟机运行包/VMware便携运行环境/vmrun.exe`
- VMX：`D:/workspace/01_用户原始资料/学生资料/01.开发环境/Ubuntu2204Bit/Ubuntu2204Bit/BitDev.vmx`
- Ubuntu 用户 `bit`；Java `/opt/module/jdk1.8.0_261`；Hadoop `/opt/module/hadoop-3.2.1`。
- 已有 NameNode：`/opt/module/hadoop-3.2.1/data/namenode`；DataNode：`/opt/module/hadoop-3.2.1/data/datanode`。
- 原 namespaceID `1349493153`；clusterID `CID-631698cc-6116-45b9-be4e-e0ec7de1cce6`，原元数据继续使用。
- 网卡 `ens33`，本次 DHCP 地址 `192.168.203.128`；NameNode UI/WebHDFS `http://192.168.203.128:9870`；DataNode HTTP `9864`。
- RPC 只监听 Ubuntu `127.0.0.1:9000`，DataNode 广告 localhost/bitdev；同步客户端只对本单节点受信任的 9864 重定向替换主机地址，不修改全局 Hadoop 配置。
- 已启动 NameNode、DataNode、SecondaryNameNode。初始报告 1 个在线 DataNode，0 missing/corrupt blocks，安全模式 OFF。SSH 22 已监听，传输不依赖 SSH。

## Windows 使用

在项目目录 PowerShell 中运行：

```powershell
$python = 'D:/workspace/runtime/bigdata-python/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
& $python deploy/hdfs_sync.py sync --source data --remote /evcharge-stage2 --overwrite --evidence deploy/verification-latest
& $python deploy/hdfs_sync.py get --remote /evcharge-stage2/ads/dashboard.json --output runtime/hdfs-dashboard.json
& $python deploy/hdfs_pipeline.py
```

`--endpoint http://新IP:9870` 是同步脚本的全局参数，应放在 `sync`/`get` 前面；亦支持 `EVCHARGE_WEBHDFS`。演示脚本也接受 `--endpoint`。

正式重算入口 `deploy/hdfs_pipeline.py` 默认列举 `/evcharge-stage2/ods`，按 UTC run_id 选择最新目录；要求目录内三个 CSV 齐全，并与正式 `data/ads/dashboard.json` 的源 SHA256 一致。无完整输入或哈希不同则失败，不偷偷回退旧输入。默认输出为项目 `data_hdfs_roundtrip`，新 run 的结果在该目录的 ods/dwd/models/ads/reports 中；下载来源和基准快照在 `_hdfs_inputs/<时间>`。核对结果为 `data_hdfs_roundtrip/comparison.json`，历史比较保存在 reports。退出码 0 表示计算且比较通过，比较失败返回 1。

可选参数：`--endpoint http://IP:9870`、`--user bit`、`--remote-root /evcharge-stage2/ods`、`--run-id 20260914T120724782833Z`、`--output data_hdfs_roundtrip`、`--baseline data/ads/dashboard.json`。默认路径锚定项目根目录；显式传入的本地相对路径相对于当前工作目录。重复运行保留独立的 run 目录并更新独立输出目录内的最新 dashboard/comparison，不覆盖正式 data。完整训练模型，无跳过模型的默认行为。

同步为保留远端历史的增量复制，不删除远端多余文件、不移动本地文件。默认拒绝覆盖内容不同的文件；`--overwrite` 仅允许在硬性限定的 `/evcharge-stage2` 下覆盖不同内容（包括最新 `ads/dashboard.json`）。同内容跳过上传但仍下载核对。每个源文件在传输前后做 SHA256，且与真实 HDFS 下载文件对比；验收目录保存下载副本和 `manifest.json`。未结束的 manifest 不含 `completed_at`，不能视为全量完成。

新旧入口均先从 HDFS 下载 3CSV，核对正式 run 的 source_sha256，再调用原 `jobs.pipeline.run(..., train=True)`。旧 `hdfs_pipeline_demo.py` 保留兼容，默认直接读取 ODS 根目录三份教师原件，产物写入 `deploy/hdfs-demo/<UTC时间>/output`。新入口行为如上。结果 `comparison.json` 比较 kpis/charts/quality/model 以及关键来源元数据。忽略 run_id/updated_at，数组按标识字段排序；数值容差 relative=1e-9、absolute=1e-8。独立 Spark 执行的 Parquet/模型二进制含生成标识，不要求跨运行二进制 SHA 一致；同步同一个文件则必须 SHA 完全一致。pipeline 的 storage_mode 保留 local，与计算方式一致；比较报告另行如实记录 HDFS 输入链路。

## 网络恢复与服务启停

VM 已运行时：

```powershell
& ./deploy/guest.ps1 -RestoreNetwork
& ./deploy/guest.ps1 -Script ./deploy/start-hdfs.sh -Output /tmp/evcharge-stage2-start.txt -Destination ./deploy/start-result.txt
```

正常停止仅 HDFS（不关 Ubuntu、不操作旧项目）：

```powershell
& ./deploy/guest.ps1 -Script ./deploy/stop-hdfs.sh
```

Ubuntu 本机亦可先 `export JAVA_HOME=/opt/module/jdk1.8.0_261`，再使用 `/opt/module/hadoop-3.2.1/bin/hdfs --daemon start|stop namenode|datanode|secondarynamenode`。启动脚本必须检测现有 VERSION 存在，绝不 format。日志在 `/opt/module/hadoop-3.2.1/logs`；`hdfs dfsadmin -report` 查看健康状态。

## 环境限制

当前为单节点、副本数 1；已有配置关闭 HDFS 权限校验且 WebHDFS 未认证，仅适合受控教学网络，勿转发到公网。旧版 Java/Hadoop 保持原样；不改其兼容配置。DHCP IP 可能变更；用 `vmrun getGuestIPAddress <VMX>` 查询并传 `--endpoint`。未解压教师巨型分卷镜像。未写第一阶段、frontend、jobs、api 或正式 data。


## 本次已完成验收

- 教师原始 3CSV：535,774 字节，3/3 SHA256 一致。证据 `verification-teacher/manifest.json`。
- 正式 data 全量：95 文件（包括隐藏 CRC 辅助文件），3,836,695 字节，95/95 下载 SHA256 一致；包含两个历史 run，当前 `ads/dashboard.json` 对应 `20260914T120724782833Z`。证据 `verification-data-20260914T120724782833Z/manifest.json`。
- 真正 HDFS 源重算：输入先从 `/evcharge-stage2/ods` 下载，Spark 新 run `20260914T120951041564Z`，与正式 run `20260914T120724782833Z` 的 kpis/charts/quality/model 比较通过，differences 为空。
- 重算及比较：`hdfs-demo/20260914T120950625256Z/output` 和 `hdfs-demo/20260914T120950625256Z/comparison.json`。重算完成后修正比较器的内存 date/Decimal 与 JSON 类型不对称，改为两边实际落盘 JSON 比较；未改业务结果。
- 只重新执行已完成产物的比较：`python deploy/hdfs_pipeline_demo.py --resume-comparison deploy/hdfs-demo/20260914T120950625256Z`。这仍重新从 HDFS 下载并验证输入，但不重新计算 Spark。
- Spark 提示本机 OpenBLAS DLL 不可用，但完整模型训练和结果验收成功；未将该警告当成 HDFS 故障。
- 最终 `fsck /evcharge-stage2`：HEALTHY，98 文件（95 产物 + 3 教师原件）、4,372,469 字节、80 个已验证数据块，缺失/损坏/副本不足均为 0。原 namespace/clusterID 保持不变，详见 `final-hdfs-status.txt`。
- 正式最新 dashboard 与 HDFS 下载副本的 SHA256 均为 `fcd403ee46e8fb4c8ef1cf32372fa40dbd93797445b51d053539148dd631188c`。
