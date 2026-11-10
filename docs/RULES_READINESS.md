# Submission readiness — updated 10 November

This is a project readiness assessment, not an organizer eligibility ruling.
Sources: [official rules](https://paypalaihackathon.devpost.com/rules),
[5 November organizer update](https://paypalaihackathon.devpost.com/updates/47307-submission-checklist-it-s-go-time)
and the authenticated Devpost rules, requirements, dates, criteria and announcements
feeds fetched on 8 November. The rules webpage returned 403; the connected rules
feed returned complete text. [Readback and scoped proof](../evidence/runs/submission-ready/rules-nov8.json).
The official website prevails if this assessment differs.

## Corrections that matter

- **Hosting is optional.** The rule says the project “does not need to be publicly hosted or deployed”. Use the working local build and complete setup as the primary runnable path. AWS and the GitHub Pages account lock are not, by themselves, submission disqualifiers. A decorative mockup is insufficient; the local command actually recomputes both outcomes.
- **Access must last beyond judging.** The 5 November update asks for the demonstrated build, test credentials, trials and credits through the 21 December winner announcement. Future operating instructions now retain access through 22 December UTC as a timezone buffer, with cleanup no earlier than 23 December UTC. Historical receipts keep their actual earlier tags.
- **Freeze linked material.** After the submission deadline, do not edit the submitted repository, video or linked material until winners are announced, absent an explicit organizer exception. Keeping a service running does not mean deploying new product behavior during that freeze.
- **PayPal and meaningful AI are required; extra sponsors are optional.** The requirement permits PayPal technology/API/SDK/product/developer capability. A particular SDK, PayPal AI Toolkit or additional sponsor is not mandatory. Existing substantive Orders/capture/payment-read/signature-verification logic matters more than adding an unused SDK.
- **Video remains required.** It must be public on YouTube, under three minutes, and show the functioning project. The script permits the actual local build; there is no reason to wait for AWS to record it. Historical AI must remain clearly distinguished from a new model run and from the separate faulty checkout.

## Dates and operating buffer

Deadline: **13 November 2026, 01:30 IST** (12 November, 20:00 UTC).
Formal judging ends **15 December 2026, 21:30 IST**. Winner announcement is 21 December.
The formal rules name 14:00 Pacific; the key-dates feed returns 17:00 UTC for that
announcement, so their exact times conflict. Retain access through the actual
announcement and 22 December UTC; do not infer that 15 December teardown is safe.
These are operating instructions, not evidence of future uptime.

## Current gates — 10 November readback

| Gate | Actual state and next action |
| --- | --- |
| Public source and OSI licence | GitHub API readback: public repository, default branch main, detected MIT. LICENSE present. This does not license private vendor bundles. |
| Working local build | Fresh public clone and actual script/HTTP verification recorded in the linked evidence. Saved input is executed; no provider or model call occurs. This establishes replay functionality, not the complete configured AI workflow. |
| PayPal-plus-AI capability | Actual historical Sandbox webhook/recovery and separate real DeepSeek evidence exist. The current keyless path is recorded. Complete judge-accessible configured PayPal-plus-AI execution remains unverified; do not claim a recorded model trace is an executable AI service. |
| Public video | **Published.** The submitted entry links the [2:45 public video](https://www.youtube.com/watch?v=gFWje84_wEA). Its saved Sandbox flow and separate healthy replay are labelled; this feature branch does not replace it. |
| Access through winner announcement | **OPEN operational obligation.** Keyless source has no credential expiry. Any claimed live workspace/model access needs usable, free judge access and permitted allowance throughout the longer window. No new provider execution or paid extension is authorized by this document. |
| AG Studio optional workflow | Private trial ends 17 December. The [6 November vendor announcement](https://www.ag-grid.com/blog/build-a-payments-dashboard-without-building-a-dashboard/) promises judging-period keys. Confirm delivery and coverage through 22 December before publishing the new recorded explorer or selecting the prize. The keyless build does not load AG Studio. |
| Other sponsors | Describe actual roles only. Postman performs API checks; KERNEL supplies separately bounded browser observation; Bryntum supplies a configured timing view. Optional prize use requires accessible working evidence, not a logo or installed package. Render remains excluded; Modal hosts the model and is not an event tool sponsor. |
| Entry submitted | **NO.** The project page is published, but this hackathon's submitted_at is null. The owner retains final submission. No registration, form edit, submission or rules-acknowledgement write occurred. |
| Final form | Submitted 10 November, 14:31:32 IST; readback confirmed Submitted, 5/5. Current optional sponsor selections are Bryntum, KERNEL and Postman. AG Grid and APIMatic are off. No entry edits are authorized before the owner replies exactly `submit`. |

## Judging priorities

The five equally weighted criteria are Technological Implementation, Design,
Potential Impact, Innovation/Idea and Presentation; the scoring scale is 1–5.
Prioritize a coherent payment→evidence→AI investigation→deterministic finding
story over more sponsor surfaces. Show actual behavior and identify the audience;
claim no customer adoption, measured savings or live merchant connection without
proof. Current replay and historical AI are separate cases and must stay labelled.

The original private acceptance remains **47/60**, with no new CC IDs or weakened
conditions. Submission rules and the 60-item full-release contract are different
boundaries. This review neither closes CC-059/060 nor declares the entry compliant.

## Current hosted access — 10 November

The [current recorded demo](https://crashcart.32.193.44.79.sslip.io/) is verified on the independently approved $12/month Lightsail instance. The previous shared host remains untouched; the Pages mirror also serves the recorded core. The hosted example shows saved AI observations, not a current model endpoint; complete configured PayPal-plus-AI access remains separate. The public video and submitted entry were verified on 10 November. The dedicated host is retained through 22 December and its current certificate expires 8 February 2027; future uptime is not a verified result. [Hosting and restart](OPERATIONS.md).
