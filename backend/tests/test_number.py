"""EINE Zahl aus einer Eingabe (``domain/number``) – wie Menschen in der Schweiz Zahlen schreiben."""

from decimal import Decimal

import pytest

from app.domain import number
from app.domain import voucher as vo


@pytest.mark.parametrize("text", ["1'234.50", "1’234.50", "1 234,50", "1.234,50", "1,234.50", "1234.5"])
def test_every_swiss_way_of_writing_a_number_is_the_same_number(text):
    assert number.decimal(text) == Decimal("1234.5")


def test_the_amount_of_a_voucher_reads_the_typographic_apostrophe():
    """Bug-Form: «1’234.50» (Apostroph der Tastatur am Mac) war «kein Betrag»."""
    assert vo.amount("1’234.50", "CHF") == Decimal("1234.50")


def test_nothing_is_none_and_nonsense_is_a_sentence():
    assert number.decimal("") is None and number.decimal(None) is None
    with pytest.raises(ValueError, match="keine Zahl"):
        number.decimal("zwölf")
    assert number.lenient("Total CHF 1'234.50 inkl. MWST") == Decimal("1234.50")
    assert number.lenient("kein Betrag") is None
