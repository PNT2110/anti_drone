---
title: SkyWatch Anti-Drone
emoji: 🛰️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# SkyWatch — phát hiện và tracking drone

Bảng điều khiển web phát hiện drone bằng YOLO và gán ID theo dõi cho từng drone.
Tải video lên để phân tích, hoặc dùng camera của máy bạn.

Space này chạy trên CPU nên xử lý chậm hơn thời gian thực; mỗi lần chỉ xử lý một video.
Mã nguồn: thư mục `web/` của repository `anti_drone`.
