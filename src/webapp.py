import asyncio
import logging
import tomllib

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Route

from padelbot.core.config import readconfig
from padelbot.core.logger import LOG_FILE, start_logger


async def get_logs(request):
    try:
        with open(LOG_FILE, "r") as f:
            return PlainTextResponse(f.read())
    except Exception as e:
        return PlainTextResponse(f"Error: {e}", status_code=500)


async def log_viewer(request):
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PadelBot Log Viewer</title>
    <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
    <style>
        body { font-family: monospace; background: #222; color: #eee; }
        #log { white-space: pre-wrap; background: #111; padding: 1em; border-radius: 8px; max-height: 80vh; overflow-y: auto; font-size: 1em; }
        .timestamp { color: #7fd8ff; }
        .level-info { color: #b2ffb2; }
        .level-warning { color: #ffe066; }
        .level-error { color: #ff7f7f; }
        .level-debug { color: #b2b2ff; }
        .refresh-btn { margin-bottom: 1em; padding: 0.5em 1em; background: #444; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
        .refresh-btn:hover { background: #666; }
    </style>
</head>
<body>
    <div id="app">
        <h2>PadelBot Log Viewer</h2>
        <button class="refresh-btn" @click="fetchLog">Refresh Log</button>
        <div id="log" ref="logDiv">
            <div v-html="colorizedLog"></div>
        </div>
    </div>
    <script>
    const { createApp } = Vue;
    createApp({
        data() {
            return { log: '' }
        },
        computed: {
            colorizedLog() {
                if (!this.log) return '';
                // Split log into lines and colorize
                return this.log.split('\\n').map(line => {
                    // Match timestamp (e.g., 2025-09-26 12:34:56)
                    const tsMatch = line.match(/^(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})/);
                    let html = line;
                    if (tsMatch) {
                        html = html.replace(tsMatch[1], `<span class='timestamp'>${tsMatch[1]}</span>`);
                    }
                    // Match log level
                    if (/INFO/.test(line)) {
                        html = html.replace(/INFO/, `<span class='level-info'>INFO</span>`);
                    } else if (/WARNING/.test(line)) {
                        html = html.replace(/WARNING/, `<span class='level-warning'>WARNING</span>`);
                    } else if (/ERROR/.test(line)) {
                        html = html.replace(/ERROR/, `<span class='level-error'>ERROR</span>`);
                    } else if (/DEBUG/.test(line)) {
                        html = html.replace(/DEBUG/, `<span class='level-debug'>DEBUG</span>`);
                    }
                    return html;
                }).join('<br>');
            }
        },
        mounted() {
            this.fetchLog();
            setInterval(this.fetchLog, 2000);
            this.$nextTick(this.scrollToBottom);
        },
        updated() {
            this.$nextTick(this.scrollToBottom);
        },
        methods: {
            fetchLog() {
                fetch('/logs').then(r => r.text()).then(t => { this.log = t });
            },
            scrollToBottom() {
                const logDiv = this.$refs.logDiv;
                if (logDiv) {
                    logDiv.scrollTop = logDiv.scrollHeight;
                }
            }
        }
    }).mount('#app');
    </script>
</body>
</html>
        """
    return HTMLResponse(content=html)


async def show_logs(request):
    padelbot = (
        request.app.state.padelbot if hasattr(request.app.state, "padelbot") else None
    )
    if padelbot is None or not hasattr(padelbot, "cfg"):
        return PlainTextResponse("PadelBot is not initialized.", status_code=500)
    else:
        # Example: return logging level and bot status
        info = f"Logging level: {padelbot.cfg['logging']['level']}\nBot initialized: {type(padelbot).__name__}"
        return PlainTextResponse(info)


app = Starlette(
    debug=True,
    routes=[
        Route("/", log_viewer),
        Route("/logs", get_logs),
    ],
)


@app.on_event("startup")
async def startup():
    await start_logger()
    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]
    logging.info(f"Starting padelbot v{version}")
    cfg = readconfig()
    if cfg is None:
        logging.error("Missing configuration")
        return
    logging.getLogger().setLevel(cfg["logging"]["level"])
    from padelbot.padelbot import PadelBot

    app.state.padelbot = PadelBot(cfg)
    # Run padelbot.run() in the background
    asyncio.create_task(run_padelbot(app))


async def run_padelbot(app):
    while True:
        await app.state.padelbot.run()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webapp:app", host="0.0.0.0", port=8000, reload=True)
