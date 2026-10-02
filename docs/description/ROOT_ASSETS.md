# Root assets và quy tắc sắp xếp

Root repository được giữ cho các file điều phối chuẩn của Python project và các asset mà workflow hiện tại tham chiếu trực tiếp. Không đưa tất cả file vào `docs/` chỉ để làm trống root, vì như vậy sẽ làm sai relative path và deployment contract.

| Nhóm | Vị trí | Lý do |
| --- | --- | --- |
| Project metadata | `pyproject.toml`, `environment.yml` | Tooling Python/Conda tự tìm ở root |
| Dependencies | `requirements*.txt` | Lệnh cài đặt và Pi bundle hiện dùng các path này |
| Pi launcher | `run_tracking.sh` | Launcher tương thích layout deployment hiện tại |
| Baseline model | `yolo26n.pt` | Web app và test hiện tìm model này ở root |
| Dataset archives | `*.tar.gz` | Archive nguồn được giữ để tái lập dữ liệu; không đưa vào `docs/` và không sửa `data/` |
| Human documentation | `docs/` | Hướng dẫn, kế hoạch, báo cáo và chính sách repository |
| Web application | `web/` | Source, template, static assets và runtime của web app |

`remote_home.html` là artifact cũ không có reference trong source, test hoặc tài liệu canonical; nó đã được đưa ra archive cleanup ngoài workspace. Cache `.pytest_cache/` cũng là generated output và được đưa ra ngoài workspace sau khi kiểm tra.

## Quy tắc bảo toàn data

Không đổi tên, di chuyển, xóa hoặc chỉnh sửa bất kỳ nội dung nào dưới `data/`. Dataset archive ở root chỉ là bản nguồn để tái lập; mọi output training/export/benchmark phải nằm trong `artifacts/` hoặc thư mục generated tương ứng.
