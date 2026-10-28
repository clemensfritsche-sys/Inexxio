# Das Frontend für die LOKALE Entwicklung (`docker-compose.yml`: `npm run dev`, Quelltext
# als Volume). Ausgeliefert wird es nie als Container: `next build` ist ein statischer
# Export (`out/`), den der Deploy nach Firebase Hosting legt – einen Node-Server gibt es
# dort nicht.
FROM node:22-alpine

WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000

# Ohne `website/dist` (nicht im Bild) sind Kopf und Fuss Platzhalter (scripts/site-shell.mjs).
CMD ["npm", "run", "dev"]
