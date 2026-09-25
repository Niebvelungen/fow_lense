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
| Detection | `src/lib/yolo.js` + `models/card-detector.onnx` | YOLOv8, 640px letterbox, one class "card". Still the Riftbound model |
| Tracking | `src/lib/tracker.js` | IoU matching frame to frame |
| Identification | `src/lib/identify.js`, `src/lib/embed-id.js` | On hover: crop box at 320px, embed at 128px, cosine match against `models/id-index.bin`. Accept at score 0.80 with margin 0.05 |
| Overlay | `src/lib/overlay.js`, `src/overlay.css` | Positioned buttons plus hover zoom that loads the S3 image |

Card images are linked from `https://fowsim.s3.amazonaws.com/media/cards/<image>.jpg`; the
extension packages no card art.

## Regenerating data

```
# catalog (data/cards.json) from the fowsim DB export
python ../tools/build_arena_json.py ../data/cards.json ../data/cards_arena.json
# index (models/id-index.bin) from ../media/cards using the embedding model
../.venv/Scripts/python ../tools/build_index.py
# offline test of the whole chain on a video
../.venv/Scripts/python ../tools/test_pipeline.py ../samples/<video>.mp4
```

The index format is the Riftbound layout with magic `FOWIDX01`: 64 byte header, 40 byte
card records, string heap, then float32 embeddings (8 variants per card image). Flip cards that
share one image become one entry named "Front // Back".
