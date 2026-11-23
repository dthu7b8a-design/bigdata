# 数据来源、口径与校验

## 输入文件

`teacher/` 保存课程提供的“04.数据集最终版”三份原始 CSV 的逐字节副本。不混入第一阶段 SQLite 演示订单，不改写输入来满足结果预期。

| 文件 | 内容 | 数据行数，不含表头 | 原始字节数 |
|---|---|---:|---:|
| `nvv2t.csv` | 会话电量、费用、时间、用户与站点标识 | 3,395 | 420,477 |
| `nvv2t_md_end.csv` | 站点、设施类型与设备数 | 105 | 13,018 |
| `dsv13r2.csv` | 电池相关采样字段 | 1,594 | 102,279 |

SHA-256 见 [teacher/SHA256SUMS](teacher/SHA256SUMS)。CSV 保留原始行尾，转换 CRLF/LF 会改变摘要。不要由编辑器或格式化工具自动保存原始输入。

Linux 在 `datasets/teacher/` 中执行 `sha256sum -c SHA256SUMS`。Windows 在项目根执行：

```powershell
Get-Content datasets/teacher/SHA256SUMS | ForEach-Object {
    $expected, $name = $_ -split '\s+', 2
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path datasets/teacher $name)).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "SHA256 mismatch: $name" }
    Write-Output "OK: $name"
}
```

## 清洗口径

以 [cleaning.py](../jobs/cleaning.py) 与 [pipeline.py](../jobs/pipeline.py)为准：

- 会话电量大于 0，连接时长大于 0 且不超过 24 小时。零费用属于免费订单，不等同无效订单。保存基线隔离 55 条零电量和 1 条超长会话，保留 3,339 条有效订单。
- `0014/0015` 年份解释为 `2014/2015`，通过星期、起止小时和时长交叉核对并保留原字段。该解释基于文件内部一致性，没有外部采集证据。
- 站点以唯一主键关联；主数据无效或未运营时隔离相关会话。空站名/地址使用显式标签并保留缺失标记，不补造地理位置。
- 设施编码 1/2/3 对应课程采用的交流/直流/交直流一体，其他值保留未知标签及原编码。
- 峰/平/谷只按会话开始、结束小时作教学分类，不拆分跨时段电量、时长或费用，不代表实际电价政策。
- 电池采样按电流、SOC、温度、能量/容量、电压校验。1,594 条因负电流隔离，不能为得到有效曲线而取绝对值。时间精度和单位有限，不恢复未知时间、不将 `kw` 字段擅自换算为电量。
- 原件存 ODS，拒绝记录存 DWD，规则计数及摘要存 ADS/报告；不从原文件删除拒绝数据。

保存基线有效订单电量 19,719.59 kWh、费用 398.02、用户 84、站点 105。费用币种未知。早期快照统计原始全部会话，不能与当前有效订单口径直接比较。

## 路径与生命周期

- 默认输入为 `datasets/teacher/`，环境变量 `BIGDATA_SOURCE` 可覆盖，CLI `--source` 优先。
- 默认生成 `data/`；用 `--output` 隔离复算，测试用 `BIGDATA_RESULT` 指定其 ADS 文件。
- 完整运行生成 ODS、DWD、ADS、质量报告、LR/RF 模型。模型 `metadata/`、`data/` 及 RF `treesMetadata/` 是整体，不能只留元数据。
- [最终参考产物](../results/reference/)保留原最终快照与模型；其摘要见 `SHA256.json`。它不替代重新运行。
- `data_hdfs_roundtrip/`、`deploy/verification*/` 是历史证据，部分旧副本行尾不同，按对应清单核对，不套用本目录摘要。归档处理以整理报告为准。

## 来源与使用边界

未取得可以证明外部采集来源、开放数据许可或独立再许可范围的材料，因此只称课程给定输入，不声称公开授权的现实运营数据集。文件含用户、会话与站点标识，不能据此断言已匿名化；公开及再分发范围应以课程/提供方授权为准。项目没有替数据或团队成果添加新许可。
