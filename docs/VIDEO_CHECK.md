# Submission video

**Local export:** `dist/crashcart-demo.mp4` (intentionally ignored by Git).

| Property | Actual export |
| --- | --- |
| Runtime | **165.000 seconds — 2:45** |
| File size | **6,518,147 bytes — 6.52 MB**, below 100 MB |
| Picture | H.264, 1920 × 1080, 30 fps, MP4 |
| Narration | Burned-in text captions; no audio track or music |
| Capture | Playwright recording of the actual running app, followed by MP4 conversion |

The source presentation is on `ship/devpost` at `7d4c66c`. The footage shows the saved **8 November Sandbox payment and real AI investigation**, then explicitly switches to a **different recorded checkout** for the healthy 32.26-second comparison. It does not show a new payment, new AI call, fresh repaired purchase or original buyer-approval video. The November 8 case has no original checkout recording.

The app was served locally from a private SQLite backup. Sign-in finished before recording. New payment/model actions were disabled; the browser made no external requests. The store card's read time can show 9 November because the backup is being inspected then. The PayPal and AI activity retain their actual 8 November dates.

## Frame inspection

Frames were extracted from the **final MP4**, not just from rehearsal screenshots:

| Position | Inspected result |
| --- | --- |
| 0:00 | Landing page and readable customer-problem caption. |
| 0:20 / 0:38 | Saved-run date badge, confirmed payment and zero tickets; no key or buyer details. |
| 1:08 / 1:16 / 1:25 | Actual saved assistant steps, explained in plain words; technical drawers stay closed. |
| 1:44 | Caption explicitly says this is a different recorded checkout. |
| 1:54 | Recovered order shows one ticket at 32.26 seconds and the recorded-replay label. |
| 2:24 / 2:40 | Runnable download and closing try-it address are legible. |

No third-party logos appear; PayPal is named factually. Captions do not cover the result being discussed. A complete decode of the export completed with exit 0 and no error output. This is a frame/decode check, not a claim of a fresh provider run.

```sh
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate -of json dist/crashcart-demo.mp4
ffmpeg -hide_banner -loglevel error -i dist/crashcart-demo.mp4 -f null -
```

## Owner before submission

Upload this MP4 to YouTube as **Public**, check the watch link while signed out, then replace the video placeholder in [DEVPOST.md](DEVPOST.md). No upload or Devpost submission has been performed.
