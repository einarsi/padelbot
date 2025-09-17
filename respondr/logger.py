import asyncio
import logging
from logging import FileHandler, StreamHandler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue


async def init_logger():
    log = logging.getLogger()
    que = Queue()
    log.addHandler(QueueHandler(que))
    log.setLevel(logging.DEBUG)
    listener = QueueListener(que, FileHandler("app.log"), StreamHandler())
    try:
        listener.start()
        logging.debug("Logger initialized")
        while True:
            await asyncio.sleep(60)
    finally:
        logging.debug("Stopping logger")
        listener.stop()

LOGGER_TASK = None

async def start_logger():
    LOGGER_TASK = asyncio.create_task(init_logger())
    await asyncio.sleep(0)
