# Scope 17 — Coordinate Contract

Contract đã được kiểm chứng bằng archive JSON, image header thực tế và 30.227 rows:

- Source annotation: `gt_rect = [x, y, width, height]`, pixel coordinates.
- Frame index: 0-based; dùng trực tiếp `exist[frame]` và `gt_rect[frame]`.
- Image space: direct source/prepared image; không resize, crop hoặc letterbox trong repair.
- Visible dimensions: 1920×1080. Infrared dimensions: 640×512.
- YOLO conversion: `xc=(x+w/2)/W`, `yc=(y+h/2)/H`, `wn=w/W`, `hn=h/H`.
- Output precision: 8 decimal places; audit tolerance `5e-6`.
- Box policy: rectangle phải dương và trong biên; không clip âm thầm. Toàn bộ mapped rectangles pass, nên không có `BLOCKED_SAMPLES` vì tọa độ.
- Class: luôn `0`, không thêm class.

Không có sample negative thật trong 30.227 assigned rows, và không có multi-box frame trong source mapping này. Quy tắc vẫn giữ được nhiều box nếu source JSON cung cấp nested rectangles.
