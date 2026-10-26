# 实验复现说明

本仓库发布源代码，不附带历史实验结果文件。以下流程用于在明确的输入、划分和模型配置下开展新实验。

## 一 生成本地输入

已有带词义 ID 的 CSV 和独立词典时：

```bash
python prepare_data.py --source-dir /path/to/document11 --inventory-source /path/to/babelnet_inventory_cache_healed.json
```

公开真实语料可用 `python fetch_public_data.py` 下载转换。合并多类输入时重复使用 `--source-dir`，并为新的准备版本选择未使用过的 `--output-root`。完整要求见 [data_schema.md](data_schema.md)。

`data_manifest.json` 记录输入指纹、清理与分组协议；`excluded_rows.csv` 记录排除原因。这里的数据处理数量不是模型性能结果。人工数据按共享词义关联，真实数据按文档关联，相同句子保持同侧；这属于新的保守评估设置，会影响示例覆盖与可比较性。

## 二 准备编码器和模型接口

```bash
python prepare_embeddings.py
cp .env.example .env
```

如需复用本地 E5 权重，用 `--local-e5-source` 指定本地目录。脚本从官方来源补齐 pooling 元数据，不修改来源。配置写入本地 `models/encoder_paths.local.json`，runner 自动读取；也可由环境变量 `WSD_E5_MODEL` 和 `WSD_SAMPLER_MODEL` 覆盖。

`.env` 中配置自己的服务凭证与模型端点。模型适配器已经提供；无需找到旧配置或恢复旧密钥。参数与身份检查见 [model_interface.md](model_interface.md)。没有有效凭证时仍可运行输入检查和离线检索检查。

## 三 分阶段检查

```bash
python -B -m unittest discover -s tests -v
python experiment_runner1_v2.py --check-only --data-types artificial problem
python experiment_runner1_v2.py --dry-run --models gpt-4o --languages fr --data-types artificial --levels simple --limit 1
python experiment_runner1_v2.py --check-config --models gpt-4o
```

`--check-only` 只用标准库检查输入；`--dry-run` 使用真实编码器走同一套检索、示例选择与提示代码，但不创建生成模型客户端、不计算准确率；`--check-config` 仅检查配置和凭证是否设置，不请求服务。

若真实数据没有英语示例库，明确采用单语回退并只选择存在的语言：

```bash
python experiment_runner1_v2.py --check-only --data-types real --languages de fr es it --allow-missing-english
python experiment_runner1_v2.py --dry-run --models gpt-4o --data-types real --languages de fr es it --allow-missing-english --limit 1
```

没有指定 `--allow-missing-english` 时，缺失英语池会报错。该选项不创建英语数据，也不使目标英语评估自动可用。

## 四 各组实验

| 组名 | 示例与提示 |
| --- | --- |
| `Baseline` | 单语同词示例最多随机选择 3 条，关闭显式推理提示 |
| `Ours(No_CoT)` | 英语检索、语义选择、自适应示例数，关闭显式推理提示 |
| `Ours(Fusion)` | 同上，并按复杂度决定是否开启显式推理提示 |

表层复杂度为标记句子的空格分词数加 0.2 倍指定标点数。得分低于 15 时 k=3；低于 30 时 k=5；其余 k=5，完整组开启推理。真实数据 k 上限为 3、语义权重系数为 1，其余来源系数为 2。Baseline 使用 42+i 的采样种子，不保证远程生成确定性。

非英语目标按独立候选词义约束英语示例；E5 最多召回 15 条，MiniLM 加权排序。真实来源在直接匹配为空时使用 lemma 桥接，实际阈值下限为 0.86。英语目标或检索为空时采用单语回退。真实来源提示不展示示例金标，其他来源展示。E5 保留语言代码前缀输入协议。

配置完凭证后，以下命令会实际调用服务并产生费用：

```bash
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types artificial --versions Baseline 'Ours(No_CoT)' 'Ours(Fusion)' --save-response
```

单个版本可通过 `--versions Baseline`、`--versions 'Ours(No_CoT)'` 或 `--versions 'Ours(Fusion)'` 选择。建议同一次调用运行三个版本，便于配对计算 Baseline 差值。

```bash
python experiment_runner1_v2.py --data-types artificial problem --save-response
python experiment_runner1_v2.py --data-types real --languages de fr es it --allow-missing-english --save-response
```

`--data-dir`、`--support-dir` 和 `--inventory` 可覆盖默认 `local_data/current/` 路径。完整数据矩阵准备齐备后可运行不带筛选参数的入口；缺项会报错，不静默补样本。

## 五 指标与导出

真实生成实验保存到 `outputs/<运行标识>/`：

- `fusion_summary_*.csv`：按模型、来源、语言、难度、版本区分的汇总。
- `fusion_sample_detail_*.csv`：输入、候选、策略与正确性；调用元数据使用 JSON 编码。
- `sample_journal.jsonl`：每条完成响应立即写入的本地记录，便于异常后检查；当前不提供自动续跑。
- `config_*.json`：代码所用配置、接口身份、包版本、选择条件与输入指纹。
- `report_*.md`：该次运行结果的逐单元报告，不混合模型或来源平均。

准确率为正确数除以总数，取值 0–1。`improvement` 为准确率差，乘 100 为百分点；缺少同次同组 Baseline 时留空。只接受响应结尾仅含 `sense_id` 的合法 JSON，完整 ID 区分大小写精确匹配；分析正文中的正确 ID、数字片段或子串不计分。空响应和格式失败计错；服务异常终止该运行，不产生完整实验结论。

提示与响应默认不保留全文；需要独立重评分时启用 `--save-response`，必要时加 `--save-prompt`。样本记录即使没有响应全文仍包含输入文本与标注，应受本地权限和数据许可约束。

离线检查只产生 `pipeline_check.json`，标明 `model_calls=0` 和 `metrics_computed=false`。它不能作为模型性能、论文结论或服务连通性的证据。

## 六 记录与比较

本地已安装包清单见 `requirements-tested-macos-py312.txt`；它对应新的验证环境。还应记录硬件、代码提交、输入版本、资源来源、实际模型快照和完整调用设置。语义近重复、预训练污染和供应商内部更新无法仅凭静态检查排除。

当前实验矩阵不能分离所有模块的独立因果效应，也不自动输出重复运行统计、置信区间或显著性检验。协议变化见 [changes.md](changes.md)。
