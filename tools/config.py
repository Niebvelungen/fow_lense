"""Settings shared by the data/index build tools. Change here, then rebuild:
  python tools/build_catalog.py                                            (rewrites extension/data/cards.json)
  .venv/Scripts/python tools/build_index.py                                (rewrites extension/models/id-index.bin)
"""
# Where card images are served from. The extension loads <IMAGE_BASE_URL><image file name> on hover.
# Currently the fowsim (forceofwind.online) bucket; point this at your own host before publishing.
IMAGE_BASE_URL = "https://fowsim.s3.amazonaws.com/media/cards/"
