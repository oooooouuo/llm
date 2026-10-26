# 本地词义资源

运行默认使用 `local_data/current/resources/babelnet_inventory_cache_healed.json`，由 `prepare_data.py` 从独立词义缓存清理得到。只移除空项、非法格式和重复候选，不生成释义，也不用评估金标补齐词典。

【该配置文件需要使用者自行根据数据集/模型凭证补充】：准备数据时所用的独立候选词义缓存。已有缓存可直接作为输入，无需原构建脚本。资源版本与许可请随数据处理记录保存。详见 [数据说明](../docs/data_schema.md)。
