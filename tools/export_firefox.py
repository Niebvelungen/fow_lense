r"""Export extension/ as a Firefox add-on.

Writes dist/firefox/ (an unpacked add-on: about:debugging -> This Firefox -> Load Temporary
Add-on -> pick its manifest.json) and dist/lens-for-fow-<version>-firefox.zip (upload as is to
https://addons.mozilla.org/developers/; an .xpi is the same zip once AMO has signed it).

What differs from the Chrome package (everything else is copied unchanged):
  - manifest: no `offscreen` permission and no `minimum_chrome_version`; `background` is the page
    src/background-firefox.html instead of a service worker; `host_permissions` repeats the content
    script matches so Firefox 127+ asks for them at install; `browser_specific_settings.gecko`
    carries the add-on id, the minimum Firefox version and the (empty) data collection declaration
    that AMO requires for new submissions.
  - src/background.js and src/engine-host.html (Chrome's service worker and offscreen document)
    are left out. The engine runs in the background page, see src/background-firefox.js.

usage: .venv/Scripts/python tools/export_firefox.py [--lint] [--no-zip]
  --lint    run `web-ext lint` on the export if npx is available (npm i -g web-ext)
  --no-zip  only write dist/firefox/
"""
import fnmatch, json, os, shutil, subprocess, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FIREFOX_GECKO_ID, FIREFOX_MIN_VERSION  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, 'extension')
OUT_DIR = os.path.join(ROOT, 'dist', 'firefox')
BACKGROUND_PAGE = 'src/background-firefox.html'
EXCLUDE_FILES = {'README.md', '.DS_Store', 'Thumbs.db'}
# Chrome-only files: the service worker and the offscreen document (engine-host.js stays, the
# Firefox background page imports it).
EXCLUDE_PATHS = {'src/background.js', 'src/engine-host.html'}
REQUIRED = ['manifest.json', BACKGROUND_PAGE, 'src/background-firefox.js', 'src/engine-host.js',
            'models/card-detector.onnx', 'models/embedder.onnx', 'models/id-index.bin',
            'data/cards.json', 'vendor/ort/ort-wasm-simd-threaded.wasm', 'icons/toolbar128.png']


def firefox_manifest(chrome):
    m = json.loads(json.dumps(chrome))  # deep copy
    m.pop('minimum_chrome_version', None)
    m['permissions'] = [p for p in m.get('permissions', []) if p != 'offscreen']
    matches = []
    for cs in m.get('content_scripts', []):
        for pattern in cs.get('matches', []):
            if pattern not in matches:
                matches.append(pattern)
    m['host_permissions'] = matches
    m['background'] = {'page': BACKGROUND_PAGE}
    m['browser_specific_settings'] = {
        'gecko': {
            'id': FIREFOX_GECKO_ID,
            'strict_min_version': FIREFOX_MIN_VERSION,
            # Nothing is collected or transmitted; AMO requires the declaration since 2025-11-03.
            'data_collection_permissions': {'required': ['none']},
        }
    }
    # Keep the key order readable: browser_specific_settings right after the version.
    ordered = {}
    for k, v in m.items():
        if k == 'browser_specific_settings':
            continue
        ordered[k] = v
        if k == 'version':
            ordered['browser_specific_settings'] = m['browser_specific_settings']
    return ordered


def copy_tree():
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    n = 0
    for root, dirs, files in os.walk(EXT):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, EXT).replace(os.sep, '/')
            if f in EXCLUDE_FILES or rel in EXCLUDE_PATHS or rel == 'manifest.json':
                continue
            dst = os.path.join(OUT_DIR, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    return n


def exported_files():
    for root, _, files in os.walk(OUT_DIR):
        for f in files:
            yield os.path.relpath(os.path.join(root, f), OUT_DIR).replace(os.sep, '/')


def check(m):
    problems = []

    def exists(rel):
        return os.path.exists(os.path.join(OUT_DIR, rel))

    for r in REQUIRED:
        if not exists(r):
            problems.append(f'missing {r}')
    if len(m['description']) > 132:
        problems.append('description over 132 characters')
    if 'offscreen' in m.get('permissions', []):
        problems.append('offscreen permission left in manifest')
    if 'service_worker' in m.get('background', {}):
        problems.append('service worker background left in manifest (Firefox does not run it)')
    gecko = m.get('browser_specific_settings', {}).get('gecko', {})
    if '@' not in gecko.get('id', ''):
        problems.append('gecko id must look like an email address')
    if not gecko.get('data_collection_permissions', {}).get('required'):
        problems.append('data_collection_permissions.required missing')
    # every file the manifest points at must be in the export
    refs = [m['background']['page'], m['action']['default_popup']]
    refs += list(m['icons'].values()) + list(m['action'].get('default_icon', {}).values())
    for cs in m['content_scripts']:
        refs += cs.get('js', []) + cs.get('css', [])
    for r in refs:
        if not exists(r):
            problems.append(f'manifest references missing file {r}')
    files = list(exported_files())
    for war in m.get('web_accessible_resources', []):
        for pattern in war['resources']:
            if not any(fnmatch.fnmatch(f, pattern) for f in files):
                problems.append(f'web_accessible_resources pattern matches nothing: {pattern}')
    # nothing in the export may call Chrome-only APIs or mention the reference extension
    for f in files:
        if not f.endswith(('.js', '.html', '.json', '.css')) or f.startswith('vendor/'):
            continue
        text = open(os.path.join(OUT_DIR, f), encoding='utf-8', errors='ignore').read()
        if 'chrome.offscreen' in text or 'getContexts' in text:
            problems.append(f'Chrome-only API used in {f}')
        if 'Riftbound' in text or 'riftcodex' in text or 'riftscribe' in text:
            problems.append(f'Riftbound references left in {f}')
    return problems


def lint():
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if not npx:
        print('lint skipped: npx not found (install Node, then `npm i -g web-ext` and rerun with --lint)')
        return 0
    cmd = [npx, '--yes', 'web-ext', 'lint', '--source-dir', OUT_DIR]
    print('$', ' '.join(cmd))
    return subprocess.call(cmd)


def main(argv):
    chrome = json.load(open(os.path.join(EXT, 'manifest.json'), encoding='utf-8'))
    m = firefox_manifest(chrome)
    n = copy_tree()
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(m, f, indent=2)
        f.write('\n')
    problems = check(m)
    if problems:
        print('export FAILED:\n  ' + '\n  '.join(problems))
        return 1
    gecko_id = m['browser_specific_settings']['gecko']['id']
    print(f"{OUT_DIR}: {n + 1} files (version {m['version']}, id {gecko_id})")
    if '--no-zip' not in argv:
        out = os.path.join(ROOT, 'dist', f"lens-for-fow-{m['version']}-firefox.zip")
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for rel in sorted(exported_files()):
                z.write(os.path.join(OUT_DIR, rel), rel)
        print(f'{out}: {os.path.getsize(out) / 1e6:.1f} MB')
    if '--lint' in argv:
        return lint()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
