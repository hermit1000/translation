#!/usr/bin/env python3
"""Encode one Dracula ADV98 MES using its info/lang JSON pair."""

from typing import Any

from gspecific.dob2.adv98_mes.encode_mes import main as encode_main


_ORIGINAL_TRANSLATION = "_dracula_original_translation"
DRACULA_LINE_WIDTH = 41  # shared encoder uses width - 1 as the real 40-char line
DISPLAY_LINE_CELLS = DRACULA_LINE_WIDTH - 1
KEEP_ORIGINAL = "@keep"
SECTIONS = ("dialogue_groups", "overlay_texts")


def _entries(lang: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        entry.get("offset"): entry
        for section in SECTIONS
        for entry in lang.get(section, [])
        if isinstance(entry, dict) and entry.get("offset")
    }


def _speaker_layout(value: str) -> tuple[str, str, int] | None:
    """Return (speaker, body, body column) for a translated speaker line."""
    # Japanese corner quotes are ordinary quotation marks in overlay text
    # (for example, newspaper excerpts), not speaker labels.  Treating a
    # long ``「...」`` sentence as a speaker makes display wrapping grow the
    # continuation indent dramatically and can stall encoding.  Speaker
    # labels in these MES files use square brackets only.
    for opening, closing in (("[", "]"), ("［", "］")):
        if not value.startswith(opening):
            continue
        closing_index = value.find(closing, len(opening))
        if closing_index < 0:
            return None
        speaker = value[: closing_index + 1]
        body = value[closing_index + 1 :].lstrip(" \u3000")
        return speaker, body, len(speaker) + (1 if body else 0)
    return None


def _wrap_display_text(
    value: str, *, initial_indent: int = 0, continuation_indent: int = 0
) -> str:
    """Wrap a translated display line at Dracula's 40-cell window width."""
    output: list[str] = []
    cells = 0
    if initial_indent:
        output.append(" " * initial_indent)
        cells = initial_indent

    for character in value:
        if cells >= DISPLAY_LINE_CELLS:
            output.append(" " * (DISPLAY_LINE_CELLS - cells))
            output.append(" " * continuation_indent)
            cells = continuation_indent
            # A source line may contribute one ordinary separator space at the
            # boundary. It is not part of the translated content.
            if character in (" ", "\u3000"):
                continue
        output.append(character)
        cells += 1
    return "".join(output)


def _set_translation(entry: dict[str, Any], value: str) -> None:
    if _ORIGINAL_TRANSLATION not in entry:
        entry[_ORIGINAL_TRANSLATION] = entry.get("translation")
    entry["translation"] = value


def align_and_wrap_display_groups(lang: dict[str, Any]) -> None:
    """Apply translated-speaker alignment only to the in-memory lang object."""
    entries = _entries(lang)
    for group in lang.get("display_groups", []):
        speaker_entry = entries.get(group.get("speaker_offset"))
        if not speaker_entry:
            continue
        speaker_translation = speaker_entry.get("translation")
        if not isinstance(speaker_translation, str) or not speaker_translation or speaker_translation == KEEP_ORIGINAL:
            continue
        layout = _speaker_layout(speaker_translation)
        if layout is None:
            continue
        speaker, body, content_column = layout
        speaker_value = speaker + (" " + body if body else "")
        _set_translation(speaker_entry, _wrap_display_text(
            speaker_value,
            continuation_indent=content_column,
        ))

        for line in group.get("lines", []):
            entry = entries.get(line.get("offset"))
            if not entry:
                continue
            translation = entry.get("translation")
            if not isinstance(translation, str) or not translation or translation == KEEP_ORIGINAL:
                continue
            if line.get("role") == "speaker":
                current = _speaker_layout(translation)
                if current is not None:
                    _, current_body, current_column = current
                    translation = _speaker_layout(translation)[0] + (
                        " " + current_body if current_body else ""
                    )
                    content_column = current_column
                    _set_translation(entry, _wrap_display_text(
                        translation, continuation_indent=content_column
                    ))
                continue
            if line.get("role") != "continuation":
                continue
            body = translation.lstrip(" \u3000")
            _set_translation(entry, _wrap_display_text(
                body,
                initial_indent=content_column,
                continuation_indent=content_column,
            ))


def normalize_fullwidth_spaces(info: dict[str, Any], lang: dict[str, Any]) -> None:
    """Normalize editable placeholders only during encoding."""
    for section in ("dialogue_groups", "overlay_texts"):
        for entry in lang.get(section, []):
            translation = entry.get("translation")
            if not isinstance(translation, str):
                continue
            # The Korean font table maps ASCII [ and ] to the game's
            # two-byte fullwidth bracket glyphs (81 6D / 81 6E).  Keep the
            # editable ASCII placeholders here; converting them to Unicode
            # fullwidth brackets would bypass that font-table mapping.
            normalized = translation.replace("\u3000", " ").translate(
                str.maketrans({"［": "[", "］": "]"})
            )
            if normalized != translation:
                _set_translation(entry, normalized)

    align_and_wrap_display_groups(lang)


def restore_fullwidth_spaces(info: dict[str, Any], lang: dict[str, Any]) -> None:
    for section in ("dialogue_groups", "overlay_texts"):
        for entry in lang.get(section, []):
            original = entry.pop(_ORIGINAL_TRANSLATION, None)
            if original is not None:
                entry["translation"] = original


if __name__ == "__main__":
    raise SystemExit(
        encode_main(
            width=DRACULA_LINE_WIDTH,
            preserve_boundary_runs=True,
            preprocess_lang=normalize_fullwidth_spaces,
            postprocess_lang=restore_fullwidth_spaces,
        )
    )
