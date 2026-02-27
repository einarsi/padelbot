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
        logging.error(f"Error fetching events: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def log_viewer(request):
    import os

    template_path = os.path.join(
        os.path.dirname(__file__), "templates", "log_viewer.html"
    )
    with open(template_path, "r") as f:
        html = f.read()
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
