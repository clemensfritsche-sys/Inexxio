"""Dump the FastAPI OpenAPI schema to backend/openapi.json.

This file is the single source of truth from which the frontend TypeScript API
types are generated (see frontend `npm run generate:types`). Run after changing
any Pydantic request/response schema:

    cd backend && python -m scripts.dump_openapi
"""
import json
from pathlib import Path

from app.main import app

OUT = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote OpenAPI schema → {OUT}")


if __name__ == "__main__":
    main()
