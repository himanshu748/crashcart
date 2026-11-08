# Submission readiness — official rules rechecked 8 November

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

## Current gates

| Gate | Actual state and next action |
| --- | --- |
| Public source and OSI licence | GitHub API readback: public repository, default branch main, detected MIT. LICENSE present. This does not license private vendor bundles. |
| Working local build | Fresh public clone and actual script/HTTP verification recorded in the linked evidence. Saved input is executed; no provider or model call occurs. This establishes replay functionality, not the complete configured AI workflow. |
| PayPal-plus-AI capability | Actual historical Sandbox webhook/recovery and separate real DeepSeek evidence exist. The current keyless path is recorded. Complete judge-accessible configured PayPal-plus-AI execution remains unverified; do not claim a recorded model trace is an executable AI service. |
| Public video | **OPEN.** Live Devpost readback has an empty video URL. Record, inspect duration and truthful labels, upload publicly to YouTube, and check signed-out playback. A script is insufficient. |
| Access through winner announcement | **OPEN operational obligation.** Keyless source has no credential expiry. Any claimed live workspace/model access needs usable, free judge access and permitted allowance throughout the longer window. No new provider execution or paid extension is authorized by this document. |
| AG Studio optional workflow | Private trial ends 17 December; it does not cover the extended window. Obtain an authorized vendor grant or leave this optional workflow/prize claim out of the submitted experience. The keyless build does not load AG Studio. |
| Other sponsors | Describe actual roles only. Postman performs API checks; KERNEL supplies separately bounded browser observation; Bryntum supplies a configured timing view. Optional prize use requires accessible working evidence, not a logo or installed package. Render remains excluded; Modal hosts the model and is not an event tool sponsor. |
| Entry submitted | **NO.** The project page is published, but this hackathon's submitted_at is null. The owner retains final submission. No registration, form edit, submission or rules-acknowledgement write occurred. |
| Final form | Check all current required fields, public video, public repo and working-build/setup URL. Do not publish usable API keys or buyer secrets in the repo. Provide any special access privately through the allowed judging instructions. Personal declarations remain the owner's statements. |

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

## Current hosted access — 8 November

The [current recorded demo](https://crashcart.52.202.25.181.sslip.io/) is verified on an existing Lightsail host, without a new instance or plan upgrade. The Pages link remains an older fallback. The hosted example includes historical AI, not a current model endpoint; complete configured PayPal-plus-AI access remains open. The public video and owner submission are still missing. A retention tag and a valid certificate support the plan through the winner announcement; future uptime is not a verified result. [Hosting evidence and limits](LIGHTSAIL_SHARED_HOST.md).
