# Dùng AI

Phần này mình (A — Khánh) ghi lại việc dùng AI cho khung `validator/validate.py`
và 5 lỗi phần A: `missing_image`, `wrong_hash`, `invalid_class`,
`bbox_out_of_bounds`, `duplicate_box`.

## 1. Nhờ AI làm gì

Mình nhờ AI (Claude Code trong VS Code) dựng **khung `validate.py`**: phần CLI
(`argparse` đọc thư mục delivery, `--out`, `--candidates`), lớp `Delivery` đọc
`manifest.json` / `classes.txt` / nhãn YOLO, và viết **5 hàm `check_*` của phần A**.
Mình yêu cầu AI mô tả yêu cầu từng lỗi trước khi viết, rồi giải thích từng khối để
mình tự giải thích lại được khi vấn đáp. Các hàm của B (metadata/panoptic) và C
(đối chiếu) để trống `TODO`, không nhờ AI làm thay.

## 2. Ai quyết định ngưỡng

Có 3 ngưỡng trong code: `OOB_EPS` (tràn mép), `DUP_SIZE_PX` (cùng kích thước),
`DUP_SHIFT_PX` (tâm lệch). AI **đo trên lô** (lô sạch `runs/clean` và các seed luyện
tập) rồi **đề xuất** con số: cặp lỗi gài lệch kích thước ~0 px, còn cặp box COCO tự
nhiên gần nhau vẫn lệch kích thước ≥ 0,7 px → chọn `DUP_SIZE_PX = 0.1 px` để tách hai
loại; `OOB_EPS = 1e-4` chỉ để bỏ sai số làm tròn 6 chữ số của YOLO (tràn thật 1 px vẫn
báo). **Mình đọc lại lý do, thấy hợp lý và đồng ý** giữ các giá trị này. Quyết định
cuối là của mình, không phải AI tự chốt.

## 3. Kiểm tra thế nào

- **Lô sạch `runs/clean` phải báo 0 lỗi** → đạt (validator im lặng trên lô sạch,
  tránh báo thừa làm F1 giảm).
- Chạy trên nhiều seed và đều **bắt được lỗi** (số thật đo ngày chạy):

  | Lô | Tổng lỗi | Chi tiết |
  |---|---|---|
  | `runs/clean` | 0 | — |
  | `runs/r11` | 7 | bbox_out_of_bounds×2, duplicate_box×2, missing_image×1, wrong_hash×2 |
  | `runs/r22` | 4 | bbox_out_of_bounds×1, duplicate_box×1, invalid_class×1, wrong_hash×1 |
  | `runs/r33` | 5 | bbox_out_of_bounds×1, duplicate_box×1, missing_image×1, wrong_hash×2 |
  | `runs/r5007` | 6 | bbox_out_of_bounds×1, duplicate_box×1, invalid_class×2, wrong_hash×2 |

  Lệnh: `python validator/validate.py runs/<seed>/delivery --out runs/<seed>/rules.json`.

## 4. Một lần AI sai

- **Nén zip lần đầu bị lỗi:** lần đầu nhờ AI đóng gói, bước nén `.zip` chạy lỗi
  (không ra file đúng như mong đợi). Mình phát hiện khi kiểm lại đầu ra, báo lại và
  làm lại mới xong.

Rút ra: AI dựng khung và đo ngưỡng nhanh, nhưng **kết luận cuối (ngưỡng, đóng gói,
độ tin của công cụ) là mình kiểm lại và quyết**.

---

# Dùng AI — phần D (Thúy An)

Phần này mình (D — Thúy An) ghi lại việc dùng AI cho công cụ xem ảnh `tools/view.py`.

## 1. Nhờ AI làm gì

Mình nhờ AI (Claude Code) viết `tools/view.py`: vẽ box YOLO (kèm tên lớp) và viền
segment panoptic lên ảnh, xuất PNG + `index.html` để review bằng mắt ở Pha 2. Công cụ
dùng Pillow (chỉ ở công cụ xem; `validator/` vẫn chỉ thư viện chuẩn) và **chỉ đọc thư
mục delivery**, không đọc `_private/`. Mình yêu cầu chạy được trên cả Mac và Windows.

## 2. AI sai ở đâu

- **Mất viền cạnh trái/trên của vật thể:** lần đầu AI chỉ so điểm ảnh với láng giềng
  bên phải và bên dưới, nên viền panoptic bên trái/trên bị mất (mình thấy ở ảnh nhà vệ
  sinh). Đã sửa thành so cả 4 hướng.
- **Ảnh quá rộng và rối:** bản đầu xuất 5772 px, vẽ cả viền vùng nền (stuff) nên khó
  nhìn. Đã giảm còn 2 khung, chỉ viền vật thể (thing), phóng 2 lần.
- **Lỗi font/phiên bản (Windows):** AI viết giả định font và hàm Pillow chỉ có trên
  Mac; khi thử giả lập thiếu font thì chạy lỗi. Đã thêm danh sách font dự phòng, chữ
  ASCII khi không có font, và bỏ hàm đã cũ (`getdata`).

## 3. Mình kiểm tra thế nào

- Chạy trên 10 ảnh mẫu và đối chiếu bằng mắt: viền ôm đủ 4 phía.
- Không tin mắt thuần: với ảnh nghi lỗi mình kiểm bằng số (IoU giữa box và segment)
  rồi mới kết luận; một số chỗ lệch là sai khác tự nhiên của COCO (đa giác thô, bị
  che), không phải lỗi gài.
- Đã gửi gói test cho cả nhóm chạy trên Windows (kết quả: chờ báo cáo từng bạn).

---

# Dùng AI — phần C (Việt Quân): ngưỡng `find_candidates`

## 1. Nhờ AI làm gì

Nhờ AI (Claude Code) dò lại bộ ngưỡng trong `find_candidates` (đối chiếu detection ↔
panoptic) sau khi bản đầu đặt `CAND_MIN_CLASS_OVERLAP=0.65` làm hàng đợi lô sạch còn 7
ứng viên — thấp bất thường, nguy cơ bỏ sót lỗi.

## 2. AI sai ở đâu — và nhóm sửa

Lần đầu AI chọn ngưỡng bằng cách **đo recall trên `_private/truth.json`** của các seed
luyện tập (ra con số "recall 24/29") rồi viết vào comment code và commit `0c2671e`.
**Đây là dùng đáp án gián tiếp — RULES cấm.** Nhóm phát hiện khi soát lại commit, đã
sửa ở commit `3431bfe`: bỏ ràng buộc suy từ đáp án (`CAND_DRIFT_MAX_CENTER_SCALE`),
viết lại comment, và chọn/giải thích ngưỡng **chỉ bằng nhiễu đo trên lô sạch + nguyên
tắc hình học**.

## 3. Mình kiểm tra thế nào

- `validator/validate.py` **không đọc `_private`** (kiểm bằng đọc code): đạt.
- Đo **số ứng viên trên lô sạch (66)** — hợp lệ vì lô sạch không có đáp án.
- Verdict cuối do **người xem ảnh** quyết, không để AI kết luận thay.

Rút ra: dùng `_private` để **tự kiểm tra** thì được (như `tests/`), nhưng **tuyển ngưỡng
theo đáp án** là gian lận — phải chọn bằng lô sạch + kết quả review.

---

# Phần B — Lê Ngọc Bích Loan (metadata + panoptic)

Phần này ghi việc dùng AI cho 4 lỗi luật phần B trong `validator/validate.py`:
`scene_leak`, `guideline_mismatch`, `invalid_category_id`, `thing_overlap`.

## 1. Prompt đã dùng

Công cụ: Claude (claude.ai). Prompt chính em tự viết (lưu nguyên văn trong nhật ký hội thoại):

> "Bạn là mentor Python và Data QA... Tôi mới học Python nên hãy hướng dẫn từng bước
> để tôi tự viết, tự chạy và giải thích được khi vấn đáp... Mỗi lượt chỉ làm một bước...
> Đợi tôi gửi output trước khi chuyển bước."

Em yêu cầu AI đọc GUIDE/RULES/DELIVERY và khung `validate.py` của A trước, không tự giả định
tên hàm hay seed. Em đọc mẫu dữ liệu thật (`metadata.json`, `jobs.csv`, `panoptic.json`)
trước khi viết từng luật, rồi tự dán code vào 4 hàm `check_*` có sẵn của khung và tự chạy.

## 2. Kết quả thật (validator chung, đo 19/11/2026)

| Luật B | r5007 | r11 | r23 | clean |
|---|---|---|---|---|
| scene_leak | 1 | 1 | 1 | 0 |
| guideline_mismatch | 1 | 2 | 1 | 0 |
| invalid_category_id | 1 | 2 | 0 | 0 |
| thing_overlap | 1 | 1 | 1 | 0 |

`score_findings.py`: F1 lỗi luật ≈ 1.0 trên 5007, 11, 23 (đây là F1 của validator chung A + B).
r23 không có `invalid_category_id` vì số lỗi mỗi loại đổi theo seed, có loại vắng.

## 3. Cách em kiểm lại (không chỉ tin con số)

Với từng luật, em chạy lệnh in dữ liệu gốc của chính ảnh bị báo:
- scene_leak: `scene_315` có 4 ảnh train + 1 ảnh val (`000000025394`).
- guideline_mismatch: `000000015597` ghi v1.2, nhưng job J07 trong `jobs.csv` là v1.3.
- invalid_category_id: `000000021503` có segment category_id 83, không có trong `categories`.
- thing_overlap: `000000012639`, segment 11516589 khai area 573 nhưng đếm trong mask chỉ 481 pixel.
Lô sạch 50 ảnh: cả 4 luật đều báo 0.

## 4. Chỗ AI sai / chỗ em phải sửa

- **AI tự giả định cấu trúc code:** lúc chưa xem khung của A, AI viết một file riêng `rules_b.py`.
  Khi có khung `validate.py`, em bỏ file đó và viết thẳng vào 4 hàm `check_*` có sẵn.
- **AI đưa lệnh `py` nhưng máy em không có:** báo lỗi "py is not recognized"; em kiểm bằng
  `python --version` (3.12.10) và dùng `python` cho mọi lệnh.
- **Gợi ý tự động của Codex trong VS Code** viết sẵn `check_scene_leak` bằng phép so
  `{"train","val"} <= splits` nhưng không chuẩn hoá chữ (`strip().lower()`); em thay bằng bản
  đếm `len(set) > 1` có chuẩn hoá.
- **Lỗi khi dán code (em tự gây ra):** dán đè lên `return [` cũ gây SyntaxError; thừa 3 dấu cách
  trước `def` gây IndentationError (tìm ra bằng lệnh in `repr` của dòng); lúc thêm `import csv`
  em lỡ xoá `from __future__ import annotations` của A, phát hiện nhờ đọc `git diff` trước khi
  commit và khôi phục lại.

Rút ra: AI giúp viết code nhanh, nhưng em phải đọc dữ liệu thật, kiểm từng ảnh bị báo và đọc
`git diff` trước khi commit thì mới chắc không sai và không làm hỏng code của bạn khác.
