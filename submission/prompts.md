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
