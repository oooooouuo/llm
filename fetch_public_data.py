"""Download the linked public multilingual WSD package and convert SemEval-2013 inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen
from convert_wsd import convert

PUBLIC_URL = 'https://drive.google.com/uc?export=download&id=19Q1bg2LoMlEN3zK7gn8MuD0DAgL5cwbn'
SOURCE_README = 'https://github.com/SapienzaNLP/mwsd-datasets'


def fetch(output_root):
    root = Path(output_root)
    if root.exists():
        raise ValueError('Refusing to overwrite a previous public-data download')
    with urlopen(PUBLIC_URL, timeout=60) as response:
        content = response.read(50_000_001)
    if len(content) > 50_000_000 or not content.startswith(b'\x1f\x8b'):
        raise ValueError('Public download did not return the expected gzip archive; no inputs created')
    root.mkdir(parents=True)
    archive_path = root / 'multilingual_wsd_all_v1.0.tar.gz'
    archive_path.write_bytes(content)
    conversions = {}
    with tarfile.open(archive_path) as archive:
        for language in ['de', 'es', 'fr', 'it']:
            folder = root / 'raw' / f'semeval2013-{language}'
            folder.mkdir(parents=True)
            for suffix in ['data.xml', 'gold.key.txt']:
                name = f'multilingual_wsd_all_v1.0/semeval2013-{language}/semeval2013-{language}.{suffix}'
                member = archive.getmember(name)
                if not member.isfile() or member.size > 10_000_000:
                    raise ValueError('Unexpected archive member')
                (folder / f'semeval2013-{language}.{suffix}').write_bytes(archive.extractfile(member).read())
            conversions[language] = convert(folder / f'semeval2013-{language}.data.xml',
                                              folder / f'semeval2013-{language}.gold.key.txt',
                                              root / 'converted' / language / f'sem13_{language}.csv', language)['rows']
        license_member = archive.getmember('multilingual_wsd_all_v1.0/LICENSE')
        if license_member.isfile():
            (root / 'UPSTREAM_LICENSE').write_bytes(archive.extractfile(license_member).read())
    manifest = {'purpose': 'public_input_acquisition_not_experimental_results',
                'source_readme': SOURCE_README, 'archive_url': PUBLIC_URL,
                'archive_sha256': hashlib.sha256(content).hexdigest(),
                'dataset': 'SemEval-2013 multilingual ALL split mapped to BabelNet 4.0',
                'converted_rows_by_language': conversions, 'historical_project_inputs': False,
                'english_included': False}
    (root / 'download_manifest.json').write_text(json.dumps(manifest, indent=2))
    print('Downloaded/converted public inputs. English is not part of this archive.')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=Path('local_data/upstream'))
    args = parser.parse_args()
    try:
        fetch(args.output_root)
    except (ValueError, OSError, tarfile.TarError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
