"""
This module provides the OZM class for handling OZM image files, along with
various helper functions for data conversion and compression. The OZM format
is a proprietary image format that uses a form of RLE compression and a
planar data layout.

This module can depend on the 'Pillow' and 'numpy' libraries for certain
operations like reading PNGs and handling image data.
"""

import io
import sys
import struct
from ..palette import Palettes, find_closest_color_index
from ..planar import decode_plane_major_column_planar

try:
    from PIL import Image
except ImportError:
    # Pillow is an optional dependency, required only for PNG handling.
    pass


class OZM:
    """
    A class to handle OZM image files, providing methods for reading,
    decompressing, compressing, and converting OZM data.
    """

    def __init__(self):
        """Initializes the OZM object with default header and data values."""
        # Header information
        self.ver = 0
        self.palette_type = 0
        self.width_bytes = 0
        self.height = 0
        self.start_ofs = 0
        self.width = 0

        # Palette information
        self.raw_palette = bytearray()
        self.palette = Palettes()

        # Main data
        self.compressed_data = bytearray()
        self.vplanar_data = bytearray()
        self.data_8bpp = bytearray()

    def read_ozm(self, ozm_file_path: str, rgb: str = "rgb") -> bool:
        """
        Reads an OZM file, including its header, palette, and compressed data.

        Args:
            ozm_file_path (str): The path to the OZM file.

        Returns:
            True if the file was read successfully, False otherwise.
        """
        with open(ozm_file_path, "rb") as f:
            # Read header
            self.ver = struct.unpack(">H", f.read(2))[0]
            if self.ver == 0x301:
                self.palette_type = 0x1

            self.width_bytes, self.height, self.start_ofs = struct.unpack("<HHH", f.read(6))
            self.width = self.width_bytes * 8

            if self.start_ofs == 0x3A:
                temp = f.read(1)
                if temp[0] != self.palette_type:
                    # The original code had a check here that was commented out.
                    # It's kept here for reference.
                    pass

            print(f"  Version: {self.ver:04X}, Size: {self.width}x{self.height}, Data offset: {self.start_ofs:04X}")
            if self.ver not in [0x200, 0x300, 0x301]:
                print(f"  Warning: Unexpected version {self.ver:04X}", file=sys.stderr)
                return False

            if self.start_ofs in [0x39, 0x3A]:
                self.raw_palette = f.read(48)
                self.palette.set_palettes(self.raw_palette, order=rgb)

            f.seek(self.start_ofs)
            self.compressed_data = f.read()
        return True

    def decompress(self):
        """
        Decompresses the OZM data and converts it to 8bpp indexed format.
        """
        if not self.compressed_data:
            raise ValueError("Compressed data is empty. Call read_ozm first.")

        self.vplanar_data = ozm_unpack_rle(self.compressed_data)
        print(f"  Decompressed {len(self.compressed_data)} bytes into {len(self.vplanar_data)} bytes of planar data.")
        self.data_8bpp = bytearray(
            decode_plane_major_column_planar(
                self.vplanar_data, self.width, self.height, 4
            )
        )

    def save_as_png(self, out_path: str):
        """
        Saves the decompressed 8bpp indexed data as a True-Color PNG image.

        Args:
            out_path (str): The path to save the PNG file.
        """
        if not self.data_8bpp:
            raise ValueError("8bpp data is empty. Call decompress first.")

        # Convert 8bpp indexed data to a list of RGB tuples.
        rgb_pixels = [self.palette.palettes[0][index] for index in self.data_8bpp]

        # Create a new RGB image and put the pixel data.
        rgb_img = Image.new("RGB", (self.width, self.height))
        rgb_img.putdata(rgb_pixels)

        rgb_img.save(out_path, "PNG")
        print(f"  Successfully saved True-Color image to {out_path}")

    def read_png_as_8bpp(self, png_path: str, palette_index: int = 0):
        """
        Reads a PNG file and converts it to 8bpp indexed data using the OZM palette.

        Args:
            png_path (str): The path to the PNG file.
        """
        img = Image.open(png_path).convert("RGB")
        width, height = img.size

        if self.width == 0:
            self.width = width
            self.height = height
            self.width_bytes = width // 8

        pixels = list(img.getdata())

        unpacked_pixels_8bpp = bytearray(width * height)
        for i, pixel_rgb in enumerate(pixels):
            unpacked_pixels_8bpp[i] = find_closest_color_index(pixel_rgb, self.palette.palettes[palette_index], "last")

        self.data_8bpp = unpacked_pixels_8bpp

    def compress(self, out_path: str):
        """
        Compresses 8bpp image data and saves it as an OZM file.

        Args:
            out_path (str): The path to save the compressed OZM file.
        """
        w = self.width >> 3
        h = self.height

        # Build the OZM header.
        header = [
            3,  # Constant value, purpose unknown.
            self.palette_type,
            w & 255,
            w >> 8,
            h & 255,
            h >> 8,
            0x3A,  # Start offset of data.
            0,
            self.palette_type,
        ]
        outbuf = bytearray(header)
        outbuf += bytearray(self.raw_palette)
        outbuf.append(0x0F)  # End of palette marker.

        # Compress the 8bpp data using RLE.
        compressed_8bpp = ozm_pack_rle_from_8bpp(self.data_8bpp, self.width, h)
        outbuf.extend(compressed_8bpp)

        with open(out_path, "wb") as f:
            f.write(outbuf)


def ozm_unpack_rle(data: bytes) -> bytearray:
    """
    Decompresses OZM data using a custom RLE algorithm.

    The ozm_unpack_rle function in module/ozmlib.py decompresses OZM-specific RLE data. It reads command bytes from an io.BytesIO
    stream and appends decompressed data to a bytearray. Non-zero command bytes are treated as literal data. A 0x00 command byte
    signals a special RLE operation, followed by a cmd_code. cmd_code values 1-5 indicate runs of zero bytes, 6 signals a run of a
    single repeated byte, and 7 indicates runs of 2-byte words, with reps specifying total bytes (potentially ending with a partial
    word). The function returns the complete decompressed bytearray. Potential improvements include more robust error handling,
    replacing magic numbers with named constants for readability, and optimizing dest.extend for extreme repetition counts. This
    analysis covers its current logic and behavior.

    Args:
        data (bytes): The compressed OZM data.

    Returns:
        A bytearray containing the decompressed data.
    """
    src = io.BytesIO(data)
    dest = bytearray()
    while True:
        cmd_byte = src.read(1)
        if not cmd_byte:
            break
        cmd = cmd_byte[0]
        if cmd != 0:
            dest.append(cmd)
        else:
            cmd_code_byte = src.read(1)
            if not cmd_code_byte:
                break
            cmd_code = cmd_code_byte[0]
            if 1 <= cmd_code <= 5:
                dest.extend([0] * cmd_code)
            elif cmd_code == 6:
                b = src.read(1)[0]
                reps = struct.unpack("<H", src.read(2))[0]
                dest.extend([b] * reps)
            elif cmd_code == 7:
                w_bytes = src.read(2)
                reps = struct.unpack("<H", src.read(2))[0]
                for _ in range(reps // 2):
                    dest.extend(w_bytes)
                if reps % 2 != 0:
                    dest.append(w_bytes[0])
    return dest


def ozm_pack_rle_from_8bpp(data_8bpp: bytearray, width: int, height: int) -> bytearray:
    """
    Compresses 8bpp data using the OZM RLE-like algorithm.

    Args:
        planar_data (bytearray): The 8bpp data to compress.
        width (int): The width of the image.

    Returns:
        A bytearray containing the compressed data.
    """
    w = width >> 3
    h = height

    outbuf = bytearray()

    # The bitmap is an array of individual 4/8 bpp pixel values in scanline order.
    bitmask = 1
    for i in range(4):
        # Process one bitplane at a time, first 0x01 the lowest bits.
        plane = bytearray(map(lambda x: (x & bitmask) >> i, data_8bpp))
        bitmask = bitmask << 1
        # Pack the plane into an 8px column.
        buf = bytearray()
        for x in range(w):
            ofs = x << 3
            for y in range(h):
                row = 0
                for j in range(8):
                    row += plane[ofs + j] << (7 - j)
                buf.append(row)
                ofs += width
        # RLE-compress the columnified bitplane, add to output buffer.
        y = 0
        while y < len(buf):
            if (y + 4 < len(buf)) and (buf[y] == buf[y + 1]) and (buf[y] == buf[y + 2]) and (buf[y] == buf[y + 3]):
                outbuf.append(0)  # special code
                outbuf.append(6)  # repeat next byte
                i = buf[y]
                outbuf.append(i)
                rep = 4
                y += 4
                while (y < len(buf)) and (buf[y] == i):
                    rep += 1
                    y += 1
                y -= 1
                outbuf.append(rep & 255)
                outbuf.append(rep >> 8)
            elif buf[y] != 0:
                outbuf.append(buf[y])  # output literal
            else:
                outbuf.append(0)  # special code
                outbuf.append(1)  # one 0 byte
            y += 1

    return outbuf


def ozm_pack_rle(planar_data: bytearray) -> bytearray:
    """
    Compresses planar data using the OZM RLE-like algorithm.

    Args:
        planar_data (bytearray): The planar data to compress.

    Returns:
        A bytearray containing the compressed data.
    """
    dest = bytearray()
    i = 0
    while i < len(planar_data):
        # Prioritize word runs (0x00, 0x07)
        if i + 3 < len(planar_data) and planar_data[i : i + 2] == planar_data[i + 2 : i + 4]:
            w_bytes = planar_data[i : i + 2]
            count = 0
            while i + count + 1 < len(planar_data) and planar_data[i + count : i + count + 2] == w_bytes:
                count += 2

            if count >= 4:
                dest.extend([0, 7])
                dest.extend(w_bytes)
                dest.extend(struct.pack("<H", count))
                i += count
                continue

        # Next, prioritize byte runs (0x00, 0x06)
        if (
            i + 3 < len(planar_data)
            and planar_data[i] == planar_data[i + 1]
            and planar_data[i] == planar_data[i + 2]
            and planar_data[i] == planar_data[i + 3]
        ):
            run_byte = planar_data[i]
            count = 0
            while i + count < len(planar_data) and planar_data[i + count] == run_byte and count < 65535:
                count += 1

            dest.extend([0, 6])
            dest.append(run_byte)
            dest.extend(struct.pack("<H", count))
            i += count
            continue

        # Handle short zero runs
        if planar_data[i] == 0:
            count = 0
            while i + count < len(planar_data) and planar_data[i + count] == 0 and count < 5:
                count += 1

            if count > 0:
                dest.extend([0, count])
                i += count
                continue

        # Handle literal non-zero byte
        if planar_data[i] != 0:
            dest.append(planar_data[i])
            i += 1
            continue

        # Safeguard for single zero
        dest.extend([0, 1])
        i += 1

    return dest
