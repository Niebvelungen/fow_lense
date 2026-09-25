# fow_lense

Chrome extension that recognises Force of Will (FoW) TCG cards in YouTube and Twitch videos and
shows a high resolution card image on hover. Modelled on the "Lens for Riftbound" extension, whose
unpacked source lives in `ext/src/` (git-ignored, third party, reference only).

## Layout

| Path | What |
|---|---|
| `extension/` | The extension. Load unpacked in Chrome. See `extension/README.md` |
| `extension/data/cards.json` | Packaged catalog: flat list of `{id, name, orientation, imageUrl, image, set, tags}` |
| `extension/models/` | Git-ignored. `card-detector.onnx` (YOLOv8), `embAll2_mnv3s128.onnx` (embedder), `id-index.bin` (generated) |
| `tools/` | Python tooling: DB extraction, JSON builders, index builder, offline test harness |
| `data/cards.json` | Flat card export from the DB (all 8,307 cards, DB ids, abilities, rulings) |
| `data/cards_arena.json` | Same data in the TCG Arena nested format plus `image` and `image_url` |
| `media/cards/` | Git-ignored. 8,173 card JPEGs (480x670), file name = `image` field in the catalog |
| `samples/`, `results/` | Git-ignored. Test videos and offline test output |

## Data provenance

- Card data comes from a Heroku pg_dump of the fowsim (forceofwind.online) Django database.
  `tools/pgdump_extract.py` reads the custom dump format directly, no Postgres needed.
  A restored copy also runs in Docker container `fow-pg` (postgres:15, port 5433, db `fow`).
- Card images are served from `https://fowsim.s3.amazonaws.com/media/cards/<image>.jpg`.
  The file name is not always `<card_id>.jpg`, so always use the catalog's `image` field.
- Card ids: DB marks flip sides with `^`, we use `*` (TCG Arena convention). J-Rulers end in `J`.
  Flip cards share one image, so the index has one entry per image named "Front // Back".

## Recognition pipeline (mirrors the Riftbound design)

content script samples video at 480px -> YOLO card detector (640 letterbox) -> IoU tracker ->
on hover: crop box at 320px -> embed 128x128 (ImageNet mean/std, 256-d unit vector) -> cosine
match against index -> accept at score >= 0.80 and margin >= 0.05 -> overlay + S3 image zoom.

`tools/test_pipeline.py` replicates this chain in Python for offline testing on videos and is the
benchmark for any model change. Findings so far: the stock Riftbound models recognise large clear
cards (stream sidebar previews) reliably but not small blurry table cards; our own embedder trained
with heavy degradation augmentation is the main open work item, detector fine-tuning the second.

## Conventions

- Python runs from `.venv` (`.venv/Scripts/python`), packages: onnxruntime, numpy, pillow,
  opencv-python-headless, yt-dlp. Training deps (torch, ultralytics) go in the same venv when added.
- Set `PYTHONIOENCODING=utf-8` when printing card names on Windows.
- Regenerate, do not hand edit: `extension/data/cards.json`, `data/cards_arena.json`, `id-index.bin`.
- Keep the extension's internal `rift-` CSS/DOM prefixes; only user-facing strings and storage keys (`fow.*`) were renamed.
- Never commit the dump, `data/*.tsv` (contains user password hashes and sessions), `media/`, videos.
