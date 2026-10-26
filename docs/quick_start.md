# 快速上手

本项目发布源代码，不附带历史实验结果文件。模型接口、数据准备和 XML 转换已经提供，运行前只需配置实际数据、编码器与自己的服务凭证。

## 安装与准备

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python prepare_data.py --source-dir /path/to/document11 --inventory-source /path/to/babelnet_inventory_cache_healed.json
python prepare_embeddings.py
```

已有 E5 权重时，可将最后一条改为 `python prepare_embeddings.py --local-e5-source /path/to/multilingual-e5-large`。准备脚本不会修改来源文件；已有输出会拒绝覆盖。

## 先验证离线流程

```bash
python experiment_runner1_v2.py --check-only --data-types artificial problem
python experiment_runner1_v2.py --dry-run --models gpt-4o --languages fr --data-types artificial --levels simple --limit 1
```

第二条使用真实编码器进行检索与提示构建，不调用付费生成模型，不计算准确率。输出为本地 `outputs/<运行目录>/pipeline_check.json`，其中明确记录 `metrics_computed=false`。

## 再启动真实实验

```bash
cp .env.example .env
```

在 `.env` 中填写自己的服务密钥，核对模型 ID 和服务地址。无需复制历史接口或使用旧凭证。

```bash
python experiment_runner1_v2.py --check-config --models gpt-4o
python experiment_runner1_v2.py --models gpt-4o --languages fr --data-types artificial --levels simple --limit 2 --save-response
```

后一条会向服务发送真实文本并产生费用。检查调用元数据、响应格式与样本数量后，再移除 `--limit` 执行完整分组。更多命令见 [reproduce.md](reproduce.md)。
