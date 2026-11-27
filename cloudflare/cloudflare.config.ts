import { bindings, defineConfig } from "cf/config";

export default defineConfig({
  accountId: "0e9d9e3453b93f963b60116f28e8368a",
  worker: {
    name: "smritishuddhi",
    compatibilityDate: "2026-09-17",
    entrypoint: "./src/index.ts",
    observability: {
      enabled: true,
    },
    assets: {
      htmlHandling: "auto-trailing-slash",
      notFoundHandling: "none",
      runWorkerFirst: ["/api/*", "/ws", "/favicon.ico", "/static/uploads/*"],
    },
    workersDev: true,
    env: {
      ASSETS: bindings.assets(),
      BACKEND_URL: bindings.text("https://smritishuddhi-889339834867.asia-south1.run.app"),
    },
  },
});
