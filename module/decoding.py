import struct
from module.compress.lzss_gss2 import LZSS_GSS2


def _xor_process(data, encoding_info: str, is_encoding=False):
    if "xor" in encoding_info:
        xor_key = encoding_info.split(":")[-1]
        xor_key = int(xor_key, 16)
        data = bytearray([b ^ xor_key for b in data])
    if "taikou2" in encoding_info:
        # For Taikou 2 decoding / encoding only
        # Extract xor key
        seed1 = data[0x12]
        seed2 = data[0x13]
        xor_key = seed1 ^ seed2

        if is_encoding:
            stored_checksum = struct.unpack("<H", data[0x10:0x12])[0]
            # Compute checksum from predefined data region =(0x58C~)
            checksum = 0
            for b in data[0x58C:]:
                checksum = (checksum + b) & 0xFFFF

            # Update checksum if it is different
            if checksum != stored_checksum:
                struct.pack_into("<H", data, 0x10, checksum)

        # XOR the data for predefined region =(0x58C~)
        data[0x58C:] = bytearray([b ^ xor_key for b in data[0x58C:]])

    if "lzss:gss2" in encoding_info:
        lzss = LZSS_GSS2()
        if is_encoding:
            data = lzss.compress(data)
        else:
            data = lzss.decompress(data)
        data = bytearray(data)

    return data


def decode(data, encoding_info: str):
    return _xor_process(data=data, encoding_info=encoding_info, is_encoding=False)


def encode(data, encoding_info: str):
    return _xor_process(data=data, encoding_info=encoding_info, is_encoding=True)


def convert_3to4bpp(in_path, out_path):
    with open(in_path, "rb") as f_in, open(out_path, "wb") as f_out:
        while chunk := f_in.read(3):
            f_out.write(chunk)
            if len(chunk) == 3:
                f_out.write(b"\x00")


def convert_4to3bpp(in_path, out_path):
    with open(in_path, "rb") as f_in, open(out_path, "wb") as f_out:
        while True:
            chunk = f_in.read(4)
            if len(chunk) < 4:
                f_out.write(chunk[:3])
                break
            f_out.write(chunk[:3])
