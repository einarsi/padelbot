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


async def get_events(request):
    """Return upcoming events with participant information."""
    from starlette.responses import JSONResponse

    padelbot = (
        request.app.state.padelbot if hasattr(request.app.state, "padelbot") else None
    )
    if padelbot is None:
        return JSONResponse({"error": "PadelBot is not initialized."}, status_code=500)

    try:
        # Use cached events from padelbot instead of fetching again
        events = padelbot.events
        events_data = []

        # Sort events by startTimestamp in ascending order
        sorted_events = sorted(
            events.upcoming, key=lambda e: e.get("startTimestamp", "")
        )

        for event in sorted_events[:5]:  # Show only next 5 upcoming events
            members = event.get("recipients", {}).get("group", {}).get("members", [])
            member_map = {m["id"]: f"{m['firstName']} {m['lastName']}" for m in members}

            responses = event.get("responses", {})

            events_data.append(
                {
                    "heading": event.get("heading", "Untitled"),
                    "startTimestamp": event.get("startTimestamp", ""),
                    "endTimestamp": event.get("endTimestamp", ""),
                    "accepted": [
                        member_map.get(id, id)
                        for id in responses.get("acceptedIds", [])
                    ],
                    "unconfirmed": [
                        member_map.get(id, id)
                        for id in responses.get("unconfirmedIds", [])
                    ],
                    "waitinglist": [
                        member_map.get(id, id)
                        for id in responses.get("waitinglistIds", [])
                    ],
                    "declined": [
                        member_map.get(id, id)
                        for id in responses.get("declinedIds", [])
                    ],
                    "unanswered": [
                        member_map.get(id, id)
                        for id in responses.get("unansweredIds", [])
                    ],
                }
            )

        return JSONResponse({"events": events_data})
    except Exception as e:
        logging.error(f"Error fetching events: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def log_viewer(request):
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PadelBot Log and Event Viewer</title>
    <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
    <style>
        body { font-family: monospace; background: #222; color: #eee; margin: 0; padding: 1em; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1em; }
        .container { display: flex; gap: 1em; }
        .log-section { flex: 2; }
        .events-section { flex: 1; background: #111; padding: 1em; border-radius: 8px; max-height: 80vh; overflow-y: auto; }
        #log { white-space: pre-wrap; background: #111; padding: 1em; border-radius: 8px; max-height: 80vh; overflow-y: auto; font-size: 1em; }
        .timestamp { color: #7fd8ff; }
        .level-info { color: #b2ffb2; }
        .level-warning { color: #ffe066; }
        .level-error { color: #ff7f7f; }
        .level-debug { color: #b2b2ff; }
        .refresh-btn { padding: 0.5em 1em; background: #444; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
        .refresh-btn:hover { background: #666; }
        .event-card { background: #1a1a1a; padding: 0.8em; margin-bottom: 1em; border-radius: 4px; border-left: 3px solid #7fd8ff; }
        .event-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.5em; }
        .event-title { color: #7fd8ff; font-weight: bold; font-size: 1.1em; }
        .event-time { color: #999; font-size: 0.9em; }
        .participant-section { margin-top: 0.5em; }
        .participant-label { color: #b2ffb2; font-weight: bold; font-size: 0.95em; }
        .participant-list { color: #ddd; font-size: 0.85em; margin-left: 0.5em; }
        .accepted-list { font-size: 1em; }
        .waitinglist-label { color: #ffe066; }
        .declined-label { color: #ff7f7f; }
        .unanswered-label { color: #999; }
    </style>
</head>
<body>
    <div id="app">
        <div class="header">
            <h2 style="margin: 0;">PadelBot Log and Event Viewer</h2>
            <button class="refresh-btn" @click="fetchLog">Refresh Log</button>
        </div>
        <div class="container">
            <div class="log-section">
                <div id="log" ref="logDiv">
                    <div v-html="colorizedLog"></div>
                </div>
            </div>
            <div class="events-section">
                <div v-if="events.length === 0" style="color: #999;">Loading...</div>
                <div v-for="event in events" :key="event.heading" class="event-card">
                    <div class="event-header">
                        <div class="event-title">{{ event.heading }}</div>
                        <div class="event-time">{{ formatTime(event.startTimestamp, event.endTimestamp) }}</div>
                    </div>
                    <div class="participant-section" v-if="event.accepted.length > 0">
                        <div class="participant-label">Accepted ({{ event.accepted.length }}):</div>
                        <div class="participant-list accepted-list">
                            <div v-for="(name, index) in event.accepted" :key="index">
                                {{ index + 1 }}. {{ name }}
                            </div>
                        </div>
                    </div>
                    <div class="participant-section" v-if="event.waitinglist.length > 0">
                        <div class="participant-label waitinglist-label">Waitinglist ({{ event.waitinglist.length }}):</div>
                        <div class="participant-list">{{ event.waitinglist.join(', ') }}</div>
                    </div>
                    <div class="participant-section" v-if="event.unconfirmed.length > 0">
                        <div class="participant-label">Unconfirmed ({{ event.unconfirmed.length }}):</div>
                        <div class="participant-list">{{ event.unconfirmed.join(', ') }}</div>
                    </div>
                    <div class="participant-section" v-if="event.declined.length > 0">
                        <div class="participant-label declined-label">Declined ({{ event.declined.length }}):</div>
                        <div class="participant-list">{{ event.declined.join(', ') }}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
    const { createApp } = Vue;
    createApp({
        data() {
            return { log: '', events: [] }
        },
        computed: {
            colorizedLog() {
                if (!this.log) return '';
                // Split log into lines and colorize
                return this.log.split('\\n').map(line => {
                    // Match timestamp with timezone offset (e.g., 2025-09-26 12:34:56+0100 or 2025-09-26 12:34:56+01:00)
                    const tsMatch = line.match(/^(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}[+-]\\d{2}:?\\d{2})/);
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
            this.fetchEvents();
            setInterval(this.fetchLog, 10000);
            setInterval(this.fetchEvents, 30000);
            this.$nextTick(this.scrollToBottom);
        },
        updated() {
            this.$nextTick(this.scrollToBottom);
        },
        methods: {
            fetchLog() {
                fetch('/logs').then(r => r.text()).then(t => { this.log = t });
            },
            fetchEvents() {
                fetch('/events').then(r => r.json()).then(data => { 
                    if (data.events) this.events = data.events; 
                }).catch(e => console.error('Error fetching events:', e));
            },
            scrollToBottom() {
                const logDiv = this.$refs.logDiv;
                if (logDiv) {
                    logDiv.scrollTop = logDiv.scrollHeight;
                }
            },
            formatTime(startTimestamp, endTimestamp) {
                if (!startTimestamp) return '';
                const startDate = new Date(startTimestamp);
                
                const weekday = startDate.toLocaleDateString('en-GB', { weekday: 'short' });
                const year = startDate.getFullYear();
                const month = String(startDate.getMonth() + 1).padStart(2, '0');
                const day = String(startDate.getDate()).padStart(2, '0');
                const startTime = startDate.toLocaleTimeString('en-GB', { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
                
                let result = `${weekday} ${year}-${month}-${day} ${startTime}`;
                
                if (endTimestamp) {
                    const endDate = new Date(endTimestamp);
                    const endTime = endDate.toLocaleTimeString('en-GB', { 
                        hour: '2-digit', 
                        minute: '2-digit' 
                    });
                    result += `-${endTime}`;
                }
                
                return result;
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
        Route("/events", get_events),
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
