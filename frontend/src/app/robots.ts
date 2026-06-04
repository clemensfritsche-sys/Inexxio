import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  if (process.env.NEXT_PUBLIC_ENVIRONMENT === 'development') {
    return {
      rules: { userAgent: '*', disallow: '/' },
    };
  }
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/erp/', '/admin/', '/konto/'],
      },
    ],
    sitemap: `${process.env.NEXT_PUBLIC_APP_URL}/sitemap.xml`,
  };
}
