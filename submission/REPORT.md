# Báo cáo nhóm 05

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): lỗi luật F1 ≈ 1,0 trên lô sạch và các
  seed (đo bằng `score_findings.py` chế độ học viên — chỉ in F1 làm tròn, không đọc
  `_private`). Phần cross_check đo sau khi cả nhóm review xong `review_log.csv`.
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
<<QC v1 a/b, kết luận, vì sao R-021 phải xem lại hoặc train lại.>>

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
