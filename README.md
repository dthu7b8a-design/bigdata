# 充电运营数据分析平台 · 第二阶段

在 PyCharm 的 `bigdata` 项目开发：**Python 3.13 + PySpark 4.2 + Flask + MySQL + Vue3/JavaScript + DataV + ECharts**。Ubuntu Hadoop 3.x 提供 HDFS 存储。本阶段只使用老师的三份 CSV，保留第一阶段 Qt 的深色卡片、蓝色操作与绿色指标风格。

## 先打开哪里

详细从零操作见 **[完整操作手册](docs/00完整操作手册.md)**。本目录是可运行项目，不是已经向老师提交的材料包；提交目录的整理与材料生成需在用户审核项目后另行开始。

已初始化过的本机环境，在 PyCharm 下方 Terminal（PowerShell）执行：

```powershell
cd 'D:\workspace\第二阶段\bigdata'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

打开 `http://127.0.0.1:5000`。停止由该脚本启动的大屏后台：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

在 PyCharm 中运行 `main.py` 或 `01 Web Flask` 也可启动后台，但须先启动项目独立 MySQL。不要同时用两个入口占用5000端口。

## 数据流和代码位置

需要演示虚拟机HDFS时，先启动Ubuntu，再在项目Terminal执行`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_hdfs.ps1`。该脚本检查网络并启动已有HDFS，完整步骤见手册第9节。

```text
教师 CSV → jobs.pipeline（PySpark清洗、聚合）→ 本地Parquet / HDFS
                         ↓ jobs.forecast（ML训练与评估）
                     data/ads/dashboard.json
                         ↓ api.import_results（事务导入）
                    MySQL独立分析数据库
                         ↓ Flask /api/dashboard
                  Vue3 + DataV + ECharts
```

| 目录 | 内容 |
|---|---|
| `jobs/` | Spark运行环境、清洗、10维分析、两组交叉分析、预测 |
| `api/` | Flask、MySQL初始化与事务导入；`.env`仅留本机 |
| `frontend/` | Vue3 + JavaScript + Vite，DataV与ECharts |
| `deploy/` | Ubuntu/HDFS启动、同步、读回校验 |
| `scripts/` | 启停、重算、前端构建 |
| `tests/` | 原始CSV对账、接口及集成测试 |
| `data/ods/` | 按批次保留原始文件和SHA-256来源信息 |
| `data/dwd/` | 清洗Parquet、站点、隔离记录、电池原始补充表 |
| `data/ads/` | 各批次及最新分析JSON |
| `data/models/` | Spark ML模型 |
| `data/reports/` | 清洗质量报告 |
| `docs/` | 操作、技术说明、口径与评估 |

## 关键口径

- 3395条会话、105个站点、85个用户；总电量19723.69 kWh，原始费用合计401.52，币种未给出。
- `0014/0015`年份解释为2014/2015，经过全部星期、小时、时长交叉校验，并保留原始字段。
- 零电量和零费用记录保留；长连接不等同于持续通电。
- 电池记录的时间精度已丢失，未用作连续曲线或预测特征。负电流没有盲目删除。
- 预测是历史样本的次日电量预测，按时间切分评估。大屏刷新是重新读取已计算结果，不是实时设备采集。
- Hadoop为存储层，本机Spark为计算层。通过WebHDFS传输和校验不等于Spark在YARN集群计算。

当前依赖版本锁定在`requirements.txt`与`frontend/package-lock.json`。首次迁移到另一台机器需按手册配置路径、Java、数据库与HDFS，不应直接复制虚拟环境使用。

## 当前验收

2026-09-15：后端及数据26项测试、浏览器7项测试全部通过；真实Flask/MySQL页面、移动端与错误状态已检查；启停和再次启动成功；HDFS重启后结果读回SHA-256一致。第一阶段分离副本在Ubuntu编译通过，API37项、源码回归27项、补充检查13项通过。范围与证据见[需求与验收矩阵](docs/03需求与验收矩阵.md)。
