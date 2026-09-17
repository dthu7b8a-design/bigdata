# EV INSIGHT 前端开发说明

Vue 3 + JavaScript + Vite + ECharts + 老师指定的 `@dataview/datav-vue3`。本目录是可运行前端与验收测试，不是第二阶段提交材料。

## 启动与构建

在本目录使用 PowerShell：

```powershell
$env:PATH = 'D:/node;' + $env:PATH
& 'D:/node/node.exe' 'D:/node/node_modules/npm/bin/npm-cli.js' ci --cache .npm-cache
& 'D:/node/node.exe' 'D:/node/node_modules/npm/bin/npm-cli.js' run dev
```

开发地址 `http://127.0.0.1:5173`，`/api` 代理到 `http://127.0.0.1:5000`。生产构建执行 `npm run build`，输出 `frontend/dist/index.html` 与 `frontend/dist/assets/`，由 Flask 分别提供 `/` 与 `/assets/<path>`。客户端使用同源 `/api/dashboard`、`/api/health`，无需生产代理或 CORS。三个页面通过组件状态切换，不需要 SPA 路由回退。

`npm run preview` 在 4173 预览生产构建，也代理 5000。依赖使用精确版本与 package-lock.json。指定 DataV 包在 npm 上为测试版本，其 package.json 声明 `es/index.js`，实际文件是 `es/index.mjs`；Vite 精确别名解决入口问题，不修改依赖文件、不换包。运行总览的数据观察卡使用真实 `BorderBox1`，测试检查其 SVG。

## 页面和契约

- 运行总览：六项 KPI、日趋势双轴、小时节律、周分布、站点排名、峰值观察。
- 多维分析：区域、设施编码、平台、车辆编码、用户、连接时长、站点平均连接时长，以及站点×小时热力图、平台×日类型分组比较、全量会话电量×连接时长散点。散点读取 `charts.energy_duration` 全部记录，不采样或补造数据；支持次数/电量切换。
- 质量与预测：清洗前后会话/站点/采样数、规则明细、IQR 与汇总一致性报告、模型测试指标与验证 RMSE、测试集实际/预测、历史次日预测及模型限制。

最终契约变化：

1. 不支持日期筛选，前端只显示 `meta.range_start/range_end`，刷新请求不含日期参数。
2. `meta.currency` 仅作为原始费用单位说明；费用不加人民币、美元或其他币种符号。
3. `quality.before/after` 为 sessions/stations/telemetry；`rules` 为 `{id,issue,count,action}[]`，规则数量不相加；其余字段原值展示。
4. `model.predictions` 是测试集预测，`forecast` 是历史数据结束后的次日单步预测；不称实时预测或一次预测整个测试区间。显示 `selected_model/split/features/limitations`。
5. `charts.energy_duration` 为 `{session_id,duration_h,energy_kwh}[]`。
6. 设施类型与 managerVehicle 保留后端编码；无编码字典时不推测含义。连接时长不当作持续通电时长。

数据只由 API 载入。请求超时 45 秒，HTTP 错误、无效 JSON、缺少主要契约字段、空数据和缺失维度均有明确状态；缺失指标显示 `—`，不转换为虚构的零。刷新时清除旧数据以免误读。CSV 与 ADS 文件均不由前端写入。

## 浏览器验收

已安装本机 Chrome 时：

```powershell
$env:PATH = 'D:/node;' + $env:PATH
$env:TEMP = 'D:/workspace/第二阶段/bigdata/frontend/.browser-temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
& 'D:/node/node.exe' node_modules/@playwright/test/cli.js test
```

可通过 `CHROME_PATH` 指定其他 Chromium 浏览器路径。测试从 `../data/ads/dashboard.json` 只读加载真实业务数据；合成响应只用于空数据、错误和契约异常测试，不进入产品代码。Flask 在线时额外测试真实 HTTP 接口；不在线则明确跳过该项。截图保存在 `screenshots/`，测试报告在 `playwright-report/`。

真实生产截图：`screenshots/live-flask.png`（总览）、`screenshots/live-analysis.png`（多维分析）、`screenshots/live-quality.png`（质量与预测），直接访问 Flask 5000 的静态页面与真实 API，不拦截请求。

其他截图 overview / analysis / quality / mobile 使用只读 ADS 文件的请求拦截测试，不能称为在线 API 截图；error / empty 是异常状态测试截图。主题沿用第一阶段 `#111315 / #1b1e21 / #2f6fed / #7ce38b`，保留 DataV 青色装饰。Node engines 明确要求 ≥23，实际使用 `D:/node/node.exe` v24。

官方参考：[指定 DataV 使用说明](https://datav-vue3.jiaminghi.com/guide/)、[Vite 开发代理](https://vite.dev/config/server-options)、[生产构建](https://vite.dev/config/build-options)。
