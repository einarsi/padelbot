"""Turn the Spond dumps from `tools/dump_data.py` into anonymised test data.

Reads `dumps/event` and `dumps/group` and writes `tests/test_data/spond_event.json`
and `tests/test_data/spond_group.json`. The structure of the data is kept; every
value that could identify a person or the group is replaced:

- IDs become counters. The same ID gets the same replacement in both files.
- Names and e-mail addresses become `First1 Last1 <player1@example.com>`.
- All other strings become "redacted", unless their key is in KEEP_KEYS.
- Coordinates and integer timestamps become 0.
- Members are trimmed to those who answered the event, plus a few who did not.

The script refuses to write the files if an original value outside KEEP_KEYS
survives. Review the output before committing it, in particular the kept keys.
"""

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DUMPS = REPO_ROOT / "dumps"
OUTPUT = REPO_ROOT / "tests" / "test_data"

# Strings under these keys are kept as they are. None of them is personal.
KEEP_KEYS = {
    "heading",
    "type",
    "visibility",
    "autoReminderType",
    "response",
    "startTimestamp",
    "endTimestamp",
}
UNANSWERED_MEMBERS_TO_KEEP = 3
ID_PATTERN = re.compile(r"[0-9A-F]{32}")
# Integers this large are timestamps, e.g. when the group was created.
EPOCH_MILLISECONDS = 10**11


class Anonymiser:
    def __init__(self) -> None:
        self.ids: dict[str, int] = {}

    def _number(self, original_id: str) -> int:
        return self.ids.setdefault(original_id, len(self.ids) + 1)

    def _id(self, value: str) -> str | None:
        """The replacement for `value` if it is an ID, otherwise None."""
        if ID_PATTERN.fullmatch(value):
            return f"{self._number(value):032X}"
        return None

    def anonymise(self, value: Any, key: str = "", person: int | None = None) -> Any:
        if isinstance(value, dict):
            if person is None and "firstName" in value and "id" in value:
                person = self._number(value["id"])
            return {
                self._id(k) or k: self.anonymise(v, k, person) for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.anonymise(v, key, person) for v in value]
        if isinstance(value, float):
            return 0.0
        if isinstance(value, int) and value >= EPOCH_MILLISECONDS:
            return 0
        if not isinstance(value, str):
            return value
        if replacement := self._id(value):
            return replacement
        if key in KEEP_KEYS:
            return value
        if person is not None and key == "firstName":
            return f"First{person}"
        if person is not None and key == "lastName":
            return f"Last{person}"
        if person is not None and key == "email":
            return f"player{person}@example.com"
        return "redacted"


def trim_members(event: dict, group: dict) -> None:
    responses = event["responses"]
    responses["unansweredIds"] = responses["unansweredIds"][:UNANSWERED_MEMBERS_TO_KEEP]
    keep = {member_id for ids in responses.values() for member_id in ids}
    for members_owner in (event["recipients"]["group"], group):
        members_owner["members"] = [
            m for m in members_owner["members"] if m["id"] in keep
        ]


def strings(value: Any, key: str = "") -> set[str]:
    """All string values in `value`, except those under KEEP_KEYS."""
    if isinstance(value, dict):
        return {s for k, v in value.items() for s in strings(v, k)}
    if isinstance(value, list):
        return {s for v in value for s in strings(v, key)}
    if isinstance(value, str) and key not in KEEP_KEYS:
        return {value}
    return set()


def main() -> None:
    originals = {
        name: ast.literal_eval((DUMPS / name).read_text())
        for name in ("event", "group")
    }
    secrets = strings(originals)

    trim_members(originals["event"], originals["group"])
    anonymiser = Anonymiser()
    outputs = {name: anonymiser.anonymise(data) for name, data in originals.items()}

    leaked = secrets & strings(outputs)
    if leaked:
        print(
            f"Refusing to write: {len(leaked)} original value(s) survived.",
            file=sys.stderr,
        )
        sys.exit(1)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        path = OUTPUT / f"spond_{name}.json"
        path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
