# Lens for Force of Will

Chrome extension that detects Force of Will cards in YouTube and Twitch videos and shows a
high resolution card image on hover. Derived from the "Lens for Riftbound" extension
(unpacked source in `../ext/src`), with the catalog, index and branding swapped.

## Load for development

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** and pick this `extension/` folder.
3. Open a YouTube watch page or Twitch stream, hover the video and click the icon in the top right corner of the player.

## How it works

| Stage | File | Notes |
|---|---|---|
| Frame sampling | `src/content.js` | 480px wide canvas grab every 500ms while the pointer is over the player |
| Detection | `src/lib/yolo.js` + `models/card-detector.onnx` | YOLOv8n, 640px letterbox, one class "card", fine-tuned on synthetic FoW scenes (`tools/train_detector.py`) |
| Tracking | `src/lib/tracker.js` | IoU matching frame to frame |
| Identification | `src/lib/identify.js`, `src/lib/embed-id.js` | On hover: crop box at 320px, embed at 128px with `models/embedder.onnx` (MobileNetV3-small trained on FoW cards, `tools/train_embedder.py`), cosine match against `models/id-index.bin`. Accept at score 0.70 with margin 0.05 |
| Overlay | `src/lib/overlay.js`, `src/overlay.css` | Positioned buttons plus hover zoom that loads the S3 image |

Card images are linked from `https://fowsim.s3.amazonaws.com/media/cards/<image>.jpg`; the
extension packages no card art.

## Regenerating data

```
# catalog (data/cards.json); image host is IMAGE_BASE_URL in ../tools/config.py
python ../tools/build_catalog.py
# index (models/id-index.bin) from ../media/cards using models/embedder.onnx (3 views per card)
../.venv/Scripts/python ../tools/build_index.py
# retrain the models (GPU): see the docstrings of tools/train_embedder.py and tools/train_detector.py
# offline test of the whole chain on a video
../.venv/Scripts/python ../tools/test_pipeline.py ../samples/<video>.mp4
```

The index format is the Riftbound layout with magic `FOWIDX01`: 64 byte header, 40 byte
card records, string heap, then float32 embeddings (3 views per card image: full card, art band, grayscale). Flip cards that
share one image become one entry named "Front // Back".
