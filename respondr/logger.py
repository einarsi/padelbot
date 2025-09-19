import asyncio
import logging
import os
from datetime import datetime
from logging import FileHandler, StreamHandler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue


async def init_logger():
    log = logging.getLogger()
    que = Queue()
    log.addHandler(QueueHandler(que))
    log.setLevel(logging.DEBUG)
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"app_{timestamp}.log"
    file_handler = FileHandler(os.path.join(log_dir, log_filename))
    stream_handler = StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    listener = QueueListener(que, file_handler, stream_handler)
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
