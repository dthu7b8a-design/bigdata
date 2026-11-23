# 完整复现指南

目标是从 Git 中的三份 CSV 重算、构建前端、发布 MySQL 版本并验证 API。快速路径使用已有真实结果；完整路径执行清洗、聚合与训练。HDFS 是额外的存储与回读验证，不是大屏必需服务。实际执行结果见 [VALIDATION.md](VALIDATION.md)，本指南不构成“已经全部通过”的声明。

## 1. 环境

| 项目 | 要求与用途 |
|---|---|
| Python | 原基线 3.13，安装 requirements.txt 的精确版本 |
| Java | JDK 17，供本地 Spark 使用，JAVA_HOME 指安装根目录 |
| Node.js | package.json 要求 ≥23，使用 npm 与 package-lock |
| MySQL | 专用 8.0 实例，原环境 8.0.30，端口 3307 |
| 浏览器 | Playwright Chromium，或 CHROME_PATH 指定本机浏览器 |
| Hadoop | 可选 HDFS 需既有 HDFS/WebHDFS；Windows native 工具按本机需要配置 HADOOP_HOME |

默认 Spark 为 `local[2]`，无需 GPU。没有正式容量压测，不给出未经验证的最低内存或生产吞吐。Linux 不运行 Windows MySQL/VMware 启动工具，使用已配置的专用 MySQL 和直接 WebHDFS；未实测部分以验证记录为准。

先检查 `java -version`、`node --version`、`npm --version`。Windows Python、JDK 和 Spark 路径建议使用 ASCII，避免 Spark 的 .cmd 启动器/控制台编码问题。项目可在中文目录，但首次复现宜使用简单路径。

## 2. 安装

Windows PowerShell：

~~~powershell
git clone -c core.longpaths=true --branch cleanup/bigdata-audit-20261123 https://github.com/dthu7b8a-design/bigdata.git C:\ev-insight
Set-Location C:\ev-insight
py -3.13 -m venv .venv
$python = (Resolve-Path .venv\Scripts\python.exe).Path
& $python -m pip install -r requirements.lock.txt
~~~

无需激活 venv；新开终端后重新赋值 `$python`。完整 Spark 路径另需：

~~~powershell
$env:JAVA_HOME = 'C:\Java\jdk-17' # 替换为本机实际目录
$env:BIGDATA_PYTHON_HOME = (Resolve-Path .venv).Path
~~~

Linux shell：

~~~bash
git clone -c core.longpaths=true --branch cleanup/bigdata-audit-20261123 https://github.com/dthu7b8a-design/bigdata.git
cd bigdata
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock.txt
java -version
~~~

Linux 使用 PATH/JAVA_HOME 中的 JDK 和当前 Python。下文 `& $python` 换成 `python`，环境变量使用 `export NAME=value`。

## 3. 原始输入与保存结果

[输入说明](../datasets/README.md)给出三 CSV 的行数、语义和 SHA-256 校验方法。`datasets/teacher/` 不依赖原开发目录相邻文件夹，不转换原始行尾。

[results/reference/dashboard.json](../results/reference/dashboard.json) 是原最终批次 `20260917T072007238833Z`，包含 KPI、图表、质量和模型评估。`results/reference/models/` 保存其完整 LR/RF 模型，[SHA256.json](../results/reference/SHA256.json)给出文件摘要。它用于快速展示与回归参照，不替代重新计算。

参考产物校验可在项目根运行：

~~~powershell
@'
import hashlib, json
from pathlib import Path
root = Path("results/reference")
manifest = json.loads((root / "SHA256.json").read_text(encoding="utf-8"))
for entry in manifest["files"]:
    path = root / entry["path"]
    assert path.stat().st_size == entry["bytes"], str(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], str(path)
print("Reference artifact hashes OK")
'@ | & $python -
~~~

Linux 可将同一 Python 代码放入 `python - <<'PY'` 的 heredoc 执行。

## 4. 选择运行路径

### 快速路径：不重新训练

完成第 5、6 节的 MySQL 和前端构建后：

~~~powershell
& $python -m api.import_results results/reference/dashboard.json
& $python -m api.run
~~~

此时展示保存基线，不能据此宣称重新执行过 Spark、训练或 HDFS。仅 API 单元测试可独立运行；要求完整 ADS 的测试可显式指定参考文件：

~~~powershell
$env:BIGDATA_RESULT = (Resolve-Path results/reference/dashboard.json).Path
& $python -m pytest tests/test_api.py tests/test_pipeline_results.py -q
~~~

### 完整路径：三 CSV 重算

~~~powershell
& $python -m jobs.pipeline --source datasets/teacher --output data
$env:BIGDATA_RESULT = (Resolve-Path data/ads/dashboard.json).Path
& $python -m pytest -q
& $python -m api.import_results data/ads/dashboard.json
~~~

批次号、时间戳每次变化；不要求与保存基线逐字节相同。目录如下：

~~~text
data/
├── ods/<run_id>/                  # 三份原始 CSV 原件
├── dwd/<run_id>/                  # 7类 Parquet，有效/拒绝记录分开
├── ads/<run_id>/dashboard.json    # 本次结果
├── ads/dashboard.json            # 最新成功快照
├── models/<run_id>/               # 全量重训 LR / RF
└── reports/<run_id>-quality.json  # 规则计数与限制
~~~

已有批次不覆盖。JSON 先写临时文件再替换；失败批次可能留下诊断目录，不能凭目录存在认定成功。

只检查清洗可使用 `--skip-model --output runtime/smoke-data`。其 `model` 为空，不能用于要求预测结果的完整验收。

隔离回归：

~~~powershell
& $python -m jobs.pipeline --source datasets/teacher --output runtime/reproduce
$env:BIGDATA_SOURCE = (Resolve-Path datasets/teacher).Path
$env:BIGDATA_RESULT = (Resolve-Path runtime/reproduce/ads/dashboard.json).Path
& $python -m pytest tests/test_pipeline_results.py tests/test_cleaning.py -q
~~~

`BIGDATA_RESULT` 仅改变测试读取文件，不改变 API 的 MySQL 来源。完整模型应同时保留 metadata、data，以及 RF 的 treesMetadata；不能将参数目录当普通缓存。独立加载时须按 `jobs/forecast.py` 中相同顺序构造六个特征，模型文件不包含整个数据清洗流水线。

可在配置好 Java 的 PowerShell 中独立验证参考模型能否加载；这只验证模型文件与特征维数，不代替重新训练和预测误差验证：

~~~powershell
@'
from pathlib import Path
from pyspark.ml.regression import LinearRegressionModel, RandomForestRegressionModel
from jobs.runtime import spark_session
spark = spark_session("reference-model-load")
try:
    root = Path("results/reference/models").resolve()
    linear = LinearRegressionModel.load(str(root / "linear_regression"))
    forest = RandomForestRegressionModel.load(str(root / "random_forest"))
    assert linear.numFeatures == forest.numFeatures == 6
    print("Reference LR/RF loaded; feature count = 6")
finally:
    spark.stop()
'@ | & $python -
~~~

| 配置 | 含义 |
|---|---|
| BIGDATA_SOURCE / --source | 输入目录；CLI 优先，默认 datasets/teacher |
| --output | 输出根目录，默认 data |
| BIGDATA_RESULT | 测试读取的 ADS JSON 路径 |
| JAVA_HOME / HADOOP_HOME | 本机 Java / 可选 Hadoop 根目录 |
| BIGDATA_PYTHON_HOME | Windows ASCII 虚拟环境根目录，默认当前环境 |
| SPARK_HOME / PYSPARK_PYTHON | 显式分发与 Python worker，运行时保留 |
| BIGDATA_SPARK_WAREHOUSE | warehouse URI，默认项目 data/warehouse 的文件 URI |
| SPARK_MASTER | 默认 local[2]，修改它不等于部署集群 |

预期数据守恒：3,395 = 3,339 有效 + 56 隔离；有效电量 19,719.59 kWh、费用 398.02、84 用户、105 站点。各维度核对相同总体。模型采用 219/47/48 天划分，保存基线 LR RMSE 45.1469、基线 47.6504、RF 88.4494 kWh。RF seed 为 20260914；不同 Spark/JVM 平台的浮点差异需解释，不改预期掩盖回归。

## 5. MySQL 配置

### A. Windows 首次新建专用实例

准备 MySQL 8.0 ZIP 分发，确认 3307 空闲且 `api/.env` 尚不存在：

~~~powershell
$env:MYSQL_BASEDIR = 'C:\MySQL\mysql-8.0.30-winx64'
# 可选，默认项目 runtime/mysql：
# $env:BIGDATA_MYSQL_RUNTIME = 'C:\ev-insight-runtime\mysql'
& $python -m api.bootstrap_mysql
~~~

工具建立独立 datadir，只监听 127.0.0.1:3307，生成随机管理员及应用口令写入忽略的 `api/.env`，不修改 3306。检测到已有配置或半初始化状态会拒绝覆盖。失败后先核查提示和本地日志，不删除数据库“重试”。

重启继续使用原 .env 和 runtime；若实例已运行，初始化工具提示端口占用，先确认健康和导入，不重复建立实例。

### B. 已有专用实例 / Linux

管理员只连接自己的专用 3307：

~~~bash
mysql --host=127.0.0.1 --port=3307 --user=root --password
~~~

首次创建应用库及账号：

~~~sql
CREATE DATABASE bigdata_dashboard CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'bigdata_api'@'localhost' IDENTIFIED BY 'REPLACE_WITH_LOCAL_RANDOM_PASSWORD';
CREATE USER 'bigdata_api'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_LOCAL_RANDOM_PASSWORD';
GRANT SELECT, INSERT, UPDATE, CREATE, REFERENCES ON bigdata_dashboard.* TO 'bigdata_api'@'localhost';
GRANT SELECT, INSERT, UPDATE, CREATE, REFERENCES ON bigdata_dashboard.* TO 'bigdata_api'@'127.0.0.1';
~~~

替换示例密码；同名对象已存在时核实归属，不覆盖未知库。复制 `api/.env.example` 为 `api/.env`，填写 MYSQL_HOST、MYSQL_PORT、MYSQL_USER、MYSQL_PASSWORD、MYSQL_DATABASE。进程环境优先于 .env，排错需检查遗留配置。真实凭据不入 Git。

### 事务发布与启动

~~~powershell
& $python -m api.import_results data/ads/dashboard.json
& $python -m api.run
~~~

快速路径将参数换成 `results/reference/dashboard.json`。导入先校验 JSON，再初始化 schema；版本、图表和活动指针同事务提交，失败回滚。DDL 初始化独立执行，不声称 DDL 也能随业务事务回滚。

Flask 默认 127.0.0.1:5000、debug 关闭，定位为本地课程演示，没有生产 WSGI/TLS/账号系统。

## 6. 前端与接口

~~~powershell
Push-Location frontend
npm ci
npm run build
Pop-Location
Invoke-RestMethod http://127.0.0.1:5000/api/health
Invoke-RestMethod http://127.0.0.1:5000/api/dashboard
Invoke-RestMethod http://127.0.0.1:5000/api/quality
Invoke-RestMethod http://127.0.0.1:5000/api/model
~~~

Linux 使用 `cd frontend && npm ci && npm run build` 及 curl。Flask 提供 frontend/dist，浏览器访问 http://127.0.0.1:5000/。Vite 开发/预览服务不替代 MySQL→Flask 链路。

health 的 ready=true 说明连接库且有活动版本；还需访问 dashboard 确认完整快照。结果接口拒绝日期和未知参数；数据库不可用、无结果或快照无效返回 503，静态越界路径返回 404。页面不以旧文件或随机值掩盖错误。

## 测试层次

~~~powershell
& $python -m pytest -q
~~~

- API 单元测试用 mock 和临时静态目录，无需数据库。
- test_cleaning 启动真实本地 Spark，验证清洗边界。
- test_pipeline_results 从 CSV 独立计算期望并核对完整 ADS。
- 真实 MySQL 默认跳过，显式选择时只在专用3307创建并删除本次随机测试库。

数据库测试需本地 api/.env 提供 MYSQL_ADMIN_PASSWORD，由 bootstrap 生成；已有实例须由管理员自行配置，不回显口令：

~~~powershell
$env:BIGDATA_MYSQL_INTEGRATION = '1'
& $python -m pytest tests/test_api.py -q
Remove-Item Env:\BIGDATA_MYSQL_INTEGRATION
~~~

浏览器测试在完整 ADS、前端构建与 Flask 就绪后运行：

~~~powershell
Push-Location frontend
npx playwright install chromium
npm run test:e2e
Pop-Location
~~~

可设 CHROME_PATH 使用本机浏览器，BIGDATA_SCREENSHOTS 指定截图输出；默认 frontend/test-results/screenshots。多数用例拦截 HTTP 验证真实 ADS 的 UI 状态；真实 Flask 用例另行访问5000，未就绪时明确跳过。需记录通过/失败/跳过，不能把 mock 结果当全链成功。

## 7. 可选 HDFS 回读复算

准备可访问的单节点 HDFS，NameNode WebHDFS 与 DataNode 重定向地址都需可达。启动脚本操作既有安装，不格式化 NameNode。直接 WebHDFS 无需 VMware。

~~~powershell
$env:EVCHARGE_WEBHDFS = 'http://YOUR_NAMENODE:9870'
& $python deploy/hdfs_sync.py --endpoint $env:EVCHARGE_WEBHDFS --user bit sync --source data --remote /ev-insight/reproduce-20261123 --evidence runtime/hdfs-evidence
& $python deploy/hdfs_pipeline.py --endpoint $env:EVCHARGE_WEBHDFS --user bit --remote-root /ev-insight/reproduce-20261123/ods --output runtime/hdfs-roundtrip --baseline data/ads/dashboard.json
~~~

替换 endpoint、HDFS 用户与独立远程目录。同步默认拒绝替换不同内容，不加 --overwrite 迁就未知目录。清单和回读文件存 evidence；复算下载所选 HDFS ODS 批次三 CSV、核对摘要、在本地运行 Spark，检查 comparison.json 的 passed=true 及 differences。

VMware 辅助 guest.ps1 要求 VMRUN_PATH、VMX_PATH、VM_GUEST_USER、VM_GUEST_PASSWORD，参考 deploy/.env.example；模板不会自动加载，不再从历史脚本提取密码。VM 和网络操作只用于自己的虚拟机，并非主链必要步骤。本轮未实际运行的 HDFS 项须如实记录。

## 8. 排错与留档

| 现象 | 核查 |
|---|---|
| Spark 启动失败 | JAVA_HOME、当前解释器、ASCII 路径及依赖安装，不改算法/数据 |
| 找不到 CSV | 当前目录、BIGDATA_SOURCE 与三个文件名 |
| 结果/模型测试失败 | 是否完整训练、BIGDATA_RESULT 是否为同源新结果，保留失败证据 |
| 503 | 专用 MySQL、权限、显式导入，不改为文件回退 |
| 指标仍旧 | 导入文件、活动 UUID、meta.run_id；刷新不重算 |
| 缺静态页/浏览器 | npm ci/build、playwright install chromium |
| HDFS 主页正常但下载失败 | DataNode 重定向地址及网络，NameNode 首页不等于回读成功 |

保留命令、环境版本、源摘要、批次、测试摘要、API 和截图；不记录口令/.env内容。最终见 [VALIDATION.md](VALIDATION.md) 与 [整理报告](PROJECT_CLEANUP_REPORT.md)。

## 依赖锁定范围

requirements.txt保留原10项直接版本；requirements.lock.txt记录本轮干净Python3.13环境中实测的完整传递依赖版本，首次复现优先按lock安装。本轮未升级既有直接依赖或Node lock。Linux仅给出操作路径，未以Windows锁文件安装成功代替Linux端到端证明。

## Windows长路径

历史证据路径较深，Windows首次clone请保留上文`-c core.longpaths=true`。若已检出到较深目录，先`git config core.longpaths true`，检查`git status`；首次checkout即使返回0也可能报Filename too long并缺少文件。不要对有个人改动的目录直接checkout/reset；应在短路径重新克隆后验证全部manifest。该配置仅作用当前仓库，不修改全局Git或系统策略。
