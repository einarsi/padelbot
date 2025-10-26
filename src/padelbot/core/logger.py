import asyncio
import logging
import os
from logging import StreamHandler
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from queue import Queue

LOG_FILE = os.path.join("logs", "padelbot.log")


async def init_logger():
    log = logging.getLogger()
    que = Queue()
    log.addHandler(QueueHandler(que))
    log.setLevel(logging.DEBUG)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1024 * 1024, backupCount=5)
    stream_handler = StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S%z"
    )
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    listener = QueueListener(que, file_handler, stream_handler)
    try:
        listener.start()
        while True:
            await asyncio.sleep(60)
    finally:
        logging.debug("Stopping logger")
        listener.stop()


LOGGER_TASK = None


async def start_logger():
    asyncio.create_task(init_logger())
    await asyncio.sleep(0)
