"""Local CLI, one-shot or interactive, streaming by default."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from . import __version__
from .agent import build_agent, tool_specs
from .config import settings
from .http import close_clients

# Colour only when attached to a terminal, so piped output stays clean.
_COLOUR = sys.stdout.isatty()


def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m" if _COLOUR else text


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _COLOUR else text


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="karachi-agent",
        description="Ask a Strands agent about Karachi: weather, air quality, prayer times.",
        epilog='Example: karachi-agent "Is it a good evening for a walk at Seaview?"',
    )
    parser.add_argument(
        "prompt", nargs="*", help="Question to ask. Omit for an interactive session."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="Print the tool schemas Strands generated from the Python, then exit.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Wait for the full answer instead of streaming tokens.",
    )
    parser.add_argument(
        "--trace", action="store_true", help="Show each tool call as the model makes it."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.show_tools:
        print(json.dumps(tool_specs(), indent=2))
        return 0

    config = settings()
    if args.debug:
        print(_dim(f"model={config.model_id} region={config.region}"), file=sys.stderr)

    try:
        agent = build_agent(config)
    except Exception as exc:
        print(f"Could not start the agent: {exc}", file=sys.stderr)
        print(
            "Check your AWS credentials and that the model is enabled in this region.",
            file=sys.stderr,
        )
        return 1

    try:
        if args.prompt:
            return asyncio.run(_ask(agent, " ".join(args.prompt), args))
        return asyncio.run(_repl(agent, args))
    except KeyboardInterrupt:
        print()
        return 130
    finally:
        close_clients()


async def _ask(agent: Any, prompt: str, args: argparse.Namespace) -> int:
    if args.no_stream:
        result = await agent.invoke_async(prompt)
        print(str(result).strip())
        return 0

    seen_tools: set[str] = set()
    wrote_anything = False
    async for event in agent.stream_async(prompt):
        if args.trace:
            _trace_tool(event, seen_tools)
        chunk = event.get("data") if isinstance(event, dict) else None
        if chunk:
            print(chunk, end="", flush=True)
            wrote_anything = True
    if wrote_anything:
        print()
    return 0


def _trace_tool(event: dict[str, Any], seen: set[str]) -> None:
    """Announce each distinct tool invocation once, on stderr."""
    current = event.get("current_tool_use") if isinstance(event, dict) else None
    if not isinstance(current, dict):
        return
    key = str(current.get("toolUseId") or current.get("name"))
    if key in seen:
        return
    seen.add(key)
    print(_dim(f"  -> {current.get('name')}({current.get('input') or ''})"), file=sys.stderr)


async def _repl(agent: Any, args: argparse.Namespace) -> int:
    print(_bold("Karachi city agent") + _dim("  (ctrl-d or 'exit' to quit)"))
    print(_dim("Try: aaj mausam kaisa hai? / how's the air right now? / when is Maghrib?"))
    while True:
        try:
            line = input(_bold("\n> ")).strip()
        except EOFError:
            print()
            return 0
        if not line:
            continue
        if line.lower() in {"exit", "quit", ":q"}:
            return 0
        await _ask(agent, line, args)


if __name__ == "__main__":
    raise SystemExit(main())
