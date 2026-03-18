/**
 * Holoarchive Image Proxy Worker
 *
 * Proxies card images from hololive-official-cardgame.com to bypass
 * hotlink protection. The official site blocks requests from external
 * Referer headers — this Worker fetches images server-side (no Referer)
 * and forwards them to the browser.
 *
 * Deploy:
 *   1. In Cloudflare dashboard → Workers & Pages → Create → Worker
 *   2. Paste this code
 *   3. Deploy — you'll get a URL like https://holo-img.YOUR-ACCOUNT.workers.dev
 *   4. Update IMAGE_PROXY_BASE in index.html to point to your Worker URL
 *
 * Usage:
 *   https://your-worker.workers.dev/?url=https://hololive-official-cardgame.com/wp-content/images/cardlist/hBP01/hBP01-007_OSR.png
 */

const ALLOWED_HOST = "hololive-official-cardgame.com";
const CACHE_TTL    = 60 * 60 * 24 * 7; // 7 days — card images never change

export default {
  async fetch(request, env, ctx) {
    const url    = new URL(request.url);
    const imgUrl = url.searchParams.get("url");

    // ── Validate ────────────────────────────────────────────────────────
    if (!imgUrl) {
      return new Response("Missing ?url= parameter", { status: 400 });
    }

    let parsed;
    try {
      parsed = new URL(imgUrl);
    } catch {
      return new Response("Invalid URL", { status: 400 });
    }

    // Only proxy images from the official hololive OCG site
    if (!parsed.hostname.endsWith(ALLOWED_HOST)) {
      return new Response("Not allowed", { status: 403 });
    }

    // Only allow image paths
    if (!parsed.pathname.includes("/cardlist/")) {
      return new Response("Not a card image path", { status: 403 });
    }

    // ── Cache check ──────────────────────────────────────────────────────
    const cache     = caches.default;
    const cacheKey  = new Request(imgUrl);
    let   cached    = await cache.match(cacheKey);
    if (cached) return cached;

    // ── Fetch from origin ────────────────────────────────────────────────
    // Fetch WITHOUT a Referer header — this is what bypasses hotlink protection
    let originResp;
    try {
      originResp = await fetch(imgUrl, {
        headers: {
          "User-Agent":      "Mozilla/5.0 (compatible; Holoarchive/1.0)",
          "Accept":          "image/png,image/webp,image/*,*/*",
          "Accept-Encoding": "gzip, deflate, br",
          // No Referer header — intentional
        },
        cf: {
          cacheEverything: true,
          cacheTtl: CACHE_TTL,
        },
      });
    } catch (e) {
      return new Response("Failed to fetch image: " + e.message, { status: 502 });
    }

    if (!originResp.ok) {
      return new Response(`Origin returned ${originResp.status}`, {
        status: originResp.status,
      });
    }

    // ── Build response with CORS + cache headers ─────────────────────────
    const contentType = originResp.headers.get("Content-Type") || "image/png";
    const imageData   = await originResp.arrayBuffer();

    const response = new Response(imageData, {
      status: 200,
      headers: {
        "Content-Type":                contentType,
        "Cache-Control":               `public, max-age=${CACHE_TTL}`,
        "Access-Control-Allow-Origin": "*",
        "X-Proxied-By":                "Holoarchive",
      },
    });

    // Store in cache
    ctx.waitUntil(cache.put(cacheKey, response.clone()));

    return response;
  },
};
