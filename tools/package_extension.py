r"""Package extension/ into a Chrome Web Store upload zip: dist/lens-for-fow-<version>.zip.

Checks the manifest parses, required files exist, no third-party leftovers, and reports the size.
usage: .venv/Scripts/python tools/package_extension.py
"""
import json, os, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, 'extension')
EXCLUDE_FILES = {'README.md', '.DS_Store', 'Thumbs.db'}
REQUIRED = ['manifest.json', 'models/card-detector.onnx', 'models/embedder.onnx', 'models/id-index.bin',
            'data/cards.json', 'vendor/ort/ort-wasm-simd-threaded.wasm', 'icons/toolbar128.png']


def main():
    manifest = json.load(open(os.path.join(EXT, 'manifest.json'), encoding='utf-8'))
    for k in ('name', 'version', 'description', 'icons', 'manifest_version'):
        assert k in manifest, f'manifest missing {k}'
    assert len(manifest['description']) <= 132, 'description over 132 characters'
    for r in REQUIRED:
        assert os.path.exists(os.path.join(EXT, r)), f'missing {r}'
    leftovers = []
    for root, _, files in os.walk(EXT):
        for f in files:
            if f.endswith(('.js', '.html', '.json', '.css')):
                text = open(os.path.join(root, f), encoding='utf-8', errors='ignore').read()
                if 'Riftbound' in text or 'riftcodex' in text or 'riftscribe' in text:
                    leftovers.append(os.path.relpath(os.path.join(root, f), EXT))
    assert not leftovers, f'Riftbound references left in {leftovers}'

    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    out = os.path.join(ROOT, 'dist', f"lens-for-fow-{manifest['version']}.zip")
    n = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(EXT):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in sorted(files):
                if f in EXCLUDE_FILES:
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, EXT).replace(os.sep, '/'))
                n += 1
    print(f"{out}: {n} files, {os.path.getsize(out) / 1e6:.1f} MB (version {manifest['version']})")


if __name__ == '__main__':
    main()
