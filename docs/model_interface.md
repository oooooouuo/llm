# 模型接口与凭证配置

`model_interface.py` 实现统一接口，使用 Python 标准库发送 OpenAI 兼容的 Chat Completions 请求。不依赖供应商 SDK，不读取历史凭证文件，也不在导入时调用服务。

## 配置

将根目录 `.env.example` 复制为 `.env`，填入本地凭证。`.env` 只按 `KEY=VALUE` 读取，不执行 shell 命令；已经设置的环境变量优先。凭证不进入 Git 或调用元数据。

| 实验组 | 凭证环境变量 | 默认服务 | 示例请求 ID |
| --- | --- | --- | --- |
| `gpt-4o` | `OPENAI_API_KEY` | OpenAI | `gpt-4o` |
| `llama-3.1-70b` | `TOGETHER_API_KEY` | Together | `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` |
| `deepseek-v3` | `SILICONFLOW_API_KEY` | SiliconFlow | `deepseek-ai/DeepSeek-V3` |

`WSD_GPT4O_*`、`WSD_LLAMA_*`、`WSD_DEEPSEEK_*` 的 `BASE_URL` 与 `MODEL_ID` 可配置到支持对应模型的服务，包括本地 OpenAI 兼容部署。远程端点须使用 HTTPS，本机回环地址允许 HTTP。URL 不能携带用户名、密码、查询凭证或片段。

【该配置文件需要使用者自行根据数据集/模型凭证补充】：本地 `.env`。当前服务是否开放示例 ID，需要在所用账户确认；下线后不会自动改用其他模型。自部署也应暴露可以核对身份的模型 ID，而非不透明的别名。

## 身份校验与记录

实验别名与请求模型分别保存。GPT-4o 允许对应日期快照；Llama 组限定 3.1 和 70B；DeepSeek 组限定 V3 及明确的 V3 日期版本。不把不同版本或不同系列混记为同组。请求前检查配置，响应中存在 `model` 字段时再次校验，身份不符即终止。

每条真实调用的元数据包含请求模型、响应模型、响应 ID、请求 ID、系统指纹、token 用量、结束原因、响应 SHA-256 和接收时间。服务未提供的字段保持空值。它们构成可追溯记录，但不能独立证明供应商内部权重身份。

## 请求与失败处理

默认温度为 0、超时 120 秒、重试次数 0。可通过 `WSD_TEMPERATURE`、`WSD_TIMEOUT`、`WSD_RETRIES` 调整；重试仅适用于连接异常和暂时性 HTTP 错误，可能带来重复计费。错误信息不回显服务返回体、请求文本或密钥。

调用 `generate_response(prompt, max_tokens=1024)` 时，OpenAI 使用 `max_completion_tokens`，其他默认服务使用 `max_tokens`；上限不会被接口固定覆盖。服务错误终止运行；合法空响应保留为空并计为错误预测。

## 不调用服务的检查

```bash
python experiment_runner1_v2.py --check-config --models gpt-4o
python model_interface.py --models gpt-4o
```

这些命令只检查本地配置，不证明密钥有效、端点在线或模型可访问。

接口参数依据：[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[Together Chat Completions](https://docs.together.ai/reference/chat-completions)、[SiliconFlow Chat Completions](https://docs.siliconflow.cn/docs/api/chat-completions-post)。模型生命周期参见 [Together deprecations](https://docs.together.ai/docs/deprecations) 与 [SiliconFlow 更新说明](https://docs.siliconflow.cn/docs/release-notes/overview)。
