# Lens for Force of Will

A Chrome extension that spots Force of Will cards in YouTube and Twitch videos and shows the card
in high resolution when you hover it. Point it at a feature match or an online client stream and
read the cards without pausing.

The design follows the "Lens for Riftbound" extension: a small YOLO detector finds card rectangles
in the video, an embedding model turns each crop into a vector, and the vector is matched against
an index built from every Force of Will card image. Everything runs locally in the browser with
ONNX Runtime WebAssembly; card art is loaded from the fowsim S3 bucket on demand.

## Try it

1. Build the index once (needs the card images in `media/cards/`, see below):
   ```
   python -m venv .venv
   .venv/Scripts/pip install onnxruntime numpy pillow opencv-python-headless yt-dlp
   .venv/Scripts/python tools/build_index.py
   ```
2. Open `chrome://extensions`, enable Developer mode, **Load unpacked**, choose `extension/`.
3. Open a Force of Will video on YouTube, hover the player, click the icon in the top right.

## Repository map

| Path | What |
|---|---|
| `extension/` | The extension itself ([details](extension/README.md)) |
| `tools/` | Python tooling: database extraction, catalog and index builders, offline test harness |
| `data/cards.json` | All 8,307 cards with abilities, rulings and image file names |
| `data/cards_arena.json` | Same data in the TCG Arena nested format |

## Card data and images

Card text comes from a database export of fowsim (forceofwind.online). `tools/pgdump_extract.py`
reads a PostgreSQL custom-format dump without a Postgres install, `tools/build_cards_json.py` joins
the tables, and `tools/build_arena_json.py` produces the nested catalog.

Images are not in the repository. Each catalog entry has an `image` file name and an `image_url`
on `https://fowsim.s3.amazonaws.com/media/cards/`. Put the files in `media/cards/` to build the
index.

## Testing on a video

```
.venv/Scripts/yt-dlp -f "bv*[height<=720][ext=mp4]" -o "samples/%(title)s.%(ext)s" <youtube url>
.venv/Scripts/python tools/test_pipeline.py samples/<video>.mp4 --start 120 --every 60
.venv/Scripts/python tools/contact_sheet.py results/<video> <second>
```

The harness writes annotated frames, per-box crops and a `summary.json` to `results/<video>/`.
The contact sheet puts each crop next to its top three matches so you can judge them by eye.

## Labelling real crops

The models improve most from crops taken from real streams. Dump crops with the harness, then label
them in a local page (one keypress per crop, since the correct card is usually among the top five
guesses shown next to it):

```
.venv/Scripts/python tools/test_pipeline.py samples/<video>.mp4 --every 30 --max-frames 70 --out results/label_<video>
.venv/Scripts/python tools/label_server.py results/label_<video>      # opens http://localhost:8765
.venv/Scripts/python tools/eval_labels.py                              # accuracy and threshold sweep on the labels
```

## Training your own models

Both models ship as ONNX and were trained here with the scripts in `tools/` (needs a CUDA GPU;
`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 ultralytics onnx onnxscript`):

```
.venv/Scripts/python tools/train_embedder.py --epochs 40          # -> runs/embedder/embedder.onnx
.venv/Scripts/python tools/make_det_dataset.py --n 3000           # -> datasets/cards
.venv/Scripts/python tools/train_detector.py --epochs 40          # -> runs/detector/card-detector.onnx
```

## Status

- The embedder is trained on all Force of Will card images with stream-style degradation and
  identifies large and medium cards reliably; the index holds two views per card (full card and
  art band, so full-art prints still match on their illustration).
- The detector is fine-tuned on synthetic table scenes plus pseudo-labelled real frames and finds
  most table cards, including rested ones. Stream UI such as the sidebar card preview is not a
  target.
- Very small blurry table cards (under about 60 px wide in a 720p stream) remain hard and are
  left unlabelled rather than mislabelled.

Force of Will is a trademark of Eye Spy Productions. This is an unofficial fan project.
