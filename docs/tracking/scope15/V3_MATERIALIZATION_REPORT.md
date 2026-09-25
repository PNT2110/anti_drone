# V3 Materialization Report

Output riêng: `/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v3-candidate/`.

Materialization dùng `shutil.copy2` vào thư mục tạm `*.building-PID`, kiểm tra hash từng ảnh sau khi copy, rồi atomic rename. Không dùng symlink/hardlink, không resize ảnh, không rewrite label và không sửa source V1/V2. Nếu output tồn tại hoặc thiếu dung lượng, script dừng thay vì ghi đè.

Trước copy, source image + label ước lượng `2,388,255,708` bytes; free space `14,333,112,320` bytes; ngưỡng an toàn `2,895,516,734` bytes. Materialization hoàn tất trong khoảng `16.21` giây. Dataset sau copy chiếm khoảng `2.4G`.

`materialization_report.json` ghi PASS, 30,227 samples và counts `train=12,142`, `val=8,237`, `test=9,848`. `data.yaml` chưa được tạo trong phase copy; chỉ được tạo sau direct-disk audit PASS.
