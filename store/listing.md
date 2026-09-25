# Chrome Web Store listing

Copy from here into the developer dashboard. Fields with CHANGE-ME need a decision first.

## Store listing

**Name** (45 chars max): Lens for Force of Will

**Summary** (132 chars max, same as manifest description):
Hover cards in Force of Will YouTube and Twitch videos to see them in high resolution. Unofficial fan project.

**Category**: Entertainment (alternative: Tools)

**Language**: English

**Description**:

Lens for Force of Will finds the cards in a Force of Will TCG video and shows you the card in high
resolution when you hover it, so you can follow feature matches and online client streams without
pausing to squint.

How it works
- Open a Force of Will video on YouTube or a stream on Twitch.
- Hover the video and click the lens icon in the top right corner of the player.
- Move the mouse over any card on the table. A zoomed card image appears next to it with the card
  name and the closest alternatives.

Everything runs locally in your browser. Detection and recognition use small on-device models
(ONNX Runtime WebAssembly). Nothing about you or what you watch is sent anywhere. The only network
requests are for the card images themselves when a zoom is shown.

Limits
- Recognition works on cards that are reasonably legible in the video. Very small or badly blurred
  table cards are left unlabelled rather than guessed.
- Only YouTube watch pages and Twitch streams are supported.

Lens for Force of Will is an unofficial fan project and is not affiliated with or endorsed by
Eye Spy Productions or Force of Will Co., Ltd. Force of Will and all card images are the property
of their respective owners.

**Screenshots** (1280x800 or 640x400 PNG/JPEG, 1 to 5): take them from a feature match with the
overlay active and a zoom open. Blur other people's faces if a webcam is in frame.

**Small promo tile** (440x280, optional but recommended): the icon on a dark background with the
name.

**Homepage URL**: CHANGE-ME (the GitHub repo; also set `homepage_url` in manifest.json)

**Support URL**: CHANGE-ME (GitHub issues)

## Privacy tab

**Single purpose**: Identify Force of Will trading cards shown in YouTube and Twitch videos and
display a high resolution image of the hovered card.

**Permission justifications**
- `storage`: remembers whether the overlay is enabled and the model loading status.
- `offscreen`: runs the card detection and recognition models (WebAssembly) in an offscreen
  document so the video page stays responsive.
- Host permissions `youtube.com`, `twitch.tv` (content scripts): read the video frames of the
  page the user is watching to find cards and draw the overlay on the player.

**Remote code**: No. All scripts and WebAssembly ship inside the package. The ONNX model files are
data, not code.

**Data usage**: the extension does not collect, transmit or sell any user data. Declare "does not
collect user data" for every category. Card images are fetched from the image host declared in
`tools/config.py` when a zoom is shown; no identifying information is attached.

**Privacy policy URL**: optional when no data is collected, but the dashboard nags without one.
Host `store/privacy.md` on the repo (GitHub Pages or the raw file) and paste the link.

## Before uploading (checklist)

1. Image host: the fowsim S3 bucket in `tools/config.py`, used with the owner's permission. Nothing to
   change unless the host moves (then `python tools/build_catalog.py` and `.venv/Scripts/python tools/build_index.py`).
2. `extension/manifest.json`: `homepage_url`, and bump `version` for every upload (the store
   rejects re-uploads of the same version).
3. `extension/icons/`: currently the Force of Will logo (`store/assets/fow-favicon-192.png`, installed with
   `tools/make_icons.py --source ...`). Using the trademark owner's mark raises the odds of an
   impersonation flag or complaint; `tools/make_icons.py` without arguments restores generic icons.
4. `.venv/Scripts/python tools/package_extension.py` -> `dist/lens-for-fow-<version>.zip`
   (about 42 MB; the store limit is far above that).
5. Test the zip: `chrome://extensions` -> Load unpacked from an unzipped copy, or drag the zip
   onto the page, and run through one YouTube and one Twitch video.

## Publishing steps

1. Register at https://chrome.google.com/webstore/devconsole (one-time 5 USD fee, Google account).
   Verify the contact email in Account settings; the store requires it before publishing.
2. New item -> upload the zip.
3. Fill Store listing (text above, screenshots, icon is taken from the manifest).
4. Fill Privacy (single purpose, permission justifications, data usage, remote code = no).
5. Distribution: Public, all regions, free.
6. Submit for review. First reviews of extensions with host permissions take a few days; later
   updates are usually faster. Choose "publish automatically after review" or publish by hand.

## Name and trademark note

"Force of Will" is a registered trademark. The store allows descriptive use ("Lens for Force of
Will") when the listing clearly states the extension is unofficial, which the description does.
If a trademark complaint ever arrives the safe fallback is "FoW Lens" (already the manifest
`short_name`).
