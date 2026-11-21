#!/usr/bin/env python3
"""Chia hàng đợi ứng viên cho 4 người review — chia THEO ẢNH (một ảnh chỉ một người xem).

  python tools/chia_review.py <candidates.json> --out <thư_mục> [--names khanh loan quan an]

Ra <thư_mục>/review_<k>_<tên>.csv với cột image,type,verdict,note,candidate_type,evidence_count.
Cột verdict và note ĐỂ TRỐNG: người xem ảnh tự điền (không điền sẵn chữ máy).
Cột bang_chung (máy ghi) chỉ để biết dòng ứng với box số mấy / mask nào — KHÔNG chép vào note.
Thứ tự trong mỗi file: ảnh có missing_box / class_disagreement trước, ảnh ít bằng chứng trước,
ảnh đông vật (nhiều bằng chứng) để cuối — hết giờ thì dừng, dòng chưa xem không đưa vào errors.json.
Sau đó mỗi người xem ảnh của mình:  python tools/view.py <delivery> --review <file csv của mình> --open
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PRIORITY = {"missing_box": 0, "class_disagreement": 1, "instance_merge": 2, "bbox_drift": 3}


def evidence_text(r: dict) -> str:
    """Bằng chứng gọn để biết dòng CSV ứng với box/mask nào. Số box = số "N." trên khung detection."""
    parts = []
    for e in r.get("evidence", [])[:4]:
        if "detection_class" in e:
            parts.append(f"box {e.get('box_index')}: detection={e['detection_class']} / mask={e.get('panoptic_class')}")
        elif "box_indices" in e:
            parts.append(f"mask {e.get('class_name')} phủ box {'+'.join(map(str, e['box_indices']))}")
        elif "box_index" in e:
            cov = e.get("segment_coverage")
            parts.append(f"box {e['box_index']} {e.get('class_name', '')}" + (f" (box phủ {cov:.0%} mask)" if cov is not None else ""))
        else:
            parts.append(", ".join(f"{k}={v}" for k, v in e.items() if k != "segment_id"))
    more = len(r.get("evidence", [])) - 4
    return " | ".join(parts) + (f" | +{more} cặp nữa" if more > 0 else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--out", required=True)
    ap.add_argument("--names", nargs="+", default=["khanh", "loan", "quan", "an"])
    args = ap.parse_args()

    cands = json.loads(Path(args.candidates).read_text(encoding="utf-8"))["candidates"]
    by_image: dict[str, list[dict]] = {}
    for c in cands:
        by_image.setdefault(c["target"], []).append(c)

    def key(img: str):
        rows = by_image[img]
        best = min(PRIORITY.get(r["type"], 9) for r in rows)
        evid = min(len(r.get("evidence", [])) for r in rows)
        return (best, evid, img)

    images = sorted(by_image, key=key)
    buckets: list[list[str]] = [[] for _ in args.names]
    for i, img in enumerate(images):                      # chia vòng: mỗi người đều có ảnh ưu tiên
        buckets[i % len(args.names)].append(img)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for k, (name, imgs) in enumerate(zip(args.names, buckets), start=1):
        path = out / f"review_{k}_{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["image", "type", "verdict", "note", "candidate_type", "evidence_count", "bang_chung"])
            for img in imgs:
                for r in sorted(by_image[img], key=lambda r: PRIORITY.get(r["type"], 9)):
                    t = r["type"] if r["type"] != "class_disagreement" else ""
                    w.writerow([img, t, "", "", r["type"], len(r.get("evidence", [])), evidence_text(r)])
        print(f"{path}: {len(imgs)} ảnh, {sum(len(by_image[i]) for i in imgs)} dòng")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
