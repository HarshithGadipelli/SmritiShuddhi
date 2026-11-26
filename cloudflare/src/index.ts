interface Env {
  ASSETS: Fetcher;
  BACKEND_URL: string;
}

const DEFAULT_BACKEND_ORIGIN = "https://smriti-shuddhi-app-889339834867.asia-south1.run.app";

function resolveBackendUrl(requestUrl: URL, env: Env): URL {
  const baseOrigin = (env.BACKEND_URL || DEFAULT_BACKEND_ORIGIN).replace(/\/+$/, "");
  return new URL(`${baseOrigin}${requestUrl.pathname}${requestUrl.search}`);
}

function buildUpstreamHeaders(request: Request, requestUrl: URL): Headers {
  const headers = new Headers(request.headers);
  // Let Workers runtime set Host/SNI to upstreamUrl.host while forwarding original host/proto.
  headers.delete("host");
  headers.set("X-Forwarded-Host", requestUrl.host);
  headers.set("X-Forwarded-Proto", requestUrl.protocol.replace(":", ""));
  return headers;
}

function applySecurityHeaders(response: Response, pathname: string): Response {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  if (pathname === "/" || pathname.endsWith(".html")) {
    headers.set("Cache-Control", "no-cache");
  } else if (pathname.startsWith("/static/")) {
    headers.set("Cache-Control", "public, max-age=3600");
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const requestUrl = new URL(request.url);
    const { pathname } = requestUrl;

    // Proxy API requests and WebSocket upgrades to Google Cloud Run backend.
    if (pathname.startsWith("/api/") || pathname === "/ws") {
      const upstreamUrl = resolveBackendUrl(requestUrl, env);
      const upstreamHeaders = buildUpstreamHeaders(request, requestUrl);

      try {
        const upstreamRequest = new Request(upstreamUrl.toString(), {
          method: request.method,
          headers: upstreamHeaders,
          body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
          redirect: "manual",
        });
        const upstreamResponse = await fetch(upstreamRequest);
        // Return WebSocket 101 Switching Protocols response directly untouched.
        if (upstreamResponse.status === 101) {
          return upstreamResponse;
        }
        return upstreamResponse;
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return Response.json(
          {
            detail: "Backend service temporarily unreachable from edge proxy",
            error: message,
          },
          { status: 502 },
        );
      }
    }

    if (pathname === "/favicon.ico") {
      return new Response(null, { status: 204 });
    }

    const assetResponse = await env.ASSETS.fetch(request);
    return applySecurityHeaders(assetResponse, pathname);
  },
};
