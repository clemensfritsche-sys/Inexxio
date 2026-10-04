// @ts-check
/**
 * Strukturierte Daten (JSON-LD) – generiert aus der Konfiguration, nie von Hand.
 *
 * Eine fehlende Angabe wird WEGGELASSEN statt leer hineingeschrieben.
 * Keine Review- und keine AggregateRating-Angaben – es gibt keine echten.
 */
import { site, contactEmail, isMissing } from '../config/site.mjs';
import { plain } from './text.mjs';

/** @param {string} siteUrl @param {string} [path] */
export const abs = (siteUrl, path = '/') => (path === '/' ? `${siteUrl}/` : `${siteUrl}${path}`);

/**
 * Entfernt leere Werte, damit kein `"legalName": ""` entsteht.
 * @param {any} obj
 * @returns {any}
 */
function clean(obj) {
  if (Array.isArray(obj)) {
    /** @type {any[]} */
    const arr = obj.map(clean).filter((v) => v !== undefined);
    return arr.length ? arr : undefined;
  }
  if (obj && typeof obj === 'object') {
    /** @type {Record<string, any>} */
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      const c = clean(v);
      if (c !== undefined) out[k] = c;
    }
    return Object.keys(out).length ? out : undefined;
  }
  if (typeof obj === 'string') {
    const p = plain(obj);
    return p === '' ? undefined : p;
  }
  return obj;
}

/**
 * Leistungen für hasOfferCatalog – die drei Bereiche mit ihren Unterleistungen, aus
 * derselben Datenstruktur, die auch die Navigation zeigt (site.areas).
 * @param {string} siteUrl
 */
function offerCatalog(siteUrl) {
  return {
    '@type': 'OfferCatalog',
    name: 'Leistungen',
    itemListElement: site.areas.map((a) => ({
      '@type': 'OfferCatalog',
      name: a.label,
      description: a.text,
      url: abs(siteUrl, a.href),
      itemListElement: a.children.map((c) => ({
        '@type': 'Offer',
        itemOffered: { '@type': 'Service', name: `${a.label}: ${c.label}`, description: c.text, url: abs(siteUrl, c.href) },
      })),
    })),
  };
}

/** @param {string} siteUrl */
export function organization(siteUrl) {
  const a = site.address;
  const email = contactEmail();
  return clean({
    '@type': ['Organization', 'LocalBusiness'],
    '@id': `${siteUrl}/#organisation`,
    name: site.brand.name,
    alternateName: [plain(site.brand.full), ...site.brand.alternateNames],
    legalName: isMissing(site.brand.legalName) ? undefined : site.brand.legalName,
    description: site.brand.summary,
    disambiguatingDescription: site.brand.notToConfuse,
    url: abs(siteUrl),
    logo: `${siteUrl}/logo/inexxio-ehemals-hs-steiner.png`,
    image: `${siteUrl}/og/default.png`,
    telephone: site.phone.intl,
    email,
    address: {
      '@type': 'PostalAddress',
      streetAddress: a.street,
      postalCode: a.zip,
      addressLocality: a.city,
      addressRegion: a.canton,
      addressCountry: a.country,
    },
    geo: { '@type': 'GeoCoordinates', latitude: site.geo.lat, longitude: site.geo.lng },
    foundingDate: String(site.history.founded),
    founder: { '@type': 'Person', name: site.people.founder.name },
    knowsAbout: site.seo.knowsAbout,
    hasOfferCatalog: offerCatalog(siteUrl),
    contactPoint: [
      { '@type': 'ContactPoint', telephone: site.phone.intl, contactType: 'customer service', availableLanguage: 'de' },
    ],
    sameAs: site.seo.sameAs,
  });
}

/** @param {string} siteUrl */
export function website(siteUrl) {
  return clean({
    '@type': 'WebSite',
    '@id': `${siteUrl}/#website`,
    url: abs(siteUrl),
    name: plain(site.brand.full),
    inLanguage: 'de-CH',
    publisher: { '@id': `${siteUrl}/#organisation` },
  });
}

/**
 * @param {string} siteUrl
 * @param {{ name: string, path: string }[]} trail  ohne die Startseite
 */
export function breadcrumbs(siteUrl, trail) {
  const all = [{ name: 'Startseite', path: '/' }, ...trail];
  return {
    '@type': 'BreadcrumbList',
    itemListElement: all.map((c, i) => ({ '@type': 'ListItem', position: i + 1, name: plain(c.name), item: abs(siteUrl, c.path) })),
  };
}

/**
 * @param {{ q: string, a: string }[]} faqs – nur, was auch sichtbar auf der Seite steht.
 * Eine Frage, deren Antwort noch ganz offen ist (nur eine Markierung), fällt weg: eine
 * leere Antwort wäre keine – und ohne beantwortete Frage gibt es keinen FAQPage-Knoten.
 */
export function faqPage(faqs) {
  const answered = faqs
    .map((f) => ({ q: plain(f.q), a: plain(f.a) }))
    .filter((f) => f.q && f.a);
  if (!answered.length) return null;
  return {
    '@type': 'FAQPage',
    mainEntity: answered.map((f) => ({
      '@type': 'Question',
      name: f.q,
      acceptedAnswer: { '@type': 'Answer', text: f.a },
    })),
  };
}

/**
 * @param {string} siteUrl
 * @param {{ name: string, serviceType: string, path: string, description: string }} s
 */
export function service(siteUrl, s) {
  return clean({
    '@type': 'Service',
    name: s.name,
    serviceType: s.serviceType,
    description: s.description,
    url: abs(siteUrl, s.path),
    provider: { '@id': `${siteUrl}/#organisation` },
  });
}

/**
 * Produkt «Heukrananlage» (Auftrag 12.4): nur belegbare Angaben – Name, Beschreibung,
 * Hersteller, Bild. Keine Preise, keine Bewertungen.
 * @param {string} siteUrl
 * @param {{ name: string, description: string, path: string }} p
 */
export function product(siteUrl, p) {
  return clean({
    '@type': 'Product',
    name: p.name,
    description: p.description,
    url: abs(siteUrl, p.path),
    image: `${siteUrl}/og/krantechnik.png`,
    brand: { '@type': 'Brand', name: site.brand.name },
    manufacturer: { '@id': `${siteUrl}/#organisation` },
    category: 'Krananlage',
  });
}

/** @param {string} siteUrl */
export function owner(siteUrl) {
  const o = site.people.owner;
  return clean({
    '@type': 'Person',
    '@id': `${siteUrl}/#clemens-fritsche`,
    name: o.name,
    jobTitle: o.role,
    worksFor: { '@id': `${siteUrl}/#organisation` },
    description: o.short,
  });
}

/**
 * @param {string} siteUrl
 * @param {{ title: string, description: string, path: string, published: string, updated: string }} a
 */
export function article(siteUrl, a) {
  return clean({
    '@type': 'Article',
    headline: a.title,
    description: a.description,
    url: abs(siteUrl, a.path),
    mainEntityOfPage: abs(siteUrl, a.path),
    datePublished: a.published,
    dateModified: a.updated,
    inLanguage: 'de-CH',
    author: { '@type': 'Person', name: site.people.owner.name, '@id': `${siteUrl}/#clemens-fritsche` },
    publisher: { '@id': `${siteUrl}/#organisation` },
    image: `${siteUrl}/og/default.png`,
  });
}

/** @param {(object | null)[]} nodes – null fällt weg */
export function graph(nodes) {
  return JSON.stringify({ '@context': 'https://schema.org', '@graph': nodes.filter(Boolean) })
    .replace(/</g, '\\u003c');
}
