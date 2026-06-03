/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    unoptimized: true,
    domains: ['storage.googleapis.com', 'lh3.googleusercontent.com'],
  },
};

module.exports = nextConfig;
