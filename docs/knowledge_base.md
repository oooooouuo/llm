# 知识库存档版项目简介

项目：多语言词义消歧实验工具（multilingual-wsd），仓库为 https://github.com/oooooouuo/llm。

目标：将跨语言语义检索、语义示例选择与自适应提示整合为可配置的多语言 WSD 推理流程，输出完整词义 ID。

方法：multilingual-e5-large 检索英语上下文；多语言 MiniLM 按相似度与频率权重选择示例；词数和标点分数决定示例数量与显式推理提示。真实来源限制示例数；英语和空检索采用单语回退。

入口：`experiment_runner1_v2.py`。`model_interface.py` 提供三个保留模型组的 HTTP 适配器与身份校验；`prepare_data.py` 清理真实输入并建立独立划分；`fetch_public_data.py` 与 `convert_wsd.py` 获取、转换公开语料；`prepare_embeddings.py` 准备编码器。接口、转换和准备功能已提供，不需要找到旧实现才能开展新实验。

数据：真实多语言资源来自 SapienzaNLP/mwsd-datasets；人工与问题导向数据由带词义标注的本地 CSV 导入。准备记录包含文件哈希、源行号、排除原因和分组协议。数据、缓存、凭证与权重不随代码分发。

实验范围：gpt-4o、llama-3.1-70b、deepseek-v3；五种语言；三类数据来源；三个难度层级；Baseline、Ours(No_CoT)、Ours(Fusion)。本地实际可运行的组取决于已准备输入和服务权限。

边界：本仓库不附带历史实验结果文件。真实编码器的离线检索和提示构建已验证；付费生成服务端到端实验与论文结论验证尚未完成。新的数据转换、分组和判分协议应与论文历史报告分别记录。`--dry-run` 不调用生成模型，也不计算准确率。

使用：先准备数据与编码器，运行 `--check-only` 和 `--dry-run`；在本地 `.env` 中配置自己的有效凭证和对应模型端点后，检查配置再运行真实实验。配置缺失与验证状态以 README 和 docs/reproduce.md 为准。
