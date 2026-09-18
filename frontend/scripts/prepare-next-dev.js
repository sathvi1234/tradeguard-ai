/**
 * next build writes hashed CSS only. next dev expects /_next/static/css/app/layout.css.
 * If a production .next cache is left behind (or mixed into the dev cache), the
 * stylesheet 404s as HTML and the UI renders as unstyled markup.
 */
const fs = require('fs');
const path = require('path');

function isProductionCssCache(root) {
  const devCss = path.join(root, 'static', 'css', 'app', 'layout.css');
  if (fs.existsSync(devCss)) return false;
  const cssDir = path.join(root, 'static', 'css');
  if (!fs.existsSync(cssDir)) return false;
  const hashed = fs.readdirSync(cssDir).some((name) => name.endsWith('.css'));
  const buildId = fs.existsSync(path.join(root, 'BUILD_ID'));
  return hashed || buildId;
}

function clearCache(root) {
  if (!fs.existsSync(root) || !isProductionCssCache(root)) return false;
  fs.rmSync(root, { recursive: true, force: true });
  return true;
}

const frontend = path.join(__dirname, '..');
const cleared = ['.next', '.next-dev'].filter((dir) => clearCache(path.join(frontend, dir)));
if (cleared.length) {
  console.log('Cleared production Next.js CSS cache (' + cleared.join(', ') + ') so Tailwind can compile in next dev.');
}
