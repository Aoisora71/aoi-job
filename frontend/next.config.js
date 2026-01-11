/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    // Backend API URL
    // For local development (same machine): use localhost
    // For production/external access: set NEXT_PUBLIC_API_URL=http://65.108.194.239:8003
    // Or use domain: NEXT_PUBLIC_API_URL=http://job.aoi-webstudio.com/api
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003',
  },
  typescript: {
    ignoreBuildErrors: false,
  },
}

module.exports = nextConfig


