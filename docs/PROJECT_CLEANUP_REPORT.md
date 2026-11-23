# 工程整理报告

日期：2026-11-23。仅本地独立分支，不推送、不创建PR、不合并。

## 1. 基线、远程和备份

原目录`D:\workspace\第二阶段\bigdata`，本地main=`eea3695c3620d75a1d6a28581d59d6c3fbce81ce`；GitHub <https://github.com/dthu7b8a-design/bigdata> 的main=`ea359c85dd58c9796f6e77d0955fd92852e3d65f`，领先2提交，删除旧docs和聚合文件。

独立`cleanup/bigdata-audit-20261123`以远程新main为基线，原目录和本地旧main不动。新docs按当前事实重写，未恢复旧文档错误口径；远程已删除的项目代码2.md未带回。

完整备份13,507文件、1,092,483,759字节，包含.git、.env、venv、data、模型、runtime及IDE成果，逐文件哈希通过，另有Git bundle。备份含本机秘密，仅本地保管，不随Git提交。

## 2. 目录与处理清单

保留jobs/api/frontend/deploy/scripts/tests分层，新加datasets/teacher、results/reference、docs；默认data仍为运行输出，不强改src或引入Docker。

| 处理 | 范围 | 依据 |
|---|---|---|
| 修复忽略 | data/改为/data/ | 防止误排除嵌套模型参数 |
| 补全 | 64个归档模型data配套文件 | 原本被忽略，恢复manifest和模型加载能力 |
| 新增规范来源 | 三CSV、SHA256SUMS、数据说明 | 与最终ADS原始哈希一致，不再依赖父目录 |
| 保留最终结果 | results/reference快照、LR/RF模型及SHA | 最新最终产物随clone可用，不靠隐藏data |
| 保护原字节 | .gitattributes精确覆盖原始CSV/历史证据 | 避免Git换行导致SHA失败，不篡改清单 |
| 新增 | 传递依赖lock、当前真实截图、技术档案/复现/成果索引 | 可复现和展示 |
| 整合文档 | 根/API/前端/HDFS README | 删除私有绝对路径说明与旧口径，统一到完整指南 |
| 保留待确认 | 历史CSV/Parquet/JSON/模型、CRC/_SUCCESS、IDE配置、Office/PPT/视频 | 有引用或独特证据，不按体积/文件名删除 |

没有删除原工作区任何数据、报告、模型或未跟踪个人成果。重复blob不当作等额Git历史节省；优先完整性而非宣称仓库显著瘦身。

## 3. 代码和配置

- pipeline只改变默认输入路径/环境覆盖，cleaning和forecast算法不变。
- runtime尊重实际Python/Java/Hadoop与显式warehouse，移除原机器固定目录。
- bootstrap_mysql只参数化安装/运行路径，3307与拒绝覆盖逻辑不变；DB schema/API契约不变。
- Node构建/Playwright不硬编码D盘安装，HDFS用显式本地配置，不再读历史脚本中的密码。
- 浏览器验证使用真实来源哈希和现有契约，结合Python独立CSV对账，不用替换常量来掩盖清洗错误；两处页面文案对齐设施映射和有效会话。
- package-lock和原10项直接依赖未升级，新增本轮实测的完整传递锁。

## 4. 验证与质量

新venv完整重算、与最终参考0差异、30项pytest（含真实Spark/MySQL）、8项浏览器含真实Flask、20模型加载、全部清单及当前截图，详见 [VALIDATION](VALIDATION.md)。干净检出结果在收尾补入。

完整性：必要来源/快照/模型进入正式Git；代码与结构：低风险参数化；文档：真实口径与个人职责；可靠性：当前Windows链路实测；限制：HDFS与Linux未端到端，依赖仍有安全告警，课程附件授权未明确。个人贡献依据团队职责，不把已有模型应用或HDFS存储包装为科研创新。

## 5. Git交付、回滚与发布边界

最终工程SHA与报告SHA在本地交付清单记录；`git rev-parse HEAD`可核对整理副本。原main/原目录保留，回退优先使用原目录或备份/新检出，不对有用户后续成果的目录执行reset/clean。

正式成果大型Office/PPT/视频及其他成员材料未擅自复制公开。源码CSV内容已有历史版本，但对外授权仍应在推送审阅时明确，不自动附加LICENSE。

拟推送上述GitHub的同名整理分支；最终diff和测试展示后等待用户明确确认才push/PR，合并另需明确同意。不force、不重写历史。
