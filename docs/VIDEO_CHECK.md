# Submission video

**Final local edit:** `dist/crashcart-demo.mp4`. An identical archive is retained at `var/final-run-nov10/bryntum-video/crashcart-demo.mp4` in the private build workspace. The source film at `var/ship-devpost/dist/crashcart-demo.mp4` is preserved unchanged. These local video files are not committed to Git.

| Property | Actual final export |
| --- | --- |
| Runtime | **165.000 seconds — 2:45** |
| File size | **9,220,462 bytes — 9.22 MB**, below 100 MB |
| Picture | H.264, 1920 × 1080, 30 fps, MP4 |
| Narration | Existing AAC audio, mono, 96 kHz; copied without re-encoding |
| Captions | Original burned-in captions, chapter labels and progress retained |
| Updated footage | Actual Playwright recording of the existing Bryntum timing view, replacing only **2:10–2:20** |

The film shows the saved **8 November Sandbox payment and real AI investigation**, then explicitly switches to a **different recorded checkout** for the healthy 32.26-second comparison. It does not show a new payment, new AI call, fresh repaired purchase or original buyer-approval video. The November 8 case has no original checkout recording.

The ten-second insert shows the actual Bryntum Scheduler Community **8.0.0-beta.1** view, under its distributed MIT licence. Both cases were freshly replayed locally from the unchanged canonical public `early-response-loss-input.json`: the faulty case has zero tickets; the healthy case has one at **32.261423 seconds**. These are recorded replays, not fresh Sandbox transactions. The browser shows both cases, briefly filters to the healthy case, then returns to both. No product code or payment rule changed for the recording.

The capture server served only local public replay records and existing assets, rejected writes and denied outbound connections. Playwright recorded zero external requests and zero page errors. No credentials were used for the insert. The temporary capture server has been stopped.

## Final-file inspection

Frames were extracted from the **new final MP4**, including both cut boundaries:

| Position | Inspected result |
| --- | --- |
| 2:10 / 2:12 | Both recorded cases fit in the timing view; the 60-second window and healthy ticket marker are legible. |
| 2:15 | The healthy-case filter shows one ticket at 32.261423 seconds. |
| 2:20 | The film returns to its original download scene and caption. |
| 2:44 | The original closing product view and repository invitation remain legible. |

The original caption, “The missing-ticket case needs attention. The recovered order keeps the same one-minute promise,” remains on the insert. The separate-recorded-replay label stays visible, and neither covers the chart's result or marker. No third-party logo was added.

The entire final video and audio decoded successfully with exit 0 and no error output. The original and final compressed AAC packet payloads have the same SHA-256, confirming the existing narration was retained unchanged:

```text
f5e0e00f73e7ae281c4ec21c7b930f8eba18e16d2da2898f91aca451dc2f39f9
```

Final MP4 SHA-256:

```text
35be48ddb77e5287c394404ec976449ab2af7bc1f0d9a64ccf58dae95ffed15d
```

```sh
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate,channels -of json crashcart-demo.mp4
ffmpeg -hide_banner -loglevel error -i crashcart-demo.mp4 -f null -
```

## Publication

Published as **Public** on 10 November 2026: [watch the demo](https://www.youtube.com/watch?v=gFWje84_wEA). Safari Private Browsing showed the signed-out Sign in control and actual playback advancing to 0:27 of 2:45. The video is under 3 minutes. Devpost has not been submitted; final approval is still required.
