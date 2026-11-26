# Deploying Smriti Shuddhi (Zero-Card Hugging Face Spaces + Cloudflare, or Google Cloud Run)

Smriti Shuddhi serves both the **FastAPI backend (`/api/v1/*`, `/ws`)** and the **dashboard UI (`/`, `/static/*`)** from one container backed by **Supabase PostgreSQL + `pgvector`**, with **Cloudflare** in front as the HTTPS CDN/proxy/WebSocket edge.

---

## Option A (Free $0, No Payment Card): Hugging Face Spaces (16 GB RAM Docker) + Cloudflare

### 1. Create the Space on Hugging Face
1. Go to `https://huggingface.co/new-space` (free account, no credit card).
2. Settings:
   - **Space name**: `smriti-shuddhi`
   - **License**: `mit` (or any)
   - **Select the Space SDK**: **Docker** → **Blank**
   - **Space hardware**: **CPU basic · 2 vCPU · 16 GB · FREE**
3. Create the Space and copy its Git URL:
   `https://huggingface.co/spaces/YOUR_HF_USERNAME/smriti-shuddhi`

### 2. Add Secrets in Hugging Face Space Settings
In your Space → **Settings → Variables and secrets → New secret**, copy values from your local `.env`:
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GUARDIAN_API_KEY`
- `THE_NEWS_API_TOKEN`
- `GOOGLE_FACTCHECK_API_KEY`
- `GEMINI_API_KEY`
- `SECRET_KEY` (any strong random passphrase)

Add **Variables** (non-secret):
- `MODEL_BACKEND` = `hybrid_lora`
- `GEMINI_MODEL` = `gemini-3-flash-preview`
- `NEWS_AUTO_SYNC_MINUTES` = `5`
- `ALLOWED_ORIGINS` = `*` *(tighten to your Cloudflare URL once live)*

### 3. Commit & Push Code from PowerShell
Create a Hugging Face Access Token with **Write** permission at `https://huggingface.co/settings/tokens`, then run:
```powershell
cd "c:\Users\Harshith Gadipelli\Documents\Projectlu\SmritiShuddhi"
git add -A
git commit -m "Deploy Smriti Shuddhi v3.0 to Hugging Face Spaces + Cloudflare"
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/smriti-shuddhi
git push hf HEAD:main
```
*(When prompted for password, paste your Hugging Face Write token. Every tracked file is < 6 MB, while `Dockerfile` automatically pre-downloads `bge-small-en-v1.5`, `deberta-v3-xsmall`, and builds initial SISA shards cleanly inside Hugging Face's builder!)*

Wait for the **Building** status badge in your Space to turn **Running**. Your backend + UI will be live at:
`https://YOUR_HF_USERNAME-smriti-shuddhi.hf.space`

### 4. Put Cloudflare Frontend CDN & WebSocket Proxy in Front
1. In **Cloudflare Dashboard → Workers & Pages → Create → Create Worker** (free on `*.workers.dev`, no custom domain required):
2. Edit code and deploy:
   ```javascript
   export default {
     async fetch(request) {
       const url = new URL(request.url);
       url.hostname = "YOUR_HF_USERNAME-smriti-shuddhi.hf.space";
       const proxied = new Request(url.toString(), request);
       return fetch(proxied);
     }
   };
   ```
   *(If you later attach a custom domain to that Worker or proxy DNS, enable **WebSockets: ON** and set a Cache Rule to bypass `/api/*`.)*

---

## Option B: Google Cloud Run + Cloudflare (Requires Billing Account)
1. Ensure billing is linked at `https://console.cloud.google.com/billing/linkedaccount?project=smriti369`.
2. Run:
   ```powershell
   gcloud config set project smriti369
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
   gcloud artifacts repositories create smriti-shuddhi --repository-format=docker --location=asia-south1
   gcloud builds submit --config cloudbuild.yaml
   ```
3. Add the same secrets in **Cloud Run → `smriti-shuddhi-app` → Edit & Deploy New Revision → Variables & Secrets**.
4. Front with Cloudflare `CNAME` (`ghs.googlehosted.com`, **Full (strict)** SSL, **WebSockets ON**, bypass `/api/*` cache) or a Cloudflare Worker proxy.
