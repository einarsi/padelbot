#!/usr/bin/env python3
"""Generate the naco-backend API client from a filtered OpenAPI spec.

Only the paths listed in ALLOWED_PATHS are included in the generated client,
to avoid exposing the full API surface of the closed-source backend.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_SPEC = REPO_ROOT.parent / "naco" / "openapi.json"
OUTPUT_DIR = REPO_ROOT / "naco-backend-client"

ALLOWED_PATHS = [
    "/api/v1/users",  # POST: create user
]


def filter_spec(spec: dict) -> dict:
    """Return a copy of the spec containing only ALLOWED_PATHS and referenced schemas."""
    filtered = {k: v for k, v in spec.items() if k != "paths"}
    filtered["paths"] = {
        path: methods
        for path, methods in spec.get("paths", {}).items()
        if path in ALLOWED_PATHS
    }

    # Collect only the schemas referenced by the filtered paths
    refs: set[str] = set()
    _collect_refs(filtered["paths"], refs)
    schemas = spec.get("components", {}).get("schemas", {})

    # Resolve transitive references
    resolved: set[str] = set()
    while refs - resolved:
        for ref in list(refs - resolved):
            resolved.add(ref)
            if ref in schemas:
                _collect_refs(schemas[ref], refs)

    if "components" in spec:
        filtered["components"] = {
            k: v for k, v in spec["components"].items() if k != "schemas"
        }
        filtered["components"]["schemas"] = {
            name: schema for name, schema in schemas.items() if name in refs
        }

    return filtered


def _collect_refs(obj: object, refs: set[str]) -> None:
    """Recursively collect all $ref schema names."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if ref.startswith("#/components/schemas/"):
                refs.add(ref.split("/")[-1])
        for v in obj.values():
            _collect_refs(v, refs)
    elif isinstance(obj, list):
        for item in obj:
            _collect_refs(item, refs)


def main() -> None:
    if not OPENAPI_SPEC.exists():
        print(f"OpenAPI spec not found at {OPENAPI_SPEC}", file=sys.stderr)
        sys.exit(1)

    with open(OPENAPI_SPEC) as f:
        spec = json.load(f)

    filtered = filter_spec(spec)
    print(
        f"Filtered spec: {len(filtered['paths'])} paths, "
        f"{len(filtered.get('components', {}).get('schemas', {}))} schemas"
    )

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        print(f"Removed existing {OUTPUT_DIR.name}/")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(filtered, tmp, indent=2)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "openapi_python_client",
                "generate",
                "--path",
                tmp_path,
                "--meta",
                "uv",
                "--output-path",
                str(OUTPUT_DIR),
            ],
            cwd=REPO_ROOT,
        )
    finally:
        Path(tmp_path).unlink()

    if result.returncode != 0:
        print("Client generation failed.", file=sys.stderr)
        sys.exit(result.returncode)

    print(f"Client generated at {OUTPUT_DIR.name}/")


if __name__ == "__main__":
    main()
