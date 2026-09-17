# Flask + MySQL API

在项目根目录使用 Python 3.13 运行；依赖由主项目安装。

```powershell
$python = 'D:/workspace/runtime/bigdata-python/Scripts/python.exe'
& $python -m api.bootstrap_mysql
& $python -m api.import_results data/ads/dashboard.json
& $python -m api.run
```

`api.run.main()` 也可由主项目入口调用。服务监听 `127.0.0.1:5000`，关闭 debug/reloader。

## 数据库

`api/.env` 为本地配置，已在 API 目录的 `.gitignore` 排除。环境变量优先于此文件，配置键见 `.env.example`。禁止发布 `.env` 或输出其中的密码。

`bootstrap_mysql` 仅管理独立 `127.0.0.1:3307` 实例，数据及无凭据日志在 `D:/workspace/runtime/bigdata-mysql`，不连接 3306、不更改 Windows 服务、不修改既有实例。它生成随机管理员和应用密码，只保存在本地 `.env`。应用账户仅有专用数据库的 SELECT/INSERT/UPDATE/CREATE/REFERENCES 权限。已有 3307 监听时拒绝再次创建；重启已初始化的独立实例可再次运行该命令。中断初始化后不会自动覆盖配置或清空数据，需查看本地日志排查。

导入必须事先提供可用的专用数据库；导入器创建三张 InnoDB 表：`dashboard_runs` 保存 UUID、导入时间、摘要和四个 JSON 对象；`dashboard_charts` 保存每版本的图表 JSON 数组；`dashboard_active` 指向当前版本。表初始化 DDL 在事务之前执行，版本插入、图表插入和活动版本切换在同一事务提交，失败回滚，保留之前的活动版本与历史版本。API 使用同一 REPEATABLE READ 事务读取当前版本及图表。

## 接口契约

| GET 路径 | 成功返回 |
| --- | --- |
| `/api/health` | `status`, `database`, `ready`, `run_id`；数据库可用且已有导入版本时 200，否则 503 |
| `/api/dashboard` | 原样五段对象 `{meta,kpis,charts,quality,model}` |
| `/api/quality` | `quality` 对象本身 |
| `/api/model` | `model` 对象本身 |

本次明确不支持日期筛选。数据接口收到 `start` 或 `end`（包括空值）返回 HTTP 400，`error.code=DATE_FILTER_UNSUPPORTED`；其他查询参数也返回 400。数据库失败或没有导入版本返回 503，绝不回退到 JSON 文件。API 的错误响应为 `{error:{code,message}}`，屏蔽底层连接错误及凭据。

JSON 要求顶层恰有上述五项，均为对象；charts 至少包含以下数组，内部字段原样保留：daily、hourly、weekday、stations、locations、facility、platform、vehicle、users、duration、station_hour、platform_daytype。拒绝 NaN/Infinity 和无效图表名称。

静态根目录默认为 `frontend/dist`；测试/集成可通过 `create_app({"FRONTEND_DIST": ...})` 覆盖。已有文件直接提供；无扩展名的前端路由回退 `index.html`。未知 API、缺失资产、隐藏文件与越界路径返回 404。

## 测试

```powershell
& $python -m unittest discover -s tests -p test_api.py -v
$env:BIGDATA_MYSQL_INTEGRATION = '1'
& $python -m unittest discover -s tests -p test_api.py -v
```

真实集成测试只连接独立 3307，使用本地管理员凭据创建随机名称的测试库；验证空状态、中文 JSON 往返、版本切换、历史保留和插入失败回滚。结束仅删除本次创建的随机测试库，不修改应用数据。单元测试覆盖接口、拒绝日期筛选、无 JSON 回退、输入校验和静态路由。
