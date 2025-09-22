import asyncio
import pprint
from pathlib import Path

import aiofiles
from dotenv import dotenv_values
from spond import spond


async def write_dump(filename, data):
    dumps = Path("dumps/")
    async with aiofiles.open(dumps / filename, "w") as f:
        await f.write(pprint.pformat(data))


async def main():
    cfg = dotenv_values(".env")
    username = cfg.get("USERNAME")
    password = cfg.get("PASSWORD")
    group_id = cfg.get("GROUP_ID")

    if not username or not password or not group_id:
        raise ValueError(
            "USERNAME, PASSWORD, and GROUP_ID must be set in the .env file"
        )

    s = spond.Spond(username, password)

    group_task = asyncio.create_task(s.get_group(group_id))
    events_task = asyncio.create_task(s.get_events(group_id))

    group = await group_task
    events = await events_task

    write_group = asyncio.create_task(write_dump("group", group))
    if not events:
        raise ValueError("No events found")

    write_event = asyncio.create_task(write_dump("event", events[0]))

    userid = events[0]["recipients"]["group"]["members"][0]["id"]
    person = await s.get_person(userid)
    write_person = asyncio.create_task(write_dump("person", person))

    await asyncio.gather(write_group, write_event, write_person)

    await s.clientsession.close()


if __name__ == "__main__":
    asyncio.run(main())
