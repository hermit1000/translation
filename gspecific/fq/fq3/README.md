# FQ3 PC-98 Korean patch

Final rendering uses `fq3-BISCO.bmp` and disables bold in `MAIN.EXE`,
`OPEN.EXE`, and `END.BIN`. The editable text and fixed custom word map are in
`workspace13/script-pc98`.
`MAIN.EXE` also fixes the name/class field width when one- and two-byte glyphs
are mixed.

From `C:\work_han\translation`:

```powershell
python -m gspecific.fq.fq3.gen_font_from_db_fq3
python -m gspecific.fq.fq3.write_lang
python -m gspecific.fq.fq3.build_ending_test
```

The first command builds `fq3-BISCO.bmp` from the fixed custom word map,
`C:\work_han\font_update_db\BISCO.bmp`, and the established custom glyph
atlas `C:\work_han\font_update_db\fq3-ThinDungGeunMo.bmp`. `write_lang` reads
the packed Japanese files in `jpn-pc98` and writes the Korean files to `kor-pc98` and
`kor-pc98-dosbox-x`. The ending builder creates the direct-ending copy.

Launch the regular game with `fq3-kor.bat` and the ending with
`FirstQueen-ending.bat` in the workspace.
