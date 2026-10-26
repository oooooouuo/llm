"""Convert authorized WSD XML/gold files for a NEW, explicitly labelled data preparation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from evaluation import gold_ids
from experiment_runner1_v2 import ActualComplexityAnalyzer


def convert(xml_path, gold_path, output, language):
    xml_path, gold_path, output = map(Path, (xml_path, gold_path, output))
    if output.exists() or output.with_suffix('.conversion.json').exists():
        raise ValueError('Refusing to overwrite conversion outputs')
    labels = {}
    for line in gold_path.read_text(encoding='utf-8-sig').splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) < 2 or parts[0] in labels or gold_ids(' '.join(parts[1:])) != set(parts[1:]):
            raise ValueError('Gold keys must contain unique instance IDs and full sense identifiers')
        labels[parts[0]] = ' '.join(parts[1:])
    tree = ET.parse(xml_path)
    rows, omitted = [], []
    analyzer = ActualComplexityAnalyzer()
    for text in tree.getroot().iter('text'):
        for sentence in text.iter('sentence'):
            tokens = list(sentence)
            for target in tokens:
                if target.tag != 'instance':
                    continue
                instance_id = target.get('id')
                if not instance_id or instance_id not in labels:
                    omitted.append(instance_id)
                    continue
                words = []
                for token in tokens:
                    content = ''.join(token.itertext()).strip()
                    words.append(f'<WSD>{content}</WSD>' if token is target else content)
                rendered = ' '.join(words)
                rows.append({'num': instance_id, 'sentence': rendered, 'fileid': text.get('id', ''),
                             'senseid': labels[instance_id],
                             'complexity': analyzer.get_adaptive_strategy(rendered)['level_judged'],
                             'data_type': 'real', 'lemma': target.get('lemma', ''),
                             'language': language, 'difficulty_policy': 'surface_v1_new_preparation'})
    if not rows:
        raise ValueError('No labelled WSD instances found')
    if len({x['num'] for x in rows}) != len(rows):
        raise ValueError('Duplicate instance IDs in XML')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {'purpose': 'input_conversion_not_experiment_results', 'historical_conversion': False,
                'xml_file': xml_path.name, 'xml_sha256': hashlib.sha256(xml_path.read_bytes()).hexdigest(),
                'gold_file': gold_path.name, 'gold_sha256': hashlib.sha256(gold_path.read_bytes()).hexdigest(),
                'rows': len(rows), 'unlabelled_instance_ids': omitted,
                'text_reconstruction': 'space_join_original_XML_token_text',
                'difficulty_policy': 'surface_v1_new_preparation'}
    output.with_suffix('.conversion.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--gold', type=Path, required=True)
    parser.add_argument('--language', choices=['en', 'de', 'fr', 'es', 'it'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = convert(args.xml, args.gold, args.output, args.language)
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(f"Converted {result['rows']} genuine input instances; no model evaluation performed.")


if __name__ == '__main__':
    main()
