FROM python:3.12-slim

WORKDIR /app

# System-Bibliotheken für WeasyPrint (PDF-Rendering): Pango + transitiv HarfBuzz/
# FontConfig/FreeType/GLib. Die Marken-Fonts (Inter/Inter Tight) sind im Repo gebündelt
# (app/assets/fonts) und werden per @font-face eingebettet – kein Netzwerk zur Render-Zeit.
# fonts-dejavu-core als Fallback-Glyphen für alles, was Inter nicht abdeckt.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]
