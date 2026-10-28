FROM python:3.12-slim

WORKDIR /app

# Abhängigkeiten aus der Sperrdatei, jede mit Prüfsumme: derselbe Stand bei jedem Build,
# und ein verändertes Paket bricht den Build ab (requirements.lock, aus requirements.txt
# erzeugt – infra/README.md).
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY . .

# IP→Land für die Kontaktdaten der Website (DB-IP Lite). Scheitert der Download, läuft der
# Dienst weiter – die Website zeigt dann die Angaben des Betreibers –, aber laut im Build-Log.
RUN python scripts/build_geoip.py \
 || echo "WARNING: GeoIP-Tabelle nicht gebaut – das Land des Besuchers bleibt unbekannt."

RUN chmod +x start.sh \
 && useradd --system --uid 10001 --home /app inexxio \
 && chown -R inexxio /app
USER inexxio

EXPOSE 8080
CMD ["./start.sh"]
