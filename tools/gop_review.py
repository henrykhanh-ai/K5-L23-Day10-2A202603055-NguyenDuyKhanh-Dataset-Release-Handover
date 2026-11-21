#!/usr/bin/env python3
"""Gộp các file review của nhóm thành review_log.csv và kiểm lỗi định dạng trước khi merge_review.

  python tools/gop_review.py review_1_khanh.csv review_2_loan.csv review_3_quan.csv review_4_an.csv --out review_log.csv

- Đọc được file có BOM (do mở bằng Excel); tên ảnh toàn số bị mất số 0 thì bù lại đủ 12 chữ số.
- Thêm cột reviewer (lấy từ tên file) — RULES yêu cầu ghi rõ ai xem.
- BÁO LỖI (không ghi file) nếu: verdict trống/sai, confirmed mà type không phải lỗi gán nhãn
  (vd còn để class_disagreement), note < 20 ký tự, note trùng nhau, một ảnh bị confirmed 2 lỗi.
Không tự sửa nội dung review: chỉ người xem ảnh được sửa verdict/note.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

SEMANTIC = {"class_swap", "bbox_drift", "missing_box", "category_swap", "instance_merge"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows, problems = [], []
    for f in args.files:
        who = re.sub(r"^review_\d+_", "", Path(f).stem)
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for n, r in enumerate(csv.DictReader(fh), start=2):
                img = (r.get("image") or "").strip()
                if img.isdigit() and len(img) < 12:
                    img = img.zfill(12)
                verdict = (r.get("verdict") or "").strip()
                typ = (r.get("type") or "").strip() or (r.get("candidate_type") or "").strip()
                note = (r.get("note") or "").strip()
                where = f"{f}:{n} ({img})"
                if verdict not in ("confirmed", "rejected"):
                    problems.append(f"{where}: verdict trống hoặc sai")
                if verdict == "confirmed" and typ not in SEMANTIC:
                    problems.append(f"{where}: confirmed nhưng type='{typ}' (class_disagreement phải đổi thành class_swap/category_swap)")
                if len(note) < 20:
                    problems.append(f"{where}: note < 20 ký tự")
                rows.append({"image": img, "type": typ, "verdict": verdict, "note": note, "reviewer": who})

    # cùng một note được phép lặp trong CÙNG một ảnh (tả chung cảnh); lặp sang ảnh khác là chép mẫu
    imgs_of: dict[str, set] = {}
    for r in rows:
        imgs_of.setdefault(r["note"], set()).add(r["image"])
    dup_notes = [n for n, s in imgs_of.items() if len(s) > 1 and n]
    for n in dup_notes:
        problems.append(f"note trùng nhau: '{n[:50]}...'")
    multi = [i for i, c in Counter(r["image"] for r in rows if r["verdict"] == "confirmed").items() if c > 1]
    for i in multi:
        problems.append(f"ảnh {i} bị confirmed nhiều hơn 1 lỗi (mỗi ảnh tối đa 1 lỗi)")

    if problems:
        print(f"CHƯA GỘP — {len(problems)} vấn đề:")
        for p in problems:
            print("  -", p)
        return 1
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["image", "type", "verdict", "note", "reviewer"])
        w.writeheader()
        w.writerows(rows)
    conf = sum(r["verdict"] == "confirmed" for r in rows)
    print(f"Đã gộp {len(rows)} dòng ({conf} confirmed, {len({r['image'] for r in rows})} ảnh) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
