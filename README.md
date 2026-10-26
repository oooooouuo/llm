# 多语言词义消歧实验工具

## 项目简介

我们研究多语言词义消歧（Word Sense Disambiguation，WSD）中的示例选择与提示策略，将跨语言语义检索、动态示例选择和基于表层复杂度的自适应提示整合为统一的推理流程。

本仓库提供实验入口、模型适配器、数据准备与公开语料转换脚本。数据、模型权重和凭证在本地配置，不附带历史实验结果文件。真实编码器的离线检索与提示构建已进行本地验证；付费生成模型的端到端实验与论文结论验证尚未完成。验证范围见 [本地验证记录](docs/validation.md)。

## 任务背景

任务从给定候选词义中预测句中目标词的完整标识符。实验代码支持 en、fr、de、es、it 五种语言，`real`、`artificial`、`problem` 三类来源及三个难度层级。

三个实验版本为 `Baseline`、`Ours(No_CoT)` 和 `Ours(Fusion)`。生成模型分组使用 `gpt-4o`、`llama-3.1-70b`、`deepseek-v3`。接口将分组与实际请求模型分别记录，并检查请求与响应的模型标识；不会自动换用其他模型。

## 环境依赖

本地验证环境为 Python 3.12、macOS ARM64。安装依赖：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` 固定本次使用的直接依赖；[完整环境清单](requirements-tested-macos-py312.txt) 记录本次安装的包版本，属于新的执行环境，不是论文历史环境锁定文件。其他系统可先用直接依赖清单安装，再记录实际解析版本。HTTP 模型适配器仅用 Python 标准库，不依赖供应商 SDK。

## 安装部署步骤

1. 安装依赖。
2. 准备已有 CSV 与独立候选词义缓存，执行数据检查和独立划分：

   ```bash
   python prepare_data.py --source-dir /path/to/document11 --inventory-source /path/to/babelnet_inventory_cache_healed.json
   ```

   默认输出为 `local_data/current/`，包含评估集、示例库、缓存、来源指纹与排除记录。已有输出不会被覆盖。原始输入不会被修改。

3. 准备真实编码器：

   ```bash
   python prepare_embeddings.py
   # 如有本地 E5 权重，可复用；缺失的 pooling 元数据从官方仓库取得
   python prepare_embeddings.py --local-e5-source /path/to/multilingual-e5-large
   ```

   两条命令任选其一。编码器路径写入被 Git 忽略的本地配置，入口会自动读取。权重仍受其原始许可约束。

4. 配置模型服务：

   ```bash
   cp .env.example .env
   ```

   【该配置文件需要使用者自行根据数据集/模型凭证补充】：本地 `.env` 中的服务凭证，以及有权限访问的模型端点。接口实现已经包含在仓库，无需寻找旧接口文件。配置和模型身份约束见 [模型接口说明](docs/model_interface.md)。

## 运行命令

从仓库根目录执行：

```bash
# 校验已准备输入，不加载编码器、不调用生成服务
python experiment_runner1_v2.py --check-only --data-types artificial problem

# 真实 E5 / MiniLM 检索与提示检查；零生成服务调用，不计算准确率
python experiment_runner1_v2.py --dry-run --models gpt-4o --languages fr --data-types artificial --levels simple --limit 1

# 仅检查本地服务配置和凭证是否已设置，不请求服务
python experiment_runner1_v2.py --check-config --models gpt-4o

# 配置凭证后，执行真实生成实验；会产生服务费用
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types artificial --levels simple --limit 2 --save-response

# 单元测试不连接外部服务
python -B -m unittest discover -s tests -v
```

`--limit` 是逐单元按输入顺序截取的检查选项，不能代替完整评估。准备全部输入后可省略分组参数运行完整矩阵；缺少某组输入时会明确报错。分来源、分语言运行及指标导出见 [复现说明](docs/reproduce.md)。

## 数据集说明

`real` 使用 [SapienzaNLP/mwsd-datasets](https://github.com/SapienzaNLP/mwsd-datasets) 的多语言资源；`artificial` 为围绕词义构造的分层句子；`problem` 使用干扰较强或领域化上下文。CSV 包含 `sentence`、`senseid` 和 `complexity`，目标词由一个 `<WSD>...</WSD>` 标记对标出。

公开多语言真实数据可自动下载与转换：

```bash
python fetch_public_data.py
python prepare_data.py --source-dir local_data/upstream/converted --inventory-source /path/to/babelnet_inventory_cache_healed.json --output-root local_data/real_prepared --allow-missing-english
```

该公开包不含英语。英语数据与词义映射必须匹配所用协议；没有英语示例库时，只有显式指定 `--allow-missing-english` 才允许单语回退。下载、转换和难度标注属于新的数据准备，不等同于历史项目输入。详细字段、分组和授权说明见 [数据说明](docs/data_schema.md)。

## 复现说明

数据准备保留源文件 SHA-256、原始行号与排除原因，不修改真实标签或通过真实标签补齐候选词典。人工/问题数据按共享词义分组，真实数据按文档分组；归一化相同句子也保持同一侧。这是一套新的保守划分，可能降低跨语言检索覆盖，不能直接对应论文数值。

真实实验导出分组汇总、样本明细、调用元数据和运行配置。准确率采用最终 JSON 中完整词义 ID 的精确匹配；改进值只与同模型、同来源、同语言和同层级的 Baseline 比较。离线检查只输出流程验证记录，不生成准确率或模型性能表。

## 重要声明

本仓库仅提供源代码，不附带历史实验结果文件。新运行结果应注明代码、数据处理、模型服务及评估协议版本，并与论文历史报告分别记录。

原论文中包含的通义千问对比实验组，已遵照导师建议在论文和本仓库中移除。

模型服务、快照与访问权限可能变化。示例模型 ID 不构成当前可用性承诺；服务不可用或模型身份不符时程序会终止，不以其他模型代替原实验组。样本级输出含文本和标注，应在授权范围内使用与保管。

## 引用

使用本项目时，请注明[仓库地址](https://github.com/oooooouuo/llm)、提交哈希及采用的评估协议，同时引用数据、编码器和模型的原始工作。当前仓库未提供正式论文书目信息。

## 许可证

原创代码与文档采用 [MIT License](LICENSE)。数据、词义资源、权重及外部服务遵循其各自许可与条款，不随代码再分发。
