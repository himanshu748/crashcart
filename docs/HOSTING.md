# Free recorded walkthrough hosting

The deploy target is **GitHub Pages on this public repository**. It needs no
payment card or paid plan. It serves a read-only project demonstration, not a
commercial SaaS, payment form, production checkout or live backend.

The `Recorded walkthrough` workflow waits for `Source behavior` to pass on a
push to `main`. It checks out that exact tested revision, runs the replay and
judge-mode tests, and executes both merchant variants while exporting the site.
Only the generated static directory is uploaded. No credentials, private
database, AG Studio bundle, model call or live transaction is deployed.

```sh
python3 -m crashcart.judge --export-site _site
```

The local judge command recomputes both outcomes at launch. The hosted page
displays outcomes recomputed **during the site build**. Interactions inspect
those saved records; opening the site does not rerun the Python engine or make
a payment. Download the exact input and run the documented commands to repeat
the check locally.

Repository Pages settings must use **GitHub Actions** as the source. The owner
has authorized this free deployment. Keep Pages enabled and this public source
available through **15 December 2026**; there is no automatic expiry or teardown
in the workflow. Platform availability remains subject to GitHub's service and
usage limits, not an uptime guarantee made by CrashCart. No paid upgrade or
custom domain is required.

The deploy URL and actual publication result belong in STATUS.md after target
readback. A prepared workflow is not deployment evidence.

## Why not a hosted live server?

Hugging Face's current documentation says new Docker/Gradio compute Spaces
require a paid plan even though CPU Basic hardware has no hourly charge. Static
Spaces remain free, but an additional service is unnecessary here. We did not
create a paid Space or add billing. Render remains excluded. A live backend
would additionally require permitted provider credentials, reachable notification
ingress and bounded service usage; none is implied by this recorded walkthrough.

Verified 4 November 2026 against [GitHub Pages availability](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages),
[custom publishing workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages),
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
and [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-overview).
