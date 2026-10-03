// @ts-check
/**
 * Strukturierte Daten (JSON-LD) – generiert aus der Konfiguration, nie von Hand.
 *
 * Eine fehlende Angabe (Markierung) wird WEGGELASSEN statt als Text hineingeschrieben:
 * ein JSON-LD mit «[[PLATZHALTER …]]» wäre eine falsche Aussage über das Unternehmen.
 * Im Modus «live» gibt es keine Markierungen mehr (der Build bricht sonst vorher ab).
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

/** Leistungen für hasOfferCatalog – dieselbe Navigation, die der Header zeigt. */
function offerCatalog() {
  const items = [];
  for (const group of site.nav) {
    if (!group.children) continue;
    for (const c of group.children) {
      items.push({ '@type': 'Offer', itemOffered: { '@type': 'Service', name: `${group.label}: ${c.label}`, description: c.text } });
    }
  }
  items.push({ '@type': 'Offer', itemOffered: { '@type': 'Service', name: 'Service-Abo für Krane mit digitalem Kranbuch' } });
  return { '@type': 'OfferCatalog', name: 'Leistungen', itemListElement: items };
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
    description:
      'Prüfung, Wartung, Reparatur und Modernisierung von Krananlagen und Fahrmischern aller Marken in der Ostschweiz. Seit 1982 in Tuttwil-Wängi TG.',
    disambiguatingDescription: site.brand.notToConfuse,
    url: abs(siteUrl),
    logo: `${siteUrl}/logo/inexxio-wortmarke.png`,
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
    openingHoursSpecification: site.hours.spec.map((h) => ({
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: h.days.map((d) => `https://schema.org/${d}`),
      opens: h.opens,
      closes: h.closes,
    })),
    areaServed: [
      ...site.area.served.map((name) => ({ '@type': 'AdministrativeArea', name: `Kanton ${name}` })),
      { '@type': 'Country', name: 'Schweiz' },
    ],
    foundingDate: String(site.history.founded),
    founder: { '@type': 'Person', name: site.people.founder.name },
    knowsAbout: site.seo.knowsAbout,
    hasOfferCatalog: offerCatalog(),
    contactPoint: [
      { '@type': 'ContactPoint', telephone: site.phone.intl, contactType: 'customer service', areaServed: 'CH', availableLanguage: 'de' },
      site.features.pikett
        ? { '@type': 'ContactPoint', telephone: site.pikett.intl, contactType: 'emergency', areaServed: 'CH', availableLanguage: 'de' }
        : undefined,
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

/** @param {{ q: string, a: string }[]} faqs – nur, was auch sichtbar auf der Seite steht. */
export function faqPage(faqs) {
  return {
    '@type': 'FAQPage',
    mainEntity: faqs.map((f) => ({
      '@type': 'Question',
      name: plain(f.q),
      acceptedAnswer: { '@type': 'Answer', text: plain(f.a) },
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
    areaServed: site.area.served.map((name) => ({ '@type': 'AdministrativeArea', name: `Kanton ${name}` })),
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
    sameAs: isMissing(o.linkedin) ? undefined : [o.linkedin],
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

/** @param {object[]} nodes */
export function graph(nodes) {
  return JSON.stringify({ '@context': 'https://schema.org', '@graph': nodes.filter(Boolean) })
    .replace(/</g, '\\u003c');
}
