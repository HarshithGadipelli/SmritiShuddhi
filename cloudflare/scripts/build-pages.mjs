import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cfRoot = resolve(__dirname, "..");
const publicDir = resolve(cfRoot, "public");
const distPagesDir = resolve(cfRoot, "dist-pages");
const require = createRequire(import.meta.url);

// 1. Ensure fresh assets + hashed CSS/JS links exist in public/
execFileSync(process.execPath, [resolve(__dirname, "sync-assets.mjs")], { stdio: "inherit" });

// 2. Stage clean Cloudflare Pages bundle (assets + _worker.js + _routes.json)
rmSync(distPagesDir, { recursive: true, force: true });
mkdirSync(distPagesDir, { recursive: true });
cpSync(publicDir, distPagesDir, { recursive: true });

const entryTs = resolve(cfRoot, "src", "index.ts");
const outWorkerJs = resolve(distPagesDir, "_worker.js");

let bundled = false;
try {
  const esbuildPath = require.resolve("esbuild", {
    paths: [cfRoot, resolve(cfRoot, "node_modules", "wrangler")],
  });
  const esbuild = require(esbuildPath);
  await esbuild.build({
    entryPoints: [entryTs],
    bundle: true,
    format: "esm",
    platform: "browser",
    target: "es2022",
    outfile: outWorkerJs,
  });
  bundled = true;
} catch (err) {
  console.warn(`[build-pages] esbuild JS API fallback to TypeScript compiler: ${err?.message || err}`);
}

if (!bundled) {
  const ts = require(require.resolve("typescript", { paths: [cfRoot] }));
  const tsSource = readFileSync(entryTs, "utf8");
  const out = ts.transpileModule(tsSource, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
      removeComments: false,
    },
  });
  writeFileSync(outWorkerJs, out.outputText, "utf8");
}

// 3. Route only API, WebSocket, favicon, and fallback uploads through _worker.js
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
