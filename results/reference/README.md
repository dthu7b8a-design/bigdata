# 最终参考结果（2026-09-17）

本目录保留整理前真实最终批次 `20260917T072007238833Z`，不是本轮重训结果。

- `dashboard.json`：3339条有效会话、19719.59 kWh、398.02原始费用（币种未知）、84用户标识、105站点，含质量报告与评估。
- `models/`：全量重训后的线性回归和随机森林发布模型，metadata/data完整。
- `SHA256.json`：上述21文件的原始字节校验，不包含说明和清单自身。

快速展示从项目根执行 `python -m api.import_results results/reference/dashboard.json`；前提是依赖、专用MySQL和前端构建已准备，见 [复现说明](../../docs/REPRODUCIBILITY.md)。

评估使用时间切分；保存的发布模型用于全量历史后的次日预测，不用其拟合误差替代独立测试指标。Flask不在线加载模型，而读取MySQL预计算快照。历史次日为2015-10-05，不代表当前运营需求。数据来源与限制见 [datasets](../../datasets/README.md)。
