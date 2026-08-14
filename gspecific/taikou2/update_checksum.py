import os
import struct
from pathlib import Path


class TR2ChecksumTool:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        with open(file_path, "rb") as f:
            self.data = bytearray(f.read())

    def get_info(self):
        """파일 헤더 정보 및 XOR 키를 추출합니다."""
        # 0x10 위치에서 2바이트(Little Endian) 체크섬 읽기
        stored_sum = struct.unpack("<H", self.data[0x10:0x12])[0]
        # 0x12, 0x13 위치의 시드값으로 XOR 키 계산
        seed1 = self.data[0x12]
        seed2 = self.data[0x13]
        key = seed1 ^ seed2
        return {"stored_sum": stored_sum, "seed1": seed1, "seed2": seed2, "key": key}

    def calculate_correct_sum(self):
        """복호화된 데이터 본체(0x58C~)의 Sum16을 계산합니다."""
        info = self.get_info()
        key = info["key"]

        checksum = 0
        # 0x58C 오프셋부터 파일 끝까지 순회
        for b in self.data[0x58C:]:
            # 각 바이트를 XOR 키로 복호화한 후 합산
            decrypted_byte = b ^ key
            checksum = (checksum + decrypted_byte) & 0xFFFF

        return checksum

    def verify(self):
        """현재 파일의 체크섬이 올바른지 검증합니다."""
        info = self.get_info()
        calculated = self.calculate_correct_sum()
        is_valid = info["stored_sum"] == calculated

        print(f"--- [{os.path.basename(self.file_path)}] 검증 결과 ---")
        print(f"XOR Key (0x12^0x13): 0x{info['key']:02X}")
        print(f"기록된 체크섬 (0x10): 0x{info['stored_sum']:04X}")
        print(f"계산된 체크섬       : 0x{calculated:04X}")
        print(f"상태: {'정상 (VALID)' if is_valid else '오류 (INVALID/MODIFIED)'}")
        return is_valid

    def update_and_save(self, output_path=None):
        """새로운 체크섬을 계산하여 파일에 기록하고 저장합니다."""
        new_checksum = self.calculate_correct_sum()

        # 0x10-0x11 위치에 리틀 엔디안으로 새로운 체크섬 기록
        struct.pack_into("<H", self.data, 0x10, new_checksum)

        save_path = output_path if output_path else self.file_path
        with open(save_path, "wb") as f:
            f.write(self.data)

        print(f"새 체크섬(0x{new_checksum:04X})이 {save_path}에 기록되었습니다.")


# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    # 파일명이 실제 폴더에 있는 이름과 일치하는지 확인하세요.
    ws_num = 2
    base_dir = Path(f"../workspace{ws_num}/kor-dos")
    files_to_check = ["SNDATA1.TR2", "SNDATA2.TR2"]

    for filename in files_to_check:
        file_path = base_dir / filename
        try:
            if file_path.exists():
                tool = TR2ChecksumTool(file_path)
                tool.verify()
                # 수정을 원하시면 아래 주석을 해제하세요.
                # tool.update_and_save()
                print("\n")
            else:
                print(f"파일이 없습니다: {file_path}\n")
        except Exception as e:
            print(f"[{filename}] 에러 발생: {e}\n")
