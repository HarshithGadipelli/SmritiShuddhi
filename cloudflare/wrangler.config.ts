import { defineWranglerConfig } from "wrangler/experimental-config";

export default defineWranglerConfig({
  assetsDirectory: "./public",
  tsconfig: "./tsconfig.json",
  build: {
    command: "node scripts/sync-assets.mjs",
  },
});
