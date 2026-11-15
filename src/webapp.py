import asyncio
import logging
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Route

from padelbot.core.config import readconfig
from padelbot.core.logger import LOG_FILE, start_logger

logger = logging.getLogger(__name__)


async def get_logs(request):
    try:
        async with aiofiles.open(LOG_FILE, "r") as f:
            return PlainTextResponse(await f.read())
    except Exception as e:
        logger.exception("Error reading log file")
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

        for event in sorted_events:
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
        logger.exception("Error fetching events")
        return JSONResponse({"error": str(e)}, status_code=500)


async def log_viewer(request):
    template = Path(__file__).parent / "templates" / "log_viewer.html"
    html = template.read_text().replace("__VERSION__", request.app.state.version)
    return HTMLResponse(html)


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


async def health(request):
    """Report whether the bot is working, for the container healthcheck."""
    padelbot = getattr(request.app.state, "padelbot", None)
    if padelbot is None:
        return PlainTextResponse("Bot is not running", status_code=503)
    if not padelbot.is_healthy():
        return PlainTextResponse(
            "Bot has not completed a cycle when expected", status_code=503
        )
    return PlainTextResponse("ok")


@asynccontextmanager
async def lifespan(app):
    await start_logger()
    async with aiofiles.open("pyproject.toml", "rb") as f:
        data = tomllib.loads((await f.read()).decode())
    version = data["project"]["version"]
    app.state.version = version
    logger.info(f"Starting padelbot v{version}")
    cfg = readconfig()
    if cfg is None:
        logger.error("Missing configuration")
    else:
        logging.getLogger().setLevel(cfg["logging"]["level"])
        from padelbot.padelbot import PadelBot

        app.state.padelbot = PadelBot(cfg)
        asyncio.create_task(app.state.padelbot.run_forever())
    yield


app = Starlette(
    debug=True,
    routes=[
        Route("/", log_viewer),
        Route("/logs", get_logs),
        Route("/events", get_events),
        Route("/health", health),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webapp:app", host="0.0.0.0", port=8000, reload=True)
