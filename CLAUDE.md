# fow_lense

Chrome extension that recognises Force of Will (FoW) TCG cards in YouTube and Twitch videos and
shows a high resolution card image on hover. Modelled on the "Lens for Riftbound" extension, whose
unpacked source lives in `ext/src/` (git-ignored, third party, reference only).

## Layout

| Path | What |
|---|---|
| `extension/` | The extension. Load unpacked in Chrome. See `extension/README.md` |
| `extension/data/cards.json` | Packaged catalog: flat list of `{id, name, orientation, imageUrl, image, set, tags}` |
| `extension/models/` | Git-ignored. `card-detector.onnx` (YOLOv8n, ours), `embedder.onnx` (MobileNetV3-small, ours), `id-index.bin` (generated, 3 views per card) |
| `runs/` | Git-ignored. Training outputs: `runs/embedder/{best.pt,embedder.onnx,log.jsonl}`, `runs/detector*/` |
| `datasets/cards/` | Git-ignored. Synthetic YOLO dataset from `tools/make_det_dataset.py` |
| `tools/` | Python tooling: DB extraction, JSON builders, index builder, offline test harness |
| `data/cards.json` | Flat card export from the DB (all 8,307 cards, DB ids, abilities, rulings) |
| `data/cards_arena.json` | Same data in the TCG Arena nested format plus `image` and `image_url` |
| `media/cards/` | Git-ignored. 8,173 card JPEGs (480x670), file name = `image` field in the catalog |
| `samples/`, `results/` | Git-ignored. Test videos and offline test output |

## Data provenance

- Card data comes from a Heroku pg_dump of the fowsim (forceofwind.online) Django database.
  `tools/pgdump_extract.py` reads the custom dump format directly, no Postgres needed.
  A restored copy also runs in Docker container `fow-pg` (postgres:15, port 5433, db `fow`).
- Card images: originals from `https://fowsim.s3.amazonaws.com/media/cards/<image>.jpg`; for release they
  are served free via jsDelivr from the public GitHub repo `fow-card-images` (local copy F:/R/fow-card-images,
  same file names). `tools/config.py` holds the base URL; the extension falls back to fowsim on error.
  The file name is not always `<card_id>.jpg`, so always use the catalog's `image` field.
- Card ids: DB marks flip sides with `^`, we use `*` (TCG Arena convention). J-Rulers end in `J`.
  Flip cards share one image, so the index has one entry per image named "Front // Back".

## Recognition pipeline (mirrors the Riftbound design)

content script samples video at 480px -> YOLO card detector (640 letterbox) -> IoU tracker ->
on hover: crop box at 320px -> embed 128x128 (ImageNet mean/std, 256-d unit vector) -> cosine
match against index -> accept at score >= 0.70 and margin >= 0.05 -> overlay + S3 image zoom.

`tools/test_pipeline.py` replicates this chain in Python for offline testing on videos and is the
benchmark for any model change (`--det-model`, `--emb-model`, `--index` to test candidates before
installing them). `tools/contact_sheet.py` shows crops next to their top matches for eyeballing.

Model history:
- Stock Riftbound embedder: fine on large clear cards, near random on small blurry table cards.
- Our embedder (`tools/train_embedder.py`, MobileNetV3-small + CosFace over 7,895 card images,
  stream-condition augmentation from `tools/card_aug.py`): 96.7% top-1 on hard synthetic queries,
  true match median 0.81 vs best wrong median 0.44. Rebuilding the index with 2 views per card
  gives the same video results as 8 views, so the index is 17 MB instead of 66 MB.
- Detector (`tools/train_detector.py`, YOLOv8n on `tools/make_det_dataset.py` scenes): finds more
  small and rested table cards than the stock model. It tends to skip the large sidebar preview
  card that stream overlays show; that is acceptable, the target is gameplay on the table, not UI.

- Installed embedder = runs/embedder3 (v1 fine-tuned 15 epochs with dice/counter/finger occluders and
  tilt up to 30 degrees, after the user reported dice and tilted cards failing). On the table video:
  18 vs 12 crops above 0.7, 10 vs 8 accepted; webcam video about even. runs/embedder is the previous
  model for rollback (`cp runs/embedder/embedder.onnx extension/models/ && rebuild index`).
- First real evaluation (916 labelled crops, 801 legible, 69 distinct cards, 2025-09-25):
  occluder embedder v3: top-1 71.4%, top-5 82.5%, plain 83.7%, rotated 70.3%, dice 33.3%.
  Threshold sweep showed 0.70 gives 230 correct / 1 wrong shown vs 118 / 0 at 0.80 -> EMBED_ACCEPT is 0.70.
- Labels in training (runs/embedder4, feature-match labels only, webcam held out): held-out top-1
  82.5% -> 86.9%, top-5 87.3% -> 96.4%, still 0 wrong shown. Installed model = runs/embedder5, same
  recipe with all labels. Label caveats: tags on the first 280 labelled crops are missing (eval ignores
  them), "rested" was merged into "rotated" (direction is ambiguous across camera setups).
- Monochrome chase prints: users see grayscale variants that our images do not have. Handled with a
  grayscale index view (3 views per card now, 25 MB index) and grayscale augmentation. Set numbers
  visible at the card bottom could be an OCR fallback later; unreadable at 720p for now.
- Experiments that did NOT help on the feature-match camera feed (keep for reference, do not repeat):
  haze/contrast-loss fine-tune of the embedder (runs/embedder2, same video scores), 1080p instead of
  720p source (identical scores: the table camera is soft, not the encode), query-time per-channel
  contrast stretch (+0.03 median). What did help: sampling the video at 640 px instead of 480 for
  the detector (+13% table boxes, free since the model input is 640 anyway).
- Honest picture on the two test streams: table cards that are legible to a human are identified
  correctly and consistently across frames (e.g. AVL-097 in 9 of 14 frames); the rest score
  0.45-0.6 and are rejected. Next lever would be real labelled crops from streams, not more synthetic
  augmentation.

Training notes: Windows page file is small, so keep DataLoader workers modest (6 for the embedder,
4 for YOLO) and never run both trainings at once. The trainer keeps a memmap cache of all card
images in `runs/cards_208x290.npy`.

## Labelled crops (the real-data loop)

- `tools/test_pipeline.py ... --out results/label_<video>` dumps every detected crop; the dense sets
  for the two test videos are `results/label_yt_user_720p` (630) and `results/label_yt_gp_top4_720p` (227).
- `tools/label_server.py results/label_* ` serves a local page (http://localhost:8765): keys 1-5 pick a
  top-5 guess, u unknown, n not a card, d/r/t tag dice/rotated/rested, / searches any card.
  Labels append to `data/labels/crops.jsonl` (committed; the crop images stay local).
- `tools/eval_labels.py` scores any embedder+index on the labels: top-1/top-5, per-tag accuracy and a
  threshold sweep (correct shown vs wrong shown). Use it for every model or threshold change.
- `tools/train_embedder.py --real-labels data/labels/crops.jsonl` mixes labelled crops into training
  (15% of views by default). Keep a held-out video out of training for honest evaluation.

## Product direction

- Recognise cards in play on the table (physical camera feeds and online clients). Stream UI such
  as the sidebar card preview is not a target; it is already readable.
- Prefer an unlabelled box over a wrong label: acceptance thresholds stay strict.

## Conventions

- Python runs from `.venv` (`.venv/Scripts/python`), packages: onnxruntime, numpy, pillow,
  opencv-python-headless, yt-dlp. Training deps (torch, ultralytics) go in the same venv when added.
- Set `PYTHONIOENCODING=utf-8` when printing card names on Windows.
- Regenerate, do not hand edit: `extension/data/cards.json`, `data/cards_arena.json`, `id-index.bin`.
- Keep the extension's internal `rift-` CSS/DOM prefixes; only user-facing strings and storage keys (`fow.*`) were renamed.
- Never commit the dump, `data/*.tsv` (contains user password hashes and sessions), `media/`, videos.
