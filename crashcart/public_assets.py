"""Explicit self-hosted public presentation assets; no runtime file discovery."""

# Explicit public allowlist: no runtime packages, remote fonts or private files.
ASSETS = (
    "index.html", "product.html", "integrations.html", "demo.html", "app.js", "style.css", "site.js",
    "live.html", "live.js", "live.css",
    "landing.css", "motion.css", "motion.js", "assets/fonts.css", "assets/favicon.svg", "assets/PROVENANCE.json",
    "assets/vendor/gsap.min.js", "assets/vendor/ScrollTrigger.min.js", "assets/vendor/GSAP-LICENSE.txt",
    "assets/fonts/instrument-serif-latin.woff2", "assets/fonts/manrope-latin.woff2",
    "assets/fonts/INSTRUMENT-SERIF-OFL.txt", "assets/fonts/MANROPE-OFL.txt",
    "assets/media/delivery-timing.webp", "assets/media/payment-evidence.webp",
)
# Optional timing page: its MIT SDK is loaded only on direct navigation.
# Kept separate so the landing-page asset budget continues to cover its own assets.
TIMING_ASSETS = (
    "timing.html", "timing.css",
    "assets/vendor/bryntum/timing.js", "assets/vendor/bryntum/scheduler.css",
    "assets/vendor/bryntum/timing.css", "assets/vendor/bryntum/timing.css.LEGAL.txt",
    "assets/vendor/bryntum/fa-solid-900-5ZUYHGA7.woff2", "assets/vendor/bryntum/fa-solid-900-PJNKLK6W.ttf",
    "assets/vendor/bryntum/LICENSE.txt", "assets/vendor/bryntum/THIRD-PARTY-NOTICES.txt",
    "assets/vendor/bryntum/FONT-AWESOME-LICENSE.txt", "assets/vendor/bryntum/manifest.json",
)
ASSET_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json", ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2", ".ttf": "font/ttf", ".webp": "image/webp", ".svg": "image/svg+xml",
}
