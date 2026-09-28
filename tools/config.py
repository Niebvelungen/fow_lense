"""Settings shared by the data/index build tools. Change here, then rebuild:
  python tools/build_catalog.py                                            (rewrites extension/data/cards.json)
  .venv/Scripts/python tools/build_index.py                                (rewrites extension/models/id-index.bin)
"""
# Where card images are served from. The extension loads <IMAGE_BASE_URL><image file name> on hover.
# Currently the fowsim (forceofwind.online) bucket; point this at your own host before publishing.
IMAGE_BASE_URL = "https://fowsim.s3.amazonaws.com/media/cards/"

# Firefox add-on identity (tools/export_firefox.py). The id is registered with addons.mozilla.org
# on the first upload and must never change afterwards; email-like form, the domain need not exist.
FIREFOX_GECKO_ID = "lens-for-fow@fow-lense"
# Firefox 128 ESR: MV3 event pages, wasm-unsafe-eval CSP, host permissions shown at install (127+).
FIREFOX_MIN_VERSION = "128.0"
