#!/usr/bin/env python3
"""Dựng lô bàn giao v2 từ delivery v1 + errors.json (D, Pha 4). Không sửa gì trong delivery/.

  python3 tools/build_v2.py --run runs/r5007

Tạo runs/<run>/handover/<release_id>_v2/ gồm images/, labels/, rework_queue.csv, manifest.csv (phần D).
label_summary.csv + truyvet.csv (C) và README.txt (B) chép vào sau; rồi pack_release.py, check_handover.
Chạy lại script sẽ xoá và dựng lại cả thư mục v2: chép lại file của B, C sau đó.

Quy tắc (GUIDE Pha 4):
- Lỗi nhãn detection / thiếu file -> rework_queue.csv, bỏ khỏi v2 (giao lại người gán/kiểm theo jobs.csv).
- Lỗi chỉ ở panoptic -> ảnh ở lại v2, ghi vào Ghi chú README để báo team panoptic.
- wrong_hash (đã mở ảnh kiểm: còn nguyên) -> manifest v2 tính lại sha256.
- guideline_mismatch -> truyvet.csv ghi guideline theo job.
- scene_leak -> cả cảnh về split chiếm đa số trong cảnh.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import shutil
from pathlib import Path

DET_REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box",
              "class_swap", "bbox_drift", "missing_box"}
PANOPTIC_ONLY = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}
ACTION = {
    "missing_image": "bổ sung ảnh gốc rồi kiểm lại nhãn",
    "invalid_class": "gán lại lớp trong 0-79 theo classes.txt",
    "bbox_out_of_bounds": "vẽ lại box nằm trong khung ảnh",
    "duplicate_box": "xóa box trùng",
    "class_swap": "sửa lớp detection cho đúng vật",
    "bbox_drift": "vẽ lại box ôm sát vật",
    "missing_box": "vẽ thêm box cho vật bị thiếu",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dựng lô v2")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run = Path(args.run)
    d = run / "delivery"
    rid = json.loads((d / "release.json").read_text(encoding="utf-8"))["release_id"]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = {m["image"]: m for m in json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]}
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}

    errors = json.loads((run / "errors.json").read_text(encoding="utf-8"))["errors"]

    # 1. Chia lỗi
    rework = [e for e in errors if e["target"] in man and e["type"] in DET_REWORK]
    rework_imgs = {e["target"] for e in rework}
    panoptic = [e for e in errors if e["type"] in PANOPTIC_ONLY and e["target"] not in rework_imgs]
    hash_fixed = [e["target"] for e in errors if e["type"] == "wrong_hash"]
    gl_fixed = [e["target"] for e in errors if e["type"] == "guideline_mismatch"]

    # scene_leak: cả cảnh về split đa số
    split = {s: m["split"] for s, m in meta.items()}
    leak_notes = []
    for e in errors:
        if e["type"] != "scene_leak":
            continue
        imgs = sorted(s for s, m in meta.items() if m["scene_id"] == e["target"])
        major = collections.Counter(split[s] for s in imgs).most_common(1)[0][0]
        moved = [s for s in imgs if split[s] != major]
        for s in moved:
            split[s] = major
        leak_notes.append(f"{e['target']} đưa cả cảnh về {major} (chuyển {', '.join(moved)})")

    # 2. Thư mục v2
    v2 = run / "handover" / f"{rid}_v2"
    if v2.exists():
        shutil.rmtree(v2)
    (v2 / "images").mkdir(parents=True)
    (v2 / "labels").mkdir()
    keep = sorted(s for s in man if s not in rework_imgs and (d / man[s]["image"]).is_file())
    for s in keep:
        shutil.copyfile(d / man[s]["image"], v2 / "images" / f"{s}.jpg")
        shutil.copyfile(d / man[s]["label"], v2 / "labels" / f"{s}.txt")

    # 3. rework_queue.csv
    rows = []
    for e in sorted(rework, key=lambda e: e["target"]):
        j = jobs[meta[e["target"]]["job_id"]]
        rows.append([e["target"], e["type"], j["annotator"], j["reviewer"], ACTION[e["type"]]])
    write_csv(v2 / "rework_queue.csv", ["image", "type", "annotator", "reviewer", "action"], rows)

    # 4. manifest.csv (sha256 tính lại từ file thật)
    files = sorted(p for sub in ("images", "labels") for p in (v2 / sub).iterdir() if p.is_file())
    write_csv(v2 / "manifest.csv", ["file", "sha256"], [[p.relative_to(v2).as_posix(), sha(p)] for p in files])

    # label_summary.csv + truyvet.csv là phần của C, README.txt là phần của B: không sinh ở đây.
    # In số liệu phân loại để bàn giao cho B (README) và C (truyvet: split / guideline đã sửa).
    total = sum(1 for s in keep for ln in (v2 / "labels" / f"{s}.txt").read_text(encoding="utf-8").splitlines() if ln.strip())
    n_err = len({e["target"] for e in errors})
    owners = collections.defaultdict(list)
    for e in rework:
        j = jobs[meta[e["target"]]["job_id"]]
        owners[f"{j['annotator']}/{j['reviewer']}"].append(e["target"])
    print(f"{v2}: {len(keep)} ảnh, {total} nhãn")
    print(f"QC v1: {n_err}/{len(man)} = {n_err / len(man) * 100:.1f}%  (ngưỡng 2%)")
    print(f"Rework ({len(rework_imgs)} ảnh, rời v2): " + "; ".join(f"{k}: {', '.join(sorted(v))}" for k, v in sorted(owners.items())))
    print("Ở lại v2, báo team panoptic: " + ", ".join(f"{e['target']} ({e['type']})" for e in sorted(panoptic, key=lambda e: e["target"])))
    print("Sửa split: " + ("; ".join(leak_notes) or "không có"))
    print("Sửa hash (ảnh còn nguyên, manifest.csv ghi sha256 mới): " + (", ".join(hash_fixed) or "không có"))
    print("Sửa guideline theo job: " + ", ".join(f"{s} -> {jobs[meta[s]['job_id']]['guideline']} ({meta[s]['job_id']})" for s in gl_fixed))
    print("Còn thiếu để pack: label_summary.csv, truyvet.csv (C), README.txt (B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
