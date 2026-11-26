import { copyFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cfRoot = resolve(__dirname, "..");
const repoRoot = resolve(cfRoot, "..");

const publicStaticDir = resolve(cfRoot, "public", "static");
mkdirSync(publicStaticDir, { recursive: true });

copyFileSync(
  resolve(repoRoot, "templates", "enterprise_dashboard.html"),
  resolve(cfRoot, "public", "index.html"),
);
copyFileSync(
  resolve(repoRoot, "static", "dashboard.css"),
  resolve(publicStaticDir, "dashboard.css"),
);
copyFileSync(
  resolve(repoRoot, "static", "dashboard.js"),
  resolve(publicStaticDir, "dashboard.js"),
);

// Prevent Vite from failing on missing entry module if index.html stays in public/
writeFileSync(resolve(cfRoot, "public", ".assetsignore"), "*.map\n", "utf8");
writeFileSync(
  resolve(cfRoot, "public", "_headers"),
  [
    "/*",
    "  X-Content-Type-Options: nosniff",
    "  Referrer-Policy: strict-origin-when-cross-origin",
    "",
    "/static/*",
    "  Cache-Control: public, max-age=3600",
    "",
  ].join("\n"),
  "utf8",
);

console.log("[sync-assets] Synced dashboard HTML, CSS, JS, and _headers into cloudflare/public/");
