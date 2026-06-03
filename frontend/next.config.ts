import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,

  headers: async () => [
    {
      source: "/(.*)",
      headers: [
        { key: "X-Frame-Options", value: "SAMEORIGIN" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(self), microphone=()" },
      ],
    },
    {
      // Prevent search engine indexing of ERP
      source: "/(app|admin)(.*)",
      headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
    },
  ],

  experimental: {
    typedRoutes: true,
  },
};

export default nextConfig;
