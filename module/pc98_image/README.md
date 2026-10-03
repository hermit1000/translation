# PC-98 indexed image primitives

This package separates reusable indexed-image operations from game and file
format codecs.

The common representation is `IndexedImage`: row-major palette indices plus
dimensions and an optional RGB palette. Planar bytes are not treated as one
universal format. Callers must select the actual storage layout:

- `interleaved`: plane bytes are adjacent for each horizontal eight-pixel group.
- `plane_major_row`: complete planes, with rows contiguous inside each plane.
- `plane_major_column`: complete planes, with columns contiguous inside each plane.

`formats.olh`, `formats.ozm`, and `formats.adv98_gpc` own their headers and
compression algorithms.
Game-specific containers, compression, screen splitting, and palette-file rules
remain under `gspecific`.

## ADV98 GPC

DOB1, DOB2, Marine Philt, Dracula, and Necronomicon use
`module.pc98_image.formats.adv98_gpc` for zero-mask compression, runtime
stride XOR, row XOR, interlace, planar/index conversion, and native GPC
encoding. The stride accumulator carries across chains; the machine-code
verification is documented in
[`GPC_RUNTIME_ANALYSIS.md`](../../gspecific/dob1/GPC_RUNTIME_ANALYSIS.md).

```python
from module.pc98_image.formats.adv98_gpc import decode_gpc, encode_gpc

decoded = decode_gpc(source_bytes, output_mode=0)
encoded, planar = encode_gpc(source_bytes, edited_indices, output_mode=0)
assert decode_gpc(encoded, output_mode=0).indices == edited_indices
```

`variant="necronomicon"` supports zero declared file sizes and descriptor-inclusive
compressed sizes, retaining those header conventions when encoding. It also
preserves the Necronomicon artifact's existing logical-row planar ordering;
standard GPC artifacts preserve compression-stream row ordering.

The default packed palette expands four-bit components with `n * 17`.
Dracula and Necronomicon select `palette_decoder=decode_packed_palette_dac`
to match their six-bit DAC capture colors. Encoding operates on palette indices
and preserves the source palette bytes.

The default `cumulative_xor=True` reconstructs rows in stream order before
interlace placement. Necronomicon's existing mode-1 facade selects
`cumulative_xor=False`; use the same setting when encoding its mode-1 resources.
These settings are format options, not alternate implementations.

`module.pc98_image.adv98_artifacts` owns exact PNG palette mapping
(`normalize_indexed`) and binary/PNG/metadata writing (`write_artifacts`).
Its `png_output` argument selects a separate PNG directory. Game launchers
choose file lists, MES output modes, container extraction, and output paths.

Existing imports from `gspecific.dob1.gpc` and encoding helpers from
`gspecific.dob1.encode_korean_images` remain compatibility exports. New callers
should import the shared modules directly. DOB1's explicit legacy FRR bit
correction remains in its game wrapper and is not part of generic GPC encoding.
