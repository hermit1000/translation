import sys
import os

class LZSS_GSS2:
    def __init__(self):
        self.dict_size = 256
        self.init_pos = 0xEF
        self.threshold = 2
        self.max_len = 15 + self.threshold # 17

    def decompress(self, data: bytes) -> bytes:
        if not data:
            return b""
        
        dictionary = bytearray([0x20] * self.dict_size)
        dict_pos = self.init_pos
        
        input_pos = 0
        bit_buffer = 0
        bits_left = 0
        
        output = bytearray()
        
        def read_bit():
            nonlocal bit_buffer, bits_left, input_pos
            if bits_left == 0:
                if input_pos >= len(data):
                    return None
                bit_buffer = data[input_pos]
                input_pos += 1
                bits_left = 8
            
            bit = (bit_buffer >> 7) & 1
            bit_buffer = (bit_buffer << 1) & 0xFF
            bits_left -= 1
            return bit

        def read_bits(n):
            res = 0
            for _ in range(n):
                bit = read_bit()
                if bit is None:
                    return None
                res = (res << 1) | bit
            return res

        while True:
            bit = read_bit()
            if bit is None:
                break
            
            if bit == 1:
                # Literal byte
                val = read_bits(8)
                if val is None:
                    break
                output.append(val)
                dictionary[dict_pos] = val
                dict_pos = (dict_pos + 1) & 0xFF
            else:
                # Match: 8 bits position, 4 bits length
                match_pos = read_bits(8)
                if match_pos is None:
                    break
                match_len_bits = read_bits(4)
                if match_len_bits is None:
                    break
                
                match_len = match_len_bits + self.threshold
                
                for _ in range(match_len):
                    val = dictionary[match_pos]
                    output.append(val)
                    dictionary[dict_pos] = val
                    dict_pos = (dict_pos + 1) & 0xFF
                    match_pos = (match_pos + 1) & 0xFF
                    
        return bytes(output)

    def compress(self, data: bytes) -> bytes:
        if not data:
            return b""
            
        dictionary = bytearray([0x20] * self.dict_size)
        dict_pos = self.init_pos
        
        output_data = bytearray()
        bit_buffer = 0
        bits_count = 0
        
        def write_bit(bit):
            nonlocal bit_buffer, bits_count
            bit_buffer = (bit_buffer << 1) | (bit & 1)
            bits_count += 1
            if bits_count == 8:
                output_data.append(bit_buffer)
                bit_buffer = 0
                bits_count = 0
                
        def write_bits(val, n):
            for i in range(n - 1, -1, -1):
                write_bit((val >> i) & 1)
        
        def flush():
            nonlocal bit_buffer, bits_count
            if bits_count > 0:
                bit_buffer <<= (8 - bits_count)
                output_data.append(bit_buffer)
                bits_count = 0

        i = 0
        while i < len(data):
            # Search for best match
            best_pos = -1
            best_len = 0
            
            # Max length is 17
            max_search_len = min(self.max_len, len(data) - i)
            
            if max_search_len >= self.threshold:
                for pos in range(self.dict_size):
                    match_len = 0
                    # Simulate the circular buffer matching
                    # to handle cases where match_pos and dict_pos overlap
                    cur_match_pos = pos
                    # We can't easily modify the dictionary during search without backup
                    # but we can observe that:
                    # dictionary[cur_match_pos] is what we'd read.
                    # If we match, we'd write it to dictionary[cur_dict_pos].
                    # This only matters if cur_match_pos is one of the positions 
                    # we just wrote to during *this* match.
                    
                    # For simplicity and speed, let's use a small simulation:
                    while match_len < max_search_len:
                        # Value that would be at cur_match_pos
                        # It's either from the current dictionary or from 
                        # bytes we've already matched in this specific loop.
                        # (This handles the RLE case)
                        
                        # Distance from start of match
                        # If cur_match_pos was already overwritten by this match:
                        # This happens if cur_match_pos is in [dict_pos, dict_pos + l - 1] (circular)
                        
                        # Let's just use a temporary buffer or a clever check.
                        # Actually, a simple check:
                        # If l > 0 and we are reading a position we just wrote:
                        # The "distance" from dict_pos to cur_match_pos is (cur_match_pos - dict_pos) % 256.
                        # If this distance is < l, it means we are reading a byte we just wrote.
                        
                        if match_len > 0:
                            dist = (cur_match_pos - dict_pos) % self.dict_size
                            if dist < match_len:
                                # We are reading a byte we just matched
                                # The byte we wrote at distance 'dist' from dict_pos
                                # was data[i + dist]
                                val = data[i + dist]
                            else:
                                val = dictionary[cur_match_pos]
                        else:
                            val = dictionary[cur_match_pos]
                            
                        if data[i + match_len] == val:
                            match_len += 1
                            cur_match_pos = (cur_match_pos + 1) & 0xFF
                        else:
                            break
                    
                    if match_len > best_len:
                        best_len = match_len
                        best_pos = pos
                        if best_len == max_search_len:
                            break
            
            if best_len >= self.threshold:
                # Write match
                write_bit(0)
                write_bits(best_pos, 8)
                write_bits(best_len - self.threshold, 4)
                # Update dictionary
                for _ in range(best_len):
                    dictionary[dict_pos] = data[i]
                    dict_pos = (dict_pos + 1) & 0xFF
                    i += 1
            else:
                # Write literal
                write_bit(1)
                write_bits(data[i], 8)
                # Update dictionary
                dictionary[dict_pos] = data[i]
                dict_pos = (dict_pos + 1) & 0xFF
                i += 1
                
        flush()
        return bytes(output_data)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Decompress: python lzss.py -d <input_file> [output_file]")
        print("  Compress:   python lzss.py -c <input_file> [output_file]")
        print("\nNote: Without -c/-d, defaults to decompression if file ends in .TBZ, else compression.")
        return

    mode = None
    args = sys.argv[1:]
    
    if args[0] == "-d":
        mode = "decompress"
        args = args[1:]
    elif args[0] == "-c":
        mode = "compress"
        args = args[1:]
        
    if not args:
        print("Error: Input file not specified.")
        return
        
    input_path = args[0]
    
    if mode is None:
        if input_path.upper().endswith(".TBZ"):
            mode = "decompress"
        else:
            mode = "compress"
            
    if len(args) >= 2:
        output_path = args[1]
    else:
        if mode == "decompress":
            if input_path.upper().endswith(".TBZ"):
                output_path = input_path[:-4] + ".dec"
            else:
                output_path = input_path + ".dec"
        else:
            output_path = input_path + ".TBZ"

    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    with open(input_path, "rb") as f:
        data = f.read()

    lzss = LZSS_GSS2()
    
    if mode == "decompress":
        result = lzss.decompress(data)
        verb = "Decompressed"
    else:
        result = lzss.compress(data)
        verb = "Compressed"

    with open(output_path, "wb") as f:
        f.write(result)
    
    print(f"{verb} {input_path} -> {output_path} ({len(result)} bytes)")

if __name__ == "__main__":
    main()
