FROM python:3.12-slim

WORKDIR /app

# Abhängigkeiten aus der Sperrdatei, jede mit Prüfsumme: derselbe Stand bei jedem Build,
# und ein verändertes Paket bricht den Build ab (requirements.lock, aus requirements.txt
# erzeugt – infra/README.md).
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# IP→Land für die Kontaktdaten der Website (DB-IP Lite, monatlich neu). VOR `COPY . .`
# und abhängig nur vom Skript und vom Monat (`GEOIP_MONTH`, JJJJ-MM, setzt der Deploy):
# eine Code-Änderung baut die Schicht nicht neu, ein neuer Monat schon – derselbe Monat
# ergibt dieselbe Tabelle. Ohne Monat oder ist er noch nicht veröffentlicht, wählt das
# Skript selbst (laufender, sonst voriger Monat). Scheitert der Download, läuft der Dienst
# weiter – die Website zeigt dann die Angaben des Betreibers –, aber laut im Build-Log.
ARG GEOIP_MONTH=""
COPY scripts/build_geoip.py scripts/build_geoip.py
RUN { [ -n "$GEOIP_MONTH" ] \
      && python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" \
           "https://download.db-ip.com/free/dbip-country-lite-$GEOIP_MONTH.csv.gz" \
           "/tmp/dbip-country-lite-$GEOIP_MONTH.csv.gz" \
      && python scripts/build_geoip.py "/tmp/dbip-country-lite-$GEOIP_MONTH.csv.gz"; } \
 || python scripts/build_geoip.py \
 || echo "WARNING: GeoIP-Tabelle nicht gebaut – das Land des Besuchers bleibt unbekannt."; \
    rm -f /tmp/dbip-country-lite-*.csv.gz

COPY . .

RUN chmod +x start.sh \
 && useradd --system --uid 10001 --home /app inexxio \
 && chown -R inexxio /app
USER inexxio

EXPOSE 8080
CMD ["./start.sh"]
