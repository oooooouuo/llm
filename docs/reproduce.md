# 实验复现说明

本仓库仅提供源代码，不附带历史实验结果文件。本说明描述如何在材料齐备后进行新的独立运行，不承诺恢复论文数值。当前未进行真实模型端到端运行。

## 运行前条件

按 [data_schema.md](data_schema.md) 准备独立的评估集、示例库和候选缓存，按 [model_interface.md](model_interface.md) 补齐真实模型接口及凭证。确认有权向模型服务发送数据，并记录实际模型快照、供应商、采样参数、SDK 版本和资源版本。

依赖未作历史版本锁定。安装成功并完成真实运行验证后，可以在本地记录环境：

```bash
python -m pip freeze > requirements-lock.local.txt
python --version > run-environment.local.txt
```

这两个文件被 Git 忽略。审查 `pip freeze` 中的本地路径、私有索引和 URL 凭证后，才能决定是否另行发布脱敏的锁定环境。不得将当前冻结版本表述为原始实验环境。

## 实验组与保留行为

| 组名 | 示例与提示策略 |
| --- | --- |
| `Baseline` | 独立单语示例库中相同目标词最多随机选 3 条，关闭显式推理提示 |
| `Ours(No_CoT)` | 英语检索、语义重排与自适应示例数，关闭显式推理提示 |
| `Ours(Fusion)` | 同上，并按表层复杂度决定是否启用显式推理提示 |

表层复杂度为原始标记句子的空格分词数加 0.2 倍指定标点数。得分低于 15 时 `k=3`，低于 30 时 `k=5`，其余 `k=5` 并在完整组启用推理提示。真实数据示例数上限为 3，语义权重系数为 1.0；其他来源系数为 2.0。Baseline 按样本序号使用 `42+i` 随机种子，不代表远程模型生成确定性。

非英语目标先按候选词义集合约束英语示例，E5 最多召回 15 条，MiniLM 进行频率与相似度加权排序。真实数据词义匹配为空时尝试英语 lemma 桥接，阈值实际为 `max(0.82, 0.86)=0.86`；检索为空时回退单语同词示例。英语目标直接采用单语回退。真实数据的提示保留上下文示例，但不显示示例正确 ID；其他来源显示示例标注。

E5 输入继续使用现存代码的语言代码前缀；本次未更换嵌入输入协议。`--levels` 选择 CSV 已有层级，不改变策略重新计算的分数。这里只提供完整组与关闭推理组的比较，不能证明每个模块各自的独立因果贡献。

## 检查输入

```bash
python experiment_runner1_v2.py --check-only --models gpt-4o --languages fr --data-types real
```

缺失文件、列、词义覆盖或重复句子会使检查失败。只校验所选数据来源和语言，并要求相应英语示例库。没有选中层级的样本时该层级跳过；最终无样本则报错，不导出空结果。

## 启动各组

为便于同组计算增益，建议在一次调用中运行三个版本：

```bash
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types real --versions Baseline 'Ours(No_CoT)' 'Ours(Fusion)'
```

只运行单个版本时可用：

```bash
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types real --versions Baseline
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types real --versions 'Ours(No_CoT)'
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types real --versions 'Ours(Fusion)'
```

分开调用生成独立输出，程序不会跨调用合并 Baseline；没有同次、同模型、同来源、同语言、同层级的 Baseline 时，改进值为空。

分来源执行所有保留模型与语言：

```bash
python experiment_runner1_v2.py --data-types real
python experiment_runner1_v2.py --data-types artificial
python experiment_runner1_v2.py --data-types problem
```

执行所有保留模型、五种语言、三种来源、三种层级和三个版本：

```bash
python experiment_runner1_v2.py
```

首次可添加 `--limit 2 --levels simple` 做冒烟检查，该选项按输入顺序截取每个单元，不能作为完整评估。接口每次请求最多要求 1024 个输出 token；主脚本请求间隔为 1.2 秒，服务端实际限额与重试由接口处理。没有自动样本级续跑，异常后重新启动会创建新的运行目录；不得将不同运行的部分结果冒充完整运行。

## 指标与导出

真实运行完成后自动生成：

```text
outputs/<独立运行目录>/
  fusion_summary_<运行标识>.csv
  fusion_sample_detail_<运行标识>.csv
  config_<运行标识>.json
  report_<运行标识>.md
  [debug_]experiment_progress.json
  [debug_]temp_experiment_results/
```

这些是程序未来实际执行时的输出路径，本仓库不附带对应结果文件。

汇总按 `model_name`、`data_source`、`target_language`、`data_level`、`system_version` 区分。`accuracy=correct_samples/total_samples`，取值 0–1；`improvement=组准确率−同组Baseline准确率`，乘 100 为百分点，不能写成相对百分比提升。Baseline 自身改进值为 0。

答案必须在响应结尾提供只含 `sense_id` 的合法 JSON 对象，可包在 Markdown 代码围栏中；推理文字可以出现在该最终对象之前。完整标识符须与某一真实标签精确、区分大小写相等。正文或推理中提到正确 ID、数字片段或子串均不计正确。格式错误、空响应计错，不从分母剔除；服务异常终止运行，不生成完整运行结论。

样本明细含真实输入句子、标注、候选集、策略选择、回退状态及正确性；即使未保存提示/响应，仍有数据隐私和许可约束。若授权允许且需要独立复核响应，可显式加 `--save-response`，必要时加 `--save-prompt`，保存于本地。未保存响应时无法事后独立重判。

配置 JSON 记录本次选择、Python 与主要包版本、评估协议、输入行数及 SHA-256；接口 SDK、服务采样参数、权重 revision、硬件及代码提交哈希仍须另行记录。逐单元检查样本数、空响应与格式失败情况，保留运行材料后再撰写结果。程序不生成置信区间、重复运行统计或显著性检验，不能暗示已有这些证据。

## 与现存实现的差异

见 [changes.md](changes.md)。公开整理版的评估协议有明确调整，新输出不能直接当作论文历史结果。完全重复检查不能替代跨语言或同源文档的数据划分审计。
