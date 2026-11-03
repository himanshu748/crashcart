"""Explicit configuration; never discovers or prints credentials elsewhere."""

import os
from pathlib import Path


def load_env(path=".env"):
    file = Path(path)
    if not file.exists():
        return
    for line in file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep and key.replace("_", "").isalnum():
            os.environ.setdefault(key, value.strip().strip("\"'"))


def prerequisites():
    groups = {
        "paypal": ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"],
        "webhook": ["PAYPAL_WEBHOOK_ID", "CRASHCART_PUBLIC_URL"],
        "model": (["MODAL_API_KEY", "MODAL_MODEL", "MODAL_BASE_URL"]
                  if os.environ.get("CRASHCART_MODEL_PROVIDER", "openai") == "modal"
                  else ["OPENAI_API_KEY", "OPENAI_MODEL"]),
        "kernel": ["KERNEL_API_KEY", "CRASHCART_PUBLIC_URL"],
        "studio": ["AG_STUDIO_LICENSE_KEY"],
    }
    return {
        key: {"configured": all(os.environ.get(n) for n in names),
              "missing": [n for n in names if not os.environ.get(n)],
              "connectivity_verified": False}
        for key, names in groups.items()
    }
