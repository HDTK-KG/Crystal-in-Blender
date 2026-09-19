"""Build the installable ZIP and example inputs using standard Python."""
from pathlib import Path
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crystal_builder.presets import PRESETS


def main():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    target = output / 'crystal_builder-1.2.1.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / 'crystal_builder').glob('*.py')):
            archive.write(path, f'crystal_builder/{path.name}')
        for name in ('space_group.csv', 'Wyckoff.csv'):
            archive.write(ROOT / 'Database_of_crystal_symmetry' / name, f'crystal_builder/data/{name}')
        archive.write(ROOT / 'DATA_NOTICE.md', 'crystal_builder/data/DATA_NOTICE.md')
    examples = ROOT / 'examples'
    examples.mkdir(exist_ok=True)
    for name, config in PRESETS.items():
        (examples / f'{name.lower()}.json').write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
