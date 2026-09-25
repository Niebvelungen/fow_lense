# Chrome Web Store listing

Copy from here into the developer dashboard. Fields with CHANGE-ME need a decision first.

## Store listing

**Name** (45 chars max): Lens for Force of Will

**Summary** (132 chars max, same as manifest description):
Show high resolution Force of Will card overlays on YouTube and Twitch.

**Category**: Entertainment (alternative: Tools)

**Language**: English

**Description**:

See every Force of Will card clearly while you watch. Lens for Force of Will spots the cards in a
YouTube video or Twitch stream and shows a high resolution image of any card you hover, with its
name, so you can follow a feature match without pausing or squinting.

Works on any video or livestream. It is most accurate on tabletop feature matches and online client
streams where the cards are reasonably visible; tiny or badly blurred cards are left unmarked rather
than guessed.

To use it, hover a YouTube or Twitch video and click the Lens icon in its top-right corner, then
move your mouse over a card. It only runs on videos where you turn it on. To hide the icon on all
videos, disable the extension from its toolbar popup.

Everything runs in your browser. Card recognition uses small on-device models; nothing about you or
what you watch is sent anywhere. The only network requests are for the card images themselves.

Lens for Force of Will is a free, unofficial fan project and is not affiliated with or endorsed by
Eye Spy Productions or Force of Will Co., Ltd. Force of Will and all card images belong to their
respective owners.

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
