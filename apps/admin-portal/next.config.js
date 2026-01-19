/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@fec-saas/ui', '@fec-saas/api-client', '@fec-saas/types'],
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
};

module.exports = nextConfig;
