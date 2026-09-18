/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== 'production';

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // Isolate next dev from next build. Production .next only has hashed CSS
  // (/_next/static/css/*.css). next dev expects /_next/static/css/app/layout.css.
  // Sharing one cache makes the stylesheet 404 as HTML and the UI looks unstyled.
  distDir: isDev ? '.next-dev' : '.next',
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production',
  },
};

module.exports = nextConfig;