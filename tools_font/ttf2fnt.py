import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTCollection

CELL_SIZE = 16
BASE_OFFSET = 0  # 나중에 8x8, 8x16 글꼴 추가시 보정 가능


# ---------------- 글자 렌더링 ----------------
def render_char(ch, font):
    glyph = Image.new("1", (CELL_SIZE, CELL_SIZE), 0)
    draw = ImageDraw.Draw(glyph)
    bbox = font.getbbox(ch)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (CELL_SIZE - w) // 2 - bbox[0]
    y = (CELL_SIZE - h) // 2 - bbox[1]
    draw.text((x, y), ch, font=font, fill=1)
    return glyph


# ---------------- 비트맵 변환 ----------------
def process_range(font, start_lead, end_lead, y_offset, img, bin_file, table, base_offset=0):
    rows = end_lead - start_lead + 1
    for row, lead in enumerate(range(start_lead, end_lead + 1)):
        for col, trail in enumerate(range(0xA1, 0xFF)):
            code = (lead << 8) | trail
            try:
                ch = bytes([lead, trail]).decode("cp949")
            except UnicodeDecodeError:
                continue

            glyph = render_char(ch, font)
            x = col * CELL_SIZE
            y = y_offset + row * CELL_SIZE
            img.paste(glyph, (x, y))

            bits = []
            for yy in range(CELL_SIZE):
                byte = 0
                for xx in range(CELL_SIZE):
                    byte = (byte << 1) | glyph.getpixel((xx, yy))
                    if (xx % 8) == 7:
                        bits.append(byte)
                        byte = 0
                if CELL_SIZE % 8 != 0:
                    bits.append(byte << (8 - CELL_SIZE % 8))
            offset = bin_file.tell()
            bin_file.write(bytes(bits))
            table.append((code, base_offset + offset))
    return y_offset + rows * CELL_SIZE


# ---------------- 전체 변환 ----------------
def make_full(ttf_path, areas, font_index=0, base_offset=0):
    outdir = os.path.dirname(os.path.abspath(__file__))
    font = ImageFont.truetype(ttf_path, CELL_SIZE, index=font_index)

    font_base = os.path.splitext(os.path.basename(ttf_path))[0]
    if ttf_path.lower().endswith(".ttc"):
        font_base += f"_{font_index}"

    cols = 94
    total_rows = sum(end - start + 1 for start, end, _ in areas)
    img = Image.new("1", (cols * CELL_SIZE, total_rows * CELL_SIZE), 0)

    bmp_path = os.path.join(outdir, f"{font_base}_cp949_full.bmp")
    bin_path = os.path.join(outdir, f"{font_base}_cp949_full.bin")
    tbl_path = os.path.join(outdir, f"{font_base}_cp949_full.tbl")

    y_offset = 0
    table = []
    with open(bin_path, "wb") as bin_file:
        for start, end, label in areas:
            y_offset = process_range(font, start, end, y_offset, img, bin_file, table, base_offset)

    img.save(bmp_path, "BMP")

    # ---------------- 오프셋 16진수 출력 ----------------
    with open(tbl_path, "w", encoding="utf-8") as f:
        for code, off in table:
            f.write(f"{code:04X},{off:08X}\n")

    return bmp_path, bin_path, tbl_path


# ---------------- UI ----------------
class FontToolUI:
    def __init__(self, root):
        self.root = root
        root.title("TTF/TTC → CP949 Bitmap Converter")

        self.ttf_path = tk.StringVar()
        self.font_index = tk.IntVar(value=0)

        tk.Label(root, text="폰트 파일:").grid(row=0, column=0, sticky="w")
        tk.Entry(root, textvariable=self.ttf_path, width=40).grid(row=0, column=1)
        tk.Button(root, text="찾기", command=self.select_font).grid(row=0, column=2)

        tk.Label(root, text="TTC 인덱스:").grid(row=1, column=0, sticky="w")
        self.index_combo = ttk.Combobox(root, textvariable=self.font_index, width=5, state="readonly")
        self.index_combo.grid(row=1, column=1, sticky="w")

        self.preview_canvas = tk.Canvas(root, width=300, height=50, bg="white")
        self.preview_canvas.grid(row=2, column=0, columnspan=3, pady=5)

        # ---------------- 체크박스 프레임으로 균등 정렬 ----------------
        frame_chk = tk.Frame(root)
        frame_chk.grid(row=3, column=0, columnspan=3, sticky="w", pady=2)

        self.symbols_var = tk.BooleanVar(value=True)
        self.hangul_var = tk.BooleanVar(value=True)
        self.hanja_var = tk.BooleanVar(value=True)

        tk.Checkbutton(frame_chk, text="부호 (A1A1-ACFE)", variable=self.symbols_var).pack(side="left", padx=5)
        tk.Checkbutton(frame_chk, text="한글 (B0A1-C8FE)", variable=self.hangul_var).pack(side="left", padx=5)
        tk.Checkbutton(frame_chk, text="한자 (CAA1-FDFE)", variable=self.hanja_var).pack(side="left", padx=5)

        tk.Button(root, text="변환 실행", command=self.run).grid(row=4, column=0, columnspan=3, pady=10)

    # ---------------- 폰트 선택 ----------------
    def select_font(self):
        folder = os.path.dirname(os.path.abspath(__file__))
        path = filedialog.askopenfilename(
            title="TTF/TTC 폰트를 선택하세요",
            initialdir=folder,
            filetypes=[("Font Files", "*.ttf *.ttc"), ("All Files", "*.*")],
        )
        if path:
            self.ttf_path.set(path)
            self.update_font_index_options()
            self.update_preview()

    def update_font_index_options(self):
        """TTC 파일인 경우 폰트 인덱스 옵션 업데이트"""
        if self.ttf_path.get().lower().endswith(".ttc"):
            try:
                ttc = TTCollection(self.ttf_path.get())
                indices = list(range(len(ttc)))
                self.index_combo["values"] = indices
                self.index_combo.set(0)
            except Exception:
                self.index_combo["values"] = [0]
                self.index_combo.set(0)
        else:
            self.index_combo["values"] = [0]
            self.index_combo.set(0)

    def update_preview(self):
        """폰트 미리보기 업데이트"""
        self.preview_canvas.delete("all")
        if not self.ttf_path.get():
            return

        try:
            ImageFont.truetype(self.ttf_path.get(), 20, index=self.font_index.get())
            self.preview_canvas.create_text(150, 25, text="한글 ABC 123", font=("Arial", 12), fill="black")
        except (OSError, ValueError):
            self.preview_canvas.create_text(150, 25, text="폰트 로드 실패", fill="red")

    def run(self):
        """변환 실행"""
        if not self.ttf_path.get():
            messagebox.showerror("오류", "폰트 파일을 선택하세요.")
            return

        try:
            areas = []
            if self.symbols_var.get():
                areas.append((0xA1, 0xAC, "부호"))
            if self.hangul_var.get():
                areas.append((0xB0, 0xC8, "한글"))
            if self.hanja_var.get():
                areas.append((0xCA, 0xFD, "한자"))

            if not areas:
                messagebox.showerror("오류", "최소 하나의 영역을 선택하세요.")
                return

            bmp_path, bin_path, tbl_path = make_full(self.ttf_path.get(), areas, self.font_index.get(), BASE_OFFSET)

            messagebox.showinfo("완료", f"변환 완료!\n\nBMP: {bmp_path}\nBIN: {bin_path}\nTBL: {tbl_path}")

        except Exception as e:
            messagebox.showerror("오류", f"변환 중 오류 발생:\n{str(e)}")


# ---------------- 메인 실행 ----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = FontToolUI(root)
    root.mainloop()
