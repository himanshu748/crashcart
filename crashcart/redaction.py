"""Shared text and record redaction; callers retain their existing output bounds."""
import re

SECRET_KEYS = (
    "OPENAI_API_KEY", "MODAL_API_KEY", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET",
    "PAYPAL_CLIENT_SECRET", "KERNEL_API_KEY", "AG_STUDIO_LICENSE_KEY", "CRASHCART_OPERATOR_TOKEN",
)
_SENSITIVE_FIELD = re.compile(r"secret|authorization|api.?key|password|payer|shipping", re.I)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def sanitize_text(value, environ, *, max_characters=None):
    """Replace configured secrets before applying an optional caller text bound."""
    for name in SECRET_KEYS:
        secret = environ.get(name)
        if isinstance(secret, str) and secret:
            value = value.replace(secret, "[REDACTED]")
    if max_characters is not None:
        value = value[:max_characters]
    return _EMAIL.sub("[REDACTED_EMAIL]", value) if "@" in value else value


def redact(value, environ, *, max_list_items=None, max_characters=None):
    """Keep the transport unbounded and investigator bounded, without changing either policy."""
    if isinstance(value, dict):
        return {
            key: redact(item, environ, max_list_items=max_list_items, max_characters=max_characters)
            for key, item in value.items()
            if isinstance(key, str) and not _SENSITIVE_FIELD.search(key)
        }
    if isinstance(value, list):
        items = value if max_list_items is None else value[:max_list_items]
        return [redact(item, environ, max_list_items=max_list_items, max_characters=max_characters) for item in items]
    if isinstance(value, str):
        return sanitize_text(value, environ, max_characters=max_characters)
    return value
