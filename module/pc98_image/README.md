# PC-98 indexed image primitives

This package separates reusable indexed-image operations from game and file
format codecs.

The common representation is `IndexedImage`: row-major palette indices plus
dimensions and an optional RGB palette. Planar bytes are not treated as one
universal format. Callers must select the actual storage layout:

- `interleaved`: plane bytes are adjacent for each horizontal eight-pixel group.
- `plane_major_row`: complete planes, with rows contiguous inside each plane.
- `plane_major_column`: complete planes, with columns contiguous inside each plane.

`formats.olh` and `formats.ozm` own their headers and compression algorithms.
Game-specific containers, compression, screen splitting, and palette-file rules
remain under `gspecific`.
