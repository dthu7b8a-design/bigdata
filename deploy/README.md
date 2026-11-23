# 可选HDFS与历史验证材料

核心看板使用本地Spark + MySQL + Flask，不要求HDFS。这里提供WebHDFS同步/读回、可选已有VMware来宾操作，以及历史证据；没有YARN集群训练。完整步骤见 [复现说明](../docs/REPRODUCIBILITY.md)。

## 当前入口

- hdfs_sync.py：WebHDFS上传/下载与SHA256清单。
- hdfs_pipeline.py：选择时间戳ODS批次、读回、独立重算并比较基线。
- hdfs_pipeline_demo.py：早期ODS布局演示与共用compare函数，仍被新脚本导入，不能删除。
- guest.ps1：只对显式配置的既有虚拟机执行操作；不再从历史脚本提取密码。
- .env.example：配置键参考，不会自动加载。真实凭据只放本机环境，不能提交。

使用guest.ps1前需设置VMRUN_PATH、VMX_PATH、VM_GUEST_USER、VM_GUEST_PASSWORD；无配置/路径会在任何VM操作前失败。旧的网络恢复流程适用于原ens33教学虚拟机，不能保证所有VM可用；执行RestoreNetwork会修改已指定来宾网络，应先核对环境。

更通用的路径是直接提供EVCHARGE_WEBHDFS，按hdfs_sync.py --help和hdfs_pipeline.py --help运行。远端写入不是纯只读检查，不能对未知HDFS目录执行覆盖。

## 保留的历史证据

| 路径 | 含义 |
|---|---|
| verification/manifest.json | 201项本地下载证据，来自旧批次 |
| verification-data-20260914T120724782833Z/manifest.json | 95项历史包 |
| verification-teacher/manifest.json | 三原始CSV来源校验 |
| hdfs-demo/ | 早期端到端演示 |
| ../data_hdfs_roundtrip/ | 早期读回重算与对比 |

历史passed=true只证明对应批次。旧材料主要3395原始会话口径，不能证明当前3339有效会话或本轮HDFS在线验证。模型参数data与metadata、.crc/_SUCCESS有清单关系，已完整保护，不按缓存批量删除。当前可选HDFS未端到端重跑，具体见 [VALIDATION](../docs/VALIDATION.md)。
