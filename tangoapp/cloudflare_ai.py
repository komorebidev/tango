import os

import requests

DEFAULT_MODEL = "@cf/qwen/qwen3.8-27b"

CLOUDFLARE_API_URL = (
    "https://api.cloudflare.com/client/v4/accounts/"
    "{account_id}/ai/run/{model}"
)


def run_ai(messages: list[dict]) -> dict:
    """Send a chat request to Cloudflare Workers AI."""

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")

    if not account_id or not api_token:
        raise RuntimeError(
            "Cloudflare AI credentials are not configured."
        )

    response = requests.post(
        CLOUDFLARE_API_URL.format(
            account_id=account_id,
            model=DEFAULT_MODEL,
        ),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json={"messages": messages},
        timeout=(10,120),
    )

    response.raise_for_status()
    result = response.json()

    if not result.get("success"):
        raise RuntimeError(
            f"Cloudflare AI request failed: {result.get('errors')}"
        )

    return result.get("result", {})
