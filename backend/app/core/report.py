"""►►► **Eine Meldestelle für den Betrieb** (Änderungsakte V7). ◄◄◄

Was der Dienst für den Betreiber festhält – nicht für die Person am Bildschirm: «Gmail nicht
erreichbar», «Takt gescheitert», «Anfrage nicht gespeichert». **Jede** solche Meldung geht durch
diese Stelle, mit ihrer Stufe:

* ``info`` – zur Kenntnis (der Start hat Rechtstexte übernommen, eine Anfrage war Spam);
* ``warn`` – etwas ging nicht, der Dienst hilft sich selbst (nächster Versuch, Rückfall);
* ``error`` – etwas ging nicht, und ein Mensch muss es wissen. Dafür meldet Google per Mail
  (Alarm auf Stufe ERROR, einmal eingerichtet: ``infra/setup-meldungen.sh``).

Eine Zeile JSON je Meldung (``severity`` + ``message`` + Angaben) – so liest Cloud Logging die
Stufe. Personendaten gehören nicht in eine Meldung, nur Nummern.
"""

import json
import logging
import sys
from typing import Any


def _emit(severity: str, message: str, facts: dict[str, Any]) -> None:
    line = {"severity": severity, "message": message, **facts}
    print(json.dumps(line, ensure_ascii=False, default=str), file=sys.stdout, flush=True)


def info(message: str, **facts: Any) -> None:
    _emit("INFO", message, facts)


def warn(message: str, **facts: Any) -> None:
    _emit("WARNING", message, facts)


def error(message: str, **facts: Any) -> None:
    _emit("ERROR", message, facts)


class Handler(logging.Handler):
    """Was Bibliotheken über ``logging`` melden, geht durch dieselbe Stelle."""

    def emit(self, record: logging.LogRecord) -> None:
        severity = "ERROR" if record.levelno >= logging.ERROR else (
            "WARNING" if record.levelno >= logging.WARNING else "INFO")
        _emit(severity, record.getMessage(), {"logger": record.name})
