"""Validate user-supplied inputs without importing ML packages or calling APIs."""
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from evaluation import gold_ids, ID_PATTERN


def dataset_path(base, source, language):
    base = Path(base)
    if source == 'real':
        return base / language / f'sem13_{language}.csv'
    return base / f'{source}_{language}.csv'


def normalized_sentence(text):
    return ' '.join(re.sub(r'</?WSD>', '', text, flags=re.I).casefold().split())


def validate_inputs(data_dir, support_dir, inventory_path, sources, languages, require_english=True):
    errors, manifest = [], []
    inventory_path = Path(inventory_path)
    inventory = {}
    try:
        inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
        if not isinstance(inventory, dict) or not inventory:
            raise ValueError('顶层必须是非空对象')
        for senses in inventory.values():
            if not isinstance(senses, list) or not senses:
                raise ValueError('每个词条必须包含非空候选列表')
            for sense in senses:
                if (not isinstance(sense, dict) or not isinstance(sense.get('id'), str)
                        or not ID_PATTERN.fullmatch(sense['id'])
                        or not isinstance(sense.get('gloss'), str) or not sense['gloss'].strip()):
                    raise ValueError('候选必须包含完整 id 和非空 gloss')
        manifest.append({'role': 'inventory', 'file': inventory_path.name,
                         'sha256': hashlib.sha256(inventory_path.read_bytes()).hexdigest()})
    except (OSError, ValueError) as exc:
        errors.append(f'候选词义缓存不可用：{inventory_path} ({exc})')
        inventory = {}
    if Path(data_dir).resolve() == Path(support_dir).resolve():
        errors.append('评估集与示例库必须使用不同目录。')
    sentences = {'evaluation': set(), 'support': set()}
    for role, base, langs in [('evaluation', data_dir, languages),
                             ('support', support_dir, sorted(set(languages) | ({'en'} if require_english else set())))]:
        for source in sources:
            for language in langs:
                path = dataset_path(base, source, language)
                try:
                    with path.open(encoding='utf-8-sig', newline='') as handle:
                        reader = csv.DictReader(handle)
                        required = {'sentence', 'senseid'} | ({'complexity'} if role == 'evaluation' else set())
                        if not required.issubset(reader.fieldnames or []):
                            raise ValueError('缺少字段：' + ', '.join(sorted(required)))
                        rows = list(reader)
                    if not rows:
                        raise ValueError('文件为空')
                    for number, row in enumerate(rows, 2):
                        sentence = row.get('sentence') or ''
                        tags = re.findall(r'<WSD>(.*?)</WSD>', sentence, re.I)
                        if (sentence.lower().count('<wsd>') != 1 or sentence.lower().count('</wsd>') != 1
                                or len(tags) != 1 or not tags[0].strip()):
                            raise ValueError(f'第 {number} 行需要一个非空 <WSD>...</WSD> 目标')
                        truth = gold_ids(row.get('senseid'))
                        raw_truth = set(re.split(r'[,\s]+', (row.get('senseid') or '').strip()))
                        if not truth or raw_truth != truth:
                            raise ValueError(f'第 {number} 行 senseid 必须为完整标识符列表')
                        if role == 'evaluation':
                            if (row.get('complexity') or '').strip().strip("'\"") not in {'simple', 'medium', 'complex'}:
                                raise ValueError(f'第 {number} 行 complexity 不合法')
                            lemma = tags[0].strip().lower()
                            senses = inventory.get(f'{language}:{lemma}', inventory.get(lemma, []))
                            candidates = {c['id'] for c in senses}
                            if inventory and not truth.issubset(candidates):
                                raise ValueError(f'第 {number} 行候选词典缺失或未覆盖真实标签；禁止用评估标签补齐词典')
                        weight = row.get('frequency_weight')
                        if weight:
                            value = float(weight)
                            if not math.isfinite(value) or value < 0:
                                raise ValueError(f'第 {number} 行 frequency_weight 应为有限非负数')
                        sentences[role].add(normalized_sentence(sentence))
                    manifest.append({'role': role, 'source': source, 'language': language,
                                     'file': str(path.relative_to(base)), 'rows': len(rows),
                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                except (OSError, ValueError, csv.Error) as exc:
                    errors.append(f'{role} 输入不可用：{path} ({exc})')
    if sentences['evaluation'] & sentences['support']:
        errors.append('评估集与示例库存在归一化后相同句子；请重新建立独立划分。')
    return errors, manifest
