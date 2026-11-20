# Bảo mật khi làm việc
> Trả lời gắn với lô bạn vừa bàn giao, không chép slide. Mỗi mục vài câu.

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp
Em không chép lô ra USB. Lô 5007 (lab250_12a734d6195d) là dữ liệu của dự án nên phải ở lại trong hệ thống; USB dễ thất lạc và không ai kiểm soát được ai đã mở hay chép lại. Gửi lô qua email cá nhân cũng sai vì dữ liệu cũng đã rời hệ thống, chỉ là đi đường khác. Nhờ người khác làm hộ cũng sai vì trong jobs.csv ghi rõ mỗi job do ai gán, ai kiểm (ví dụ J01 là A01 gán, Q03 kiểm), nếu người khác làm thay thì truy vết sẽ chỉ sai người khi có lỗi. Cách đúng là lưu tiến độ trên hệ thống, báo lead là chưa xong và xin thêm thời gian, hôm sau làm tiếp trên máy.

## 2. Năm việc: được hay không
- Mở job được giao trên máy công ty: **Được**, vì đúng người được giao, đúng máy và đúng kênh của công ty.
- Chụp màn hình gửi người quen: **Không**, ảnh chụp mang dữ liệu ra ngoài và trong lô có ảnh lộ rõ mặt người.
- Chép lô ra USB: **Không**, dữ liệu rời khỏi hệ thống, dễ mất và không truy được ai đã giữ bản sao.
- Dán nhãn thật lên chatbot: **Không**, dữ liệu bị gửi cho dịch vụ bên ngoài. Trong lab này ảnh COCO là dữ liệu công khai nên mới được dán vào AI và phải ghi lại trong prompts.md; với dữ liệu thật của dự án thì không được.
- Đưa tài khoản CVAT cho đồng nghiệp: **Không**, mọi nhãn người đó làm sẽ mang tên em, làm sai lịch sử ai gán ai kiểm.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ
Khi thấy ảnh có mặt người rõ, em dừng lại, chuyển lô sang trạng thái **Hold** và báo người phụ trách (lead hoặc người quản lý dữ liệu) để xử lý theo quy trình chung. Em không tự làm mờ vì sửa ảnh sẽ làm sha256 khác với manifest, và v1 đã được dùng để train R-021 nên phải giữ nguyên để biết model đã học từ dữ liệu gì. Em cũng không tự xoá ảnh vì sẽ mất bằng chứng và làm lệch số liệu bàn giao. Ví dụ trong lô 5007:
- 000000016598: người phụ nữ tóc nhuộm xanh, mặc sơ mi đeo cà vạt xanh, cầm điện thoại chụp ảnh trước gương, đeo nhẫn, thấy rõ cả khuôn mặt.
- 000000019924: ảnh trắng đen, người phụ nữ đang cười, tay cầm điếu thuốc, đeo cà vạt đen, thấy rõ cả khuôn mặt.
