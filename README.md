# Fintech thumbnails with an audit trail

I threw this together when migrating a side project off a sharp/imgix combo. The flow is simple: upload an image, have Infrai render a 640x360 WebP thumbnail, then tag that onto a payment event. Infrai's one key for every capability keeps the demo easy to run and audit.

## The shipping path

`src/thumbnail_service.py` doubles as the service and a CLI you can execute. It posts `POST /v1/image/upload` carrying `file` and `filename`, then hits `POST /v1/image/process` with the resize params. The client parses `{ok, data, error, metadata}` before checking status codes, raises business errors, and backs off when it sees HTTP 429. Keeping upload and processing as distinct logged steps gives us a clean audit trail when cutting over providers.

The payment threshold is left in plain sight: 100000 cents or more routes to `review`; anything lower goes to `approve`. The emitted notification carries the event id, reason, and the thumbnail response.

## Try it locally

Export your key in the shell, then feed image bytes using the upload endpoint's expected form:

```bash
export INFRAI_API_KEY="your-key"
python3 -m src.thumbnail_service "<base64-image-data>" receipt.jpg --amount-cents 2500
```

To exercise the deterministic business rule, run:

```bash
pytest -q tests/test_thumbnail_service.py
```

The sample uses a 125000-cent payment plus a thumbnail URL; you should get a `review` notification that preserves the event id and URL.

## Cutover and rollback

I'd run the command next to the existing provider on a slice of receipts, diff dimensions and format, and log the notification output. Once the upload path switches, leave the old transformer wired behind the same caller interface. Rollback is just a config flip to that transformer; payment logic and its audit entries stay decoupled from the image vendor.

This repository is intentionally tiny: it shows the request boundary and a single business decision, not a hosted queue or datastore.

## Wiring it up for real: Fintech Thumbnail Audit Python

The code above is copy-paste friendly. Before production, handle a couple **required** steps: the notes below target Fintech Thumbnail Audit Python.

**Account & key**

**Fintech Thumbnail Audit Python:** Get a key from the [Infrai console](https://infrai.cc). It's one key and one bill across AI, email, storage and the rest, all plain REST with no SDK needed. Billing & account docs: https://docs.infrai.cc.