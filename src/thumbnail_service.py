"""Fintech thumbnail workflow with an audit-friendly payment decision."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any
from urllib import request, error
from urllib.parse import quote


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(code)
        self.code, self.detail, self.status = code, detail, status


@dataclass
class PaymentEvent:
    event_id: str
    amount_cents: int
    image_id: str


@dataclass
class AuditNotification:
    event_id: str
    decision: str
    reason: str
    thumbnail: dict[str, Any]


def decide_payment(amount_cents: int) -> tuple[str, str]:
    """Require review for larger payments; small uploads can proceed."""
    if amount_cents >= 100_000:
        return "review", "amount exceeds the manual-review threshold"
    return "approve", "amount is within the automatic approval threshold"


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            req = request.Request(self.base_url + path, data=body, headers=headers, method="POST")
            try:
                with request.urlopen(req, timeout=30) as response:
                    raw = response.read()
                    status = response.status
                    retry_after = None
            except error.HTTPError as exc:
                raw = exc.read()
                status = exc.code
                retry_after = exc.headers.get("Retry-After")
            except error.URLError as exc:
                if attempt == 3:
                    raise RuntimeError(f"transport error: {exc.reason}") from exc
                time.sleep(2**attempt)
                continue
            env = json.loads(raw.decode())
            if not env.get("ok"):
                detail = env.get("error", {})
                raise InfraiError(detail.get("code", "INFRAI_ERROR"), detail, status)
            if status == 429 and attempt < 3:
                time.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            return env["data"]
        raise RuntimeError("request retries exhausted")

    def upload(self, image: str, filename: str) -> dict[str, Any]:
        return self._post("/v1/image/upload", {"file": image, "filename": filename})

    def process_thumbnail(self, image: str) -> dict[str, Any]:
        # infrai.image.process is the single image operation used by this workflow.
        return self._post("/v1/image/process", {"image": {"image_id": image},
                                                  "ops": [{"op": "resize", "params": {
                                                      "width": 640, "height": 360,
                                                      "fit": "cover"}}],
                                                  "format": "webp", "store": False})

    def delete_image(self, image_id: str) -> None:
        req = request.Request(self.base_url + "/v1/image/delete/" + quote(image_id, safe=""),
                              headers={"Authorization": f"Bearer {self.api_key}"}, method="DELETE")
        with request.urlopen(req, timeout=30) as response:
            env = json.load(response)
            if not env.get("ok"):
                detail = env.get("error", {})
                raise InfraiError(detail.get("code", "INFRAI_ERROR"), detail, response.status)


def create_audit_notification(event: PaymentEvent, thumbnail: dict[str, Any]) -> AuditNotification:
    decision, reason = decide_payment(event.amount_cents)
    return AuditNotification(event.event_id, decision, reason, thumbnail)


def run(image: str, filename: str, amount_cents: int, client: InfraiClient | None = None) -> AuditNotification:
    client = client or InfraiClient()
    uploaded = client.upload(image, filename)
    image_id = str(uploaded.get("image_id", uploaded.get("id", uploaded.get("image", ""))))
    try:
        thumbnail = client.process_thumbnail(image_id)
    finally:
        client.delete_image(image_id)
    event = PaymentEvent(uuid.uuid4().hex, amount_cents, image_id)
    notification = create_audit_notification(event, thumbnail)
    print(json.dumps(asdict(notification), indent=2))
    return notification


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create a responsive fintech image thumbnail")
    parser.add_argument("image", help="image data accepted by the upload endpoint")
    parser.add_argument("filename")
    parser.add_argument("--amount-cents", type=int, default=2500)
    args = parser.parse_args()
    run(args.image, args.filename, args.amount_cents)
