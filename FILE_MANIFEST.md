# 仓库文件清单

仓库包含 22 个文件，涵盖实验入口、评估与校验模块、文档和单元测试。数据、模型权重、服务凭证、具体模型适配器和运行输出保留在本地。

| 文件 | 用途 |
| --- | --- |
| `.gitignore` | 本地数据、凭证、环境与输出忽略规则 |
| `FILE_MANIFEST.md` | 仓库文件清单 |
| `LICENSE` | MIT 许可证 |
| `README.md` | GitHub 首页与唯一声明版本 |
| `data/README.md` | 本地评估数据目录说明 |
| `docs/changes.md` | 发布变更与评估协议差异 |
| `docs/data_schema.md` | 数据路径、字段及独立划分要求 |
| `docs/knowledge_base.md` | 知识库存档版项目简介 |
| `docs/model_interface.md` | 缺失真实模型接口的补充契约 |
| `docs/publish_guide.md` | 移动桌面、GitHub 上传步骤与自检 |
| `docs/quick_start.md` | 快速上手 |
| `docs/reproduce.md` | 分组实验、指标定义与导出 |
| `docs/security_review.md` | 敏感信息检查与处置说明 |
| `evaluation.py` | 最终 JSON 完整词义 ID 精确判分 |
| `experiment_runner1_v2.py` | 清理后的实验入口与命令行 |
| `preflight.py` | 标准库输入校验与文件哈希 |
| `requirements.txt` | 直接依赖清单 |
| `resources/README.md` | 本地候选词义资源目录说明 |
| `support_data/README.md` | 本地独立示例库目录说明 |
| `tests/test_evaluation.py` | 判分技术单元测试 |
| `tests/test_grouping.py` | 按来源计算 Baseline 增益的技术测试 |
| `tests/test_preflight.py` | 输入结构与隔离技术测试 |

`model_interface.py`、数据 CSV 与候选词义 JSON 需在本地配置。测试中的临时结构和算术用例仅用于验证程序，不是科研样本、实验数据或模型性能结果。
