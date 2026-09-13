import os
import requests


class NotificationError(RuntimeError):
    pass


def notify(
    message: str,
    subject: str | None = None,
    *,
    line: bool = True,
    email: bool = False,
    line_targets: list[str] | None = None,
    email_to: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int = 5,
):
    base_url = (base_url or os.getenv("NOTIFICATION_BASE_URL", "")).rstrip("/")
    api_key = api_key or os.getenv("NOTIFICATION_API_KEY", "")

    if not base_url:
        raise NotificationError("NOTIFICATION_BASE_URL is not configured")
    if not api_key:
        raise NotificationError("NOTIFICATION_API_KEY is not configured")

    payload = {
        "subject": subject,
        "message": message,
        "line": line,
        "email": email,
    }
    if line_targets is not None:
        payload["line_targets"] = line_targets
    if email_to:
        payload["email_to"] = email_to

    try:
        response = requests.post(
            f"{base_url}/api/notify",
            headers={"X-API-Key": api_key},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise NotificationError(f"notification request failed: {exc}") from exc
