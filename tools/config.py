"""Settings shared by the data/index build tools. Change here, then rebuild:
  python tools/build_catalog.py                                            (rewrites extension/data/cards.json)
  .venv/Scripts/python tools/build_index.py                                (rewrites extension/models/id-index.bin)
  .venv/Scripts/python tools/package_extension.py
"""
# GitHub user/org that hosts the public "fow-card-images" repo (see F:/R/fow-card-images/README.md).
GITHUB_USER = "CHANGE-ME"

# Where card images are served from. The extension loads <IMAGE_BASE_URL><image file name> on hover.
# jsDelivr serves any public GitHub repo for free; use a tag (@v1) instead of @main once released so
# links are immutable and cached for good.
IMAGE_BASE_URL = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/fow-card-images@main/cards/"

# Tried by the extension when the primary host fails to load an image.
IMAGE_FALLBACK_BASE_URL = "https://fowsim.s3.amazonaws.com/media/cards/"
