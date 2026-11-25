/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    if (process.env.NEXT_PUBLIC_INVENTORY_TRAINING === "1") {
      if (process.env.NEXT_PUBLIC_API_URL || process.env.INTERNAL_API_URL && process.env.INTERNAL_API_URL !== "http://127.0.0.1:8400") {
        throw new Error("Inventory training refuses external API configuration");
      }
      return [{ source: "/api/:path*", destination: "http://127.0.0.1:8400/api/:path*" }];
    }
    return [{ source: "/api/:path*", destination: `${process.env.INTERNAL_API_URL || "http://localhost:8000"}/api/:path*` }];
  },
};
export default nextConfig;
