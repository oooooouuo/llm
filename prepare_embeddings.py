"""Prepare public sentence encoders; optionally reuse intact local E5 weights read-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def prepare(local_e5_source=None, output_root=Path('models')):
    os.environ.setdefault('HF_HOME', str(Path('.cache/huggingface').resolve()))
    from huggingface_hub import hf_hub_download, snapshot_download, HfApi
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    metadata = {'purpose': 'encoder_setup_not_experiment_results'}
    e5_id = 'intfloat/multilingual-e5-large'
    sampler_id = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    if local_e5_source:
        source = Path(local_e5_source).resolve()
        target = (root / 'multilingual-e5-large').resolve()
        if target.exists():
            raise ValueError('Encoder output already exists; choose a new directory')
        config = json.loads((source / 'config.json').read_text())
        if config.get('model_type') != 'xlm-roberta' or config.get('hidden_size') != 1024:
            raise ValueError('Local encoder configuration does not match multilingual-e5-large architecture')
        weight = source / 'model.safetensors'
        if not weight.is_file():
            raise ValueError('Local E5 safetensors file is missing')
        target.mkdir(parents=True)
        for name in ['config.json', 'modules.json', 'sentence_bert_config.json', 'tokenizer_config.json',
                     'special_tokens_map.json', 'tokenizer.json', 'sentencepiece.bpe.model']:
            if (source / name).is_file():
                shutil.copyfile(source / name, target / name)
        (target / 'model.safetensors').symlink_to(weight)
        revision = HfApi().model_info(e5_id).sha
        pooling = Path(hf_hub_download(e5_id, '1_Pooling/config.json', revision=revision))
        (target / '1_Pooling').mkdir()
        shutil.copyfile(pooling, target / '1_Pooling/config.json')
        (target / '2_Normalize').mkdir()
        metadata['e5'] = {'mode': 'local_weights_with_public_pooling_metadata',
                          'pooling_revision': revision,
                          'pooling_sha256': hashlib.sha256(pooling.read_bytes()).hexdigest(),
                          'local_weight_bytes': weight.stat().st_size,
                          'note': 'Local weight identity is not proven by architecture validation alone.'}
    else:
        target = Path(snapshot_download(e5_id, allow_patterns=['*.json', '*.model', 'model.safetensors',
                                                               '1_Pooling/*', '2_Normalize/*'],
                                        ignore_patterns=['onnx/*', 'openvino/*']))
        metadata['e5'] = {'mode': 'public_snapshot', 'snapshot': target.name}
    sampler = Path(snapshot_download(sampler_id, allow_patterns=['*.json', '*.model', 'vocab.txt',
                                                                 'model.safetensors', '1_Pooling/*',
                                                                 '2_Normalize/*'],
                                      ignore_patterns=['onnx/*', 'openvino/*']))
    if not (sampler / 'model.safetensors').is_file():
        hf_hub_download(sampler_id, 'pytorch_model.bin', revision=sampler.name)
    metadata['sampler'] = {'snapshot': sampler.name}
    (root / 'encoder_setup.json').write_text(json.dumps(metadata, indent=2))
    # Paths stay local and are not written to a public configuration file.
    settings = {'WSD_E5_MODEL': str(target), 'WSD_SAMPLER_MODEL': str(sampler)}
    (root / 'encoder_paths.local.json').write_text(json.dumps(settings, indent=2))
    print('Encoders prepared. Local paths: ' + str(root / 'encoder_paths.local.json'))
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-e5-source', type=Path)
    parser.add_argument('--output-root', type=Path, default=Path('models'))
    args = parser.parse_args()
    prepare(args.local_e5_source, args.output_root)


if __name__ == '__main__':
    main()
