/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {},
  async rewrites() {
    return [
      {
        source: "/gateway-api/:path*",
        destination: `${process.env.GATEWAY_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;

