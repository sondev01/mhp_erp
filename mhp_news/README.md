# MHP Tin tức — Odoo 18

Module phụ thuộc Website. Cài **MHP Tin tức** trong Apps sau khi cập nhật danh sách ứng dụng và khởi động lại Odoo.

## Sử dụng

- Quản trị viên vào **Tin tức → Nguồn tin**, mở nguồn và bấm **Lấy tin ngay**.
- Với nguồn mới chỉ nhập tên và URL; để trống `XPath tùy chỉnh` để tự nhận diện link, tiêu đề và ảnh theo HTML. Bộ nhận diện dùng cấu trúc tiêu đề và hình dạng URL để lọc menu, không đảm bảo đúng với mọi website.
- Xem `Lỗi gần nhất` khi nguồn không lấy được bài; cấu hình `XPath tùy chỉnh` nếu nhận diện chưa chính xác. Hai nguồn có sẵn vẫn giữ XPath đã kiểm tra. Muốn thử chế độ tự động trên nguồn cũ, xóa XPath rồi lưu.
- Trang công khai: `/tin-tuc`, 24 bài mỗi trang, ảnh và tiêu đề dẫn đến bài gốc trong tab mới.
- **Tin tức → Bài viết** cho phép ẩn bài bằng trường `Hiển thị công khai`.
- Scheduled Action **Tin tức: cập nhật nguồn** chạy mỗi 30 phút; có thể chỉnh chu kỳ trong chế độ nhà phát triển.
- Nguồn tắt hoạt động sẽ ngừng lấy bài và ẩn bài của nguồn khỏi trang công khai.

Không lọc theo ngày xuất bản. Bài cũ vẫn được lấy và hiển thị; không cần đọc từng trang bài để xác định ngày.

## Nguồn có sẵn

- Trang chủ https://laodong.vn/
- Trang chủ đề https://tuoitre.vn/bao-tuoi-tre-thu-do.html (không phải toàn bộ tin mới của Tuổi Trẻ).

Chỉ lưu tiêu đề, URL ảnh, URL gốc, không lưu nội dung bài. Ảnh tải trực tiếp từ máy chủ nguồn, có thể không hiện nếu nguồn chặn liên kết ngoài. Trang không có ảnh dùng biểu tượng thay thế. Thứ tự theo lần thu thập. Kiểm tra tối đa 40 bài/nguồn/lượt, không tải phân trang hoặc chạy JavaScript trên trang nguồn. Nguồn lỗi được ghi nhận riêng và thử lại ở lượt tiếp theo.

Chỉ cấp quyền cấu hình nguồn cho quản trị viên đáng tin cậy: URL được máy chủ Odoo truy cập trực tiếp. Chưa có màn hình cấu hình riêng cho từng website trong hệ thống nhiều website.
