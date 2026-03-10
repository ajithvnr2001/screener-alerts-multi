export default {
    async scheduled(event, env, ctx) {
        // The cron trigger fires here in JS world, avoiding the Pyodide NoGilError.
        // We just forward the request to the Python worker's existing manual trigger endpoint.
        const url = "https://screener-alerts-multi.quoteviral.workers.dev/api/trigger";

        const request = new Request(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "User-Agent": "Cloudflare-Cron-Trigger"
            }
        });

        // Fire and forget (waitUntil ensures it finishes even if wrapper returns)
        ctx.waitUntil(fetch(request));
    }
};
