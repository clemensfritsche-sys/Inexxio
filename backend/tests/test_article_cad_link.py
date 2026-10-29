"""Ein CAD-Link führt ins Web – sonst 422 mit einem Satz, der den Wert nennt.

Das ERP setzt den CAD-Link als ``<a href>``; ein ``javascript:``-Wert liefe beim Klick.
Dieselbe Regel liest die Oberfläche (``frontend/src/lib/web-link.ts``)."""

import pytest
from pydantic import ValidationError

from app.schemas.article import ArticleCreate


@pytest.mark.parametrize("url", ["https://cad.onshape.com/documents/1", "http://example.ch",
                                 "HTTPS://X.CH/a", "  https://x.ch  "])
def test_web_link_is_kept(url):
    assert ArticleCreate(name="Halter", cad_url=url).cad_url == url.strip()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "//evil.example",
                                 "cad.onshape.com", "ftp://x.ch", "https://", "https:///x"])
def test_anything_else_is_refused_with_a_sentence(url):
    with pytest.raises(ValidationError) as err:
        ArticleCreate(name="Halter", cad_url=url)
    assert f"CAD-Link «{url}» muss mit http:// oder https:// beginnen" in str(err.value)


def test_empty_stays_empty():
    assert ArticleCreate(name="Halter", cad_url="  ").cad_url is None
