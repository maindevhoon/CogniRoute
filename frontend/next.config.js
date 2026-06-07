/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_BACKEND_URL:
      process.env.NEXT_PUBLIC_BACKEND_URL ??
      (process.env.VERCEL ? "/_/backend" : "http://localhost:8000"),
  },
};

module.exports = nextConfig;
