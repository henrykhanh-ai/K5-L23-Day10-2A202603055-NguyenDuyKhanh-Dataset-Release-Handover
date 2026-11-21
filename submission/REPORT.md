# Báo cáo nhóm 05

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): lỗi luật F1 ≈ 1,0 trên lô sạch và các
  seed (đo bằng `score_findings.py` chế độ học viên — chỉ in F1 làm tròn, không đọc
  `_private`). Sau khi cả nhóm review xong r5007 (234 dòng, 7 `confirmed`): lỗi luật
  F1 ≈ 1,0 · lỗi gán nhãn F1 ≈ 0,4 · tổng ≈ 0,7. Lỗi gán nhãn thấp vì nhóm không confirm
  dòng `bbox_drift`/`instance_merge` nào (169/234 ứng viên) — nhiều khả năng bỏ sót; rút
  kinh nghiệm cho đề ẩn: confirm khi box dời hẳn khỏi một vật đứng riêng.
- Số ứng viên trên lô sạch (`runs/clean`, 50 ảnh, `--no-faults`): **66**; hàng đợi trên
  seed luyện tập `r5007`: **234 ứng viên**.
- Ngưỡng đã chọn và cách chọn (**không dùng `_private`**): các ngưỡng trong
  `find_candidates` được chọn theo **nhiễu đo trên lô sạch** (lô không gài lỗi, nên mọi
  ứng viên ở đó đều là lệch tự nhiên của COCO) cộng **nguyên tắc hình học**, không đối
  chiếu đáp án. Nguyên tắc: ứng viên chỉ là *hàng đợi* cho người xem ảnh — người review
  mới quyết lỗi thật — nên ngưỡng để **đủ lỏng để không bỏ sót**, miễn hàng đợi còn xem
  hết được. Cụ thể: `CAND_MIN_CLASS_OVERLAP=0.2` (box và segment phủ nhau ≥20% mới coi
  là cùng vật), `CAND_DRIFT_COVERAGE=0.5` (box phủ <50% segment cùng lớp → nghi lệch),
  `CAND_MERGE_*` (2 box gần như không chồng nhưng tâm cách xa → 1 vật bị 2 box).
  > Ghi chú trung thực: bản ngưỡng đầu (commit `0c2671e`) có đo recall bằng
  > `_private/truth.json` (con số "24/29") — cách này RULES cấm. Đã sửa ở commit
  > `3431bfe`: bỏ ràng buộc suy từ đáp án và chọn/giải thích lại chỉ bằng lô sạch.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Điểm là F1 trên từng cặp `(type, target)`: báo thừa bị trừ y như bỏ sót. Lô sạch
không có lỗi nào nhưng vẫn sinh **66 ứng viên** (lệch tự nhiên của COCO). Nếu đưa hết
66 ứng viên vào `errors.json` thì cả 66 là **false positive** → precision ≈ 0 → F1 ≈ 0,
dù recall phần luật vẫn tốt. Vì vậy ứng viên **phải qua người xem ảnh**: chỉ `confirmed`
cái thấy rõ là lỗi, còn lại `rejected`. Đây là lý do hàng đợi phải đủ nhỏ để xem hết và
tại sao không được "confirm hàng loạt".

## 3. Quyết định và lineage
- **QC v1:** `errors.json` chốt sau review có **17 lỗi trên 250 ảnh = 6,8%** (10 lỗi luật,
  7 lỗi gán nhãn đã `confirmed` bằng xem ảnh). Ngưỡng của lab là 2%, 6,8% > 2% nên
  **kết luận v1: HOLD**, không phát hành `lab250_12a734d6195d`.
- **Lineage:** ghi `decision HOLD` cho v1, rồi chạy `lineage.py impact`: training run
  **R-021 đã train trên v1 → affected=True, action=review_or_retrain**.
- **Vì sao R-021 phải xem lại hoặc train lại:** sửa dataset không tự sửa model đã học.
  R-021 đã học từ các nhãn sai của v1 (ví dụ 4 ảnh `class_swap`, 1 ảnh `missing_box`,
  box trùng, box tràn mép), nên phải đánh giá lại trên dữ liệu đã sửa, và nếu kết quả bị
  ảnh hưởng thì train lại trên v2.
- **v2:** bàn giao `lab250_12a734d6195d_v2` (parent = v1), **241 ảnh, 1669 nhãn**.
  9 ảnh lỗi nhãn detection tách sang `rework_queue.csv`, giao lại đúng người gán/người kiểm
  theo `jobs.csv`. 4 ảnh chỉ lỗi panoptic (6723, 21465 `category_swap`; 12639 `thing_overlap`;
  21503 `invalid_category_id`) ở lại v2 vì nhãn detection vẫn đúng, đã ghi chú báo team panoptic.
  Lineage ghi `release` cho v2 với parent là v1; v1 trong `delivery/` không bị sửa.

## 4. Hash chứng minh gì, không chứng minh gì?
- **Chứng minh được:** file hiện tại **giống từng byte** với file lúc manifest được ghi
  (sha256 tính trên bytes). Nếu hash khớp thì file không bị đổi, hỏng hay tráo trong lúc
  chuyển giao; `release_id` tính từ `manifest.json` + `metadata.json` nên sửa v1 là id đổi.
- **Không chứng minh được:** hash **không nói nhãn đúng hay sai**. Một file nhãn gán sai lớp
  vẫn có hash khớp hoàn toàn nếu manifest được ghi sau khi gán sai. Lỗi gán nhãn chỉ phát hiện
  được bằng đối chiếu detection ↔ panoptic và xem ảnh.
- **Ví dụ trong lô:** 2 ảnh `wrong_hash` (000000000785, 000000023272). Nhóm mở kiểm từng ảnh:
  ảnh mở được, đúng nội dung → **ảnh còn nguyên, chỉ manifest v1 ghi sai hash**, nên v2 giữ ảnh
  và ghi hash mới trong `manifest.csv`. Hash lệch chỉ cho biết "file và manifest không khớp",
  phải mở file mới biết bên nào sai.

## 5. Truy vết
- **Ticket:** team AI báo model hay bỏ sót `cup` bị che hoặc ở mép ảnh, thấy rõ ở
  scene_473 và scene_493. **Changelog:** v1.3 bắt buộc gán box cho `cup` bị che >50% hoặc
  cắt mép; v1.2 cho phép bỏ qua. Vậy ảnh rủi ro là ảnh gán theo **v1.2** có `cup`.
- **Tiêu chí:** job theo guideline cũ v1.2 (J01–J04 trong `jobs.csv`) **và** ảnh có ít nhất
  một box detection lớp `cup` (class 41) trong `labels/` của lô.
  - **tier_a** (trong các cảnh team AI nêu): 000000002592, 000000002685 (scene_473),
    000000003661 (scene_493) — 3 ảnh.
  - **tier_b** (cùng điều kiện, chưa ai báo): 000000002157, 000000002431, 000000003845,
    000000003934, 000000009400, 000000009590 — 6 ảnh.
  - **notify:** người gán và người kiểm của các job chứa ảnh tầng a/b: **A04, A05, Q01**.
- **Vì sao lấy guideline theo job, không theo từng ảnh:** guideline ghi ở từng ảnh trong
  `metadata.json` có thể chính là lỗi `guideline_mismatch` (lô này có ảnh 000000015597 ghi v1.2
  nhưng job J07 là v1.3). Job mới là đơn vị được giao việc và ban hành guideline, nên dùng
  `jobs.csv` để quyết ảnh nào bị gán theo quy tắc cũ.
- `trace.json` do D làm; A kiểm lại bằng một script nhỏ (AI viết, chỉ đọc `jobs.csv`, `metadata.json`, `labels/`) ra cùng kết quả.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- **Mã release phụ thuộc vào phiên bản zlib của máy.** Khi tạo lại lô seed 5007 trên một
  môi trường dùng zlib-ng (Python 3.13), `release_id` ra `lab250_4758e9a8ad9a`, còn trên máy
  nhóm (zlib chuẩn) là `lab250_12a734d6195d`. Ảnh và nhãn có cùng sha256; chỉ mask PNG khác
  hash vì `inject_release.py` nén lại mask bằng zlib, mà mỗi bản zlib nén ra bytes khác nhau.
  Hệ quả: chạy `export_submission --import` + `check_handover` trên máy có zlib khác sẽ báo
  H4 FAIL (không tìm thấy thư mục `<release_id>_v2`) dù bài đúng. Trên máy nhóm chạy lại
  ra 17 PASS. Gợi ý: tính release_id/hash mask trên dữ liệu pixel thay vì bytes đã nén,
  hoặc ghi rõ phiên bản Python/zlib cần dùng. Đây cũng là ví dụ cho mục 4: hash chứng
  minh "bytes giống nhau", không chứng minh "nội dung giống nhau".
- **Lineage chỉ nằm trên máy chạy `run_lab.py`.** `runs/` không được commit nên mỗi máy có
  một lineage riêng; nhóm phải chốt một máy (của D) làm HOLD, release v2 và
  `export_submission`, nếu không bài nộp dễ mang lineage thiếu HOLD.
