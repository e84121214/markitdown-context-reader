---
name: markitdown-context-reader
description: Convert, search, and summarize local PDF, Word, PowerPoint, Excel, HTML, and text documents with MarkItDown while keeping model context small. Use for document inspection, question answering, or repeated research; do not use for layout-preserving edits or artifact creation.
---

# MarkItDown Context Reader

Use local computation for conversion and filtering. Do not put a whole source file or generated Markdown file into model context unless the task genuinely requires reading all of it.

## Route the request

- For a short, one-off document, read it directly when conversion and indexing would add more overhead than they save.
- For a long document, repeated questions, or multiple related documents, convert once and reuse the content-addressed cache.
- For a complete summary, read bounded slices sequentially, summarize each slice, then synthesize. This controls context size but does not eliminate the tokens needed to understand the full document.
- For scans, diagrams, charts, equations, or layout-dependent claims, treat extracted Markdown as incomplete. Inspect the relevant original pages or images with the appropriate PDF/image tool.
- Defer document editing and layout-sensitive creation to the relevant document, PDF, presentation, or spreadsheet workflow.

## Local helper

Run `scripts/document_context.py` with `uv`; its inline dependency declaration supplies MarkItDown. The first run may need to download packages and therefore may require user approval or network access.

```powershell
uv run scripts/document_context.py convert "C:\path\report.pdf"
uv run scripts/document_context.py headings "C:\path\cached-report.md"
uv run scripts/document_context.py search "C:\path\cached-report.md" "keyword" "second term"
uv run scripts/document_context.py slice "C:\path\cached-report.md" --start-line 1
```

Resolve `scripts/document_context.py` relative to this skill directory, not the user's working directory.

The `convert` command prints only compact JSON metadata and never the document body. It uses a SHA-256 content key, so unchanged input reuses the cached Markdown. By default, cache files go under the operating-system temporary directory; pass `--cache-dir` when durable project-local reuse is wanted.

## Context-efficient workflow

1. Validate that the source is a local, trusted file. Do not pass URLs or untrusted paths to MarkItDown.
2. Convert only when routing above favors conversion. Record the returned Markdown path.
3. Use `headings` for structure or `search` for targeted questions. Start with the user's own terms and likely synonyms.
4. Read only the returned excerpts. Broaden terms or context gradually when evidence is insufficient.
5. Cite page markers, headings, and line numbers when present. State when Markdown extraction cannot verify visual or layout-dependent information.
6. For a complete summary, use `slice` with successive `next_line` values. Keep compact notes for each slice and synthesize only after reaching `end_of_file: true`.

## Token discipline

- Never print or read an entire generated Markdown file merely to inspect it.
- Do not pipe MarkItDown output to the terminal. Use the helper's cached output file.
- Keep `search` defaults unless more context is necessary; increase limits incrementally.
- Avoid loading the helper script source during ordinary use. Execute it directly.
- Reuse cached conversions and prior compact notes when the source hash is unchanged.
- If the extracted text is unexpectedly sparse or omits a referenced visual, inspect the original rather than assuming the information is absent.
