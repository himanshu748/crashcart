# Current-video caption cleanup — completed readback

## Latest result — 11 November 2026, 20:46 IST

After the owner authorized the normal-browser retry, native Safari downloaded
both subtitle backups. Manual subtitles were unpublished and remain Draft; the
automatic track was deleted. The original audio and video were unchanged.
Studio was refreshed and read back. Signed-out Chrome Guest played the opening,
middle and Bryntum interval with burned-in captions and no available CC track.
This is the last verified state, not a permanent block on YouTube generating
automatic captions later. Private backups and readback are under
`var/judge-presentation-nov11/qa/caption-cleanup/`. No repeat caption change is
proposed without first checking the current track inventory.

The dated preparation and failed first download attempt below remain history.

Prepared 11 November 2026, 20:26 IST. No caption was unpublished, deleted,
cleared, edited or saved during inspection. The current video and its URL stay
unchanged: <https://www.youtube.com/watch?v=3MIzDpFmRl0>.

## What the current Studio actually shows

Open <https://studio.youtube.com/video/3MIzDpFmRl0/translations>.
The video-language header is **English (United States)**. Its **Details** dialog
has these media rows:

| Row | Source | Status | Menu verified without choosing an action |
| --- | --- | --- | --- |
| Audio | Original | Published | Leave untouched |
| Automatic subtitles | Automatic | Published | Duplicate and edit; Download; Delete |
| Manual subtitles | Manual | Published | Edit; Unpublish; Rename; Download; Delete |

The separate **English (title and description language)** translation row has
published metadata, not another published subtitle row. Leave its title and
description unchanged. Do not change the video language or narration.

## Exact gated steps

After the owner's exact `submit` for this caption-cleanup action only:

1. Reopen the above video and **Languages → English (United States) → Details**.
   Verify the title and video ID before touching a track.
2. On **Manual subtitles**, open **Show subtitle options → Download** and retain
   a private backup. Then choose **Unpublish** and confirm only that subtitle
   action if Studio asks. Prefer this reversible action to deleting the manual
   track. Do not edit timings, clear the editor or press Publish.
3. On **Automatic subtitles**, open **Show subtitle options → Download** and
   retain a private backup. Its current menu has no Unpublish control: choose
   **Delete**, and confirm deletion of only the automatic subtitle track.
   This permanent track deletion must be included explicitly in the owner's
   approval; do not delete the video or original audio.
4. Refresh Languages and read back every media row and every translation row.
   Neither of the two subtitle rows may remain Published. If any additional
   track appears, stop and report its name rather than broadening the action.
5. In a new signed-out/private browser session, open the same watch URL. Play
   the opening, a middle frame and the Bryntum interval. Confirm the burned-in
   captions remain, and Settings → Subtitles/CC offers no published manual or
   automatic track. Save the owner-side and signed-out screenshots.
6. Stop and report. Do not upload, change the title/description, edit Devpost,
   deploy the app or proceed to the next release action under this approval.

YouTube's documented removal flow does not establish a permanent per-video
switch preventing future automatic-caption generation. Recheck after refresh;
if YouTube regenerates a track, record that limitation and stop. Changing a
viewer's CC preference or the inappropriate-words filter is not a video-wide
caption disable. Auto-translated choices depend on source captions; verify the
signed-out menu rather than assuming they disappeared.

## Sources and local review images

Official help: [Edit or remove captions](https://support.google.com/youtube/answer/2734705?hl=en)
and [Use automatic captioning](https://support.google.com/youtube/answer/6373554?hl=en).
The current Languages/Details route and menu names above were read in the
owner's actual Studio, which differs from older Subtitles-table instructions.

Private review images are in `var/judge-presentation-nov11/qa/evidence/`:
`captions-two-published-tracks.jpg`, `captions-auto-delete-option.jpg`, and
`captions-manual-unpublish-option.jpg`. They are preparation, not completion.

Native Safari private browsing successfully played the unchanged current video
signed out (visible Sign in link and 2:45 duration). One transient player state
reported captions unavailable despite Studio's published rows. It does not
establish that caption cleanup occurred; the owner-side inventory is decisive.

## 11 November 2026, 20:34:20 IST — approved caption cleanup stopped before mutation

Owner replied exactly `submit` for current-video caption cleanup only. Actual
Studio still shows English (United States) Manual and Automatic subtitles as
Published. Before changing either track, the Manual backup was attempted once
as SRT and once as Original format. Both documented download waits timed out
after 20 seconds; neither returned a local download path. A bounded check found
no recent SRT/VTT backup in Downloads or the top-level temporary directory.
This does not establish the cause of the download failure.

Under the owner's two-failure rule, the step stopped. Fresh owner-side readback
and screenshot confirm both tracks remain Published; no Unpublish, Delete,
Publish, Update or Save was selected. No signed-out removal claim is made.
Automatic backup/removal was not attempted. No push, PR, merge, deployment,
gallery upload, video upload or Devpost edit occurred. The next action remains
obtaining actual subtitle backups, then completing the same caption cleanup;
do not advance to source publication under this grant. Private artifacts:
`var/judge-presentation-nov11/qa/caption-cleanup/after-backup-failures.txt` and
`tracks-still-published.jpg`.
