from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional

import httpx

BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")


async def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        response = await client.post(path, json=payload)
        response.raise_for_status()
        return response.json()


async def api_get(path: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        response = await client.get(path)
        response.raise_for_status()
        return response.json()


def render_response(body: Dict[str, Any], verbose: bool = False, trace: bool = False) -> None:
    print(f"\nSession: {body.get('session_id')}")
    if body.get("message_id"):
        print(f"Message: {body['message_id']}")
    if body.get("answer"):
        print(f"\nAnswer:\n{body['answer']}")

    result_sets = body.get("result_sets") or []
    if result_sets:
        print("\nData:")
        for result_set in result_sets:
            items = result_set.get("items") or []
            print(f"- {result_set.get('key', 'results')} from {result_set.get('server_id')} ({len(items)} rows)")
            for item in items[:3]:
                print(f"  {format_item(item)}")
            if len(items) > 3:
                print(f"  ... {len(items) - 3} more rows")

    explain = body.get("explain") or []
    if explain:
        print("\nExplain:")
        for line in explain:
            print(f"- {line}")
    if verbose:
        print("\nResult Sets:")
        print(json.dumps(body.get("result_sets", []), indent=2, default=str))
    if trace:
        print("\nTrace:")
        print(json.dumps(body.get("trace", {}), indent=2, default=str))


def format_item(item: Dict[str, Any]) -> str:
    pairs = []
    for key, value in item.items():
        if isinstance(value, dict):
            continue
        if isinstance(value, list):
            pairs.append(f"{key}=[{len(value)} items]")
        else:
            pairs.append(f"{key}={value}")
    return ", ".join(pairs) if pairs else json.dumps(item, default=str)


async def start_session(args):
    body = await api_post(
        "/api/v1/sessions",
        {"user_id": args.user_id, "title": args.title, "source_ids": args.source_ids or []},
    )
    print(json.dumps(body, indent=2, default=str))


async def list_sources(_args):
    body = await api_get("/api/v1/sources")
    print(json.dumps(body, indent=2, default=str))


async def ask_once(args):
    body = await api_post(
        "/api/v1/chat",
        {
            "session_id": args.session_id,
            "user_id": args.user_id,
            "message": args.message,
            "source_ids": args.source_ids or [],
        },
    )
    render_response(body, verbose=args.verbose, trace=args.trace)


async def resume_session(args):
    body = await api_get(f"/api/v1/sessions/{args.session_id}")
    print(json.dumps(body, indent=2, default=str))


async def repl(args):
    session_id = args.session_id
    source_ids = list(args.source_ids or [])
    if not session_id:
        session = await api_post(
            "/api/v1/sessions",
            {"user_id": args.user_id, "title": "CLI REPL", "source_ids": source_ids},
        )
        session_id = session["session_id"]
        print(f"Started session {session_id}")

    last_message_id: Optional[str] = None
    while True:
        try:
            text = input("chat> ").strip()
        except EOFError:
            break

        if not text:
            continue
        if text == "/exit":
            break
        if text == "/sources":
            body = await api_get("/api/v1/sources")
            print(json.dumps(body, indent=2, default=str))
            continue
        if text.startswith("/use "):
            source_ids = [part.strip() for part in text[5:].split(",") if part.strip()]
            print(f"Active sources: {source_ids}")
            continue
        if text == "/history":
            body = await api_get(f"/api/v1/sessions/{session_id}/messages")
            print(json.dumps(body, indent=2, default=str))
            continue
        if text == "/trace":
            if not last_message_id:
                print("No trace available yet.")
                continue
            body = await api_get(f"/api/v1/runs/{last_message_id}")
            print(json.dumps(body, indent=2, default=str))
            continue

        body = await api_post(
            "/api/v1/chat",
            {"session_id": session_id, "user_id": args.user_id, "message": text, "source_ids": source_ids},
        )
        last_message_id = body.get("message_id")
        render_response(body, verbose=args.verbose, trace=args.trace)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI chat client for backend testing")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--user-id", required=True)
    start.add_argument("--title")
    start.add_argument("--source-ids", nargs="*", default=[])
    start.set_defaults(handler=start_session)

    resume = subparsers.add_parser("resume")
    resume.add_argument("--session-id", required=True)
    resume.set_defaults(handler=resume_session)

    sources = subparsers.add_parser("sources")
    sources.set_defaults(handler=list_sources)

    ask = subparsers.add_parser("ask")
    ask.add_argument("--session-id", required=True)
    ask.add_argument("--user-id", required=True)
    ask.add_argument("--message", required=True)
    ask.add_argument("--source-ids", nargs="*", default=[])
    ask.add_argument("--verbose", action="store_true")
    ask.add_argument("--trace", action="store_true")
    ask.set_defaults(handler=ask_once)

    repl_cmd = subparsers.add_parser("repl")
    repl_cmd.add_argument("--user-id", required=True)
    repl_cmd.add_argument("--session-id")
    repl_cmd.add_argument("--source-ids", nargs="*", default=[])
    repl_cmd.add_argument("--verbose", action="store_true")
    repl_cmd.add_argument("--trace", action="store_true")
    repl_cmd.set_defaults(handler=repl)

    return parser


async def _main_async():
    parser = build_parser()
    args = parser.parse_args()
    await args.handler(args)


def main():
    import asyncio

    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
