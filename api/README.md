# Flask / MySQL模块

本模块发布和读取版本化分析结果，不回退到本地JSON。完整安装、专用数据库配置和启动见 [复现指南](../docs/REPRODUCIBILITY.md)，实际验证见 [VALIDATION](../docs/VALIDATION.md)。

在项目根、已安装依赖并配置本地api/.env或环境变量后：

```bash
python -m api.import_results results/reference/dashboard.json
python -m api.run
```

Flask监听127.0.0.1:5000、debug关闭。Windows可选初始化工具仅管理独立3307，显式设置MYSQL_BASEDIR及BIGDATA_MYSQL_RUNTIME，不修改服务或3306；其他平台使用自行配置的专用MySQL8实例。真实密码不提交。

## 数据与事务

import_results校验五段JSON，DDL在事务之前；版本、全部图表和活动指针在同一事务提交，失败回滚并保留原活动版本。load_snapshot在REPEATABLE READ内读取版本和图表，避免跨版本拼接。

## 接口

| GET路径 | 成功结果 |
|---|---|
| /api/health | 数据库和活动版本就绪信息 |
| /api/dashboard | meta/kpis/charts/quality/model |
| /api/quality | quality本身 |
| /api/model | model本身 |

日期及其他查询参数明确拒绝；数据库不可用/无结果返回503，不伪造零或读JSON兜底。静态内容来自frontend/dist，未知API、隐藏或越界路径返回404。

## 测试

```bash
python -m pytest tests/test_api.py -q
```

设置BIGDATA_MYSQL_INTEGRATION=1才执行真实MySQL用例：读取本地管理员配置，在3307创建随机测试库，验证空状态、版本切换和失败回滚；结束仅删除该随机库。完整范围及限制见验证记录。
