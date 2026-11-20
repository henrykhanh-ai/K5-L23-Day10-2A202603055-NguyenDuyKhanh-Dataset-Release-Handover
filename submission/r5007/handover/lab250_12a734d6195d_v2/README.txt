Release: lab250_12a734d6195d_v2
Parent: lab250_12a734d6195d
Số ảnh: 241
Số nhãn: 1669
Guideline: v1.2 (J01-J04), v1.3 (J05-J10)
QC v1: 17/250 = 6,8%
Kết luận v1: Hold — 17/250 = 6,8% ảnh/cảnh có lỗi (10 lỗi luật + 7 lỗi gán nhãn đã xác nhận bằng mắt), vượt ngưỡng 2% nên không Release; R-021 đã train trên v1 nên phải xem lại hoặc train lại.
Kết luận v2: Release — bản detection 241 ảnh: đã tách 9 ảnh lỗi nhãn detection sang rework_queue.csv, đã sửa split, hash và guideline ngay trong v2; nhãn của các ảnh còn lại giữ nguyên như v1.
Ghi chú:
- Split: scene_315 bị rò train/val, đã đưa cả cảnh về train (ảnh 000000025394 chuyển từ val sang train), v2 không còn cảnh nằm ở cả hai tập.
- Hash: 000000000785 và 000000023272 bị sai sha256 trong manifest v1; đã mở ảnh kiểm, ảnh còn nguyên nên chỉ ghi lại sha256 đúng trong manifest.csv của v2.
- Guideline: 000000015597 ghi v1.2 ở ảnh nhưng job J07 theo v1.3, v2 ghi theo job là v1.3.
- Rework (9 ảnh rời v2, giao đúng người theo jobs.csv): A01/Q03 000000001993; A02/Q03 000000020333, 000000023126; A04/Q01 000000009590, 000000009769; A05/Q01 000000002587; A05/Q02 000000024027; A05/Q03 000000015497, 000000016249.
- Báo team panoptic (lỗi chỉ ở panoptic, nhãn detection vẫn đúng nên ảnh ở lại v2): 000000006723 và 000000021465 (category_swap), 000000012639 (thing_overlap), 000000021503 (invalid_category_id).
