#!/usr/bin/env python3
"""Validator của nhóm — Lab Day 10 (Dataset Release & Handover).

    python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]

Luật chơi (RULES.md): chỉ đọc thư mục delivery được truyền vào, chỉ thư viện chuẩn,
không mạng, không đọc _private/ hay data_source/.

Phân công:
  A (Khánh)  : khung + missing_image, wrong_hash, invalid_class, bbox_out_of_bounds, duplicate_box
  B (Loan)   : scene_leak, guideline_mismatch, invalid_category_id, thing_overlap   -> các hàm check_* đang để trống
  C (Quân)   : find_candidates (đối chiếu detection <-> panoptic)                   -> đang để trống
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

# Được phép import hàm đọc PNG của đề (scripts/pngutil.py, thư viện chuẩn) — dùng cho thing_overlap.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

# ---------------------------------------------------------------------------
# Ngưỡng (đặt tên rõ để vấn đáp giải thích được)
# ---------------------------------------------------------------------------
# bbox_out_of_bounds: nhãn YOLO ghi 6 chữ số thập phân nên mép box tự nhiên có thể lệch
# ~1e-6. Bỏ qua sai số làm tròn đó, còn tràn dù chỉ 1 pixel vẫn báo.
OOB_EPS = 1e-4            # theo đơn vị chuẩn hoá 0..1 (≈ 0,06 px với ảnh rộng 640)

# duplicate_box: box lặp = cùng lớp, CÙNG kích thước, tâm lệch 1–2 px.
# Đo trên lô luyện tập: cặp gài lỗi lệch kích thước đúng 0 px; cặp COCO tự nhiên gần nhau
# vẫn lệch kích thước ≥ 0,7 px ở ít nhất một chiều -> dùng 0,1 px làm "cùng kích thước".
DUP_SIZE_PX = 0.1          # chênh rộng/cao tối đa (pixel)
DUP_SHIFT_PX = 4.0         # tâm lệch tối đa (pixel); để rộng hơn 2 px phòng đề ẩn lệch hơn


# ---------------------------------------------------------------------------
# Đọc lô
# ---------------------------------------------------------------------------
def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:                      # băm trên BYTES, không phải text
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jpeg_size(path: Path) -> tuple[int, int] | None:
    """Đọc (rộng, cao) từ header JPEG, dự phòng khi panoptic.json thiếu ảnh."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 9 < len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            return width, height
        pos += 2 + length
    return None


class Delivery:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = read_json(root / "manifest.json")
        self.items: dict = self.manifest["items"]                      # tên ảnh -> đường dẫn + sha256
        self.num_classes = int(self.manifest.get("num_classes", 80))
        self.panoptic = read_json(root / "panoptic.json")
        self.metadata = read_json(root / "metadata.json")
        self._sizes = {Path(im["file_name"]).stem: (im["width"], im["height"])
                       for im in self.panoptic.get("images", [])}

    def path(self, name: str, kind: str) -> Path:
        return self.root / self.items[name][kind]

    def image_size(self, name: str) -> tuple[int, int] | None:
        stem = Path(self.items[name]["image"]).stem
        return self._sizes.get(stem) or jpeg_size(self.path(name, "image"))

    def boxes(self, name: str) -> list[tuple[str, float, float, float, float]]:
        """Các dòng nhãn YOLO: (class_id dạng chuỗi, x, y, w, h) chuẩn hoá 0..1."""
        p = self.path(name, "label")
        if not p.is_file():
            return []
        out = []
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                out.append((parts[0], *map(float, parts[1:])))
            except ValueError:
                continue
        return out


# ---------------------------------------------------------------------------
# Luật — phần A
# ---------------------------------------------------------------------------
def check_missing_image(d: Delivery) -> list[dict]:
    return [{"type": "missing_image", "target": n}
            for n in d.items if not d.path(n, "image").is_file()]


def check_wrong_hash(d: Delivery) -> list[dict]:
    errors = []
    for n, it in d.items.items():
        for kind in ("image", "label", "mask"):
            p, want = d.path(n, kind), it.get(f"{kind}_sha256")
            if want and p.is_file() and sha256_file(p) != want:
                errors.append({"type": "wrong_hash", "target": n})
                break                                   # mỗi ảnh báo một lần
    return errors


def check_invalid_class(d: Delivery) -> list[dict]:
    errors = []
    for n in d.items:
        for c, *_ in d.boxes(n):
            if not c.lstrip("-").isdigit() or not 0 <= int(c) < d.num_classes:
                errors.append({"type": "invalid_class", "target": n})
                break
    return errors


def check_bbox_out_of_bounds(d: Delivery) -> list[dict]:
    errors = []
    for n in d.items:
        for _, x, y, w, h in d.boxes(n):
            left, right, top, bottom = x - w / 2, x + w / 2, y - h / 2, y + h / 2
            if left < -OOB_EPS or top < -OOB_EPS or right > 1 + OOB_EPS or bottom > 1 + OOB_EPS:
                errors.append({"type": "bbox_out_of_bounds", "target": n})
                break
    return errors


def check_duplicate_box(d: Delivery) -> list[dict]:
    errors = []
    for n in d.items:
        size = d.image_size(n)
        if not size:
            continue
        W, H = size
        px = [(c, x * W, y * H, w * W, h * H) for c, x, y, w, h in d.boxes(n)]
        found = False
        for i in range(len(px)):
            for j in range(i + 1, len(px)):
                a, b = px[i], px[j]
                same_class = a[0] == b[0]
                same_size = abs(a[3] - b[3]) <= DUP_SIZE_PX and abs(a[4] - b[4]) <= DUP_SIZE_PX
                shift = max(abs(a[1] - b[1]), abs(a[2] - b[2]))
                if same_class and same_size and shift <= DUP_SHIFT_PX:
                    found = True
                    break
            if found:
                break
        if found:
            errors.append({"type": "duplicate_box", "target": n})
    return errors


# ---------------------------------------------------------------------------
# Luật — phần B (Loan): metadata + panoptic. Mỗi hàm trả về list {"type", "target"}.
# ---------------------------------------------------------------------------
def check_scene_leak(d: Delivery) -> list[dict]:
    return []   # TODO(B): một scene_id có ảnh ở cả train và val -> target là scene_id


def check_guideline_mismatch(d: Delivery) -> list[dict]:
    return []   # TODO(B): guideline_version của ảnh khác guideline của job trong jobs.csv


def check_invalid_category_id(d: Delivery) -> list[dict]:
    return []   # TODO(B): category_id trong segments_info không có trong categories


def check_thing_overlap(d: Delivery) -> list[dict]:
    return []   # TODO(B): đếm pixel từng segment (pngutil.read_rgb, id = R+G*256+B*65536), area khai > pixel thật


RULES = [
    check_missing_image, check_wrong_hash, check_invalid_class, check_bbox_out_of_bounds, check_duplicate_box,
    check_scene_leak, check_guideline_mismatch, check_invalid_category_id, check_thing_overlap,
]


# ---------------------------------------------------------------------------
# Ứng viên lỗi gán nhãn — phần C (Quân)
# ---------------------------------------------------------------------------
def find_candidates(d: Delivery) -> list[dict]:
    return []   # TODO(C): ghép box <-> segment qua TÊN lớp; lệch lớp/vị trí/số vật -> ứng viên để người xem ảnh


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Validator lô bàn giao Day 10")
    ap.add_argument("delivery", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--candidates", type=Path)
    args = ap.parse_args()

    d = Delivery(args.delivery)
    errors, seen = [], set()
    for rule in RULES:
        for e in rule(d):
            key = (e["type"], e["target"])
            if key not in seen:
                seen.add(key)
                errors.append(e)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")

    counts: dict[str, int] = {}
    for e in errors:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    print(f"{len(errors)} lỗi luật -> {args.out}")
    for t, c in sorted(counts.items()):
        print(f"  {t}: {c}")

    if args.candidates:
        cands = find_candidates(d)
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        args.candidates.write_text(json.dumps({"candidates": cands}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(cands)} ứng viên -> {args.candidates}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
