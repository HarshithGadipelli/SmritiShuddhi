import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cfRoot = resolve(__dirname, "..");
const publicDir = resolve(cfRoot, "public");
const distPagesDir = resolve(cfRoot, "dist-pages");

// 1. Ensure fresh assets + hashed CSS/JS links exist in public/
execFileSync(process.execPath, [resolve(__dirname, "sync-assets.mjs")], { stdio: "inherit" });

// 2. Stage clean Cloudflare Pages bundle (assets + _worker.js + _routes.json)
rmSync(distPagesDir, { recursive: true, force: true });
mkdirSync(distPagesDir, { recursive: true });
cpSync(publicDir, distPagesDir, { recursive: true });

// Bundle TypeScript Worker handler cleanly into Pages Advanced Mode _worker.js
const esbuildCli = resolve(cfRoot, "node_modules", "esbuild", "bin", "esbuild");
execFileSync(
  process.execPath,
  [
    esbuildCli,
    resolve(cfRoot, "src", "index.ts"),
    "--bundle",
    "--format=esm",
    "--platform=browser",
    "--target=es2022",
    `--outfile=${resolve(distPagesDir, "_worker.js")}`,
  ],
  { stdio: "inherit" },
);

// Route only API, WebSocket, favicon, and fallback uploads through _worker.js
writeFileSync(
  resolve(distPagesDir, "_routes.json"),
  JSON.stringify(
    {
      version: 1,
      include: ["/api/*", "/ws", "/favicon.ico", "/static/uploads/*"],
      exclude: [],
    },
    null,
    2,
  ) + "\n",
  "utf8",
);

console.log("[build-pages] Built Cloudflare Pages bundle in cloudflare/dist-pages/ (assets + _worker.js + _routes.json)");
