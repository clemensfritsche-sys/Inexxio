"""Die Datei-Ablage: Bytes im Bucket, sonst in der Zeile – eine Datei geht nie verloren."""

import pytest

from app.models import Attachment
from app.services import attachments


class _Blob:
    def __init__(self, store, name, fail):
        self.store, self.name, self.fail = store, name, fail

    def upload_from_string(self, raw, content_type=None):
        if self.fail:
            raise RuntimeError("kein Zugriff")
        self.store[self.name] = bytes(raw)

    def download_as_bytes(self):
        return self.store[self.name]

    def delete(self):
        self.store.pop(self.name, None)


class _Bucket:
    def __init__(self, fail=False):
        self.store, self.fail = {}, fail

    def blob(self, name):
        return _Blob(self.store, name, self.fail)


@pytest.fixture
def bucket(monkeypatch):
    b = _Bucket()
    monkeypatch.setattr(attachments, "bucket", lambda: b)
    return b


def test_a_file_goes_to_the_bucket_and_comes_back(db, bucket):
    att = attachments.store_raw(db, b"%PDF-1.4 hallo", "a.pdf", "application/pdf", None)
    db.flush()
    assert att.data is None and bucket.store[att.token] == b"%PDF-1.4 hallo"
    assert attachments.bytes_of(att) == b"%PDF-1.4 hallo"


def test_a_broken_bucket_keeps_the_file_in_the_row(db, monkeypatch):
    broken = _Bucket(fail=True)
    monkeypatch.setattr(attachments, "bucket", lambda: broken)
    att = attachments.store_raw(db, b"abc", "a.txt", "text/plain", None)
    assert att.data == b"abc" and not broken.store
    assert attachments.bytes_of(att) == b"abc"


def test_a_run_that_rolls_back_writes_nothing_to_the_bucket(db, bucket):
    with attachments.in_database():
        att = attachments.store_raw(db, b"vorschau", "v.html", "text/html", None)
    assert att.data == b"vorschau" and not bucket.store


def test_discard_removes_the_object_only_after_the_commit(db, bucket):
    att = attachments.store_raw(db, b"weg", "w.txt", "text/plain", None)
    db.flush()
    attachments.discard(db, att)
    db.flush()
    assert att.token in bucket.store, "vor dem Commit bleibt die Datei"
    db.commit()
    assert att.token not in bucket.store
    assert db.query(Attachment).filter(Attachment.token == att.token).first() is None
