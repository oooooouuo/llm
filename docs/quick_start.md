# 快速上手

本项目是源代码复现工具，不附带历史实验结果文件。初次使用应先配置本地依赖与数据，再启动付费模型调用。

## 环境与配置

从仓库根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python experiment_runner1_v2.py --help
```

准备 `data/` 中的评估 CSV、`support_data/` 中的独立示例 CSV、`resources/babelnet_inventory_cache_healed.json` 及根目录的 `model_interface.py`。字段见 [data_schema.md](data_schema.md)，接口见 [model_interface.md](model_interface.md)。安装接口 SDK 时把真实依赖加入本地依赖清单。

【该配置文件需要使用者自行根据数据集/模型凭证补充】：候选词义缓存与模型接口所需的凭证配置。完成配置后再启动模型调用。

## 检查与运行

```bash
python experiment_runner1_v2.py --check-only --languages fr --data-types real --models gpt-4o
python -m unittest discover -s tests -v
```

静态检查只验证文件结构、候选覆盖和完全重复的句子，不会验证凭证、服务可用性或语义层面的数据泄漏；单元测试也不代表实验验证。

配置完成后进行小规模运行：

```bash
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types real --levels simple --limit 2
```

`--limit 2` 对每个选中的评估单元最多读取两行，不是随机抽样，不能据此报告完整实验性能。真实运行结果输出到 `outputs/` 下的独立子目录，默认不会上传 Git。运行完整矩阵和检查指标口径见 [reproduce.md](reproduce.md)。
