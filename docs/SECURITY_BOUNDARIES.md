# Security and production boundaries

The public recorded walkthrough serves saved records. It makes no new PayPal,
model or KERNEL call. The private test workspace is a separate operator tool;
its current controls are not a production authentication or merchant onboarding
system.

## Operator sessions

The workspace cookie contains a deterministic HMAC derived from the operator
key and a fixed session label. It is HttpOnly and SameSite=Lax; HTTPS deployment
configuration adds Secure. It contains no timestamp, and the server does not
enforce an expiry or an idle timeout. Browser session-cookie handling is not a
server-side lifetime guarantee. Changing the operator key invalidates existing
cookies. Before production use, replace this shared operator credential with
per-user authentication, explicit expiry, revocation and store isolation.
The separately protected hosted workspace uses SameSite=Strict and Secure, but
shares the same HMAC lifetime limitation.

## PayPal notification timestamps and duplicates

The Sandbox adapter parses the transmission timestamp and validates the
certificate URL and algorithm before asking PayPal to verify the signature
against the original event object parsed from the received body, before storage redaction. It does not enforce a maximum age for a
signed transmission. Do not describe timestamp parsing as a freshness check.

The persisted event ID is the deduplication identity. An identical event returns
as a duplicate; reusing the ID with a changed stored payload or run is rejected.
A signature check does not itself establish delivery of a ticket. Deterministic
payment and ticket checks remain separate. These notes document existing
behavior; they do not change webhook acceptance, retries or payment rules.

## Reserved processing field

`webhooks.processed_at` is a reserved nullable schema field. The current receiver
writes `received_at` and verified event data, and may enqueue reconciliation;
it does not set `processed_at`. A null value is not proof that a verified event
was lost or that its reconciliation job failed. Inspect the corresponding
stored job and payment state instead. The column remains in place for schema
compatibility.

## Diagnostics and model records

Unexpected GET and POST errors log their exception type, not their message or
provider response. Model text redaction removes configured secret values and
email addresses. Transport records retain their existing text/list policy;
investigator summaries retain their separate 4,000-character and 50-item bounds.
Redaction is a limited safeguard, not a guarantee that arbitrary text contains
no personal information. Keep raw credentials and provider data private.

The prepared feature branch uses package version `0.2.0`; its workspace health
response and HTTP banner read that one value. This is a local release-preparation
label. It does not claim that the submitted public host has been upgraded.
