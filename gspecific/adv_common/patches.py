"""Apply non-overlapping ADV replacements using inclusive source offsets."""

import hashlib
import json
from pathlib import Path


def apply_replacements(source: bytes, replacements: list[tuple[int, int, bytes]]) -> bytes:
    ordered = sorted(replacements, key=lambda item: item[0])
    parts = []
    cursor = 0
    for start, end, payload in ordered:
        if not 0 <= start <= end < len(source):
            raise ValueError(f"invalid translation range: {start}-{end}")
        if start < cursor:
            raise ValueError(f"translation ranges overlap at {start:05X}")
        parts.extend((source[cursor:start], payload))
        cursor = end + 1
    parts.append(source[cursor:])
    return b"".join(parts)


def verify_patch_manifest(source: bytes, output: bytes, manifest: dict) -> None:
    """Check declared replacements and every intervening original byte.

    The manifest declares adapter-approved changes, including macro rewrites.
    It does not establish the semantic validity of those declared changes.
    """
    if manifest.get("format") != "adv-patches-v1":
        raise ValueError("unsupported patch manifest format")
    if hashlib.sha256(source).hexdigest() != manifest.get("source_sha256"):
        raise ValueError("patch manifest source hash mismatch")
    cursor = out_cursor = 0
    for patch in manifest["replacements"]:
        if patch.get("kind") not in {"text", "macro", "adapter"}:
            raise ValueError("unknown replacement kind")
        start, end = patch["start"], patch["end"]
        if not cursor <= start <= end < len(source):
            raise ValueError(f"invalid or overlapping patch range: {start}-{end}")
        if source[start:end + 1] != bytes.fromhex(patch["source_hex"]):
            raise ValueError(f"patch source bytes mismatch at {start:05X}")
        unchanged = source[cursor:start]
        if output[out_cursor:out_cursor + len(unchanged)] != unchanged:
            raise ValueError(f"unmodified source bytes changed at {cursor:05X}-{start:05X}")
        out_cursor += len(unchanged)
        payload = bytes.fromhex(patch["replacement_hex"])
        if output[out_cursor:out_cursor + len(payload)] != payload:
            raise ValueError(f"replacement bytes mismatch at source {start:05X}")
        out_cursor += len(payload)
        cursor = end + 1
    if output[out_cursor:] != source[cursor:]:
        raise ValueError(f"unmodified source tail changed at {cursor:05X}")
    if hashlib.sha256(output).hexdigest() != manifest.get("output_sha256"):
        raise ValueError("patch manifest output hash mismatch")


def write_patch_manifest(path: Path, source: bytes, output: bytes,
                         replacements: list[tuple[int, int, bytes]], *,
                         replacement_kinds: dict[tuple[int, int], str] | None = None) -> None:
    manifest = {
        "format": "adv-patches-v1",
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "replacements": [
            {"start": start, "end": end, "source_hex": source[start:end + 1].hex(),
             "replacement_hex": payload.hex(),
             "kind": (replacement_kinds or {}).get((start, end), "text")}
            for start, end, payload in sorted(replacements, key=lambda item: item[0])
        ],
    }
    verify_patch_manifest(source, output, manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
