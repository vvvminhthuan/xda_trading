# AI Working Rules

## Scope

These rules apply to all work in this repository.

## Request Handling

When receiving a new user request:

1. Check whether there is an existing active plan for the task.
2. If no active plan exists, create a new plan before making changes.
3. The plan must describe:
   - The goal of the request.
   - The logic or reasoning behind the proposed approach.
   - The technologies, frameworks, libraries, tools, or commands expected to be used.
   - The files or areas of the codebase likely to be affected.

## Approval Before Changes

Before editing, creating, deleting, moving, or renaming any file, the AI must ask the user for approval.

Do not make file changes until the user clearly confirms.

## Logic Analysis

Always analyze the user's requested logic before implementation.

The analysis should clarify:

- What the user wants to achieve.
- What behavior is expected.
- Which assumptions are being made.
- Any risks, edge cases, or unclear requirements.

## Implementation Style

After the user approves the plan and file changes:

- Follow the existing structure and style of the repository.
- Keep changes focused on the approved request.
- Avoid unrelated refactors.
- Explain any meaningful tradeoffs before applying them.

## Function and Method Documentation

Khi tạo function hoặc method mới:

- Phải viết mô tả bằng tiếng Việt.
- Mô tả cần giải thích mục đích của function hoặc method.
- Nếu có tham số quan trọng, cần mô tả vai trò của từng tham số.
- Nếu có giá trị trả về, cần mô tả ý nghĩa của giá trị trả về.

Khi sử dụng function, method, class, hoặc API từ thư viện/framework bên ngoài:

- Cần mô tả ngắn gọn bằng tiếng Việt function hoặc API đó dùng để làm gì.
- Cần giải thích vì sao nó phù hợp với logic đang triển khai.
- Ưu tiên mô tả ở vị trí gần đoạn code sử dụng, bằng comment ngắn gọn hoặc tài liệu phù hợp với phong cách hiện có của dự án.

## Documentation and Planning

Mọi kế hoạch chức năng phải được lưu lại trong thư mục `docs/`.

Quy tắc tổ chức tài liệu:

- Mỗi file trong `docs/` đảm nhận một chức năng hoặc một nhóm logic lớn.
- Tên file cần phản ánh rõ chức năng chính, ví dụ: `bot.md`, `discord.md`, `trading.md`, `trend.md`.
- Trong mỗi file, các chức năng hoặc logic nhỏ hơn phải được mô tả thành các phần riêng.
- Khi thêm hoặc thay đổi logic lớn, cần cập nhật file tài liệu tương ứng trong `docs/`.
- Nếu chưa có file tài liệu phù hợp, cần hỏi người dùng trước khi tạo file mới.

## Project Architecture

Toàn bộ dự án phải được viết bằng Python 3.12.

Quy tắc kiến trúc code:

- 100% code phải được viết theo chuẩn OOP.
- Các chức năng cần được phân tách rõ ràng theo class, module, service, adapter, model, strategy, hoặc indicator phù hợp.
- Không gom nhiều trách nhiệm không liên quan vào cùng một class hoặc method.
- Ưu tiên dependency injection hoặc truyền dependency rõ ràng thay vì tạo phụ thuộc ẩn trong logic xử lý.
- Mỗi class nên đại diện cho một trách nhiệm chính.
- Logic nghiệp vụ cần được đặt trong lớp hoặc module phù hợp, tránh viết logic lớn trực tiếp trong entrypoint.

## Verification

After making changes, verify the result when possible using the appropriate project tools, such as tests, linting, type checks, or targeted command-line checks.

If verification cannot be run, explain why.
