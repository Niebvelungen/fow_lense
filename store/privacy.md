# Privacy policy for Lens for Force of Will

Last updated: 2026-09-25

Lens for Force of Will is a browser extension that recognises Force of Will trading cards in
YouTube and Twitch videos and shows a high resolution image of the hovered card.

## What the extension processes

- Video frames of the page you are watching are read locally in your browser to find cards.
  Frames never leave your device.
- Card recognition runs entirely on your device with bundled models.
- When you hover a recognised card, the extension loads that card's image from the fowsim card
  image host (`fowsim.s3.amazonaws.com`, an Amazon S3 bucket run by the forceofwind.online
  project, used with its owner's permission). That request contains no information about you
  beyond what any image download carries (your IP address, as seen by that host). No request is
  made until you hover a card.

## What the extension stores

- Whether the overlay is enabled and the model loading status, in the browser's local extension
  storage on your device.

## Permissions and why they are needed

- `storage`: keeps your on/off setting for the overlay and the model loading status on your device.
- `offscreen`: runs the card recognition models in a background document so the video page stays
  responsive.
- Access to `youtube.com` and `twitch.tv`: the extension's script runs on these two sites only, to
  read frames of the video you are watching and draw the overlay on the player. It stays idle until
  you activate the Lens icon on a video.

## What the extension does not do

- It does not collect, transmit, sell or share personal data, browsing history, or video history.
- It does not use analytics, tracking, cookies or remote code.

## Contact

Questions: open an issue on the project's repository (see the homepage link in the store listing)
or write to the support email shown on the store listing.

Changes to this policy will be published at the same address with an updated date.
