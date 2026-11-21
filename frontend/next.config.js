/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  poweredByHeader: false,
  // Statischer Export – es gibt keinen Server, der Bilder optimieren könnte.
  images: { unoptimized: true },
};

module.exports = nextConfig;
