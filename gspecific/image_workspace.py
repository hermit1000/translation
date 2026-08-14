"""Shared paths and artifact naming for game-specific image tools."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ImageWorkspace:
    root: Path
    platform: str = "pc98"

    @property
    def source_root(self) -> Path:
        return self.root / f"jpn-{self.platform}"

    @property
    def image_root(self) -> Path:
        return self.root / f"image-{self.platform}"

    def source(self, relative_path: str | Path) -> Path:
        return self.source_root / relative_path

    def artifacts(self, relative_path: str | Path) -> Path:
        path = self.image_root / relative_path
        path.mkdir(parents=True, exist_ok=True)
        return path


def write_html_report(report: dict[str, Any], output_dir: str | Path) -> None:
    """Write a self-contained gallery for a decoder report."""
    output = Path(output_dir)
    source = str(report.get("source", "image archive"))
    frames = report.get("frames", [])

    def escaped(value: object) -> str:
        return html.escape(str(value), quote=True)

    summary_items = [
        ("source", source),
        ("frames", len(frames)),
        *(
            (key, value)
            for key, value in report.items()
            if key not in {"source", "frames", "incomplete"}
        ),
    ]
    summary = "".join(
        f"<div><strong>{escaped(key)}</strong><code>{escaped(value)}</code></div>"
        for key, value in summary_items
    )

    cards = []
    for position, frame in enumerate(frames):
        files = frame.get("files", {})
        png = files.get("png")
        preview = (
            f'<a href="{escaped(png)}"><img src="{escaped(png)}" '
            f'alt="{escaped(source)} frame {position}"></a>'
            if png
            else "<span>no preview</span>"
        )
        details = "".join(
            f"<dt>{escaped(key)}</dt><dd><code>{escaped(value)}</code></dd>"
            for key, value in frame.items()
            if key != "files"
        )
        links = " / ".join(
            f'<a href="{escaped(filename)}">{escaped(kind)}</a>'
            for kind, filename in files.items()
        )
        details += f"<dt>files</dt><dd>{links}</dd>"
        label = frame.get("offset", frame.get("index", position))
        cards.append(
            "<article>"
            f'<div class="preview">{preview}</div>'
            f'<div class="details"><h2>{position:04d} · {escaped(label)}</h2>'
            f"<dl>{details}</dl></div></article>"
        )

    incomplete = report.get("incomplete")
    warning = ""
    if incomplete:
        fields = " · ".join(
            f"{escaped(key)}: {escaped(value)}" for key, value in incomplete.items()
        )
        warning = (
            '<section class="warning"><strong>Incomplete data</strong>'
            f"<p>{fields}</p></section>"
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped(source)} image report</title>
  <style>
    :root {{ color-scheme: light; --bg:#f5f6f8; --panel:#fff; --ink:#17202a; --muted:#5d6670; --line:#d7dce2; --accent:#9f241d; }}
    * {{ box-sizing:border-box }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 system-ui,sans-serif }}
    header,main {{ padding:24px 32px }} header {{ background:var(--panel); border-bottom:1px solid var(--line) }}
    h1 {{ margin:0; font-size:24px }} h2 {{ margin:0 0 9px; font-size:15px }}
    .summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; margin-bottom:18px }}
    .summary div,.warning {{ padding:12px 14px; background:var(--panel); border:1px solid var(--line); border-radius:8px }}
    .summary strong {{ display:block; color:var(--muted); font-size:12px }}
    .warning {{ margin-bottom:18px; border-left:4px solid var(--accent) }} .warning p {{ margin:5px 0 0 }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:15px }}
    article {{ overflow:hidden; background:var(--panel); border:1px solid var(--line); border-radius:8px }}
    .preview {{ height:250px; display:flex; align-items:center; justify-content:center; padding:10px; background:#202326 }}
    .preview img {{ max-width:100%; max-height:230px; object-fit:contain; image-rendering:pixelated }}
    .details {{ padding:12px 14px 15px }} dl {{ display:grid; grid-template-columns:110px 1fr; gap:5px 8px; margin:0 }}
    dt {{ color:var(--muted) }} dd {{ margin:0; overflow-wrap:anywhere }} code {{ background:#eef1f4; padding:1px 4px; border-radius:3px }}
    a {{ color:#075985; text-decoration:none }} a:hover {{ text-decoration:underline }}
  </style>
</head>
<body>
  <header><h1>{escaped(source)} image report</h1></header>
  <main>
    <section class="summary">{summary}</section>
    {warning}
    <section class="grid">{"".join(cards)}</section>
  </main>
</body>
</html>
"""
    (output / "report.html").write_text(document, encoding="utf-8")


def native_artifact_name(source_name: str, language: str) -> str:
    if language not in {"jpn", "kor"}:
        raise ValueError(f"unsupported language: {language}")
    source = Path(source_name)
    return f"{source.stem}.{language}{source.suffix}"


def offset_stem(offset: int) -> str:
    if offset < 0:
        raise ValueError("offset must not be negative")
    return f"{offset:06X}"


def update_meta(path: Path, **values: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{path}: metadata root must be an object")
        data.update(loaded)
    data.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    return data
