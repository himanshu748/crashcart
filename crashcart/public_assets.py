"""Explicit self-hosted public presentation assets; no runtime file discovery."""

# Explicit public allowlist: no runtime packages, remote fonts or private files.
ASSETS = (
    "index.html", "product.html", "integrations.html", "demo.html", "app.js", "style.css", "site.js",
    "landing.css", "motion.css", "motion.js", "assets/fonts.css", "assets/favicon.svg", "assets/PROVENANCE.json",
    "assets/vendor/gsap.min.js", "assets/vendor/ScrollTrigger.min.js", "assets/vendor/GSAP-LICENSE.txt",
    "assets/fonts/instrument-serif-latin.woff2", "assets/fonts/manrope-latin.woff2",
    "assets/fonts/INSTRUMENT-SERIF-OFL.txt", "assets/fonts/MANROPE-OFL.txt",
    "assets/media/delivery-timing.webp", "assets/media/payment-evidence.webp",
)
ASSET_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json", ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2", ".webp": "image/webp", ".svg": "image/svg+xml",
}
