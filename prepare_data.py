"""Prepare real input files without altering originals or reconstructing historical results."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
from evaluation import ID_PATTERN, gold_ids
from preflight import normalized_sentence, validate_inputs


class UnionFind:
    def __init__(self):
        self.parent = {}

    def root(self, key):
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def join(self, first, second):
        a, b = self.root(first), self.root(second)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sanitize_inventory(path):
    original = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(original, dict):
        raise ValueError('Inventory must be an object')
    cleaned, dropped = {}, Counter()
    for key, values in original.items():
        kept, seen = [], set()
        if not isinstance(values, list):
            dropped['invalid_entry_list'] += 1
            continue
        for sense in values:
            if (not isinstance(sense, dict) or not isinstance(sense.get('id'), str)
                    or not ID_PATTERN.fullmatch(sense['id'])
                    or not isinstance(sense.get('gloss'), str) or not sense['gloss'].strip()):
                dropped['invalid_candidate'] += 1
                continue
            if sense['id'] in seen:
                dropped['duplicate_candidate'] += 1
                continue
            seen.add(sense['id'])
            kept.append({'id': sense['id'], 'gloss': sense['gloss']})
        if kept:
            cleaned[key] = kept
        else:
            dropped['empty_entry'] += 1
    if not cleaned:
        raise ValueError('No usable independent inventory entries')
    return cleaned, dict(dropped)


def prepare(source_dirs, inventory_source, output_root, seed=42, support_fraction=0.3, allow_missing_english=False):
    if not 0 < support_fraction < 1:
        raise ValueError('support_fraction must be between 0 and 1')
    output_root = Path(output_root)
    if output_root.exists():
        raise ValueError('Output directory already exists; choose a new directory to preserve provenance')
    inventory, inventory_drops = sanitize_inventory(inventory_source)
    candidates, rejected, input_files, seen_files = [], [], [], set()
    for base in map(Path, source_dirs):
        if not base.is_dir():
            raise ValueError(f'Source directory is unavailable: {base}')
        for path in sorted(base.rglob('*.csv')):
            match = re.fullmatch(r'(artificial|problem|sem13)_(en|fr|de|es|it)\.csv', path.name)
            if not match:
                continue
            source, language = match.groups()
            source = 'real' if source == 'sem13' else source
            unit = (source, language)
            if unit in seen_files:
                raise ValueError(f'Duplicate input file for {source}/{language}; choose one version explicitly')
            seen_files.add(unit)
            file_hash = digest_file(path)
            with path.open(encoding='utf-8-sig', newline='') as stream:
                reader = csv.DictReader(stream)
                if not {'sentence', 'senseid', 'complexity'}.issubset(reader.fieldnames or []):
                    raise ValueError(f'{path.name}: required columns are sentence, senseid, complexity')
                rows = list(reader)
            input_files.append({'file': path.name, 'sha256': file_hash, 'rows': len(rows),
                                'source': source, 'language': language})
            for number, row in enumerate(rows, 2):
                provenance = {'source_file': path.name, 'source_sha256': file_hash, 'source_row': number}
                sentence = row.get('sentence') or ''
                tags = re.findall(r'<WSD>(.*?)</WSD>', sentence, re.I)
                level = (row.get('complexity') or '').strip().strip("'\"")
                raw_truth = set(re.split(r'[,\s]+', (row.get('senseid') or '').strip()))
                truth = gold_ids(row.get('senseid'))
                reason = None
                if (sentence.lower().count('<wsd>') != 1 or sentence.lower().count('</wsd>') != 1
                        or len(tags) != 1 or not tags[0].strip()):
                    reason = 'invalid_or_multiple_target_markers'
                elif not truth or truth != raw_truth:
                    reason = 'invalid_gold_identifier'
                elif level not in {'simple', 'medium', 'complex'}:
                    reason = 'invalid_difficulty_label'
                else:
                    lemma = tags[0].strip().lower()
                    senses = inventory.get(f'{language}:{lemma}', inventory.get(lemma, []))
                    if not truth.issubset({s['id'] for s in senses}):
                        reason = 'independent_inventory_does_not_cover_gold'
                if reason:
                    rejected.append({**provenance, 'reason': reason})
                    continue
                row['complexity'] = level
                # Do not repair labels, candidate meanings, target positions or sentences.
                row['sample_id'] = hashlib.sha256(f'{file_hash}:{number}'.encode()).hexdigest()
                candidates.append({'row': row, 'source': source, 'language': language,
                                   'truth': truth, 'text': normalized_sentence(sentence), **provenance})
    if not input_files:
        raise ValueError('No recognized input CSV files found')
    by_context = defaultdict(list)
    for item in candidates:
        by_context[(item['source'], item['language'], ' '.join(item['row']['sentence'].casefold().split()))].append(item)
    retained = []
    for group in by_context.values():
        annotations = {(tuple(sorted(x['truth'])), x['row']['complexity']) for x in group}
        if len(annotations) > 1:
            for item in group:
                rejected.append({k: item[k] for k in ('source_file', 'source_sha256', 'source_row')} |
                                {'reason': 'conflicting_annotations_for_identical_context'})
            continue
        retained.append(group[0])
        for item in group[1:]:
            rejected.append({k: item[k] for k in ('source_file', 'source_sha256', 'source_row')} |
                            {'reason': 'duplicate_context_within_source_language'})
    if not retained:
        raise ValueError('No usable input rows remain')
    # NEW protocol: synthetic examples sharing a gold sense, real instances sharing
    # a document ID, and identical sentences across sources stay together. Gold is used for partitioning,
    # never for constructing candidates, selecting retrieval examples or prediction.
    union = UnionFind()
    for item in retained:
        text_key = 'text:' + hashlib.sha256(item['text'].encode()).hexdigest()
        item['group_key'] = text_key
        if item['source'] == 'real':
            if item['row'].get('fileid'):
                union.join(text_key, 'real_document:' + item['row']['fileid'])
        else:
            for sense in item['truth']:
                union.join(text_key, 'synthetic_sense:' + sense)
    partitions = {'evaluation': defaultdict(list), 'support': defaultdict(list)}
    assignment = Counter()
    for item in retained:
        group = union.root(item['group_key'])
        group_hash = hashlib.sha256(f'{seed}:{group}'.encode()).hexdigest()
        role = 'support' if int(group_hash, 16) / 2 ** 256 < support_fraction else 'evaluation'
        assignment[role] += 1
        item['row']['split_group'] = group_hash
        item['row']['source_sha256'] = item['source_sha256']
        item['row']['source_row'] = item['source_row']
        partitions[role][(item['source'], item['language'])].append(item['row'])
    for unit in seen_files:
        if not partitions['evaluation'][unit] or not partitions['support'][unit]:
            raise ValueError(f'No rows in one partition for {unit}; review the explicit grouping protocol/seed')
    # Create outputs only after parsing/filtering/splitting succeeded.
    output_root.mkdir(parents=True)
    for role, folder in [('evaluation', 'data'), ('support', 'support_data')]:
        for (source, language), rows in sorted(partitions[role].items()):
            path = output_root / folder / (f'{language}/sem13_{language}.csv' if source == 'real'
                                          else f'{source}_{language}.csv')
            path.parent.mkdir(parents=True, exist_ok=True)
            fields = list(dict.fromkeys(key for row in rows for key in row))
            with path.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
    inventory_path = output_root / 'resources' / 'babelnet_inventory_cache_healed.json'
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output_root / 'excluded_rows.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['source_file', 'source_sha256', 'source_row', 'reason'])
        writer.writeheader()
        writer.writerows(sorted(rejected, key=lambda x: (x['source_file'], x['source_row'])))
    validation_errors = []
    for source in sorted({s for s, lang in seen_files}):
        languages = sorted(lang for s, lang in seen_files if s == source)
        errors, _ = validate_inputs(output_root / 'data', output_root / 'support_data',
                                    inventory_path, [source], languages, require_english=not allow_missing_english)
        validation_errors.extend(errors)
    manifest = {
        'purpose': 'input_preparation_not_experimental_results',
        'protocol': 'synthetic_sense_real_document_and_identical_sentence_groups_v2',
        'historical_split': False, 'allow_missing_english': allow_missing_english, 'seed': seed, 'support_fraction': support_fraction,
        'inputs': input_files, 'inventory_source_sha256': digest_file(inventory_source),
        'inventory_entries': len(inventory), 'inventory_exclusions': inventory_drops,
        'input_rows': sum(x['rows'] for x in input_files), 'retained_rows': len(retained),
        'excluded_rows': len(rejected), 'exclusion_reasons': dict(Counter(x['reason'] for x in rejected)),
        'partition_rows': dict(assignment),
        'unit_partition_counts': [{'source': s, 'language': lang,
                                  'evaluation': len(partitions['evaluation'][(s, lang)]),
                                  'support': len(partitions['support'][(s, lang)])}
                                 for s, lang in sorted(seen_files)],
        'validation_errors': validation_errors,
    }
    (output_root / 'data_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    if validation_errors:
        raise ValueError('Prepared inputs failed validation; consult local data_manifest.json')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, action='append', required=True)
    parser.add_argument('--inventory-source', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, default=Path('local_data/current'))
    parser.add_argument('--allow-missing-english', action='store_true', help='Permit a source without an English reference pool; explicit monolingual fallback is needed at runtime')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--support-fraction', type=float, default=0.3)
    args = parser.parse_args()
    try:
        manifest = prepare(args.source_dir, args.inventory_source, args.output_root, args.seed, args.support_fraction, args.allow_missing_english)
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps({k: manifest[k] for k in ('purpose', 'protocol', 'input_rows', 'retained_rows',
                                               'excluded_rows', 'partition_rows')}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
