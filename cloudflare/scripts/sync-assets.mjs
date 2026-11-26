import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cfRoot = resolve(__dirname, "..");
const repoRoot = resolve(cfRoot, "..");

const sourceStaticDir = resolve(repoRoot, "static");
const publicStaticDir = resolve(cfRoot, "public", "static");
mkdirSync(publicStaticDir, { recursive: true });

// Copy all root static assets (excluding runtime uploads/ which proxy to Cloud Run)
let copiedCount = 0;
for (const entry of readdirSync(sourceStaticDir)) {
  if (entry === "uploads" || entry.startsWith(".")) continue;
  const srcPath = resolve(sourceStaticDir, entry);
  if (statSync(srcPath).isFile()) {
    copyFileSync(srcPath, resolve(publicStaticDir, entry));
    copiedCount++;
  }
}

function shortHash(filePath) {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex").slice(0, 8);
}

const cssHash = shortHash(resolve(publicStaticDir, "dashboard.css"));
const jsHash = shortHash(resolve(publicStaticDir, "dashboard.js"));

// Sync HTML and stamp immutable asset hashes so browsers never keep stale CSS/JS after deploys
const rawHtml = readFileSync(resolve(repoRoot, "templates", "enterprise_dashboard.html"), "utf8");
const stampedHtml = rawHtml
  .replace('href="/static/dashboard.css"', `href="/static/dashboard.css?v=${cssHash}"`)
  .replace('src="/static/dashboard.js"', `src="/static/dashboard.js?v=${jsHash}"`);
writeFileSync(resolve(cfRoot, "public", "index.html"), stampedHtml, "utf8");

writeFileSync(resolve(cfRoot, "public", ".assetsignore"), "*.map\n", "utf8");
writeFileSync(
  resolve(cfRoot, "public", "_headers"),
  [
    "/*",
    "  X-Content-Type-Options: nosniff",
    "  Referrer-Policy: strict-origin-when-cross-origin",
    "",
    "/index.html",
    "  Cache-Control: no-cache, no-store, must-revalidate",
    "",
    "/static/*",
    "  Cache-Control: public, max-age=3600",
    "",
  ].join("\n"),
  "utf8",
);

console.log(`[sync-assets] Synced ${copiedCount} static assets + versioned HTML (?v=${cssHash}/${jsHash}) into cloudflare/public/`);
