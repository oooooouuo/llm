# 整理完成后的文件清单

共 22 个交付文件。未纳入原始附件、论文历史稿、数据、模型权重、凭证、真实接口实现或实验输出。

| 文件 | 用途 |
| --- | --- |
| `.gitignore` | 本地数据、凭证、环境与输出忽略规则 |
| `FILE_MANIFEST.md` | 本文件，整理完成后的文件清单 |
| `LICENSE` | MIT 许可证，发布前核实版权归属 |
| `README.md` | GitHub 首页与唯一声明版本 |
| `data/README.md` | 本地评估数据目录说明 |
| `docs/changes.md` | 整理变更与评估协议差异 |
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
| `requirements.txt` | 提取的依赖，历史版本未知且不伪造锁定 |
| `resources/README.md` | 本地候选词义资源目录说明 |
| `support_data/README.md` | 本地独立示例库目录说明 |
| `tests/test_evaluation.py` | 判分技术单元测试 |
| `tests/test_grouping.py` | 按来源计算 Baseline 增益的技术测试 |
| `tests/test_preflight.py` | 输入结构与隔离技术测试 |

`model_interface.py`、实际 CSV、候选词义 JSON 均不是已交付文件；由使用者按文档补齐。测试中的临时结构和算术用例仅用于验证程序，不是科研样本、实验数据或模型性能结果。
