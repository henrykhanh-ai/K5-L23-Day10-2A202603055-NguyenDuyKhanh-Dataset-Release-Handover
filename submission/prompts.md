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