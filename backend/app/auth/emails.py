from fastapi import HTTPException


def clean_email(email: str) -> str:
    """Emails are compared in lowercase without spaces. Rejects text that is clearly not an email."""
    cleaned = email.strip().lower()
    local, _, domain = cleaned.partition("@")
    if not local or "." not in domain or " " in cleaned:
        raise HTTPException(422, "Enter a valid email address, for example name@shop.ma.")
    return cleaned
