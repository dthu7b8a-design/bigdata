# EV INSIGHT前端

Vue3 + JavaScript + Vite + ECharts + DataV。实际构建/浏览器验证见 [VALIDATION](../docs/VALIDATION.md)。

```bash
npm ci
npm run build
# 开发/预览依赖Flask5000
npm run dev
npm run preview
```

Node版本要求≥23，保留package-lock和现有依赖版本。构建输出dist由Flask静态提供；同源/api，无生产Node服务或SSR。Vite开发5173、预览4173，代理5000。

DataV包声明index.js而实际发布index.mjs，vite.config.js以精确alias解决，不修改node_modules。

## 页面与口径

- 总览：六项KPI、日趋势、小时/星期及站点排名。
- 分析：十维聚合、交叉分析和全部有效会话散点。
- 质量与预测：清洗/隔离规则、守恒检查、模型评估、历史单步预测和限制。

当前有效口径3339会话、84用户标识；原始3395。设施1/2/3已有中文映射，未知编码保留未知；费用币种未给出，连接时长不等于通电时长。刷新重读快照，不是实时设备采集。

## 浏览器测试

```bash
npm run test:e2e
```

默认读取../data/ads/dashboard.json，可用BIGDATA_RESULT指定完整ADS、BIGDATA_SOURCE指定规范CSV、CHROME_PATH指定本地Chromium、BIGDATA_SCREENSHOTS指定输出目录。未指定Chrome时使用Playwright管理的Chromium（需先安装浏览器）。

测试核对原始CSV SHA与ADS来源；正常UI拦截响应使用真实ADS，合成响应仅用于错误/空数据等异常场景。真实Flask可用时另外执行无拦截集成，不在线时明确skip。

默认新截图在test-results/screenshots，不覆盖历史screenshots。current-*为本轮真实Flask当前界面，其他旧图保留历史批次，不能当当前验证。依赖审计仍有开发/测试链路等告警，详见验证记录，不以构建成功替代安全结论。
