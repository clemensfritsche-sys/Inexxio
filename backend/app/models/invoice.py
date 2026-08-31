from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Invoice(Base, TimestampMixin):
    """**Die Forderung an einem Beleg** – die dritte Achse neben Ware und Geld.

    ## Warum es sie überhaupt gibt

    Vorher las ``balance`` die **Zusage** (``purchases.amount``) als wäre sie die
    **Forderung**. Solange beides dasselbe ist, geht das gut. An drei Stellen bricht es,
    und zwar still:

    * **Anzahlung** – 30 % vor der Fertigung, der Rest nach der Abnahme. Zwei Forderungen
      zu einer Zusage.
    * **Teilrechnung** – 3 von 10 geliefert, 3 berechnet.
    * **Zwei Fälligkeiten** – jede Rechnung hat ihre eigene, eine Zusage hat keine.

    ## Und sie schreibt keine Reihenfolge vor

    Ware, Forderung und Geld sind drei **unabhängige** Achsen (``domain/money``). Ob die
    Rechnung vor der Lieferung steht (Vorauszahlung) oder danach (Zahlungsziel), ist keine
    Einstellung und kein Modus – es ist die **Reihenfolge, in der ein Mensch handelt**. Das
    System hält sie fest und bietet den naheliegenden nächsten Schritt an.

    ## Eine Gutschrift ist eine NEGATIVE Rechnung

    Sie war einmal eine Zahlung der Art ``credit`` – eine Zahlung, bei der kein Geld
    fliesst, mit einer eigenen Regel dafür. Hier ist sie schlicht ein negativer Betrag:
    dieselbe Zeile, dasselbe Feld, keine Ausnahme. Eine **Erstattung** bleibt dagegen eine
    negative **Zahlung** – dort fliesst Geld, nur rückwärts. Beides nebeneinander macht
    Kulanz (Gutschrift ohne Rücknahme) und Garantie (Rücknahme ohne Gutschrift) abbildbar.

    ## Die Nummer

    Beim **Verkauf** vergeben wir sie, beim **Einkauf** erfassen wir seine
    (``Flow.invoice_number``). Unsere lautet ``<Auftragsnummer>-<laufend>`` – dieselbe
    Regel wie bei der Einzelinstanz (``<Instanznr>-<Suffix>``, kumulierend, **nicht** aus
    ``object_id_seq``): eine Rechnung ist zum Auftrag, was die Einzelinstanz zur Instanz
    ist. Sie braucht einen Namen, aber keine eigene Objektidentität – und damit weder eine
    Feed-Zeile noch einen sechsten Datensatztyp.

    Das ``-1`` der **ersten** Rechnung ist eine Lesehilfe und wird nach aussen weggelassen
    (``services/invoices.display``); gespeichert bleibt es, sonst wäre die zweite Rechnung
    eines Auftrags nicht mehr von der ersten zu unterscheiden.

    ## Keine Positionen – heute

    Die Rechnung trägt Betrag und Notiz. Positionen gehören zum **Ausdruck**, und den gibt
    es nicht (das Dokumentmodul ist entfernt, ``docs/attic.md``); die Zeilen des Belegs
    stehen ohnehin in ``purchases.ordered_lines``. Als bewusst offener Punkt in
    ``SYSTEM_LOGIC.md`` §5.9 – nicht als stille Lücke.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        # **Eine Nummer gehört zu genau einer Rechnung im Haus.** Dieselbe Regel und
        # derselbe Grund wie bei ``uq_payments_reference``: ohne sie fände die
        # Idempotenz-Prüfung eine fremde Zeile und gäbe sie zurück – 200, nichts gebucht,
        # und nichts sagt warum. Partiell, weil eine Rechnung ohne Nummer möglich bleibt
        # (ein Lieferantenbeleg, dessen Nummer noch fehlt).
        Index("uq_invoices_number", "number", unique=True,
              postgresql_where=text("number IS NOT NULL AND is_active")),
        Index("ix_invoices_purchase", "purchase_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    #: Der Beleg, an dem diese Forderung hängt. **Keine eigene Objektnummer** – dasselbe
    #: Muster wie beim Beleg selbst und bei der Zahlung.
    purchase_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: ``<Auftragsnummer>-<laufend>`` bei uns, die Nummer der Gegenpartei beim Einkauf.
    number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    #: Der Betrag. **Darf negativ sein** – das ist die Gutschrift.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CHF")

    #: **Wann die Rechnung gestellt wurde** – der Beginn der Zahlungsfrist.
    issued_on: Mapped[Optional[object]] = mapped_column(Date, nullable=True)

    #: **Wann sie fällig ist.** Sie steht hier und nicht am Beleg: eine Zusage hat keine
    #: Fälligkeit, eine Rechnung schon – und zwei Rechnungen haben zwei. Die frühere
    #: Ableitung ``committed_on + payment_days`` konnte darum nur den einfachsten Fall.
    due_on: Mapped[Optional[object]] = mapped_column(Date, nullable=True)

    #: Ein Satz dazu, falls einer nötig ist («Anzahlung 30 %», «Gutschrift Retoure»).
    note: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
