# 数据来源与准备协议

我们使用真实语料、人工构造语料和问题导向语料。数据、候选词义资源与权重保存在本地，不随代码分发。

## 数据来源与获取

- `real`：使用 [SapienzaNLP/mwsd-datasets](https://github.com/SapienzaNLP/mwsd-datasets) 的多语言资源。`fetch_public_data.py` 通过该项目列出的公开入口下载 ALL 包，转换 SemEval-2013 的 de、es、fr、it 四种语言。
- `artificial`：围绕显式词义标识符构造，并标注三个难度层级的句子。
- `problem`：具有较强干扰或领域特征的上下文。

```bash
python fetch_public_data.py
```

输出 `local_data/upstream/` 包含原始压缩包、上游许可、下载哈希、XML/gold-key 原件及转换 CSV。不会自动获取英语，也不会把重新下载的数据称为历史项目输入。英语资源另见 [English WSD Evaluation Framework](http://lcl.uniroma1.it/wsdeval/)。上游资源与词义库适用其各自条款，本仓库 MIT 不覆盖它们。

已有 XML/gold 文件时：

```bash
python convert_wsd.py --xml /path/to/dataset.data.xml --gold /path/to/dataset.gold.key.txt --language fr --output local_data/imported_real/fr/sem13_fr.csv
```

转换保留实例 ID、文档 ID、多词目标与多个金标；未标注的实例会记录后跳过。句子按原 XML token 文本以空格连接。该转换采用新的表层复杂度分层 `surface_v1_new_preparation`，不声称与历史 CSV 处理相同。

## 输入文件与字段

每个来源目录可包含 `artificial_LANG.csv`、`problem_LANG.csv` 或 `LANG/sem13_LANG.csv`。`LANG` 取 en、fr、de、es、it。可以通过重复的 `--source-dir` 同时导入多个目录；同来源同语言只能显式选择一份输入，程序不自动猜测应使用哪个旧版本。

| 字段 | 约定 |
| --- | --- |
| `sentence` | 恰好一个非空 `<WSD>...</WSD>` 目标，不能有额外或不配对标记 |
| `senseid` | 完整标识符；多个金标以逗号或空白分隔 |
| `complexity` | `simple`、`medium` 或 `complex`，输入的分层标签会保留 |
| `fileid` | 可选文档 ID；真实数据按该字段分组隔离，XML 转换会保留它 |
| `frequency_weight` | 可选有限非负权重，缺失为 1 |

词义 ID 支持 BabelNet 风格和末尾为 `::` 的 WordNet 风格键子集。runner 的提示策略分数与 CSV 难度标签分别记录，不能将二者混为同一项。

## 可追溯清理

```bash
python prepare_data.py --source-dir /path/to/document11 --inventory-source /path/to/babelnet_inventory_cache_healed.json
```

默认输出到 `local_data/current/`。程序保留源文件、写入新目录，记录输入 SHA-256、行号与稳定样本 ID。输出目录存在时拒绝覆盖。

无效目标标记、非法标签、独立词典未覆盖金标的行被排除。同来源同语言中，只有带相同目标位置的上下文才参与重复/冲突检查；同一句子的不同目标词不会因此被误删。同目标上下文的冲突标注整体排除，一致重复保留首条。每次排除均记录于 `excluded_rows.csv`，不按论文样本数反向筛选，不修改标签，也不从金标补建候选词典。

缓存只保留已有的合法 ID 和非空释义，移除空列表和重复候选；不生成替代释义。释义质量与资源授权仍需按来源审查。

## 独立划分

新协议为 `synthetic_sense_real_document_and_identical_sentence_groups_v2`：人工/问题数据共享金标词义的记录保持同组；真实数据同文档记录保持同组；跨来源、语言归一化后完全相同的句子也连为同组。真实数据缺少文档 ID 时，只能按句子关联。多个标签形成的关联会合并分组。

以种子和稳定组 ID 的 SHA-256 确定分配，默认约 30% 分配到示例库，实际比例以分组结果为准。真实数据允许不同文档共享词义；人工数据采用更保守的词义隔离，可能使英语中没有目标词义的示例，从而降低检索覆盖。这是新的独立评估设置，不是历史划分。

金标仅用于分组与评分，不用于构造候选或目标检索。分组仍不能自动排除所有翻译、改写或其他语义近重复，须结合来源审查。

## 输出与缺失英语策略

```text
local_data/current/
  data/                         # 评估 CSV
  support_data/                 # 独立示例 CSV
  resources/babelnet_inventory_cache_healed.json
  excluded_rows.csv             # 来源行号与排除原因
  data_manifest.json            # 文件指纹、协议、数量与检查状态
```

默认要求每种来源有英语示例库。公开多语言包没有英语时，可以显式添加 `--allow-missing-english` 准备数据，并在运行时采用同名选项，且只选择存在的目标语言。该来源改用单语回退，配置会记录这一变化；不得将其解释为跨语言策略已经获得验证。

独立词义缓存和模型凭证属于本地配置文件：【该配置文件需要使用者自行根据数据集/模型凭证补充】。恢复的缓存可以经清理复用，无需寻找原构建程序才能运行新实验。
