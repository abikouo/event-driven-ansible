"""
journald.py
An ansible-events event source plugin that tails systemd journald logs.

Arguments:
    match - return messages that matches this field, see https://www.freedesktop.org/software/systemd/man/systemd.journal-fields.html # noqa

Examples:
    - name: Return severity 6 messages
      ansible.eda.journald:
        match: "PRIORITY=6"

    - name: Return messages when sudo is used
      ansible.eda.journald:
        match: "_EXE=/usr/bin/sudo"

    - name: Return all messages
      ansible.eda.journald:
        match: "ALL"
"""

import asyncio
from typing import Any, Dict

from systemd import journal


async def main(queue: asyncio.Queue, args: Dict[str, Any]):
    delay = args.get("delay", 0)
    match = args.get("match", [])

    if not match:
        return

    journal_stream = journal.Reader()
    journal_stream.seek_tail()

    while True:
        if not match == "ALL":
            journal_stream.add_match(match)
        for entry in journal_stream:
            stream_dict = {}
            for field in entry:
                if field:
                    if (
                        "_TIMESTAMP" not in field
                        and "_BOOT_ID" not in field
                        and "_MACHINE_ID" not in field
                        and "__CURSOR" not in field
                    ):
                        stream_dict[field.lower()] = entry[field]

            await queue.put(dict(journald=stream_dict))
            await asyncio.sleep(delay)

            stream_dict.clear()


if __name__ == "__main__":

    class MockQueue:
        async def put(self, event):
            print(event)

    asyncio.run(main(MockQueue(), {"match": "ALL"}))
