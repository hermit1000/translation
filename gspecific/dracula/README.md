# Dracula (PC-98)

Dracula's `MES` files use the ADV98 compressed text format shared by the
Fairytale titles in this repository. The decoder reuses the common DOB2
lexical implementation and writes the standard `*_info.json` and
`*_lang.json` translation pair.

```powershell
python -m gspecific.dracula.adv98_mes.decode_mes
```

By default this reads `C:\work_han\workspace2\jpn-pc98\MES` and writes
`C:\work_han\workspace2\script-pc98\MES\*_info.json` and
`C:\work_han\workspace2\script-pc98\MES\*_lang.json`.

## Translation tools

Translation and encoding conventions are documented in
[`TRANSLATION_RULES.md`](TRANSLATION_RULES.md).

To build the mixed font, which keeps `anex86.bmp` for non-Hangul glyphs and
uses `ThinDungGeunMo.bmp` only for Hangul slots:

```powershell
python -m gspecific.dracula.build_mixed_font
```

The default output is `C:\work_han\workspace2\ThenDungGeunMo.bmp`.

## Image encoding and decoding

Dracula's `GPC` files use the same ADV98 GPC image format as DOB1. Decode
them into `image-pc98/GPC/<filename>/` for binary data and metadata, and
`image-pc98/png/` for PNG images, with:

```powershell
python -m gspecific.dracula.decode_gpc
```

Use `--file D001.GPC` for a single file or `--mode 0`/`--mode 1` to force
the output mode. Non-GPC files such as `PAL.DAT`, `END.DAT`, and `W.DAT`
are not passed to this decoder.

The common ADV98 decoder preserves the XOR accumulator between stride chains,
matching `ADVBIOS.OVL.dec` offsets `0x2787..0x27C2` and the routines verified
in DOB1, DOB2, Marine Philt, and Necronomicon. Dracula explicitly selects
six-bit DAC palette bit replication, as in its verified title capture.

Encoding and decoding live in `module.pc98_image.formats.adv98_gpc`.
The game launcher selects files and palette settings; artifact writing uses
`module.pc98_image.adv98_artifacts`. New encoders should call `encode_gpc`
with the original file bytes and edited palette indices, then verify them
with `decode_gpc`. See the [shared module API](../../module/pc98_image/README.md).

```powershell
python -m gspecific.dracula.adv98_mes.make_dialogue_dictionary
python -m gspecific.dracula.adv98_mes.apply_dialogue_dictionary --dry-run
python -m gspecific.dracula.adv98_mes.encode_mes_batch
# encode_batch.py is also available as a compatibility alias.
```

For a debug run, edit `DEBUG_INDEX_RANGE` in `encode_mes_batch.py` to a
1-based inclusive range such as `(4, 4)` or `(4, 8)`. Leave it as
`(None, None)` for the complete MES list.

The batch encoder writes translated MES files to `kor-pc98/MES` and copies
them to `kor-pc98-dosbox-x/MES` unless `--no-dosbox-x` is specified.
