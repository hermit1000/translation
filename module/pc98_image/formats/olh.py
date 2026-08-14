"""
This module provides functionality for reading, decompressing, and compressing
OLH (Old Lion-head) image files. The OLH format is a proprietary image format
that uses a combination of RLE and other compression techniques.

This module depends on the 'Pillow' library for reading PNG files and the
'numpy' library for image data manipulation.
"""

import io
import struct
import numpy as np
from ..palette import check_duplicated_elements, match_color
from ..planar import decode_plane_major_column_planar


try:
    from PIL import Image
except ImportError:
    # Pillow is an optional dependency, required only for PNG handling.
    # The program will still run, but functions that require Pillow will fail.
    pass


class OLH:
    """
    A class to handle OLH image files, providing methods for reading,
    decompressing, and compressing OLH data.
    """

    def __init__(self):
        """Initializes the OLH object with empty frames and 8bpp data."""
        self.frames = []

    def read_olh(self, olh_file_path: str):
        """
        Reads an OLH file, finds all frames, and decompresses their data.

        Args:
            olh_file_path (str): The path to the OLH file.
        """
        self.frames = self._read_olh_frames(olh_file_path)
        for i, frame in enumerate(self.frames):
            print(f"Decompressing frame {i}...")
            planesize = (frame["stride"] * frame["height"]) // 4 if frame["height"] > 0 else 0
            frame["vplanar_data"] = self._unpack_olh(frame["compressed_data"], frame["height"], planesize)
        return True if len(self.frames) else False

    def read_png_as_8bpp(self, png_path: str, frame_index: int = 0) -> tuple:
        """
        Reads a PNG file and converts it to 8bpp indexed color data based on the
        palette of the first frame of the loaded OLH file.

        Args:
            png_path (str): The path to the PNG file.

        Returns:
            A tuple containing the width, height, and palette of the image.
        """
        if not len(self.frames):
            self.frames.append({})
        if frame_index >= len(self.frames):
            assert False, f"Frame index {frame_index} out of bounds."

        img = Image.open(png_path).convert("RGB")
        width, height = img.size
        pixels = list(img.getdata())

        unpacked_pixels_8bpp = bytearray(width * height)

        # Assuming the first frame's palette is the reference
        if self.frames[frame_index]["pseudo_palette"]:
            palette = self.frames[frame_index]["pseudo_palette"]
        else:
            palette = self.frames[frame_index]["palette"]

        for i, pixel_rgb in enumerate(pixels):
            unpacked_pixels_8bpp[i] = match_color(pixel_rgb, palette)

        # if self.frames[frame_index]["data_8bpp"]:
        #     assert self.frames[frame_index]["data_8bpp"] == unpacked_pixels_8bpp, "8bpp data does not match."

        self.frames[frame_index]["width"] = width
        self.frames[frame_index]["height"] = height
        self.frames[frame_index]["stride"] = width // 2
        self.frames[frame_index]["data_8bpp"] = unpacked_pixels_8bpp
        return width, height, img.getpalette()

    def _read_olh_frames(self, filepath: str) -> list:
        """
        Reads all frames from an OLH file and extracts their metadata and
        compressed data.

        Args:
            filepath (str): The path to the OLH file.

        Returns:
            A list of dictionaries, where each dictionary represents a frame
            and contains its metadata and data.
        """
        frames = []
        with open(filepath, "rb") as f:
            data = f.read()

        src = io.BytesIO(data)

        while True:
            pos = src.tell()
            if pos >= len(data):
                break

            header_pos = data.find(b"OLH", pos)
            if header_pos == -1:
                break

            src.seek(header_pos)

            header = src.read(4)
            if len(header) < 4:
                break

            version = header[3]
            print(f"Found OLH frame at {header_pos:04X}, version {version:02X}")

            src.seek(src.tell() - 1)

            # Find the 0x1A marker, which indicates the start of the header.
            marker_found = False
            search_buf = src.read(32)
            marker_pos = search_buf.find(b"\x1a\x00")

            if marker_pos != -1:
                src.seek(header_pos + 4 - 1 + marker_pos + 2)
                marker_found = True

            if not marker_found:
                print("Could not find 1A 00 marker, skipping to next OLH block")
                next_pos = data.find(b"OLH", src.tell())
                if next_pos == -1:
                    break
                src.seek(next_pos)
                continue

            flag = src.read(1)[0]

            width = 640
            height = 400

            if (flag & 4) != 0:
                width = src.read(1)[0] * 8
                height = struct.unpack("<H", src.read(2))[0]

            stride = width // 2

            palette = None
            palette_raw = None
            if (flag & 8) != 0:
                palette = []
                palette_raw = []
                for idx in range(16):
                    j = src.read(1)[0]
                    g_byte = src.read(1)[0]
                    b = j & 0x0F
                    r = j >> 4
                    g = g_byte & 0x0F
                    palette_raw.append((r, g, b))
                    palette.append((r * 17, g * 17, b * 17))

            palette_changed, pseudo_palette = check_duplicated_elements(palette)

            current_pos = src.tell()
            next_olh_pos = data.find(b"OLH", current_pos)

            if next_olh_pos != -1:
                compressed_data = src.read(next_olh_pos - current_pos)
            else:
                compressed_data = src.read()

            frames.append(
                {
                    "width": width,
                    "height": height,
                    "stride": stride,
                    "palette": palette,
                    "pseudo_palette": pseudo_palette if palette_changed else None,
                    "palette_raw": palette_raw,
                    "compressed_data": compressed_data,
                    "vplanar_data": None,
                    "data_8bpp": None,
                    "flag": flag,
                }
            )

            if next_olh_pos == -1:
                break
            src.seek(next_olh_pos)

        return frames

    def _unpack_olh(self, data: bytes, height: int, planesize: int) -> bytearray:
        """
        Decompresses OLH data using a command-based algorithm.

        Args:
            data (bytes): The compressed OLH data.
            height (int): The height of the image.
            planesize (int): The size of each plane in the image data.

        Returns:
            A bytearray containing the decompressed image data.
        """
        src = io.BytesIO(data)
        dest = bytearray()

        while True:
            cmd_byte = src.read(1)
            if not cmd_byte:
                break

            cmd = cmd_byte[0]
            reps = 0

            b = cmd & 0xF0
            if b in [0x00, 0x10, 0xF0]:
                dest.append(cmd)
                continue

            reps = cmd & 0x0F
            if reps == 0:
                reps_byte = src.read(1)[0]
                if reps_byte < 0x10:
                    if reps_byte == 0:
                        reps = struct.unpack(">H", src.read(2))[0]
                    else:
                        reps = (reps_byte << 8) + src.read(1)[0]
                else:
                    reps = reps_byte

            handler = self._UNPACK_COMMANDS.get(b)
            if handler:
                handler(self, src, dest, reps, height, planesize)
            else:
                print(f"Unknown command {cmd:02X} at {src.tell() - 1:04X}")
        return dest

    def _pack_olh(self, vplanar_data: bytearray, height: int, planesize: int) -> bytearray:
        """
        Compresses vplanar data into OLH format.
        This is the counterpart to _unpack_olh.
        """
        outbuf = bytearray()
        planebuf = [vplanar_data[i * planesize : (i + 1) * planesize] for i in range(4)]
        h = height

        for i in range(4):
            buf = planebuf[i]
            y = 0
            literalrun = 0
            while y < len(buf):
                best = bytearray()
                bestlen = 0
                y_start = y
                row = y % h

                def KeepBest(cmd, rep, extra, current_best, current_bestlen):
                    trybest = BuildCmdRep(cmd, rep)
                    if extra is not None:
                        if isinstance(extra, list) or isinstance(extra, bytearray):
                            trybest.extend(extra)
                        else:
                            trybest.append(extra)

                    # Simple heuristic: command bytes vs data bytes.
                    # A command has a length (trybest) and compresses `rep` bytes.
                    # We want to maximize (rep - len(trybest)).
                    if rep - len(trybest) > current_bestlen - len(current_best):
                        current_bestlen = rep
                        current_best = trybest
                    return current_best, current_bestlen

                # Copy from 2 rows ago.
                y = y_start
                if (row > 1) and (buf[y] == buf[y - 2]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - 2]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0x70, rep, None, best, bestlen)

                # Copy from 4 rows ago.
                y = y_start
                if (row > 3) and (buf[y] == buf[y - 4]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - 4]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0x80, rep, None, best, bestlen)

                # Copy from previous column.
                y = y_start
                if (y >= h) and (buf[y] == buf[y - h]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (y >= h) and (buf[y] == buf[y - h]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0x90, rep, None, best, bestlen)

                # Copy from bitplane 0.
                y = y_start
                if (i > 0) and (buf[y] == planebuf[0][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xA0, rep, None, best, bestlen)

                # Copy from bitplane 0, inverted.
                y = y_start
                if (i > 0) and (buf[y] == planebuf[0][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xB0, rep, None, best, bestlen)

                # Copy from bitplane 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xC0, rep, None, best, bestlen)

                # Copy from bitplane 1, inverted.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[1][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xD0, rep, None, best, bestlen)

                # Direct RLE for string of same byte.
                y = y_start
                if (y + 1 < len(buf)) and (buf[y] == buf[y + 1]):
                    octet = buf[y]
                    rep = 2
                    y += 2
                    while (y < len(buf)) and (buf[y] == octet):
                        rep += 1
                        y += 1

                    if octet == 0x00:
                        best, bestlen = KeepBest(0x50, rep, None, best, bestlen)
                    elif octet == 0xFF:
                        best, bestlen = KeepBest(0x60, rep, None, best, bestlen)
                    else:
                        best, bestlen = KeepBest(0x30, rep, octet, best, bestlen)

                # Repeat dither pair.
                y = y_start
                if (
                    (y + 1 < len(buf))
                    and (buf[y] != buf[y + 1])
                    and (buf[y] & 0xF == buf[y] >> 4)
                    and (buf[y + 1] & 0xF == buf[y + 1] >> 4)
                ):
                    octet = buf[y]
                    octet2 = buf[y + 1]
                    pattern = (octet & 0xF0) + (octet2 & 0x0F)
                    rep = 2
                    y += 2
                    while (y < len(buf)) and (buf[y] == octet):
                        rep += 1
                        y += 1
                        octet, octet2 = octet2, octet
                    best, bestlen = KeepBest(0x40, rep, pattern, best, bestlen)

                # extended commands
                # Copy from bitplane 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x00, best, bestlen)

                # Copy from bitplane 2, inverted.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[2][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[2][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x01, best, bestlen)

                # Copy from bitplane 0 OR 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[0][y] | planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] | planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x02, best, bestlen)

                # Copy from bitplane 0 AND 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[0][y] & planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] & planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x03, best, bestlen)

                # Copy from bitplane 1 OR 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[1][y] | planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] | planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x04, best, bestlen)

                # Copy from bitplane 1 AND 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[1][y] & planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] & planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x05, best, bestlen)

                # Copy from bitplane 0 OR 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[0][y] | planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] | planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x06, best, bestlen)

                # Copy from bitplane 0 AND 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[0][y] & planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] & planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x07, best, bestlen)

                # Copy from 2 columns ago.
                y = y_start
                if (y >= h * 2) and (buf[y] == buf[y - h - h]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (y >= h * 2) and (buf[y] == buf[y - h - h]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x08, best, bestlen)

                # Copy from 16 rows ago.
                y = y_start
                if (row > 15) and (buf[y] == buf[y - 16]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - 16]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x09, best, bestlen)

                # Output whatever gave us the longest run. If there are literals between this and the
                # previous run, encode those efficiently first.
                y = y_start
                if bestlen > 1:  # or len(best) < bestlen
                    if literalrun > 0:
                        OutputLiterals(buf, outbuf, y - literalrun, literalrun)
                        literalrun = 0
                    outbuf += best
                    y += bestlen
                else:
                    y += 1
                    literalrun += 1

            # Output any leftover literals at end of plane.
            if literalrun > 0:
                OutputLiterals(buf, outbuf, y - literalrun, literalrun)

        return outbuf

    def _unpack_literal_run(self, src, dest, reps, height, planesize):
        """Handles a literal run of bytes."""
        dest.extend(src.read(reps))

    def _unpack_fill_byte(self, src, dest, reps, height, planesize):
        """Handles a fill byte command."""
        fill_byte = src.read(1)[0]
        dest.extend([fill_byte] * reps)

    def _unpack_dither_pair(self, src, dest, reps, height, planesize):
        """Handles a dither pair command."""
        fill_byte = src.read(1)[0]
        w = ((fill_byte & 0xF) + ((fill_byte & 0xF0) << 4)) * 17
        pattern = struct.pack(">H", w)
        for _ in range(reps // 2):
            dest.extend(pattern)
        if reps % 2 != 0:
            dest.append(pattern[0])

    def _unpack_fill_zero(self, src, dest, reps, height, planesize):
        """Handles a fill zero command."""
        dest.extend([0x00] * reps)

    def _unpack_fill_ff(self, src, dest, reps, height, planesize):
        """Handles a fill 0xFF command."""
        dest.extend([0xFF] * reps)

    def _unpack_copy_2_rows_ago(self, src, dest, reps, height, planesize):
        """Handles a copy from 2 rows ago command."""
        for _ in range(reps):
            dest.append(dest[-2])

    def _unpack_copy_4_rows_ago(self, src, dest, reps, height, planesize):
        """Handles a copy from 4 rows ago command."""
        for _ in range(reps):
            dest.append(dest[-4])

    def _unpack_copy_prev_col(self, src, dest, reps, height, planesize):
        """Handles a copy from the previous column command."""
        for _ in range(reps):
            dest.append(dest[-height])

    def _unpack_copy_plane(self, src, dest, reps, height, planesize, plane_num, invert):
        """Handles a copy from a previous plane command."""
        current_plane = len(dest) // planesize
        if current_plane <= plane_num:
            return
        dist = (current_plane - plane_num) * planesize
        start_offset = len(dest) - dist
        for i in range(reps):
            byte = dest[start_offset + i]
            if invert:
                byte ^= 0xFF
            dest.append(byte)

    def _unpack_extended_command(self, src, dest, reps, height, planesize):
        """Handles an extended command."""
        e_cmd = src.read(1)[0]
        handler = self._UNPACK_EXTENDED_COMMANDS.get(e_cmd)
        if handler:
            handler(self, src, dest, reps, height, planesize)
        else:
            print(f"Unknown extended command {e_cmd:02X} at {src.tell() - 2:04X}")

    def _unpack_ext_copy_plane(self, src, dest, reps, height, planesize, plane_num, invert):
        """Handles an extended copy from a plane command."""
        current_plane = len(dest) // planesize
        if current_plane <= plane_num:
            return
        dist = (current_plane - plane_num) * planesize
        start_offset = len(dest) - dist
        for i in range(reps):
            byte = dest[start_offset + i]
            if invert:
                byte ^= 0xFF
            dest.append(byte)

    def _unpack_ext_plane_op(self, src, dest, reps, height, planesize, op, p1_num, p2_num):
        """Handles an extended plane operation command."""
        current_plane = len(dest) // planesize
        if current_plane <= p1_num or current_plane <= p2_num:
            return
        dist1 = (current_plane - p1_num) * planesize
        dist2 = (current_plane - p2_num) * planesize
        start1 = len(dest) - dist1
        start2 = len(dest) - dist2
        temp_plane_data = [dest[start1 + i] for i in range(reps)]
        for i in range(reps):
            val2 = dest[start2 + i]
            if op == "or":
                dest.append(temp_plane_data[i] | val2)
            else:
                dest.append(temp_plane_data[i] & val2)

    def _unpack_ext_copy_2_cols_ago(self, src, dest, reps, height, planesize):
        """Handles an extended copy from 2 columns ago command."""
        for _ in range(reps):
            dest.append(dest[-height * 2])

    def _unpack_ext_copy_16_rows_ago(self, src, dest, reps, height, planesize):
        """Handles an extended copy from 16 rows ago command."""
        for _ in range(reps):
            dest.append(dest[-16])

    _UNPACK_COMMANDS = {
        0x20: _unpack_literal_run,
        0x30: _unpack_fill_byte,
        0x40: _unpack_dither_pair,
        0x50: _unpack_fill_zero,
        0x60: _unpack_fill_ff,
        0x70: _unpack_copy_2_rows_ago,
        0x80: _unpack_copy_4_rows_ago,
        0x90: _unpack_copy_prev_col,
        0xA0: lambda self, src, dest, reps, height, planesize: self._unpack_copy_plane(
            src, dest, reps, height, planesize, 0, False
        ),
        0xB0: lambda self, src, dest, reps, height, planesize: self._unpack_copy_plane(
            src, dest, reps, height, planesize, 0, True
        ),
        0xC0: lambda self, src, dest, reps, height, planesize: self._unpack_copy_plane(
            src, dest, reps, height, planesize, 1, False
        ),
        0xD0: lambda self, src, dest, reps, height, planesize: self._unpack_copy_plane(
            src, dest, reps, height, planesize, 1, True
        ),
        0xE0: _unpack_extended_command,
    }

    _UNPACK_EXTENDED_COMMANDS = {
        0: lambda self, src, dest, reps, height, planesize: self._unpack_ext_copy_plane(
            src, dest, reps, height, planesize, 2, False
        ),
        1: lambda self, src, dest, reps, height, planesize: self._unpack_ext_copy_plane(
            src, dest, reps, height, planesize, 2, True
        ),
        2: lambda self, src, dest, reps, height, planesize: self._unpack_ext_plane_op(
            src, dest, reps, height, planesize, "or", 0, 1
        ),
        3: lambda self, src, dest, reps, height, planesize: self._unpack_ext_plane_op(
            src, dest, reps, height, planesize, "and", 0, 1
        ),
        4: lambda self, src, dest, reps, height, planesize: self._unpack_ext_plane_op(
            src, dest, reps, height, planesize, "or", 1, 2
        ),
        5: lambda self, src, dest, reps, height, planesize: self._unpack_ext_plane_op(
            src, dest, reps, height, planesize, "and", 1, 2
        ),
        6: lambda self, src, dest, reps, height, planesize: self._unpack_ext_plane_op(
            src, dest, reps, height, planesize, "or", 0, 2
        ),
        7: lambda self, src, dest, reps, height, planesize: self._unpack_ext_plane_op(
            src, dest, reps, height, planesize, "and", 0, 2
        ),
        8: _unpack_ext_copy_2_cols_ago,
        9: _unpack_ext_copy_16_rows_ago,
    }

    def save_frame_as_png(self, frame_index: int, output_path: str):
        """
        Saves a single decompressed frame as a PNG file.

        Args:
            frame_index (int): The index of the frame to save.
            output_path (str): The path to save the PNG file to.
        """
        if frame_index >= len(self.frames):
            print(f"Error: Frame index {frame_index} out of bounds.")
            return

        frame = self.frames[frame_index]
        width, height = frame["width"], frame["height"]
        vplanar_data = frame.get("vplanar_data")

        if not vplanar_data:
            print(f"Error: Frame {frame_index} has not been decompressed.")
            return

        if width > 0 and height > 0:
            try:
                data_8bpp = decode_plane_major_column_planar(
                    vplanar_data, width, height, 4
                )
                self.frames[frame_index]["data_8bpp"] = data_8bpp
                image_array = np.frombuffer(bytes(data_8bpp), dtype=np.uint8).reshape((height, width))
                img = Image.fromarray(image_array, mode="P")
                if frame["palette"]:
                    if frame["pseudo_palette"]:
                        flat_palette = [value for color in frame["pseudo_palette"] for value in color]
                    else:
                        flat_palette = [value for color in frame["palette"] for value in color]
                    img.putpalette(flat_palette)
                else:
                    # Use a grayscale palette if no palette is defined.
                    grayscale_palette = [j for j in range(256) for _ in range(3)]
                    img.putpalette(grayscale_palette)

                img.save(output_path, "PNG")
                print(f"  Saved image to {output_path}")

            except Exception as e:
                print(f"  Could not visualize frame {frame_index}: {e}")

    def save_frame_as_bmp(self, frame_index: int, output_path: str):
        """
        Saves a single decompressed frame as a 16-color BMP file.

        Args:
            frame_index (int): The index of the frame to save.
            output_path (str): The path to save the BMP file to.
        """
        if frame_index >= len(self.frames):
            print(f"Error: Frame index {frame_index} out of bounds.")
            return

        frame = self.frames[frame_index]
        width, height = frame["width"], frame["height"]
        vplanar_data = frame.get("vplanar_data")

        if not vplanar_data:
            print(f"Error: Frame {frame_index} has not been decompressed.")
            return

        if width > 0 and height > 0:
            try:
                img_data = decode_plane_major_column_planar(
                    vplanar_data, width, height, 4
                )
                image_array = np.frombuffer(img_data, dtype=np.uint8).reshape((height, width))
                img = Image.fromarray(image_array, mode="P")

                if frame["palette"]:
                    flat_palette = [value for color in frame["palette"] for value in color]
                    img.putpalette(flat_palette)

                    # Pillow doesn't directly support saving to 4-bit BMP.
                    # We create a palettized image and then save it as BMP.
                    # The BMP saver will handle the bit depth conversion if the palette is small enough.
                    # Let's ensure we have a 16-color palette.
                    if len(frame["palette"]) > 16:
                        img = img.quantize(colors=16)

                    img.save(output_path, "BMP", bits=4)
                    print(f"  Saved image to {output_path}")
                else:
                    # Use a grayscale palette if no palette is defined.
                    grayscale_palette = [j for j in range(256) for _ in range(3)]
                    img.putpalette(grayscale_palette)
                    # Quantize to 16 colors for BMP
                    img = img.quantize(colors=16)
                    img.save(output_path, "BMP", bits=4)
                    print(f"  Saved image to {output_path}")

            except Exception as e:
                print(f"  Could not visualize frame {frame_index}: {e}")

    def compress(self, out_path: str, save_size: bool = True, save_palette: bool = True, frame_index: int = 0):
        """
        Compresses the 8bpp image data into an OLH file.

        Args:
            out_path (str): The path to save the compressed OLH file.
            save_size (bool): Whether to save the image dimensions in the header.
            save_palette (bool): Whether to save the palette in the header.
        """

        ref_frame = self.frames[frame_index]
        if ref_frame.get("data_8bpp") is None:
            raise ValueError("No 8bpp data to compress. Use read_png_as_8bpp first.")

        width, height = ref_frame["width"], ref_frame["height"]

        flag = 0x03
        if save_palette:
            flag |= 0x08
        if save_size:
            flag |= 0x04

        outbuf = bytearray([0x4F, 0x4C, 0x48, 0x1A, 0x00, flag])

        if save_size:
            outbuf += bytearray([width // 8, height & 255, height >> 8])

        if save_palette:
            palette_raw = ref_frame.get("palette_raw")
            if not palette_raw:
                raise ValueError("No raw palette info in reference OLH frame.")
            for r, g, b in palette_raw:
                outbuf += bytearray([(r << 4) | b, g])

        bitmap = ref_frame["data_8bpp"]
        w = width // 8
        h = height

        bitmask = 1
        planebuf = []
        for i in range(4):
            # Process one bitplane at a time, first 0x01 (the lowest bits).
            plane = bytearray(map(lambda x: (x & bitmask) >> i, bitmap))
            bitmask = bitmask << 1
            # Pack the plane into an 8px column.
            planebuf.append(bytearray())
            for x in range(w):
                ofs = x << 3
                for y in range(h):
                    row = 0
                    for j in range(8):
                        row += plane[ofs + j] << (7 - j)
                    planebuf[i].append(row)
                    ofs += width
            buf = planebuf[i]

            # Compress the columnified bitplane, add to output buffer.
            y = 0
            literalrun = 0
            while y < len(buf):
                best = bytearray()
                bestlen = 0
                y_start = y
                row = y % h

                def KeepBest(cmd, rep, extra, best, bestlen):
                    trybest = BuildCmdRep(cmd, rep)
                    if extra is not None:
                        trybest.append(extra)
                    if rep + len(best) > bestlen + len(trybest):
                        bestlen = rep
                        best = trybest
                    return best, bestlen

                # Copy from 2 rows ago.
                y = y_start
                if (row > 2) and (buf[y] == buf[y - 2]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - 2]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0x70, rep, None, best, bestlen)

                # Copy from 4 rows ago.
                y = y_start
                if (row > 4) and (buf[y] == buf[y - 4]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - 4]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0x80, rep, None, best, bestlen)

                # Copy from previous column.
                y = y_start
                if (y > h) and (buf[y] == buf[y - h]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - h]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0x90, rep, None, best, bestlen)

                # Copy from bitplane 0.
                y = y_start
                if (i != 0) and (buf[y] == planebuf[0][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xA0, rep, None, best, bestlen)

                # Copy from bitplane 0, inverted.
                y = y_start
                if (i != 0) and (buf[y] == planebuf[0][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xB0, rep, None, best, bestlen)

                # Copy from bitplane 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xC0, rep, None, best, bestlen)

                # Copy from bitplane 1, inverted.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[1][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xD0, rep, None, best, bestlen)

                # Direct RLE for string of same byte.
                y = y_start
                if (y + 1 < len(buf)) and (buf[y] == buf[y + 1]):
                    octet = buf[y]
                    rep = 2
                    y += 2
                    while (y < len(buf)) and (buf[y] == octet):
                        rep += 1
                        y += 1

                    if octet == 0x00:
                        best, bestlen = KeepBest(0x50, rep, None, best, bestlen)
                    elif octet == 0xFF:
                        best, bestlen = KeepBest(0x60, rep, None, best, bestlen)
                    else:
                        best, bestlen = KeepBest(0x30, rep, octet, best, bestlen)

                # Repeat dither pair.
                y = y_start
                if (
                    (y + 1 < len(buf))
                    and (buf[y] != buf[y + 1])
                    and (buf[y] & 0xF == buf[y] >> 4)
                    and (buf[y + 1] & 0xF == buf[y + 1] >> 4)
                ):
                    octet = buf[y]
                    octet2 = buf[y + 1]
                    pattern = (octet & 0xF0) + (octet2 & 0x0F)
                    rep = 2
                    y += 2
                    while (y < len(buf)) and (buf[y] == octet):
                        rep += 1
                        y += 1
                        octet, octet2 = octet2, octet
                    best, bestlen = KeepBest(0x40, rep, pattern, best, bestlen)

                # Copy from bitplane 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x00, best, bestlen)

                # Copy from bitplane 2, inverted.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[2][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[2][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x01, best, bestlen)

                # Copy from bitplane 0 OR 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[0][y] | planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] | planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x02, best, bestlen)

                # Copy from bitplane 0 AND 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[0][y] & planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] & planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x03, best, bestlen)

                # Copy from bitplane 1 OR 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[1][y] | planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] | planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x04, best, bestlen)

                # Copy from bitplane 1 AND 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[1][y] & planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] & planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x05, best, bestlen)

                # Copy from bitplane 0 OR 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[0][y] | planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] | planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x06, best, bestlen)

                # Copy from bitplane 0 AND 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[0][y] & planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] & planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x07, best, bestlen)

                # Copy from 2 columns ago.
                y = y_start
                if (y > h * 2) and (buf[y] == buf[y - h - h]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - h - h]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x08, best, bestlen)

                # Copy from 16 rows ago.
                y = y_start
                if (row > 16) and (buf[y] == buf[y - 16]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - 16]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x09, best, bestlen)

                # Output whatever gave us the longest run. If there are literals between this and the
                # previous run, encode those efficiently first.
                y = y_start
                if bestlen > 1:
                    if literalrun > 0:
                        OutputLiterals(buf, outbuf, y - literalrun, literalrun)
                        literalrun = 0
                    outbuf += best
                    y += bestlen
                else:
                    y += 1
                    literalrun += 1

            # Output any leftover literals at end of plane.
            if literalrun > 0:
                OutputLiterals(buf, outbuf, y - literalrun, literalrun)

        with open(out_path, "wb") as f:
            f.write(outbuf)


def BuildCmdRep(cmd: int, rep: int) -> bytearray:
    """
    Builds a command and repetition byte sequence for the OLH format.

    Args:
        cmd (int): The command code.
        rep (int): The number of repetitions.

    Returns:
        A bytearray containing the command and repetition data.
    """
    if rep < 0x10:
        cmd += rep
    result = bytearray([cmd])
    if rep >= 0x10 and rep < 0x100:
        result.append(rep)
    elif rep >= 0x100 and rep < 0x1000:
        result += bytearray([rep >> 8, rep & 255])
    elif rep >= 0x1000:
        result += bytearray([0, rep >> 8, rep & 255])
    return result


def OutputLiterals(srcbuf: bytearray, outbuf: bytearray, ofs: int, rep: int):
    """
    Outputs a literal run of bytes, compressing them if possible.

    Certain byte values can be output verbatim, while others are encoded
    as a literal run.

    Args:
        srcbuf (bytearray): The source buffer.
        outbuf (bytearray): The output buffer.
        ofs (int): The offset in the source buffer.
        rep (int): The number of bytes to output.
    """
    # Bytes 0x00..0x1F and 0xF0..0xFF can be output verbatim.
    while (rep > 0) and ((srcbuf[ofs] < 0x20) or (srcbuf[ofs] >= 0xF0)):
        outbuf.append(srcbuf[ofs])
        rep -= 1
        ofs += 1

    # Any such bytes at the end of the run can also be output verbatim.
    suffix = 0
    while (rep > 0) and ((srcbuf[ofs + rep - 1] < 0x20) or (srcbuf[ofs + rep - 1] >= 0xF0)):
        suffix += 1
        rep -= 1

    # Output the remaining bytes as a literal run.
    if rep > 0:
        outbuf += BuildCmdRep(0x20, rep)
        while rep > 0:
            outbuf.append(srcbuf[ofs])
            rep -= 1
            ofs += 1

    # Output the suffix bytes.
    while suffix > 0:
        outbuf.append(srcbuf[ofs])
        suffix -= 1
        ofs += 1
