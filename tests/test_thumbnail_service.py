import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.thumbnail_service import create_audit_notification, PaymentEvent, run


def test_large_payment_requires_review_and_keeps_thumbnail_record():
    event = PaymentEvent("evt-1", 125_000, "img-9")
    note = create_audit_notification(event, {"url": "https://cdn.example/thumb.webp"})
    assert note.decision == "review"
    assert note.event_id == "evt-1"
    assert note.thumbnail["url"].endswith("thumb.webp")


def test_run_deletes_uploaded_image():
    class Client:
        deleted = None

        def upload(self, image, filename):
            return {"image_id": "img-9"}

        def process_thumbnail(self, image_id):
            assert image_id == "img-9"
            return {"url": "https://cdn.example/thumb.webp"}

        def delete_image(self, image_id):
            self.deleted = image_id

    client = Client()
    run("image-data", "codecheck.png", 2500, client)
    assert client.deleted == "img-9"


def test_run_deletes_uploaded_image_when_processing_fails():
    class Client:
        deleted = None

        def upload(self, image, filename):
            return {"image_id": "img-9"}

        def process_thumbnail(self, image_id):
            raise RuntimeError("processing failed")

        def delete_image(self, image_id):
            self.deleted = image_id

    client = Client()
    try:
        run("image-data", "codecheck.png", 2500, client)
    except RuntimeError:
        pass
    else:
        assert False, "processing should fail"
    assert client.deleted == "img-9"
