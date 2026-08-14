"""
This module provides functionality for reading, decompressing, and compressing
OLH (Old Lion-head) image files. The OLH format is a proprietary image format
that uses a combination of RLE and other compression techniques.

This module depends on the 'Pillow' library for reading PNG files and the
'numpy' library for image data manipulation.
"""

import argparse
import io
import struct
from pathlib import Path

import numpy as np
from gspecific.image_workspace import ImageWorkspace, native_artifact_name, update_meta
from module.pc98_image.palette import check_duplicated_elements, match_color
from module.pc98_image.planar import (
    decode_plane_major_column_planar,
    encode_plane_major_column_planar,
)


try:
    from PIL import Image
except ImportError:
    # Pillow is an optional dependency, required only for PNG handling.
    # The program will still run, but functions that require Pillow will fail.
    pass

DEBUG = False


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

        if self.frames[frame_index]["data_8bpp"]:
            assert self.frames[frame_index]["data_8bpp"] == unpacked_pixels_8bpp, "8bpp data does not match."

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

            if b == 0x20:
                dest.extend(src.read(reps))
            elif b == 0x30:
                fill_byte = src.read(1)[0]
                dest.extend([fill_byte] * reps)
            elif b == 0x40:
                fill_byte = src.read(1)[0]
                w = ((fill_byte & 0xF) + ((fill_byte & 0xF0) << 4)) * 17
                pattern = struct.pack(">H", w)
                for _ in range(reps // 2):
                    dest.extend(pattern)
                if reps % 2 != 0:
                    dest.append(pattern[0])
            elif b == 0x50:
                dest.extend([0x00] * reps)
            elif b == 0x60:
                dest.extend([0xFF] * reps)
            elif b == 0x70:
                for _ in range(reps):
                    dest.append(dest[-2])
            elif b == 0x80:
                for _ in range(reps):
                    dest.append(dest[-4])
            elif b == 0x90:
                for _ in range(reps):
                    dest.append(dest[-height])
            elif b in [0xA0, 0xC0]:
                plane_num = (b & 0x40) >> 6
                current_plane = len(dest) // planesize
                if current_plane <= plane_num:
                    continue
                dist = (current_plane - plane_num) * planesize
                start_offset = len(dest) - dist
                for i in range(reps):
                    dest.append(dest[start_offset + i])
            elif b in [0xB0, 0xD0]:
                plane_num = (b & 0x40) >> 6
                current_plane = len(dest) // planesize
                if current_plane <= plane_num:
                    continue
                dist = (current_plane - plane_num) * planesize
                start_offset = len(dest) - dist
                for i in range(reps):
                    dest.append(dest[start_offset + i] ^ 0xFF)
            elif b == 0xE0:
                e_cmd = src.read(1)[0]
                if e_cmd == 0:
                    current_plane = len(dest) // planesize
                    if current_plane <= 2:
                        continue
                    dist = (current_plane - 2) * planesize
                    start_offset = len(dest) - dist
                    for i in range(reps):
                        dest.append(dest[start_offset + i])
                elif e_cmd == 1:
                    current_plane = len(dest) // planesize
                    if current_plane <= 2:
                        continue
                    dist = (current_plane - 2) * planesize
                    start_offset = len(dest) - dist
                    for i in range(reps):
                        dest.append(dest[start_offset + i] ^ 0xFF)
                elif e_cmd in [2, 3, 4, 5, 6, 7]:
                    op = "or" if (e_cmd % 2) == 0 else "and"
                    plane_map = {2: (0, 1), 3: (0, 1), 4: (1, 2), 5: (1, 2), 6: (0, 2), 7: (0, 2)}
                    p1_num, p2_num = plane_map[e_cmd]
                    current_plane = len(dest) // planesize
                    if current_plane <= p1_num or current_plane <= p2_num:
                        continue
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
                elif e_cmd == 8:
                    for _ in range(reps):
                        dest.append(dest[-height * 2])
                elif e_cmd == 9:
                    for _ in range(reps):
                        dest.append(dest[-16])
            else:
                print(f"Unknown command {cmd:02X} at {src.tell() - 1:04X}")
        return dest

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
                    if rep + len(best) >= bestlen + len(trybest):
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

                # Copy from bitplane 1, inverted.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[1][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xD0, rep, None, best, bestlen)

                # Copy from bitplane 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xC0, rep, None, best, bestlen)

                # Copy from bitplane 0, inverted.
                y = y_start
                if (i != 0) and (buf[y] == planebuf[0][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xB0, rep, None, best, bestlen)

                # Copy from bitplane 0.
                y = y_start
                if (i != 0) and (buf[y] == planebuf[0][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xA0, rep, None, best, bestlen)

                # Direct RLE for string of same byte.
                y = y_start
                if y + 1 < len(buf):
                    octet = buf[y]
                    rep = 1
                    y += 1
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

                # Copy from 16 rows ago.
                y = y_start
                if (row > 16) and (buf[y] == buf[y - 16]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - 16]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x09, best, bestlen)

                # Copy from 2 columns ago.
                y = y_start
                if (y > h * 2) and (buf[y] == buf[y - h - h]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == buf[y - h - h]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x08, best, bestlen)

                # Copy from bitplane 0 AND 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[0][y] & planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] & planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x07, best, bestlen)

                # Copy from bitplane 0 OR 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[0][y] | planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] | planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x06, best, bestlen)

                # Copy from bitplane 1 AND 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[1][y] & planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] & planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x05, best, bestlen)

                # Copy from bitplane 1 OR 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[1][y] | planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[1][y] | planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x04, best, bestlen)

                # Copy from bitplane 0 AND 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[0][y] & planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] & planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x03, best, bestlen)

                # Copy from bitplane 0 OR 1.
                y = y_start
                if (i > 1) and (buf[y] == planebuf[0][y] | planebuf[1][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[0][y] | planebuf[1][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x02, best, bestlen)

                # Copy from bitplane 2, inverted.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[2][y] ^ 0xFF):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[2][y] ^ 0xFF):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x01, best, bestlen)

                # Copy from bitplane 2.
                y = y_start
                if (i > 2) and (buf[y] == planebuf[2][y]):
                    rep = 1
                    y += 1
                    while (y < len(buf)) and (buf[y] == planebuf[2][y]):
                        rep += 1
                        y += 1
                    best, bestlen = KeepBest(0xE0, rep, 0x00, best, bestlen)

                # Output whatever gave us the longest run. If there are literals between this and the
                # previous run, encode those efficiently first.
                y = y_start
                if bestlen > 0:
                    if literalrun > 0:
                        # 베스트 로직이라 하더라도 미출력 리터널 바이트가 존재할 경우
                        # 2 바이트 이하의 베스트는 버림.
                        if bestlen <= 2 and len(best) >= bestlen:
                            literalrun += 1
                            y += 1
                            bestlen = 0
                        else:
                            OutputLiterals(buf, outbuf, y - literalrun, literalrun)
                            literalrun = 0

                    if bestlen > 0:
                        if DEBUG:
                            print(f"    best output: {len(outbuf):04X}:: {buf[y : y + bestlen].hex(' ')}")
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


def CheckLiterals(srcbuf, ofs, rep):
    len = 0
    # Bytes 0x00..1F and 0xF0..FF can be output verbatim.
    while (rep > 0) and ((srcbuf[ofs + len] < 0x20) or (srcbuf[ofs + len] >= 0xF0)):
        rep -= 1
        len += 1

    # Any 00..1F,F0..FF bytes at the end also can be output verbatim, minimising the length byte.
    suffix = 0
    while (rep > 0) and ((srcbuf[(ofs + len) + rep - 1] < 0x20) or (srcbuf[(ofs + len) + rep - 1] >= 0xF0)):
        suffix += 1
        rep -= 1
    return len + suffix


def OutputLiterals(srcbuf, outbuf, ofs, rep):
    # 리터럴 출력의 경우에도 처리 가능한 최대 바이트 수를 미리 체크해서 효률 우선으로 처리
    ignore = CheckLiterals(srcbuf, ofs, rep) < rep
    # Bytes 0x00..1F and 0xF0..FF can be output verbatim.
    while (rep > 0) and ((srcbuf[ofs] < 0x20) or (srcbuf[ofs] >= 0xF0)) and not ignore:
        outbuf.append(srcbuf[ofs])
        rep -= 1
        ofs += 1

    # Any 00..1F,F0..FF bytes at the end also can be output verbatim, minimising the length byte.
    suffix = 0
    while (rep > 0) and ((srcbuf[ofs + rep - 1] < 0x20) or (srcbuf[ofs + rep - 1] >= 0xF0)) and not ignore:
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


def decode_workspace_file(source_path: Path, output_dir: Path) -> None:
    codec = OLH()
    if not codec.read_olh(source_path):
        raise ValueError(f"{source_path}: no OLH frames found")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / native_artifact_name(source_path.name, "jpn")).write_bytes(
        source_path.read_bytes()
    )
    single_frame = len(codec.frames) == 1
    for index, frame in enumerate(codec.frames):
        stem = source_path.stem if single_frame else f"frame{index:03d}"
        output_png = output_dir / f"{stem}.jpn.png"
        codec.save_frame_as_png(index, output_png)
        planar = bytes(frame["vplanar_data"])
        indices = bytes(frame["data_8bpp"])
        (output_dir / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (output_dir / f"{stem}.idx.jpn.bin").write_bytes(indices)
        update_meta(
            output_dir / f"{stem}.meta.json",
            source=source_path.name,
            frame=index,
            offset=None,
            original_size=len(frame["compressed_data"]),
            encoded_size=None,
            stored_size=None,
            padding_byte=None,
            compression="olh-command",
            width=frame["width"],
            height=frame["height"],
            planes=4,
            plane_order="BRGI",
            planar_layout="plane-major-column",
            bit_order="msb-first",
            stride=frame["height"],
            palette="embedded" if frame["palette"] else "grayscale",
        )


def encode_workspace_file(source_path: Path, output_dir: Path) -> Path:
    codec = OLH()
    if not codec.read_olh(source_path):
        raise ValueError(f"{source_path}: no OLH frames found")
    if len(codec.frames) != 1:
        raise ValueError("workspace OLH encoding currently supports one frame only")

    stem = source_path.stem
    input_png = output_dir / f"{stem}.kor.png"
    if not input_png.exists():
        raise FileNotFoundError(input_png)
    codec.read_png_as_8bpp(input_png)
    frame = codec.frames[0]
    indices = bytes(frame["data_8bpp"])
    planar = encode_plane_major_column_planar(
        indices,
        frame["width"],
        frame["height"],
        4,
    )
    (output_dir / f"{stem}.idx.kor.bin").write_bytes(indices)
    (output_dir / f"{stem}.pln.kor.bin").write_bytes(planar)

    output_path = output_dir / native_artifact_name(source_path.name, "kor")
    codec.compress(output_path)
    update_meta(
        output_dir / f"{stem}.meta.json",
        encoded_size=output_path.stat().st_size,
        stored_size=output_path.stat().st_size,
        padding_byte=None,
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode or encode workspace OLH files")
    parser.add_argument("action", choices=("decode", "encode"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("inputs", nargs="+", help="OLH paths relative to jpn-pc98")
    args = parser.parse_args()
    workspace = ImageWorkspace(args.workspace)

    for relative_source in args.inputs:
        source_path = workspace.source(relative_source)
        output_dir = workspace.artifacts(relative_source)
        if args.action == "decode":
            decode_workspace_file(source_path, output_dir)
            print(output_dir)
        else:
            print(encode_workspace_file(source_path, output_dir))


if __name__ == "__main__":
    main()
