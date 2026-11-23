# 实际验证记录

日期：2026-11-23（Asia/Shanghai）。Windows、全新Python3.13.15 venv、JDK17.0.15、本地Spark4.2.0、MySQL8.0.30独立3307、Node24.20.0、Chrome157。Linux/HDFS完整链路未以本轮通过记录。

## 1. 环境与完整重算

依赖从PyPI安装到新venv，未复制原venv；原10项直接版本保持不变，新增requirements.lock.txt记录本轮完整传递版本。前端npm ci按原lock重新安装，未升级依赖。

```powershell
python -m pip install -r requirements.lock.txt
python -m jobs.pipeline --source datasets/teacher --output <独立输出目录>
```

真实重算批次`20261123T042155246992Z`：3339有效会话、19719.59kWh、398.02原始费用（币种未知）、84用户标识、105站点，选LR。与保存参考批次20260917比较kpis/charts/quality/model及来源哈希、日期、Spark版本，**差异0**；仅忽略run_id/updated_at，数值使用现有比较器rel=1e-9/abs=1e-8。

模型指标与参考一致：LR测试RMSE45.146873、MAE33.771205、R²0.741676；同星期基线RMSE47.650375但MAE更好，不能声称LR所有指标领先。未来预测仍是2015-10-05历史次日。

## 2. 后端、数据库与浏览器

```powershell
$env:BIGDATA_RESULT = '<本次独立输出>/ads/dashboard.json'
$env:BIGDATA_MYSQL_INTEGRATION = '1'
python -B -m pytest tests -q -p no:cacheprovider
```

**30 passed in 26.26s**：包括4项真实Spark边界、独立CSV/结果对账、API单元测试和3项真实MySQL集成，没有skip。真实数据库使用本轮新建3307实例，数据目录在外部验证目录；集成用随机测试库并只删除该库，不动原数据库或Windows服务。

导入新重算结果后，真实Flask四API/静态页200，health就绪，结果与重算快照在上述数值容差内一致。MySQL JSON可能改变浮点数末位，未将逐字节浮点比较误报为业务差异；字符串、键和列表仍比较。

前端npm ci成功（45包）、build成功（1257模块）。Playwright先7通过1明确跳过，启动真实Flask后**8/8通过，14.3s**，包括真实HTTP集成，无skip。正常UI测试使用真实ADS拦截响应；最后真实HTTP用例不拦截API，不能混称全部mock都是真实数据库请求。

README的current-*截图来自本轮真实Flask页面，显示3339/84/398.02和当前有效口径；旧截图原样保留并标明历史版本。移动端、图表、错误/空/加载/无效JSON状态通过。

## 3. 模型与证据完整性

20个模型实际.load成功：16归档、2最终参考、2本轮重算；均6特征，RF为32树。参考21文件SHA全部通过。历史3清单本地校验201/201、95/95、3/3通过；只是本地保留证据核对，未重新访问远端HDFS。

新检出发现历史文本会被Git行尾转换破坏原SHA，已恢复备份原字节，并对证据目录和规范CSV设精确-text规则；不修改manifest预期来掩盖差异。保留首次失败记录及修复后通过摘要。

## 4. 干净克隆

最终工程提交的独立检出、新venv/前端安装、再次重算、模型和测试在收尾执行，结果随后补写。本节不预先宣称通过。

## 5. 安全审计与未验收范围

npm audit报告7个受影响依赖节点（6 high、1 moderate），不等于7个独立漏洞。Node lock未改；本次没有以构建成功冒充依赖无风险。

| 范围 | 当前判断 |
|---|---|
| Vue/server-renderer SSR告警 | 本项目客户端createApp，无SSR入口，未见相应触发链 |
| Playwright安装器告警 | 涉及macOS安装脚本；本轮Windows使用已有Chrome，不执行该脚本 |
| source-map-js | 构建工具解析恶意indexed map的条件风险；无生产Node服务 |
| ECharts Lines系列 | 本项目未使用LinesChart；不能把普通line与lines混淆 |
| Vite开发/编辑器中间件 | 仍有条件风险；回环地址不能当完整隔离，生产采用Flask静态构建，不运行Vite |

后续安全补丁应单独变更并重做浏览器回归，ECharts修复涉及主版本兼容，未自动升级。真实告警依据为本次npm-audit.json和对应上游安全公告。

可选HDFS仅验证缺配置在VM操作前清晰失败，未启动原VM、未恢复网络、未写远端。无Linux端到端、YARN、实时设备采集、生产WSGI/TLS、容量压测或全面安全证明。

全部原始日志保留本地维护目录validation/bigdata；公开参考结果和模型可用于核验数值，清理/版本/回滚见 [整理报告](PROJECT_CLEANUP_REPORT.md)。
