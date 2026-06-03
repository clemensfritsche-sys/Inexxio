/** @type {import('next').NextConfig} */
const withNextIntl = require('next-intl/plugin')('./src/i18n.ts');

const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['storage.googleapis.com', 'lh3.googleusercontent.com'],
  },
};

module.exports = withNextIntl(nextConfig);
