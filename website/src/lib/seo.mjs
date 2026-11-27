// @ts-check
/**
 * Strukturierte Daten (JSON-LD) – generiert aus der Konfiguration, nie von Hand.
 *
 * Eine fehlende Angabe wird WEGGELASSEN statt leer hineingeschrieben.
 * Keine Review- und keine AggregateRating-Angaben – es gibt keine echten.
 */
import { site, contactEmail } from '../config/site.mjs';
import { plain } from './text.mjs';
import { t } from '../i18n/t.mjs';
import { currentLang, publishedLanguages } from '../config/languages.mjs';

const T = t('ui', { offers: 'Leistungen', home: 'Startseite' });

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
    name: T.offers,
    itemListElement: site.areas.map((a) => ({
      '@type': 'OfferCatalog',
      name: a.label,
      description: a.text,
      url: abs(siteUrl, a.href),
      // Ein Bereich ohne Unterseiten (Sonderlösungen) bietet sich selbst an.
      itemListElement: (a.children.length ? a.children : [{ label: a.label, text: a.text, href: a.href }]).map((c) => ({
        '@type': 'Offer',
        itemOffered: { '@type': 'Service', name: c.href === a.href ? a.label : `${a.label}: ${c.label}`, description: c.text, url: abs(siteUrl, c.href) },
      })),
    })),
  };
}

/** Wo wir im Einsatz sind (`site.seo.areaServed`, Ländercodes). */
const areaServed = () => site.seo.areaServed.map((/** @type {string} */ c) => ({ '@type': 'Country', name: c }));

/** @param {string} siteUrl */
export function organization(siteUrl) {
  const a = site.address;
  const email = contactEmail();
  return clean({
    '@type': ['Organization', 'LocalBusiness'],
    '@id': `${siteUrl}/#organisation`,
    name: site.brand.name,
    alternateName: [plain(site.brand.full), ...site.brand.alternateNames],
    legalName: site.brand.legalName,
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
    areaServed: areaServed(),
    knowsAbout: site.seo.knowsAbout,
    hasOfferCatalog: offerCatalog(siteUrl),
    contactPoint: [
      { '@type': 'ContactPoint', telephone: site.phone.intl, contactType: 'customer service', areaServed: site.seo.areaServed, availableLanguage: publishedLanguages().map((l) => l.code) },
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
    name: site.brand.name,
    description: site.brand.summary,
    inLanguage: currentLang().locale,
    publisher: { '@id': `${siteUrl}/#organisation` },
  });
}

/**
 * Die Seite selbst – verknüpft sie über `@id` mit Website, Firma und Brotkrumen, mit ihrem Stand
 * (`dateModified`, dasselbe Datum wie `lastmod` der Sitemap) und ihrem Vorschaubild.
 * `type`: AboutPage, ContactPage, CollectionPage … (src/lib/pages.ts), sonst WebPage.
 * Name und Beschreibung sind die des Kopfs (<title>, Meta-Description) – nichts Zusätzliches.
 * @param {string} siteUrl
 * @param {{ path: string, name: string, description: string, updated?: string, type?: string, breadcrumb: boolean, image: string }} p
 */
export function webPage(siteUrl, p) {
  const url = abs(siteUrl, p.path);
  return clean({
    '@type': p.type ?? 'WebPage',
    '@id': `${url}#webpage`,
    url,
    name: p.name,
    description: p.description,
    inLanguage: currentLang().locale,
    isPartOf: { '@id': `${siteUrl}/#website` },
    publisher: { '@id': `${siteUrl}/#organisation` },
    dateModified: p.updated,
    breadcrumb: p.breadcrumb ? { '@id': `${url}#breadcrumb` } : undefined,
    primaryImageOfPage: { '@type': 'ImageObject', url: p.image, width: 1200, height: 630 },
  });
}

/**
 * @param {string} siteUrl
 * @param {{ name: string, path: string }[]} trail  ohne die Startseite
 */
export function breadcrumbs(siteUrl, trail) {
  const all = [{ name: T.home, path: '/' }, ...trail];
  return {
    '@type': 'BreadcrumbList',
    '@id': `${abs(siteUrl, all[all.length - 1].path)}#breadcrumb`,
    itemListElement: all.map((c, i) => ({ '@type': 'ListItem', position: i + 1, name: plain(c.name), item: abs(siteUrl, c.path) })),
  };
}

/**
 * @param {{ q: string, a: string }[]} faqs – nur, was auch sichtbar auf der Seite steht.
 * Eine Frage ohne Antwort fällt weg: eine leere Antwort wäre keine – und ohne beantwortete
 * Frage gibt es keinen FAQPage-Knoten.
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
    areaServed: areaServed(),
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
 * @param {{ title: string, description: string, path: string, published: string, updated: string, image?: string }} a
 * `image`: die Zeichnung des Artikels (volle Adresse); dazu immer das Vorschaubild.
 */
export function article(siteUrl, a) {
  return clean({
    '@type': 'Article',
    headline: a.title,
    description: a.description,
    url: abs(siteUrl, a.path),
    mainEntityOfPage: { '@id': `${abs(siteUrl, a.path)}#webpage` },
    datePublished: a.published,
    dateModified: a.updated,
    inLanguage: currentLang().locale,
    author: { '@type': 'Person', name: site.people.owner.name, '@id': `${siteUrl}/#clemens-fritsche` },
    publisher: { '@id': `${siteUrl}/#organisation` },
    image: [a.image, `${siteUrl}/og/default.png`].filter(Boolean),
  });
}

/** @param {(object | null)[]} nodes – null fällt weg */
export function graph(nodes) {
  return JSON.stringify({ '@context': 'https://schema.org', '@graph': nodes.filter(Boolean) })
    .replace(/</g, '\\u003c');
}
