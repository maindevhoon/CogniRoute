/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  env: {
    NEXT_PUBLIC_BACKEND_URL:
      process.env.NEXT_PUBLIC_BACKEND_URL ??
      "https://maindevhoon-cogniroute-backend.hf.space",
  },
};

module.exports = nextConfig;

