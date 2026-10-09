import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow a separate build directory for isolated UI smoke tests.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Authenticated pages use request-time rendering and Ant Design's SSR registry.
};

export default nextConfig;
