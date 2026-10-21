# 多语言词义消歧实验工具

## 项目简介

本仓库提供多语言词义消歧（Word Sense Disambiguation，WSD）的实验源代码，组织跨语言语义检索、动态示例选择与基于句子表层复杂度的自适应提示策略。代码入口为 `experiment_runner1_v2.py`。

仓库为源代码复现工具，仅提供源代码及使用文档，不附带历史实验结果文件。当前交付不包含数据集、候选词义缓存、模型权重及模型服务接口实现；补齐依赖材料后才能开展实验。未完成真实模型端到端验证，不能据此宣称已复现论文结论或具体数值。

## 任务背景

任务根据带有目标词标记的句子，从候选词义词典中预测完整词义标识符。现有实现组织五种语言（英语、法语、德语、西班牙语、意大利语）、三类数据来源（`real`、`artificial`、`problem`）及三个难度层级（`simple`、`medium`、`complex`）。论文 IV-A 将真实数据的上游来源明确指向 [SapienzaNLP/mwsd-datasets](https://github.com/SapienzaNLP/mwsd-datasets)。项目使用的具体处理文件、上游子集及转换版本仍需与实际输入核对。

保留的模型接口标识为 `gpt-4o`、`llama-3.1-70b`、`deepseek-v3`；它们是接口别名，不代表已经确认的服务商、不可变模型快照或当前可用性。

## 环境依赖

建议在独立 Python 3.10 或更新环境中部署；原始环境版本未记录。直接依赖包括 NumPy、pandas、sentence-transformers，以及 Markdown 指标导出所需的 tabulate。`requirements.txt` 根据源代码导入与导出调用整理；由于代码未声明版本，不虚构版本锁定或声称它是历史环境。

sentence-transformers 的 PyTorch、Transformers 等传递依赖及计算设备配置由实际安装环境决定。模型接口使用的 SDK 依赖需要使用者补充。资源需求取决于设备、模型权重及服务配置，本仓库未提供实测显存或耗时承诺。

## 安装部署步骤

1. 下载或克隆本仓库，进入仓库根目录。
2. 创建虚拟环境并安装依赖：

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

3. 根据 [数据说明](docs/data_schema.md) 在本地准备独立的评估集、示例库和候选词义缓存。
4. 根据 [模型接口契约](docs/model_interface.md) 自行补充 `model_interface.py` 及其真实 SDK 依赖，通过环境变量配置凭证。
5. 准备 `intfloat/multilingual-e5-large` 和 `paraphrase-multilingual-MiniLM-L12-v2` 权重。模型缓存、下载权限与网络代理由使用者管理，代码不会关闭 TLS 校验或覆盖代理。

【该配置文件需要使用者自行根据数据集/模型凭证补充】：候选词义缓存 `resources/babelnet_inventory_cache_healed.json` 及模型接口依赖的本地凭证配置。模型接口源码本身也需使用者补充，仓库没有以占位接口模拟真实调用。

## 运行命令

以下命令均从仓库根目录执行。

```bash
# 查看参数，不加载模型
python experiment_runner1_v2.py --help

# 静态输入检查，不调用 API；缺失材料时返回非零退出码
python experiment_runner1_v2.py --check-only --models gpt-4o --languages fr --data-types real

# 输入和接口齐备后做小规模检查；可能产生服务费用
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types real --levels simple --limit 2

# 输入齐备后执行默认实验矩阵
python experiment_runner1_v2.py
```

详细的分组运行和指标导出见 [复现说明](docs/reproduce.md)，首次操作见 [快速上手](docs/quick_start.md)。

## 数据集说明

论文 IV-A 对三类数据作出说明：`real` 为带 BabelNet 或 WordNet 关联标签的真实上下文，公开上游为 [SapienzaNLP/mwsd-datasets](https://github.com/SapienzaNLP/mwsd-datasets)；`artificial` 为围绕显式词义标识符生成、带三个难度层级的句子；`problem` 为含干扰项或面向领域歧义的上下文。后两类为项目构造数据，论文未提供其独立公开下载地址。

上游提供 SemEval 多语言数据下载入口，原始交付为 XML 与 gold-key 文件，不能直接改名作为本项目 CSV。英语材料入口与四种非英语语言分开说明，具体使用的英语子集还需核实。获取、转换与待补材料见 [数据说明](docs/data_schema.md)。

`data/` 存放评估数据，`support_data/` 存放独立示例库，二者采用相同文件路径约定；候选词义缓存位于 `resources/`。输入文件及缓存默认被 Git 忽略，不随仓库分发。

CSV 至少包含 `sentence`、`senseid`；评估集还必须包含 `complexity`。目标词须由一个 `<WSD>...</WSD>` 标记对包围。使用者须确认数据来源、版本、许可、划分和跨语言平行样本隔离，记录处理流程及文件哈希。详见 [字段与路径说明](docs/data_schema.md)。本仓库不提供合成实验数据或替代历史结果。

## 复现说明

保留 `Baseline`、`Ours(No_CoT)` 和 `Ours(Fusion)` 三组。结果仅由使用者实际运行生成，准确率使用最终 JSON 中完整词义标识符的精确匹配计算。每次运行创建独立输出目录，导出汇总 CSV、样本级 CSV、配置 JSON 和 Markdown 报告；不跨模型或数据来源混合平均。

公开整理版修正了目标标签参与检索、宽松答案判分、数据来源混合计算增益及跨运行进度跳过问题，并要求示例库与评估集分离。这些属于评估协议调整，可能改变结果，不能将新运行数值直接视作论文历史数值。详见 [变更与方法边界](docs/changes.md)。

## 重要声明

本仓库仅提供源代码，不附带历史实验结果文件。文档不提供未经实际运行验证的准确率、性能提升或历史日志。复现结果受数据划分、词义库存、模型快照、服务参数和运行环境影响，应在独立实验后报告。

原论文中包含的通义千问对比实验组，已遵照导师建议在论文和本仓库中移除。

当前仓库中的可执行实现和运行配置仅包含上述三个保留模型。语言模型接口可能向外部服务发送输入文本；提示与响应默认不保存，但样本级输出仍含输入句子和标注，须按数据授权范围保管。

## 引用

使用本工具时，请在研究说明中注明实际仓库地址、使用的提交哈希、评估协议和访问日期。作者、正式论文题名、发表信息与 DOI 尚待权利人核实，当前不提供未经核实的 BibTeX 或 DOI。发布前可由作者补充真实论文信息和仓库引用条目。第三方数据、模型和软件应分别按其官方要求引用。

## 许可证

原创代码与文档采用 [MIT License](LICENSE)。许可证不授予第三方数据集、词义资源、模型权重或模型服务的使用与再分发权利。发布者应确认对所发布代码具有授权，并在上传前核实许可证中的版权归属。
