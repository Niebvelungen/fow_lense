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

## Status

- Detection and identification work for large, clear cards such as the sidebar preview in a
  feature match stream.
- Small blurry table cards are detected only partially and identified poorly by the stock models.
  Training a Force of Will specific embedder and fine-tuning the detector are the next steps.

Force of Will is a trademark of Eye Spy Productions. This is an unofficial fan project.
