"""081 – Tote Spalten am Prozessschritt und an der Datenerfassung entfernen.

Drei Altlasten, die der Code seit dem jeweiligen Umbau nicht mehr liest:

**1. Unterschrift/Foto als eigene Achse** (8 Spalten). Beim Umbau der Datenerfassung auf
frei konfigurierbare ``capture_fields`` sind ``photo`` und ``signature`` zu ganz normalen
**Feldtypen** geworden – gleichrangig neben Soll-Ist/Gut-Schlecht/Text, mit ihren Werten in
``inspections.samples``. Die frühere Parallel-Mechanik blieb stehen, aber tot:

* Definition am Schritt: ``require_signature``, ``signer_ids``, ``require_photo``,
  ``photo_instruction`` – das Frontend setzte sie beim Anlegen **hart auf false** und las
  sie nie wieder.
* Ergebnis an der Erfassung: ``signature_url``, ``signed_by``, ``signed_at``, ``photo_url``
  – wurden **nirgends geschrieben**; gelesen wurde nur ``signed_by``, das damit immer NULL
  war (der Auftrags-Embed zeigte also nie einen Unterzeichner).

**2. ``article_process_steps.transport_mode``.** Der Transport-Modus lebt am Versand-Beleg
(``shipments.transport_mode``: internal | parcel | freight) und wird zur Laufzeit aus der
Adress-Klassifikation ermittelt. Die Spalte am Schritt trug noch die von Migration 076
**abgeschafften** Werte (auto/carrier/self/none) – inklusive einer zweiten, veralteten
Whitelist ``ALLOWED_TRANSPORT_MODES`` im Schema. Zwei Wahrheiten für dieselbe Sache, von
denen eine nicht einmal mehr gültige Werte kannte.

**3. ``article_process_steps.locked``.** Die abgelöste Sperr-Spalte der Zwangs-Bewegungen;
Migration 079 hat sie bewusst stehen lassen, damit ein laufender Rollout nicht auf eine
gedroppte Spalte trifft. Dieser Folge-Deploy holt das nach – seit 079 liest sie niemand
mehr (die Rolle lebt in ``companion``).

**Rollout-Hinweis (bewusst in Kauf genommen):** Anders als bei 079 wird hier im selben
Deploy gedroppt. Während des Cloud-Run-Wechsels bedient die Vorgänger-Revision für wenige
Sekunden noch Requests und hat die Unterschrift/Foto-Spalten im Modell – ein Auftrags-Detail
mit Datenerfassungs-Schritt könnte in diesem Fenster einmalig fehlschlagen. Betroffen ist
ein Nebenpfad ohne Datenwirkung; die Alternative wäre, das Cleanup über zwei Deploys zu
strecken und die tote Achse noch eine Runde mitzuschleppen.

Idempotent und defensiv: jeder Drop prüft erst, ob die Spalte überhaupt existiert.

Revision ID: 081
Revises: 080
Create Date: 2026-07-26
"""
from alembic import op
from sqlalchemy import inspect

revision = '081'
down_revision = '080'
branch_labels = None
depends_on = None

# (Tabelle, Spalte) – alle nachweislich ungelesen.
_DEAD = (
    ("article_process_steps", "require_signature"),
    ("article_process_steps", "signer_ids"),
    ("article_process_steps", "require_photo"),
    ("article_process_steps", "photo_instruction"),
    ("article_process_steps", "transport_mode"),
    ("article_process_steps", "locked"),
    ("inspections", "signature_url"),
    ("inspections", "signed_by"),
    ("inspections", "signed_at"),
    ("inspections", "photo_url"),
)


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for table, col in _DEAD:
        if table not in tables:
            continue
        if col in {c["name"] for c in insp.get_columns(table)}:
            op.drop_column(table, col)


def downgrade() -> None:
    """Bewusst kein Rückbau: die Spalten trugen keine Daten (nie geschrieben) bzw. nur
    abgeschaffte Werte. Sie wiederherzustellen brächte leere Spalten ohne Bedeutung."""
    pass
