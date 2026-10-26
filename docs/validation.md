# 本地验证范围

验证日期：2026-10-26。以下记录程序与输入准备检查，不是论文实验结果或模型性能报告。

## 已完成

- Python 3.12 / macOS ARM64 独立虚拟环境安装成功，直接依赖和完整包版本已记录。
- 22 项单元测试通过，覆盖最终答案判分、分来源 Baseline 配对、配置身份、凭证隔离、HTTP 请求参数、服务异常、输入转换、来源指纹、确定性分组及不同目标词的保留。
- 已有人工／问题导向 CSV 经原件保留、标记与候选覆盖检查、去重和独立分组，输入检查通过。
- 公开 SemEval-2013 ALL 多语言包下载成功；四种非英语语言完成 XML/gold 转换并单独记录新难度策略。与本地缓存不相容的行按原因隔离，没有用评估标签补齐词典。
- 使用真实 E5 与 MiniLM 权重，对人工／问题数据的五种语言、三个难度和三个版本各取一条进行离线流程检查，共 90 项；四种真实语料同样检查，共 36 项。
- 上述离线检查明确记录生成模型调用为 0、指标计算为 false，不导出准确率。

E5 复用了本地权重，并从官方仓库取得缺失的 pooling 元数据；pooling revision 为 `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3`。MiniLM 下载快照为 `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`。本地 E5 架构检查不独立证明权重快照身份；具体来源与本地模型配置记录保留在运行目录。

## 检查内容

离线流程与真实实验共用 `_prepare_case`，执行实际编码器检索、示例选择及提示构建，覆盖跨语言召回和单语回退。准备数据的原始行号、SHA-256、排除原因和分组协议保留于本地 manifest，不随代码发布原始文本。

公开包不含英语真实语料。本次四种真实语料检查显式启用单语回退；没有使用人工英语语料伪装为真实英语示例池，也未验证该来源的跨语言效果。

## 尚未完成

没有使用历史密钥请求服务；没有验证各账户权限、默认模型 ID 当前可用性、付费模型完整实验或论文结论。HTTP 单元测试使用临时协议用例，不属于服务商真实调用结果。

没有重建完整历史响应库，也没有将新划分、新转换或新的依赖清单表述为历史实验配置。运行完整实验仍需自己的有效服务凭证、可访问的对应模型端点，以及明确的数据处理协议。

## 复查命令

```bash
python -B -m unittest discover -s tests -v
python experiment_runner1_v2.py --check-only --data-types artificial problem
python experiment_runner1_v2.py --dry-run --models gpt-4o --languages fr en de es it --data-types artificial problem --limit 1
python experiment_runner1_v2.py --dry-run --models gpt-4o --languages de fr es it --data-types real --allow-missing-english --limit 1
```

这些命令需要相应的本地输入与编码器；具体准备步骤见 [quick_start.md](quick_start.md)。
