#!/usr/bin/env python3
"""Công cụ xem ảnh cho Pha 2: vẽ box detection và viền segment panoptic lên ảnh.

Mỗi ảnh được vẽ thành hai khung cạnh nhau, đã phóng to (mặc định x2):
  1. Detection: box YOLO + tên lớp (màu đỏ cam)
  2. Panoptic: viền từng vật (thing) + tên lớp, kèm box detection nét đứt trắng
Thêm --orig để có khung ảnh gốc, --stuff để vẽ cả viền nền (tường, sân, trời).

Dùng (macOS/Linux gõ python3, Windows gõ py; thay <delivery> bằng đường dẫn thật):
  python3 tools/view.py <delivery> 000000000724 000000000885      # xem vài ảnh
  python3 tools/view.py <delivery> --all --open                   # xem mọi ảnh, tự mở trình duyệt
  python3 tools/view.py <delivery> --candidates candidates.json   # xem danh sách ứng viên
  python3 tools/view.py <delivery> --candidates c.json --type class_swap
Kết quả: <out>/<ảnh>.png và <out>/index.html (mở bằng trình duyệt để cuộn xem).
Mặc định --out là view_out/ ở thư mục hiện tại.
Chạy được trên macOS, Linux, Windows (cần Pillow: python3 -m pip install pillow / py -m pip install pillow).

Công cụ này CHỈ ĐỌC thư mục delivery. Được dùng Pillow (validator thì không).
"""
import argparse
import csv
import html
import json
import sys
import webbrowser
from pathlib import Path

# Windows: console mặc định không phải UTF-8, in tiếng Việt dễ lỗi. Ép UTF-8 để không crash.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Cần Pillow. macOS/Linux: python3 -m pip install pillow   Windows: py -m pip install pillow\n"
             "(chỉ công cụ xem ảnh cần Pillow, validator thì không)")

NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")

DET_COLOR = (255, 90, 40)
BOX_ON_SEG = (255, 255, 255)
PALETTE = [(46, 204, 113), (52, 152, 219), (155, 89, 182), (241, 196, 15), (26, 188, 156),
           (230, 126, 34), (231, 76, 60), (236, 240, 241), (52, 73, 94), (253, 121, 168)]


# Tên font có chữ tiếng Việt trên từng hệ điều hành (Pillow tự tìm trong thư mục font hệ thống).
FONT_CANDIDATES = (
    "arial.ttf", "Arial.ttf", "segoeui.ttf", "tahoma.ttf", "calibri.ttf",   # Windows
    "Arial Unicode.ttf", "Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
    "DejaVuSans.ttf", "LiberationSans-Regular.ttf",                         # Linux
)
HAS_TTF = False


def font(size):
    global HAS_TTF
    for name in FONT_CANDIDATES:
        try:
            f = ImageFont.truetype(name, size)
            HAS_TTF = True
            return f
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except (TypeError, OSError, ImportError):  # Pillow cũ, hoặc thiếu FreeType: dùng font bitmap nhỏ
        return ImageFont.load_default()


def T(vi, ascii_text):
    """Chữ tiêu đề vẽ lên ảnh: có font TTF thì dùng tiếng Việt, không thì dùng bản không dấu (tránh ô vuông)."""
    font(12)  # đảm bảo HAS_TTF đã được dò
    return vi if HAS_TTF else ascii_text


def load_classes(root):
    names = {}
    p = root / "classes.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                names[int(parts[0])] = parts[1]
    return names


def load_panoptic(root):
    p = root / "panoptic.json"
    if not p.exists():
        return {}, {}
    d = json.loads(p.read_text(encoding="utf-8"))
    cats = {c["id"]: c for c in d.get("categories", [])}
    segs = {}
    for a in d.get("annotations", []):
        key = Path(a.get("file_name", "")).stem or str(a.get("image_id"))
        segs[key] = a.get("segments_info", [])
    return cats, segs


def read_yolo(path):
    rows = []
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) != 5:
            continue
        try:
            rows.append((int(float(p[0])), *map(float, p[1:])))
        except ValueError:
            continue
    return rows


def find_file(folder, stem, exts):
    for e in exts:
        f = folder / (stem + e)
        if f.exists():
            return f
    return None


def draw_label(d, xy, text, color, f):
    x, y = xy
    try:
        l, t, r, b = d.textbbox((x, y), text, font=f)
    except AttributeError:
        r, b = x + 7 * len(text), y + 12
    d.rectangle([x, y, r + 3, b + 2], fill=(0, 0, 0))
    d.text((x + 2, y), text, fill=color, font=f)


def dashed_rect(d, box, color, width=1, dash=6):
    x0, y0, x1, y1 = box
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        n = max(abs(bx - ax), abs(by - ay))
        for i in range(0, int(n), dash * 2):
            s, e = i / n, min(i + dash, n) / n
            d.line([ax + (bx - ax) * s, ay + (by - ay) * s, ax + (bx - ax) * e, ay + (by - ay) * e],
                   fill=color, width=width)


def render(root, stem, scale, classes, cats, segs, tag="", show_stuff=False, show_orig=False):
    """Trả về (ảnh PIL, danh sách ghi chú). Thiếu file thì ghi chú, không crash."""
    notes = []
    img_path = find_file(root / "images", stem, (".jpg", ".jpeg", ".png"))
    if img_path is None:
        notes.append("THIẾU ẢNH trong images/")
        canvas = Image.new("RGB", (480, 120), (40, 40, 40))
        ImageDraw.Draw(canvas).text((10, 50), f"{stem}: " + T("thiếu ảnh. ", "missing image. ") + tag, fill=(255, 120, 120), font=font(16))
        return canvas, notes
    base = Image.open(img_path).convert("RGB")
    w, h = base.size
    big = (w * scale, h * scale)
    f = font(max(11, 4 * scale + 6))
    lw = max(1, scale)

    # Khung 1: ảnh gốc
    p1 = base.resize(big, NEAREST)

    # Khung 2: detection
    p2 = p1.copy()
    d2 = ImageDraw.Draw(p2)
    rows = read_yolo(root / "labels" / (stem + ".txt"))
    boxes_px = []
    if rows is None:
        notes.append("thiếu file labels/")
    else:
        for bi, (cid, xc, yc, bw, bh) in enumerate(rows):
            x0, y0 = (xc - bw / 2) * w * scale, (yc - bh / 2) * h * scale
            x1, y1 = (xc + bw / 2) * w * scale, (yc + bh / 2) * h * scale
            boxes_px.append((x0, y0, x1, y1))
            name = classes.get(cid, f"class_{cid}?")
            d2.rectangle([x0, y0, x1, y1], outline=DET_COLOR, width=lw)
            draw_label(d2, (max(0, x0), max(0, y0 - getattr(f, "size", 11) - 3)), f"{bi}. {name}", DET_COLOR, f)

    # Khung 3: panoptic
    p3 = p1.copy()
    d3 = ImageDraw.Draw(p3)
    mask_path = find_file(root / "masks", stem, (".png",))
    sinfo = {s["id"]: s for s in segs.get(stem, [])}
    if mask_path is None:
        notes.append("thiếu masks/")
    else:
        m = Image.open(mask_path).convert("RGB")
        if m.size != (w, h):
            notes.append(f"mask {m.size} khác ảnh {(w, h)}")
        mw, mh = m.size
        raw = m.tobytes()
        ids = [raw[k] + raw[k + 1] * 256 + raw[k + 2] * 65536 for k in range(0, len(raw), 3)]
        edge = {}
        for y in range(mh):
            row = y * mw
            for x in range(mw):
                i = ids[row + x]
                if i == 0:
                    continue
                if (x == 0 or ids[row + x - 1] != i) or (x + 1 >= mw or ids[row + x + 1] != i) \
                        or (y == 0 or ids[row - mw + x] != i) or (y + 1 >= mh or ids[row + mw + x] != i):
                    edge.setdefault(i, []).append((x, y))
        unknown = [i for i in edge if i not in sinfo]
        if unknown:
            notes.append(f"{len(unknown)} id trong mask không có trong panoptic.json")
        for n, (i, pts) in enumerate(sorted(edge.items())):
            color = PALETTE[n % len(PALETTE)]
            seg = sinfo.get(i)
            is_thing = bool(seg) and cats.get(seg["category_id"], {}).get("isthing", 1)
            if not is_thing and not show_stuff:
                continue
            for (x, y) in pts:
                d3.rectangle([x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1], fill=color)
        for n, (i, pts) in enumerate(sorted(edge.items())):
            s = sinfo.get(i)
            if not s or not cats.get(s["category_id"], {}).get("isthing", 1):
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            name = cats.get(s["category_id"], {}).get("name", f"cat_{s['category_id']}?")
            if s.get("iscrowd"):
                name += " (crowd)"
            draw_label(d3, (min(xs) * scale, min(ys) * scale), name, PALETTE[n % len(PALETTE)], f)
    for b in boxes_px:
        dashed_rect(d3, b, BOX_ON_SEG, width=lw)

    head = 34
    gap = 6
    panels = ([(T("ảnh gốc", "original"), p1)] if show_orig else []) + [
        (T("detection (box YOLO)", "detection (YOLO box)"), p2),
        (T("panoptic (viền vật) + box detection nét đứt", "panoptic (outline) + dashed detection box"), p3)]
    canvas = Image.new("RGB", (big[0] * len(panels) + gap * (len(panels) - 1), big[1] + head), (24, 24, 24))
    d = ImageDraw.Draw(canvas)
    d.text((6, 3), f"{stem}  {tag}", fill=(255, 255, 255), font=font(15))
    for k, (title, pimg) in enumerate(panels):
        x = k * (big[0] + gap)
        canvas.paste(pimg, (x, head))
        d.text((x + 6, 19), title, fill=(170, 170, 170), font=font(12))
    return canvas, notes


def summarize_evidence(typ, evidence):
    """Rút gọn bằng chứng của một ứng viên thành danh sách dòng ngắn (đã gộp trùng).

    Mỗi box chỉ một dòng, dù validator ghép nó với nhiều segment.
    """
    ev = [e for e in (evidence or []) if isinstance(e, dict)]
    lines, seen = [], set()

    def add(line):
        if line not in seen:
            seen.add(line)
            lines.append(line)

    # bbox_drift: mỗi box một dòng, lấy lần ghép có IoU cao nhất với segment
    best = {}
    for e in ev:
        if "bbox_iou" in e:
            k = (e.get("class_name"), e.get("box_index"))
            if k not in best or (e.get("bbox_iou") or 0) > (best[k].get("bbox_iou") or 0):
                best[k] = e
    for k in sorted(best, key=lambda k: (best[k].get("bbox_iou") or 0)):  # IoU thấp (đáng ngờ nhất) lên đầu
        e = best[k]
        add(f"{k[1]}. {k[0]}: IoU {e.get('bbox_iou'):.2f}, segment phủ {e.get('segment_coverage')}")

    # class_disagreement: mỗi box một dòng, gộp các lớp panoptic khác nhau
    pairs = {}
    for e in ev:
        if "detection_class" in e or "panoptic_class" in e:
            pairs.setdefault((e.get("box_index"), e.get("detection_class")), [])
            if e.get("panoptic_class") not in pairs[(e.get("box_index"), e.get("detection_class"))]:
                pairs[(e.get("box_index"), e.get("detection_class"))].append(e.get("panoptic_class"))
    for (bi, det), pan in sorted(pairs.items(), key=lambda kv: (kv[0][0] is None, kv[0][0])):
        add(f"{bi}. {det}: panoptic gán \"{' / '.join(map(str, pan))}\"")

    for e in ev:
        if "box_indices" in e:  # instance_merge
            add(f"{e.get('class_name')}: 1 segment bao box {', '.join(str(i) for i in e['box_indices'])}")
        elif "segment_pixels" in e:  # missing_box
            add(f"{e.get('class_name')}: có segment ({e['segment_pixels']} px) nhưng không có box")
        elif not any(k in e for k in ("bbox_iou", "detection_class", "panoptic_class")):
            add(json.dumps(e, ensure_ascii=False))
    return tuple(lines)


def parse_candidates(path):
    """Chấp nhận nhiều dạng: ["id", ...], [{"image"|"target": id, "type": ...}], {"candidates": [...]}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for k in ("candidates", "errors", "items"):
            if k in data:
                data = data[k]
                break
    out = []
    for it in data:
        if isinstance(it, str):
            out.append((it, "", ()))
        elif isinstance(it, dict):
            img = it.get("image") or it.get("target") or it.get("name") or ""
            extra = it.get("reason") or it.get("note") or it.get("score") or ""
            extra = (str(extra),) if extra else ()
            if not extra and it.get("evidence"):
                extra = summarize_evidence(it.get("type"), it["evidence"])
            out.append((str(img), str(it.get("type", "")), extra))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("delivery", help="thư mục có images/ labels/ masks/ panoptic.json classes.txt")
    ap.add_argument("images", nargs="*", help="tên ảnh (có hoặc không đuôi)")
    ap.add_argument("--all", action="store_true", help="xem mọi ảnh trong images/")
    ap.add_argument("--candidates", help="candidates.json")
    ap.add_argument("--review", help="file review_log/review_*.csv của bạn: chỉ xem các ảnh có trong cột image "
                                      "(nếu có cột candidate_type thì chỉ lấy đúng loại ứng viên đó)")
    ap.add_argument("--type", help="chỉ xem ứng viên thuộc loại này")
    ap.add_argument("--per-type", action="store_true",
                    help="mỗi (ảnh, loại ứng viên) một thẻ riêng, không gộp theo ảnh (mặc định: gộp)")
    ap.add_argument("--scale", type=int, default=2, help="hệ số phóng to (mặc định 2)")
    ap.add_argument("--stuff", action="store_true", help="vẽ cả viền nền (stuff: tường, sân, trời...)")
    ap.add_argument("--orig", action="store_true", help="thêm khung ảnh gốc")
    ap.add_argument("--open", action="store_true", help="xong thì tự mở index.html bằng trình duyệt")
    ap.add_argument("--out", default="view_out", help="thư mục ghi kết quả (mặc định view_out)")
    a = ap.parse_args()

    root = Path(a.delivery)
    if not (root / "images").is_dir():
        sys.exit(f"Không thấy {root}/images")
    classes = load_classes(root)
    cats, segs = load_panoptic(root)

    todo = []  # (stem, type, extra)
    review_order, review_pairs, review_imgs = [], set(), set()
    if a.review:
        with open(a.review, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                img = Path((row.get("image") or "").strip()).stem
                if not img:
                    continue
                ct = (row.get("candidate_type") or row.get("type") or "").strip()
                if img not in review_order:
                    review_order.append(img)
                (review_pairs.add((img, ct)) if ct else review_imgs.add(img))
        if not review_order:
            sys.exit(f"Không đọc được ảnh nào từ {a.review} (cần cột image)")
    if a.candidates:
        todo += [(Path(i).stem, t, e) for i, t, e in parse_candidates(a.candidates)
                 if (not a.type or t == a.type)
                 and (not a.review or (Path(i).stem, t) in review_pairs or Path(i).stem in review_imgs)]
    elif a.review:
        todo += [(img, "", ()) for img in review_order]
    if a.review:  # xếp theo thứ tự trong file review của bạn
        todo.sort(key=lambda x: review_order.index(x[0]) if x[0] in review_order else len(review_order))
    todo += [(Path(i).stem, "", ()) for i in a.images]
    if a.all:
        todo += [(p.stem, "", ()) for p in sorted((root / "images").iterdir())
                 if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    if not todo:
        sys.exit("Chưa chọn ảnh nào: truyền tên ảnh, --all hoặc --candidates.")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    # Gộp theo ảnh (mặc định): mỗi ảnh vẽ MỘT lần, kèm mọi loại ứng viên + bằng chứng của ảnh đó.
    # --per-type: về kiểu cũ, mỗi (ảnh, loại) một thẻ riêng.
    groups = {}  # khóa -> [stem, [(typ, extra), ...]]
    for stem, typ, extra in todo:
        key = (stem, typ) if a.per_type else stem
        g = groups.setdefault(key, [stem, []])
        if (typ, extra) not in g[1]:
            g[1].append((typ, extra))

    cards = []  # (stem, [(typ, extra)], notes, name)
    for stem, items in groups.values():
        types = [t for t, _ in items if t]
        tag = "[" + " + ".join(types) + "]" if types else ""
        canvas, notes = render(root, stem, max(1, a.scale), classes, cats, segs, tag, a.stuff, a.orig)
        name = f"{stem}{'_' + types[0] if a.per_type and types else ''}.png"
        canvas.save(out / name)
        cards.append((stem, items, notes, name))
        print(f"{name}" + (f"  ({'; '.join(notes)})" if notes else ""))
        for typ, extra in items:
            if typ or extra:
                head = f"    {typ} ({len(extra)}):" if typ else "    "
                print(head + "".join(f"\n        - {x}" for x in extra[:4]) + (f"\n        ... +{len(extra) - 4} dòng nữa" if len(extra) > 4 else ""))

    def evidence_html(items, show=5):
        parts = []
        for typ, extra in items:
            if not (typ or extra):
                continue
            lis = "".join(f"<li>{html.escape(x)}</li>" for x in extra[:show])
            more = ""
            if len(extra) > show:
                more = (f"<details><summary>+{len(extra) - show} dòng nữa</summary><ul>"
                        + "".join(f"<li>{html.escape(x)}</li>" for x in extra[show:]) + "</ul></details>")
            n = f' <span class="n">{len(extra)} mục</span>' if extra else ""
            parts.append(f'<div class="t"><span class="chip">{html.escape(typ or "ghi chú")}</span>{n}</div>'
                         f'<ul class="ev">{lis}</ul>{more}')
        return '<div class="e">' + "".join(parts) + "</div>" if parts else ""

    rows = []
    for stem, items, notes, name in cards:
        meta = " + ".join(t for t, _ in items if t)
        ev = evidence_html(items)
        warn = f'<div class="w">{html.escape("; ".join(notes))}</div>' if notes else ""
        rows.append(f'<section><h3>{html.escape(stem)} <small>{html.escape(meta)}</small></h3>{ev}{warn}'
                    f'<img src="{html.escape(name)}"></section>')
    (out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Xem ảnh</title>'
        '<style>body{background:#181818;color:#eee;font:15px sans-serif;margin:16px}'
        'img{max-width:100%}.e{margin:6px 0 10px}.t{margin-top:6px}.chip{background:#3a3320;color:#ffd37a;border-radius:4px;padding:1px 8px;font-weight:600}.n{color:#999;font-size:13px}ul.ev{margin:4px 0 4px 18px;padding:0;color:#e6e6e6;font-size:14px;line-height:1.5}summary{color:#aaa;cursor:pointer;margin-left:18px;font-size:13px}h3 small{color:#aaa;font-weight:400}.w{color:#ff9b9b}section{margin-bottom:28px}</style>'
        f'<h2>{len(cards)} ảnh</h2>' + "".join(rows), encoding="utf-8")
    page = (out / "index.html").resolve()
    print(f"\nXong {len(cards)} ảnh. Mở {page}")
    if a.open:
        webbrowser.open(page.as_uri())


if __name__ == "__main__":
    main()
