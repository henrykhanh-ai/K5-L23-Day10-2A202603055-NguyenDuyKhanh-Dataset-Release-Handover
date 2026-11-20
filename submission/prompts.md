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

Phần này mình (D — Thúy An) ghi lại việc dùng AI cho công cụ xem ảnh `tools/view.py` (Pha 1–2),
lineage + dựng lô v2 bằng `tools/build_v2.py` (Pha 3–4) và truy vết `trace.json` (Pha 5).

**Công cụ:** Claude Code (app desktop).

**Ảnh COCO đưa vào AI:** Claude Code có mở trực tiếp ảnh trong lô (ví dụ 2 ảnh `wrong_hash`
ở mục 5, và ảnh xuất ra từ `view.py` khi thử công cụ). Ảnh COCO là dữ liệu công khai nên
được phép; với dữ liệu thật của dự án thì không làm vậy (xem `security.md`).

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
- Đã gửi gói test cho cả nhóm chạy thử trên máy mỗi người (có máy Windows): tất cả đều chạy
  được, ra ảnh và `index.html` bình thường.

## 4. Cập nhật view.py ở Pha 2 (in bằng chứng ứng viên)

Khi `candidates.json` có 234 ứng viên (137 ảnh), mình nhờ AI sửa `tools/view.py` cho hợp
với việc chia hàng đợi review:

- **In bằng chứng gọn dưới mỗi ảnh**, mỗi box một dòng, ví dụ `3. bed: panoptic gán
  "teddy bear"` (class_disagreement), `5. car: IoU 0.25, segment phủ 0.61`
  (bbox_drift), `person: 1 segment bao box 8, 10` (instance_merge), `kite: có segment
  (161 px) nhưng không có box` (missing_box). Quá 5 dòng thì gập lại.
- **Gộp theo ảnh:** một ảnh có nhiều loại ứng viên chỉ hiện một thẻ (trước đây lặp lại).
- **Đánh số box** dạng `N. class` chỉ ở khung detection (khung panoptic bỏ nhãn cho đỡ
  rối), để dòng bằng chứng nói "box 3" là nhìn ra ngay box nào.
- **`--review <file.csv>`:** chỉ hiện các ảnh trong file phân công của mỗi người, đúng thứ
  tự file, thẻ đánh số `k/tổng` để vừa xem vừa điền.

Thông tin bằng chứng **lấy nguyên từ `candidates.json`** (validator của C sinh ra);
`view.py` chỉ diễn đạt lại, không đọc `_private`.

**AI sai / mình phải sửa:**
- Bản đầu AI ghi `box#7` mà không kèm tên lớp, trên ảnh thì nhãn chỉ có tên lớp nên không
  biết `#7` là box nào. Mình yêu cầu ghi cùng một dạng `7. car` ở cả bằng chứng lẫn ảnh.
- Đánh số ở cả hai khung làm ảnh nhỏ bị chồng chữ, không đọc được; mình yêu cầu bỏ số ở
  khung panoptic.

**Kiểm tra:** chạy trên `runs/r5007` với cả 4 loại ứng viên (234/234 ứng viên có dòng bằng
chứng); chạy lại với `candidates.json` dạng cũ (danh sách tên ảnh, dạng có `reason`) để
chắc không hỏng chức năng cũ; chạy `--review` với file phân công thật và so số thẻ với số
ảnh trong file. Dòng bằng chứng chỉ là gợi ý nhìn vào đâu, kết luận `confirmed`/`rejected`
do người xem ảnh quyết.

## 5. Lineage và dựng lô v2 (`tools/build_v2.py`)

Sau khi A gộp `errors.json` (17 lỗi) và `review_log.csv`, mình chạy lineage theo GUIDE:
QC v1 = 17/250 = 6,8% > 2% nên ghi **HOLD**; `lineage.py impact` ra
`R-021: affected=True action=review_or_retrain`.

Mình nhờ AI viết `tools/build_v2.py` để dựng `handover/<release_id>_v2/` từ `delivery/`
(không sửa `delivery/`) theo bảng phân loại ở Pha 4:
- lỗi nhãn detection / thiếu file → `rework_queue.csv` (người gán, người kiểm lấy theo
  `jobs.csv`) và bỏ khỏi v2: 9 ảnh;
- lỗi chỉ ở panoptic → ảnh ở lại v2, báo team panoptic: 4 ảnh;
- `wrong_hash`, `scene_leak`, `guideline_mismatch` → sửa ngay trong v2 (manifest tính lại
  sha256; cả `scene_315` về train; guideline theo job).
Kết quả v2: 241 ảnh, 1669 nhãn.

**AI sai / mình phải sửa:**
- **Làm lấn phần người khác:** bản đầu AI sinh luôn `label_summary.csv`, `truyvet.csv`
  (phần của C) và `README.txt` (phần của B), rồi đóng gói và chạy `export_submission`
  (phần của A). Mình đối chiếu bảng phân công nhóm, yêu cầu bỏ các phần đó: script chỉ dựng
  `images/`, `labels/`, `rework_queue.csv`, `manifest.csv` và **in số liệu** để bàn giao cho
  B, C. Gói `.zip`/`.sha256` đã đóng trước đó cũng xoá, đợi đủ file của B, C mới đóng lại.
- **`wrong_hash` không được tự sửa mù:** GUIDE yêu cầu mở ảnh kiểm trước khi ghi hash mới.
  Hai ảnh `000000000785` (người trượt tuyết) và `000000023272` (mèo nằm trên nắp ô tô) được
  mở ra xem: ảnh mở được, đúng nội dung và khớp nhãn (person + skis; cat + car), nên chỉ
  manifest v1 sai → giữ trong v2 với sha256 mới, không đưa vào rework.

**Kiểm tra:**
- Release ID: nhóm thống nhất dùng ID trên máy mình, `lab250_12a734d6195d` (đúng với
  `release.json` của lô), nên đóng gói và `check_handover` chạy trên máy mình.
- Đối chiếu `rework_queue.csv` với `jobs.csv` (đúng người gán/kiểm từng job).
- Khi nhận file của B, C: so cả gói C gửi với lô của mình (`diff -r`), ảnh, nhãn, manifest,
  rework, README giống hệt, chỉ thêm đúng `label_summary.csv` và `truyvet.csv`; xem `truyvet`
  của 2 ảnh được sửa (`000000025394` → train, `000000015597` → v1.3 theo J07).
- Sau khi đủ 7 phần: `pack_release.py`, `lineage.py record --event release` (parent là v1),
  rồi `scripts/check_handover.py --run runs/r5007`: **17 PASS, 0 FAIL**. Cuối cùng chạy
  `export_submission.py` sang `submission/r5007/` (không chép `.zip`).

## 6. Truy vết `trace.json`

AI chỉ đưa câu lệnh để mình tự chạy: lấy `scene_id` từ `metadata.json`, phiên bản guideline
**theo job** trong `jobs.csv` (không theo metadata từng ảnh), lọc ảnh có box thuộc lớp bị đổi
quy tắc trong `labels/`, và lấy người gán/kiểm của các job liên quan. Mình không dùng script
riêng (bản `trace_tiers.py` AI viết thử đã xoá), tự đọc kết quả từng ảnh rồi điền
`tier_a` (3 ảnh), `tier_b` (6 ảnh), `notify` (3 người). `check_handover` mục H16 PASS.

Rút ra: AI viết công cụ và script nhanh, nhưng mình phải đối chiếu với GUIDE và bảng phân công
(AI dễ làm thừa phần người khác), mở ảnh thật trước khi kết luận, và chạy `check_handover`
sau mỗi lần thay đổi lô thay vì tin vào số AI báo.

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
## 5. Review ảnh, security.md và README.txt v2

- **Review 59 ứng viên (Pha 2):** em tự mở từng ảnh trong gói review và tự kết luận
  58 rejected, 1 confirmed (000000024027 missing_box: con diều lớn có mask nhưng không có box,
  job J10 theo v1.3). AI chỉ soát định dạng file CSV (verdict, type, độ dài note, không trùng),
  không quyết định thay em.
- **security.md:** em tự chọn 2 ảnh có mặt người rõ (000000016598, 000000019924) và tự mô tả;. AI kiểm file theo luật H17.
- **README.txt v2:** AI soạn từ số liệu bạn An gửi (so_lieu_v2.txt); em kiểm lại các số:
  17 = 10 lỗi luật + 7 lỗi gán nhãn đã confirmed, 241 = 250 - 9 ảnh rework.
- **Chỗ phải sửa:** lần đầu em ghi verdict là false_positive/uncertain (sai định dạng) và để nguyên
  note của máy, sau đó sửa lại; khi dán prompts.md lần trước em lỡ xoá phần A của Khánh, phát hiện
  khi git pull báo conflict và đã ghép lại đủ 4 phần; release_id trên máy em (lab250_afa095a47015)
  khác máy An (lab250_12a734d6195d) nên phải sửa id trong security.md cho khớp lô An bàn giao.
