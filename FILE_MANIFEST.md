# 仓库文件清单

共 34 个源码、配置模板、文档和测试文件。数据、缓存、权重、服务凭证与运行输出保留在本地，不随代码发布。

| 文件 | 用途 |
| --- | --- |
| `.env.example` | 无密钥的配置模板 |
| `.github/workflows/tests.yml` | 不请求模型的源码测试 |
| `.gitignore` | 本地文件忽略规则 |
| `FILE_MANIFEST.md` | 文件清单 |
| `LICENSE` | MIT 许可证 |
| `README.md` | 项目主页 |
| `convert_wsd.py` | XML 与 gold-key 转换 |
| `data/README.md` | 本地目录说明 |
| `docs/changes.md` | 项目使用与方法文档 |
| `docs/data_schema.md` | 项目使用与方法文档 |
| `docs/knowledge_base.md` | 项目使用与方法文档 |
| `docs/model_interface.md` | 项目使用与方法文档 |
| `docs/publish_guide.md` | 项目使用与方法文档 |
| `docs/quick_start.md` | 项目使用与方法文档 |
| `docs/reproduce.md` | 项目使用与方法文档 |
| `docs/security_review.md` | 项目使用与方法文档 |
| `docs/validation.md` | 项目使用与方法文档 |
| `evaluation.py` | 最终 JSON 精确判分 |
| `experiment_runner1_v2.py` | 真实实验与离线流程入口 |
| `fetch_public_data.py` | 公开多语言数据获取 |
| `model_interface.py` | HTTP 模型适配器及身份校验 |
| `preflight.py` | 标准库输入检查 |
| `prepare_data.py` | 输入清理、审计与独立划分 |
| `prepare_embeddings.py` | 真实编码器准备 |
| `requirements-tested-macos-py312.txt` | 本次安装的完整环境清单 |
| `requirements.txt` | 本次验证的直接依赖 |
| `resources/README.md` | 本地目录说明 |
| `support_data/README.md` | 本地目录说明 |
| `tests/test_convert_wsd.py` | 技术单元测试 |
| `tests/test_evaluation.py` | 技术单元测试 |
| `tests/test_grouping.py` | 技术单元测试 |
| `tests/test_model_interface.py` | 技术单元测试 |
| `tests/test_preflight.py` | 技术单元测试 |
| `tests/test_prepare_data.py` | 技术单元测试 |

测试中的临时协议和结构用例不属于研究数据或实验结果。`.env`、`local_data/`、`models/` 和 `outputs/` 均不在此清单内。
