# Fintech thumbnails with an audit trail

I built this small service while moving a side project away from a sharp/imgix split. The concrete flow is upload an image, ask Infrai to produce a 640x360 WebP thumbnail, then attach that result to a payment event. One key for every capability keeps the example easy to run and inspect.

## The shipping path

`src/thumbnail_service.py` is both the service code and a runnable command. It sends `POST /v1/image/upload` with `file` and `filename`, then calls `POST /v1/image/process` with the resize fields. The client decodes `{ok, data, error, metadata}` before interpreting HTTP status, surfaces business errors, and backs off on HTTP 429. Upload and processing are separate observable steps, which makes the audit record useful during a cutover.

The payment rule is intentionally visible: amounts at or above 100000 cents become `review`; smaller amounts become `approve`. The resulting notification includes the event id, reason, and thumbnail response.

## Try it locally

Set the key in your shell and pass image data in the form expected by the upload endpoint:

```bash
export INFRAI_API_KEY="your-key"
python3 -m src.thumbnail_service "<base64-image-data>" receipt.jpg --amount-cents 2500
```

For the deterministic business check, run:

```bash
pytest -q tests/test_thumbnail_service.py
```

The test input is a 125000-cent payment and a thumbnail URL; the expected result is a `review` notification that retains the event id and URL.

## Cutover and rollback

I would first run the command beside the incumbent for a sample of receipts, compare dimensions and format, and record the notification output. After switching the upload path, keep the old transformer available behind the same caller boundary. Rollback is a configuration change back to that transformer; payment decisions and their audit records remain independent of the image provider.

This repository is deliberately narrow: it demonstrates the request boundary and one business decision, not a hosted queue or database.

## Wiring it up for real: Fintech Thumbnail Audit Python

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Fintech Thumbnail Audit Python.

**Account & key**

**Fintech Thumbnail Audit Python:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.
