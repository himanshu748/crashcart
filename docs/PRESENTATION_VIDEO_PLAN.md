# Evidence-first video candidate — local preparation

The current Public video is <https://www.youtube.com/watch?v=3MIzDpFmRl0>.
It remains unchanged. No new upload, public save, payment, model call or
narration request is part of this preparation.

## Smallest useful cut

Use the existing 165-second file and original Deepgram Aura-2 Thalia narration.
Replace only the first 20 seconds of picture with a real browser capture of the
new saved PayPal evidence panel. Retain the original burned-in captions in that
opening, the original audio packets, and all footage from 0:20 onward.

The evidence panel must identify these as **saved 8 November 2026 Sandbox
records**. It shows a completed USD 29.00 capture nested in an independently saved
Orders v2 **GET** response after the store lost the capture reply. The POST
capture route is displayed separately as the adapter route for this order.
This is not footage of a fresh approval or a preserved POST 201 response.

| Time | Picture | Existing narration / purpose |
| --- | --- | --- |
| 0:00–0:10 | Actual saved-evidence panel | “I paid, but my ticket never arrived.” |
| 0:10–0:20 | Hold readable evidence | Support needs to know what happened and what to do next. |
| 0:20–1:40 | Existing investigation flow | Same order; payment, ticket read, cited finding. |
| 1:40–2:10 | Existing separate repair comparison | One ticket at 32.26 seconds, unchanged 60-second promise. |
| 2:10–2:20 | Original actual Bryntum view | Preserve its exact footage and timing. |
| 2:20–2:45 | Existing download/setup/close | Keyless replay and honest recorded scope. |

The source is an actual 1920×900 local-app browser screenshot. The complete
evidence card is cropped at x=366, y=99, width=1448, height=560, uniformly scaled
and padded into the top 900 pixels of the existing 1920×1080 frame. This makes
the saved labels, amount, status, routes and IDs readable in a normal player.
The lower 180 pixels retain the original burned-in captions. No synthetic
PayPal UI, login page, model output, metric or payment is added.

## Local verification — 11 November 2026

- The screenshot comes from the implemented local app and is inspected for
  readable amount, currency, `COMPLETED`, order/capture IDs and route labels.
- Output remains 2:45, below 3:00 and 100 MB, with no new music or caption track.
- Full audio/video decoding succeeds.
- Copied AAC packets match the original Deepgram audio byte for byte.
- Source footage and timing are retained in the investigation, Bryntum
  130–140 seconds and closing intervals. Full-interval SSIM must be at least
  0.995 after the H.264 High/4.0 re-encode; AAC audio remains byte-identical.
- Opening and boundary frames are visually inspected; browser playback is
  checked at 0:20, 1:44, 2:10 and 2:40.

The local renderer and detailed results live outside the repository under
`var/judge-presentation-nov11/video/`. The MP4 must never be committed.
The focused candidate passed the checks above:

- File: `crashcart-evidence-first-focused.mp4` in that private directory.
- Duration: **165.000 seconds**; size: **9,485,711 bytes**; H.264 High/4.0,
  1920×1080 at 30 fps; AAC 48 kHz mono; no selectable subtitle stream.
- Full decode: `ffmpeg -v error -xerror -i <candidate> -f null -` exited 0.
- Copied AAC ADTS SHA-256 matches the original:
  `6d28e6e9b3bd685eb6adc7fb50724f47956db45f75d0dc9bf2059dff1dcb2d45`.
- SSIM for retained source intervals 20–22 / 81–83 / 130–140 / 157–159 seconds:
  **0.998894 / 0.999294 / 0.999671 / 0.998999**. Picture is re-encoded;
  the source timing and content remain, rather than claiming byte-identical video.
- Inspected opening at 1 and 19 seconds, boundary at 20 seconds, actual Bryntum
  at 132 and 139 seconds, and close at 158 seconds. The saved-data labels,
  route distinction, original captions and Bryntum chart remain visible.
- Installed Google Chrome played the local MP4, sought to 0:00, 0:20, 1:44,
  2:10 and 2:40 (all readyState 4, no media errors), then reached the end.
  No page errors were emitted. This is local playback, not a signed-out
  YouTube watch check; no upload occurred.
- The first private browser harness stalled while seeking over Python's simple
  HTTP server. It was replaced with a loopback-only HTTP byte-range server,
  a bounded seek wait and an already-at-zero guard; the corrected check passed.
  No media assertion was weakened.

Detailed local results are `run-crashcart-evidence-first-focused/verification.json`
and `chrome-playback.json`; review frames are under that run's `frames/` directory.
The MP4 SHA-256 is
`cbf70f7f15c20794f4c06a0c7e1c5330297f797269f9e24ec3bf67c7b3d9ad7c`.
No new payment, model call, narration call, music, upload or public edit occurred.

## Exact prospective public-field changes

Only if the owner approves the local cut and its own later publication gate:

1. Upload the new candidate as a **new** Public video, without overwriting,
   deleting, recutting in Studio or re-uploading the current video. This needs
   a new video URL; none is claimed here.
2. The proposed title is “CrashCart: why a paid PayPal order never delivered
   (PayPal AI Hackathon)”. Description keeps the repo and current demo URLs,
   names Deepgram narration, and states that the opening is saved Orders v2
   GET/capture evidence with no new PayPal or AI call.
3. **Devpost field:** replace only the existing entry's video demo URL with the
   verified new Public watch URL. Keep project identity, submission, prizes,
   tags, personal/legal answers and all other try-it links unchanged.
4. **Devpost story:** no timing or Bryntum wording needs changing; its actual
   segment remains 2:10–2:20. An optional opening sentence may point readers to
   the new saved-evidence view, but requires a separately reviewed exact diff.
5. **README and site:** replace active watch URLs and the 130-second Bryntum
   links only after the new watch URL plays signed out. This is another source
   change/release gate; do not alter historical evidence or archive URLs.

Caption removal for the current video is its own earlier gate. The candidate
contains the same burned-in captions; do not publish another selectable caption
track on a future upload without addressing the double-caption presentation.

The local candidate is feasible and checked; publication is still optional.
The lowest-risk choice is to retain the current video and add the real evidence
screenshot to the gallery. If the owner prefers the evidence-first cut, review
it locally before a separate upload gate, then verify its new watch URL before
changing any links. Never replace missing checkout footage with an invented screen.
