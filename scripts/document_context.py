# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "markitdown[pdf,docx,pptx,xlsx,xls]>=0.1,<0.2",
# ]
# ///

"""Convert and inspect documents without printing unnecessary content."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path


DEFAULT_MAX_CHARS = 12_000

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def local_file(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"not a local file: {path}")
    return path


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^\w.-]+", "-", path.stem, flags=re.UNICODE).strip("-.")
    return stem[:80] or "document"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def markdown_text(result: object) -> str:
    for attribute in ("markdown", "text_content"):
        value = getattr(result, attribute, None)
        if isinstance(value, str):
            return value
    raise RuntimeError("MarkItDown returned no Markdown text")


def convert(args: argparse.Namespace) -> None:
    from markitdown import MarkItDown

    source: Path = args.source
    cache_dir = (
        Path(args.cache_dir).expanduser().resolve()
        if args.cache_dir
        else Path(tempfile.gettempdir()) / "codex-markitdown-cache"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(source)
    output = cache_dir / f"{safe_stem(source)}-{digest[:12]}.md"
    cache_hit = output.exists() and not args.force

    if not cache_hit:
        converter = MarkItDown(enable_plugins=False)
        result = converter.convert_local(str(source))
        text = markdown_text(result)
        temporary = output.with_suffix(".md.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(output)

    text = output.read_text(encoding="utf-8")
    warnings: list[str] = []
    if len(text.strip()) < 500:
        warnings.append("Extraction is sparse; inspect the original for scans or visual content.")
    print(
        json.dumps(
            {
                "source": str(source),
                "markdown": str(output),
                "cache_hit": cache_hit,
                "sha256": digest,
                "characters": len(text),
                "lines": text.count("\n") + 1,
                "warnings": warnings,
            },
            ensure_ascii=False,
        )
    )


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def headings(args: argparse.Namespace) -> None:
    matches = []
    for number, line in enumerate(read_lines(args.markdown), start=1):
        if re.match(r"^#{1,6}\s+", line):
            matches.append(f"{number}: {line}")
            if len(matches) >= args.limit:
                break
    print("\n".join(matches) if matches else "No Markdown headings found.")


def merge_windows(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def search(args: argparse.Namespace) -> None:
    lines = read_lines(args.markdown)
    terms = [term.casefold() for term in args.terms]
    hit_lines = [
        index
        for index, line in enumerate(lines)
        if any(term in line.casefold() for term in terms)
    ][: args.max_matches]
    windows = merge_windows(
        [
            (max(0, index - args.context), min(len(lines), index + args.context + 1))
            for index in hit_lines
        ]
    )
    if not windows:
        print(json.dumps({"matches": 0, "terms": args.terms}, ensure_ascii=False))
        return

    output: list[str] = []
    used = 0
    for window_number, (start, end) in enumerate(windows, start=1):
        block = [f"--- excerpt {window_number}, lines {start + 1}-{end} ---"]
        block.extend(f"{line_number + 1}: {lines[line_number]}" for line_number in range(start, end))
        rendered = "\n".join(block) + "\n"
        if used + len(rendered) > args.max_chars:
            break
        output.append(rendered)
        used += len(rendered)
    print("\n".join(output).rstrip())
    print(json.dumps({"matched_lines": len(hit_lines), "characters_returned": used}, ensure_ascii=False))


def slice_markdown(args: argparse.Namespace) -> None:
    lines = read_lines(args.markdown)
    start = args.start_line - 1
    if start >= len(lines):
        print(json.dumps({"start_line": args.start_line, "end_of_file": True}, ensure_ascii=False))
        return

    selected: list[str] = []
    used = 0
    end = start
    while end < len(lines):
        rendered = f"{end + 1}: {lines[end]}\n"
        if selected and used + len(rendered) > args.max_chars:
            break
        selected.append(rendered)
        used += len(rendered)
        end += 1
    print("".join(selected).rstrip())
    print(
        json.dumps(
            {
                "start_line": start + 1,
                "last_line": end,
                "next_line": end + 1,
                "end_of_file": end >= len(lines),
                "characters_returned": used,
            },
            ensure_ascii=False,
        )
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    convert_parser = commands.add_parser("convert", help="Convert a local document to cached Markdown")
    convert_parser.add_argument("source", type=local_file)
    convert_parser.add_argument("--cache-dir")
    convert_parser.add_argument("--force", action="store_true")
    convert_parser.set_defaults(function=convert)

    headings_parser = commands.add_parser("headings", help="Print a bounded heading index")
    headings_parser.add_argument("markdown", type=local_file)
    headings_parser.add_argument("--limit", type=int, default=200)
    headings_parser.set_defaults(function=headings)

    search_parser = commands.add_parser("search", help="Print bounded excerpts matching plain-text terms")
    search_parser.add_argument("markdown", type=local_file)
    search_parser.add_argument("terms", nargs="+")
    search_parser.add_argument("--context", type=int, default=4)
    search_parser.add_argument("--max-matches", type=int, default=8)
    search_parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    search_parser.set_defaults(function=search)

    slice_parser = commands.add_parser("slice", help="Print one bounded sequential slice")
    slice_parser.add_argument("markdown", type=local_file)
    slice_parser.add_argument("--start-line", type=int, default=1)
    slice_parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    slice_parser.set_defaults(function=slice_markdown)

    return root


def main() -> None:
    args = parser().parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
