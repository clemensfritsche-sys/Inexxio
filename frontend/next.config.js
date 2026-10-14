/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  poweredByHeader: false,
  // `output: 'export'` liefert statisch aus – es gibt keinen Server, der Bilder
  // optimieren könnte. `domains` ist ersatzlos entfallen: es nannte den GCS-Bucket
  // des entfernten Dokument-Moduls, und das Google-Profilbild kommt ohnehin über ein
  // schlichtes <img>, nicht über next/image.
  images: { unoptimized: true },
};

module.exports = nextConfig;
