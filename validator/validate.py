#!/usr/bin/env python3
"""Validator của nhóm — Lab Day 10 (Dataset Release & Handover).

    python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]

Luật chơi (RULES.md): chỉ đọc thư mục delivery được truyền vào, chỉ thư viện chuẩn,
không mạng, không đọc _private/ hay data_source/.

Phân công:
  A (Khánh)  : khung + missing_image, wrong_hash, invalid_class, bbox_out_of_bounds, duplicate_box
  B (Loan)   : scene_leak, guideline_mismatch, invalid_category_id, thing_overlap
  C (Quân)   : find_candidates (đối chiếu detection <-> panoptic, tạo ứng viên để review)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
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
    """Một cảnh có ảnh ở cả train và val -> báo 1 lỗi, target = scene_id."""
    splits_by_scene: dict[str, set[str]] = {}          # scene_id -> {các split gặp được}
    for item in d.metadata.get("items", []):
        scene = item.get("scene_id")
        split = str(item.get("split", "")).strip().lower()
        if not scene or not split:
            continue                                     # dòng thiếu thông tin thì bỏ qua
        splits_by_scene.setdefault(scene, set()).add(split)

    errors = []
    for scene in sorted(splits_by_scene):
        if len(splits_by_scene[scene]) > 1:              # vừa train vừa val
            errors.append({"type": "scene_leak", "target": scene})
    return errors

def check_guideline_mismatch(d: Delivery) -> list[dict]:
    """guideline_version của ảnh khác guideline ghi ở job (jobs.csv) -> target = tên ảnh."""
    job_guideline: dict[str, str] = {}                   # job_id -> guideline của job
    jobs_path = d.root / "jobs.csv"
    if jobs_path.is_file():
        with jobs_path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):                # mỗi dòng thành dict theo tên cột
                job_id = (row.get("job_id") or "").strip()
                if job_id:
                    job_guideline[job_id] = (row.get("guideline") or "").strip()

    errors = []
    for item in d.metadata.get("items", []):
        job_id = str(item.get("job_id", "")).strip()
        expected = job_guideline.get(job_id)
        if expected is None:
            continue                                     # job không có trong jobs.csv thì bỏ qua
        actual = str(item.get("guideline_version", "")).strip()
        if actual != expected:
            errors.append({"type": "guideline_mismatch", "target": Path(item["image"]).stem})
    return errors


def check_invalid_category_id(d: Delivery) -> list[dict]:
    """category_id của segment không có trong categories -> target = tên ảnh (mỗi ảnh 1 lần)."""
    valid_ids = {c.get("id") for c in d.panoptic.get("categories", [])}
    image_name = {im.get("id"): Path(im.get("file_name", "")).stem
                  for im in d.panoptic.get("images", [])}          # image_id -> tên ảnh

    errors = []
    for ann in d.panoptic.get("annotations", []):
        name = image_name.get(ann.get("image_id")) or Path(ann.get("file_name", "")).stem
        if not name:
            continue
        for seg in ann.get("segments_info", []):
            if seg.get("category_id") not in valid_ids:
                errors.append({"type": "invalid_category_id", "target": name})
                break                                    # 1 ảnh chỉ báo 1 lần
    return errors


def check_thing_overlap(d: Delivery) -> list[dict]:
    """area khai báo > số pixel thật của segment trong mask -> target = tên ảnh (mỗi ảnh 1 lần)."""
    import pngutil                                       # scripts/pngutil.py (khung đã thêm đường dẫn)
    from collections import Counter

    image_name = {im.get("id"): Path(im.get("file_name", "")).stem
                  for im in d.panoptic.get("images", [])}

    errors = []
    for ann in d.panoptic.get("annotations", []):
        name = image_name.get(ann.get("image_id")) or Path(ann.get("file_name", "")).stem
        if not name:
            continue
        mask_path = d.root / "masks" / Path(ann.get("file_name") or f"{name}.png").name
        if not mask_path.is_file():
            continue
        try:
            _w, _h, px = pngutil.read_rgb(mask_path)
        except (OSError, ValueError):
            continue                                     # mask hỏng thì bỏ qua, không đoán

        # Đếm pixel theo màu (R, G, B), rồi đổi màu -> segment id = R + G*256 + B*65536
        color_counts = Counter(zip(px[0::3], px[1::3], px[2::3]))
        real = {r + g * 256 + b * 65536: n for (r, g, b), n in color_counts.items()}

        for seg in ann.get("segments_info", []):
            sid = seg.get("id")
            if not sid:                                  # id 0 = nền
                continue
            if (seg.get("area") or 0) > real.get(sid, 0):
                errors.append({"type": "thing_overlap", "target": name})
                break                                    # 1 ảnh chỉ báo 1 lần
    return errors

RULES = [
    check_missing_image, check_wrong_hash, check_invalid_class, check_bbox_out_of_bounds, check_duplicate_box,
    check_scene_leak, check_guideline_mismatch, check_invalid_category_id, check_thing_overlap,
]


# ---------------------------------------------------------------------------
# Ứng viên lỗi gán nhãn — phần C (Quân)
# ---------------------------------------------------------------------------
# Ngưỡng chỉ tạo HÀNG ĐỢI cho người xem ảnh — chọn theo nhiễu đo trên lô sạch
# (runs/clean, --no-faults) + nguyên tắc hình học, KHÔNG dùng _private. Người review
# mới là nơi quyết lỗi thật, nên ưu tiên để hàng đợi đủ nhỏ mà không siết đến mức trống.
CAND_MIN_SEGMENT_PIXELS = 100    # bỏ segment quá nhỏ (nhiễu đa giác thô của COCO)
CAND_MIN_OVERLAP_PIXELS = 32     # cần chạm tối thiểu mới xét, tránh cặp chỉ dính 1-2 px
CAND_MIN_CLASS_OVERLAP = 0.2     # box~segment phủ nhau >=20% mới coi là "cùng vật"
CAND_MIN_DRIFT_OVERLAP = 0.02    # drift = box lệch nên overlap thấp; chỉ cần chạm là đưa vào hàng đợi
CAND_MIN_MATCH_COVERAGE = 0.25   # box phủ >=25% segment mới tính là đã có box cho vật đó
CAND_DRIFT_COVERAGE = 0.5        # box phủ <50% segment cùng lớp -> nghi lệch, cho người xem
CAND_NEARBY_SCALE = 0.75         # chỉ xét cặp box/segment ở gần nhau (so với cạnh lớn hơn)
CAND_MERGE_MAX_PAIR_IOU = 0.8    # 2 box gần như không chồng nhau
CAND_MERGE_MIN_CENTER_SCALE = 0.25  # nhưng tâm cách nhau đủ xa -> 1 segment bị 2 box riêng

def find_candidates(d: Delivery) -> list[dict]:
    """Tạo ứng viên từ detection/panoptic; người xem ảnh quyết định lỗi thật."""
    import warnings

    import pngutil

    class_names: dict[int, str] = {}
    with (d.root / "classes.txt").open(encoding="utf-8-sig") as f:
        for line in f:
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                try:
                    class_names[int(parts[0])] = parts[1].strip()
                except ValueError:
                    continue

    categories = {
        category.get("id"): category
        for category in d.panoptic.get("categories", [])
        if category.get("id") is not None
    }
    image_names = {
        image.get("id"): Path(image.get("file_name", "")).stem
        for image in d.panoptic.get("images", [])
    }
    annotations_by_name: dict[str, dict] = {}
    for annotation in d.panoptic.get("annotations", []):
        name = image_names.get(annotation.get("image_id"))
        if not name and annotation.get("file_name"):
            name = Path(annotation["file_name"]).stem
        if name:
            annotations_by_name[name] = annotation

    candidates: dict[tuple[str, str], dict] = {}

    def add_candidate(kind: str, name: str, evidence: dict) -> None:
        key = (kind, name)
        candidate = candidates.setdefault(
            key, {"type": kind, "target": name, "evidence": []}
        )
        if kind == "class_disagreement":
            candidate["possible_types"] = ["class_swap", "category_swap"]
        candidate["evidence"].append(evidence)

    def intersection_area(a: tuple[float, float, float, float],
                          b: tuple[float, float, float, float]) -> float:
        return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(
            0.0, min(a[3], b[3]) - max(a[1], b[1])
        )

    for name in sorted(d.items):
        annotation = annotations_by_name.get(name)
        size = d.image_size(name)
        mask_path = d.path(name, "mask")
        if annotation is None or size is None:
            continue
        if not mask_path.is_file():
            warnings.warn(f"Skipping cross-check for {name}: missing mask {mask_path}")
            continue

        width, height = size
        mask_width, mask_height, pixels = pngutil.read_rgb(mask_path)
        if (mask_width, mask_height) != (width, height):
            raise ValueError(
                f"Mask/image size mismatch for {name}: "
                f"{mask_width}x{mask_height} vs {width}x{height}"
            )

        segment_info = {
            segment.get("id"): segment
            for segment in annotation.get("segments_info", [])
            if segment.get("id") not in (None, 0)
        }
        # Index contiguous mask runs once; reuse them for box/segment intersections.
        pixel_counts: dict[int, int] = {}
        pixel_bounds: dict[int, list[int]] = {}
        segment_runs: dict[int, list[tuple[int, int, int]]] = {}
        for y in range(height):
            row = y * width * 3
            run_start = 0
            run_id = None
            for x in range(width):
                offset = row + x * 3
                segment_id = (
                    pixels[offset]
                    + pixels[offset + 1] * 256
                    + pixels[offset + 2] * 65536
                )
                if segment_id != run_id:
                    if run_id in segment_info:
                        segment_runs.setdefault(run_id, []).append((y, run_start, x))
                        run_length = x - run_start
                        pixel_counts[run_id] = pixel_counts.get(run_id, 0) + run_length
                        bounds = pixel_bounds.get(run_id)
                        if bounds is None:
                            pixel_bounds[run_id] = [run_start, y, x, y + 1]
                        else:
                            bounds[0] = min(bounds[0], run_start)
                            bounds[1] = min(bounds[1], y)
                            bounds[2] = max(bounds[2], x)
                            bounds[3] = max(bounds[3], y + 1)
                    run_start = x
                    run_id = segment_id
            if run_id in segment_info:
                segment_runs.setdefault(run_id, []).append((y, run_start, width))
                run_length = width - run_start
                pixel_counts[run_id] = pixel_counts.get(run_id, 0) + run_length
                bounds = pixel_bounds.get(run_id)
                if bounds is None:
                    pixel_bounds[run_id] = [run_start, y, width, y + 1]
                else:
                    bounds[0] = min(bounds[0], run_start)
                    bounds[1] = min(bounds[1], y)
                    bounds[2] = max(bounds[2], width)
                    bounds[3] = max(bounds[3], y + 1)

        boxes = []
        for index, (class_id, center_x, center_y, box_width, box_height) in enumerate(
            d.boxes(name)
        ):
            try:
                class_name = class_names[int(class_id)]
            except (ValueError, KeyError):
                continue
            if box_width <= 0 or box_height <= 0:
                continue
            x1 = max(0.0, (center_x - box_width / 2) * width)
            y1 = max(0.0, (center_y - box_height / 2) * height)
            x2 = min(float(width), (center_x + box_width / 2) * width)
            y2 = min(float(height), (center_y + box_height / 2) * height)
            if x2 <= x1 or y2 <= y1:
                continue
            boxes.append({
                "index": index,
                "class_name": class_name,
                "bounds": (x1, y1, x2, y2),
            })

        # Count segment pixels in each detection box using the indexed horizontal runs.
        overlaps: dict[tuple[int, int], int] = {}
        for box_index, box in enumerate(boxes):
            x1, y1, x2, y2 = box["bounds"]
            left, top = max(0, int(x1)), max(0, int(y1))
            right = min(width, math.ceil(x2))
            bottom = min(height, math.ceil(y2))
            for segment_id, runs in segment_runs.items():
                count = sum(
                    max(0, min(run_end, right) - max(run_start, left))
                    for y, run_start, run_end in runs
                    if top <= y < bottom
                )
                if count:
                    overlaps[(segment_id, box_index)] = count

        for segment_id, segment in sorted(segment_info.items()):
            category = categories.get(segment.get("category_id"))
            if not category or not category.get("isthing") or segment.get("iscrowd"):
                continue
            actual_area = pixel_counts.get(segment_id, 0)
            bounds = pixel_bounds.get(segment_id)
            if actual_area < CAND_MIN_SEGMENT_PIXELS or bounds is None:
                continue

            segment_name = category.get("name")
            segment_box = tuple(float(value) for value in bounds)
            segment_width = segment_box[2] - segment_box[0]
            segment_height = segment_box[3] - segment_box[1]
            segment_center = (
                (segment_box[0] + segment_box[2]) / 2,
                (segment_box[1] + segment_box[3]) / 2,
            )
            hit_boxes = []
            same_class_nearby = False
            different_class_hit = False

            for box_index, box in enumerate(boxes):
                box_bounds = box["bounds"]
                overlap = overlaps.get((segment_id, box_index), 0)
                segment_coverage = overlap / actual_area
                box_area = max(
                    1.0,
                    (box_bounds[2] - box_bounds[0]) * (box_bounds[3] - box_bounds[1]),
                )
                box_coverage = overlap / box_area
                iou = intersection_area(segment_box, box_bounds) / max(
                    1.0,
                    (segment_width * segment_height)
                    + (box_bounds[2] - box_bounds[0])
                    * (box_bounds[3] - box_bounds[1])
                    - intersection_area(segment_box, box_bounds),
                )
                box_center = (
                    (box_bounds[0] + box_bounds[2]) / 2,
                    (box_bounds[1] + box_bounds[3]) / 2,
                )
                scale = max(
                    segment_width,
                    segment_height,
                    box_bounds[2] - box_bounds[0],
                    box_bounds[3] - box_bounds[1],
                    1.0,
                )
                center_distance = (
                    (box_center[0] - segment_center[0]) ** 2
                    + (box_center[1] - segment_center[1]) ** 2
                ) ** 0.5
                nearby = iou >= 0.05 or center_distance <= CAND_NEARBY_SCALE * scale

                if box["class_name"] != segment_name:
                    if (
                        overlap >= CAND_MIN_OVERLAP_PIXELS
                        and segment_coverage >= CAND_MIN_CLASS_OVERLAP
                        and box_coverage >= CAND_MIN_CLASS_OVERLAP
                    ):
                        different_class_hit = True
                        add_candidate("class_disagreement", name, {
                            "detection_class": box["class_name"],
                            "panoptic_class": segment_name,
                            "box_index": box["index"],
                            "segment_id": segment_id,
                            "segment_coverage": round(segment_coverage, 3),
                            "box_coverage": round(box_coverage, 3),
                        })
                    continue

                drift_overlap = (
                    overlap >= CAND_MIN_OVERLAP_PIXELS
                    and segment_coverage >= CAND_MIN_DRIFT_OVERLAP
                )
                # Overlap tí xíu không nên tính là "đã có box" cho vật, kẻo che mất
                # missing_box. Nên same_class_nearby đòi overlap đáng kể (>=20%),
                # còn bbox_drift vẫn xét ngay cả khi overlap thấp (box lệch khỏi vật).
                match_overlap = (
                    overlap >= CAND_MIN_OVERLAP_PIXELS
                    and segment_coverage >= CAND_MIN_CLASS_OVERLAP
                )
                if nearby and match_overlap:
                    same_class_nearby = True
                if overlap >= CAND_MIN_OVERLAP_PIXELS:
                    hit_boxes.append((box, overlap, segment_coverage, box_coverage))
                if (
                    nearby
                    and drift_overlap
                    and segment_coverage < CAND_DRIFT_COVERAGE
                ):
                    add_candidate("bbox_drift", name, {
                        "class_name": segment_name,
                        "box_index": box["index"],
                        "segment_id": segment_id,
                        "segment_coverage": round(segment_coverage, 3),
                        "bbox_iou": round(iou, 3),
                        "center_distance_scale": round(center_distance / scale, 3),
                    })

            strong_hits = [
                hit for hit in hit_boxes
                if hit[2] >= CAND_MIN_MATCH_COVERAGE and hit[3] >= 0.1
            ]
            merge_pair = None
            for first_index, first in enumerate(strong_hits):
                first_bounds = first[0]["bounds"]
                first_width = first_bounds[2] - first_bounds[0]
                first_height = first_bounds[3] - first_bounds[1]
                first_center = (
                    (first_bounds[0] + first_bounds[2]) / 2,
                    (first_bounds[1] + first_bounds[3]) / 2,
                )
                for second in strong_hits[first_index + 1:]:
                    second_bounds = second[0]["bounds"]
                    second_width = second_bounds[2] - second_bounds[0]
                    second_height = second_bounds[3] - second_bounds[1]
                    second_center = (
                        (second_bounds[0] + second_bounds[2]) / 2,
                        (second_bounds[1] + second_bounds[3]) / 2,
                    )
                    center_distance = (
                        (first_center[0] - second_center[0]) ** 2
                        + (first_center[1] - second_center[1]) ** 2
                    ) ** 0.5
                    pair_iou = intersection_area(first_bounds, second_bounds) / max(
                        1.0,
                        first_width * first_height
                        + second_width * second_height
                        - intersection_area(first_bounds, second_bounds),
                    )
                    distinct_scale = min(
                        max(first_width, first_height),
                        max(second_width, second_height),
                    )
                    if (
                        pair_iou < CAND_MERGE_MAX_PAIR_IOU
                        and center_distance >= CAND_MERGE_MIN_CENTER_SCALE * distinct_scale
                    ):
                        merge_pair = (first, second)
                        break
                if merge_pair:
                    break

            if merge_pair:
                add_candidate("instance_merge", name, {
                    "class_name": segment_name,
                    "segment_id": segment_id,
                    "box_indices": [hit[0]["index"] for hit in merge_pair],
                })
            elif not strong_hits and not same_class_nearby and not different_class_hit:
                add_candidate("missing_box", name, {
                    "class_name": segment_name,
                    "segment_id": segment_id,
                    "segment_pixels": actual_area,
                })

    return [
        candidates[key]
        for key in sorted(candidates)
    ]


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