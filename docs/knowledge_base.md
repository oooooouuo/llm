# 知识库存档版项目简介

项目名称：多语言词义消歧实验工具（multilingual-wsd）。

项目目标：为多语言词义消歧提供源代码复现工具，考察跨语言示例检索、语义示例选择与自适应提示的组合策略。输入为带目标词标记的句子及候选词义列表，输出为完整词义标识符。

方法：multilingual-e5-large 检索英语上下文；paraphrase-multilingual-MiniLM-L12-v2 按语义相似度与频率权重排序示例；表层词数与标点数决定示例数量及是否启用显式推理提示。真实数据限制示例数量，英语目标采用单语回退。

数据来源：真实数据使用 [SapienzaNLP/mwsd-datasets](https://github.com/SapienzaNLP/mwsd-datasets) 的多语言资源；人工数据为围绕显式词义 ID 生成的分层句子，问题导向数据包含干扰项或领域化歧义上下文。公开上游材料仍需核对具体子集并转换成项目 CSV；当前发布未提供后两类数据的下载包或生成脚本。

代码入口：`experiment_runner1_v2.py`。`preflight.py` 校验数据与资源；`evaluation.py` 对最终 JSON 中的完整词义 ID 精确判分。`--check-only` 只检查输入，`--limit` 用于小规模冒烟检查。

实验范围：三个保留接口别名 gpt-4o、llama-3.1-70b、deepseek-v3；en、fr、de、es、it 五种语言；real、artificial、problem 三类来源；三个难度层级；Baseline、Ours(No_CoT)、Ours(Fusion) 三组。

边界：仓库仅提供源代码，不附带历史实验结果文件。数据、独立示例库、候选词义缓存、模型权重及真实模型接口需自行补齐，当前发布未提供环境锁定文件，公开版本尚未完成真实模型端到端验证。公开版修正了标签参与检索、宽松判分及跨来源增益配对，并要求独立数据划分；其新结果不能直接替代论文历史数值。实验指标以对应版本的实际运行记录为准。

归档使用：本简介适合知识库检索；运行命令与字段以仓库 README 及 docs/reproduce.md 为准。维护时同步更新数据版本、运行环境及验证状态。
