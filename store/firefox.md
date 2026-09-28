# Firefox Add-ons (AMO) listing

Companion to `listing.md` (Chrome). Build the upload with

```
.venv/Scripts/python tools/export_firefox.py --lint
```

which writes `dist/firefox/` (load via `about:debugging` for testing) and
`dist/lens-for-fow-<version>-firefox.zip` (the file to upload). Fields with CHANGE-ME need a
decision first; they are the same decisions as for the Chrome listing.

## Before the first upload

- The add-on id is `FIREFOX_GECKO_ID` in `tools/config.py` (`lens-for-fow@fow-lense`). AMO
  registers it on the first upload and every later version must carry the same id, so settle it
  before uploading, not after.
- Bump `version` in `extension/manifest.json` for every upload; AMO rejects a version it has seen.
- Test the export in Firefox first: `about:debugging#/runtime/this-firefox` -> Load Temporary
  Add-on -> `dist/firefox/manifest.json`. Check a YouTube watch page and a Twitch stream, the
  popup, and that the model status in the popup goes from "Loading" to ready.

## Submission

1. Sign in at https://addons.mozilla.org/developers/ (free, Firefox account).
2. **Submit a New Add-on** -> **On this site** (listed). Self-distribution ("On your own") is the
   alternative if you only want a signed `.xpi` to hand out; the listing fields below are then
   not needed.
3. Upload `dist/lens-for-fow-<version>-firefox.zip`. Compatibility: **Firefox** only, not
   Firefox for Android (the overlay needs hover and a desktop video player).
4. **Do you need to submit source code?** No. The only minified code is the unmodified ONNX
   Runtime Web library (see notes to reviewers); everything else ships as plain source.
5. Fill in the listing fields below, save, and wait for the automated signing plus the manual
   review (usually days, up to a few weeks for a first listing with WebAssembly).

## Listing fields

**Name**: Lens for Force of Will

**Add-on URL** (slug): lens-for-force-of-will

**Summary** (250 chars max): Show high resolution Force of Will card overlays on YouTube and Twitch.
Hover a card in the video to see it clearly. Recognition runs on your device.

**Description**: same text as the Chrome listing in `listing.md`, "Description".

**Categories**: Games & Entertainment; second choice Photos, Music & Videos.

**Tags**: force of will, tcg, youtube, twitch, card game.

**Support email / Support website**: CHANGE-ME (same as the Chrome listing).

**Homepage**: CHANGE-ME (also `homepage_url` in `extension/manifest.json`).

**License**: CHANGE-ME. AMO requires one for listed add-ons; MIT or MPL-2.0 for our own code
(the bundled ONNX Runtime Web is MIT). Add the matching LICENSE file to the repository.

**Privacy policy**: paste `privacy.md`. AMO shows it on the listing.

**Version notes** (first release): First public release. Detects Force of Will cards in YouTube and
Twitch videos and shows a high resolution image of the hovered card. Everything runs locally.

**Screenshots**: the Chrome screenshots (any size, AMO scales them).

**Icon**: `extension/icons/toolbar128.png` (AMO wants 128x128 or larger, square).

## Data collection (manifest `data_collection_permissions`)

`required: ["none"]`. The extension collects and transmits nothing. The only network requests are
image downloads from the card image host when the user hovers a recognised card. Make sure the
listing's "Data collection" section says the same (AMO fills it from the manifest since 2025-11).

## Notes to reviewers (paste into the "Notes to Reviewer" box)

- The extension recognises trading cards in the video the user is watching. Frames are read from
  the page's `<video>` element into a canvas and processed locally; nothing is uploaded.
- `vendor/ort/` is ONNX Runtime Web 1.21.0, unmodified from the npm package `onnxruntime-web@1.21.0`
  (`dist/ort.wasm.min.mjs`, `dist/ort-wasm-simd-threaded.mjs`, `dist/ort-wasm-simd-threaded.wasm`,
  MIT). It is the reason for the `'wasm-unsafe-eval'` CSP entry. Single threaded, no
  SharedArrayBuffer, no workers.
- `models/*.onnx` and `models/id-index.bin` are data (neural network weights and a table of card
  embeddings), not code. `data/cards.json` is the card catalog.
- The background page (`src/background-firefox.html`) hosts the recognition engine, which Chrome
  runs in an offscreen document. Host permissions cover YouTube and Twitch only, for the content
  script that draws the overlay on the player.
- No remote code, no analytics, no data collection. Card images are loaded from
  `https://fowsim.s3.amazonaws.com/media/cards/` on hover, with the bucket owner's permission.
- To reproduce the package from source: `python tools/export_firefox.py` in the repository
  (CHANGE-ME link); it copies `extension/` and rewrites the manifest for Firefox.

## Updates

Bump the manifest version, rerun the export, upload the new zip under **Upload New Version**.
Listed updates are signed automatically and reviewed afterwards. If a version needs a new host
permission Firefox does not prompt existing users (it stays ungranted until they enable it in the
add-on's Permissions tab), so avoid adding hosts in updates.
