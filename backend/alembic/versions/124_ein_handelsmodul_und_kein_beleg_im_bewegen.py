"""Ein Handelsmodul — und der Verkauf ist kein Ausgang mehr

Drei Umschriften an bestehenden Daten. Keine davon dient der Rückwärtskompatibilität:
sie sorgen dafür, dass die **Entwicklungs**-Datenbank nach dem Umbau nicht bei jeder
Ansicht 400/500 wirft, weil dort Prozesse mit Schlüsseln stehen, die es nicht mehr gibt.

1 · ``beschaffen`` → ``einkauf``
   ``Beschaffen`` und ``Verkauf`` waren zwei Klassen, die sich in **vier Werten** und in
   keiner Zeile Verhalten unterschieden – und alle vier beschreiben die **Richtung**,
   nicht den Modultyp. Geblieben ist eine Klasse (``domain/modules.Handel``) mit zwei
   Einträgen; der Schlüssel heisst jetzt wie die Kachel in der Palette.

2 · Belege in einem **Bewegen**-Modul werden stillgelegt
   Ein Transport, den eine Spedition fährt, ist ein Einkauf – und den setzt man als
   eigenes Modul in die Kette, nicht als Beleg *in* das Bewegen-Modul. Der Beleg dort war
   ein Modul im Modul; er hat keinen Leser mehr (``Module.trades`` ist beim Bewegen
   ``False``), und eine Zeile ohne Leser, die trotzdem «es wurde eingekauft» behauptet,
   ist schlimmer als keine. Sie wird darum **weich** gelöscht: die Vergangenheit bleibt
   lesbar, der Beleg ist nur nicht mehr *der* Beleg dieses Schritts.

3 · ``orders.end_status`` zieht nach
   Der Endzustand ist keine Konstante mehr, sondern eine **Ableitung** aus dem Prozess
   (``Module.rest_status_for`` → ``process._rest_status``). Ein Auftrag, der ein
   Verkaufsmodul enthält, ruht in ``verkauft``; alle übrigen bleiben unberührt.

Und die Statuszeile der Stücke: ein Verkauf war ein **Ausgang** und schrieb ``verkauft``
an seinem eigenen Schritt. Diese Stücke bleiben, wie sie sind – sie *sind* verkauft. Was
sich ändert, gilt ab dem nächsten Auftrag.

Revision ID: 124
Revises: 123
"""

from alembic import op

revision = "124"
down_revision = "123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1 · Der Modulschlüssel — an **beiden** Definitionsorten (Artikel-Vorlage und
    #     Auftrags-Prozess). Nur einen umzuschreiben hiesse, dass die Hälfte der
    #     Definitionen auf einen Typ zeigt, den die Registry nicht kennt.
    for table in ("process_steps", "article_process_steps"):
        op.execute(
            f"UPDATE {table} SET module_type = 'einkauf' "
            f"WHERE module_type = 'beschaffen'"
        )

    # 2 · Belege, die an einem Bewegen-Modul hängen. ``is_active = false`` ist der
    #     Soft-Delete des Hauses; der partielle Unique-Index (Migration 119) lässt
    #     danebenstehende inaktive Zeilen ausdrücklich zu.
    op.execute(
        "UPDATE purchases SET is_active = false "
        "WHERE is_active AND step_id IN ("
        "  SELECT id FROM process_steps WHERE module_type = 'bewegen')"
    )

    # 3 · Der Endzustand der Aufträge, die verkaufen. Dieselbe Ableitung wie im Dienst,
    #     nur einmalig für den Bestand: enthält der Prozess ein Verkaufsmodul, ruht das
    #     Stück am Ende in ``verkauft``.
    op.execute(
        "UPDATE orders SET end_status = 'verkauft' WHERE id IN ("
        "  SELECT DISTINCT order_id FROM process_steps WHERE module_type = 'verkauf')"
    )


def downgrade() -> None:
    # Der Weg zurück schreibt nur den Schlüssel um. Die stillgelegten Belege bleiben
    # stillgelegt und der Endzustand bleibt stehen: beide sind Aussagen über die
    # Vergangenheit, und die wieder umzudrehen hiesse, sie zu erfinden.
    for table in ("process_steps", "article_process_steps"):
        op.execute(
            f"UPDATE {table} SET module_type = 'beschaffen' "
            f"WHERE module_type = 'einkauf'"
        )
