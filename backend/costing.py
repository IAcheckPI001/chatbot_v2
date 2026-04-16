import math
from typing import Any, Iterable


def _safe_str(value: Any) -> str:
	if value is None:
		return ""
	if isinstance(value, str):
		return value
	return str(value)


def _estimate_tokens_fallback(text: str) -> int:
	# Fast fallback when tokenizer package is unavailable.
	if not text:
		return 0
	return max(1, math.ceil(len(text) / 4))


def count_tokens(text: Any, model: str = "gpt-4.1-mini") -> int:
	"""Count tokens for a text input.

	Uses tiktoken when available; otherwise falls back to a rough estimate.
	"""
	content = _safe_str(text)
	if not content:
		return 0

	try:
		import tiktoken  # type: ignore

		try:
			encoding = tiktoken.encoding_for_model(model)
		except KeyError:
			encoding = tiktoken.get_encoding("cl100k_base")
		return len(encoding.encode(content))
	except Exception:
		return _estimate_tokens_fallback(content)


def count_message_tokens(messages: Iterable[Any], model: str = "gpt-4o-mini") -> int:
	"""Count total tokens across a chat message list.

	Supports dictionaries with keys like role/content or arbitrary objects.
	"""
	total = 0
	for msg in messages or []:
		if isinstance(msg, dict):
			role = _safe_str(msg.get("role"))
			content = _safe_str(msg.get("content"))
			total += count_tokens(role, model=model)
			total += count_tokens(content, model=model)
			continue

		total += count_tokens(msg, model=model)

	return total


prompt_extract_category = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường/xã.

NHIỆM VỤ: Xác định category của câu hỏi.

CATEGORY (chỉ chọn 1):

1. thu_tuc_hanh_chinh  
Câu hỏi về quy trình / hồ sơ / đăng ký / cấp giấy / thủ tục / nộp ở đâu / cần giấy tờ gì

2. to_chuc_bo_may  
- Câu hỏi về con người cụ thể hoặc chức danh cụ thể:
  ai là ai, ai giữ chức vụ gì, ai phụ trách lĩnh vực nào, cán bộ nào phụ trách, số điện thoại / liên hệ của một cá nhân cụ thể.

3. thong_tin_tong_quan  
- Câu hỏi về thông tin chung của UBND/xã/phường hoặc đơn vị/bộ phận:
  địa chỉ, trụ sở, giờ làm việc, hotline (đường dây nóng), email, danh sách khu phố, số lượng khu phố, cơ cấu các bộ phận, thông tin liên hệ của cơ quan hoặc bộ phận.

4. phan_anh_kien_nghi
- Câu hỏi dùng để phản ánh, kiến nghị, tố cáo, khiếu nại, báo sự cố, báo vi phạm, đề nghị cơ quan chức năng kiểm tra hoặc xử lý một vấn đề thực tế tại địa phương.

5. tuong_tac
- Chỉ dùng cho tương tác ngắn/phụ trợ: chào hỏi, cảm ơn, tạm biệt, xin lỗi, phàn nàn chung chung, chửi bới, xúc phạm.
Ví dụ: "trả lời khó hiểu vậy", "mày ngu quá", "bọn chính quyền toàn lừa đảo", "đám cán bộ này toàn lũ ngu" 

6. chu_de_cam
- Câu hỏi chứa các nội dung phạm pháp, bạo lực, đồi trụy, đời tư nhạy cảm (hỏi vợ con của người khác), trình bày ý kiến cực đoan, thù ghét, kích động bạo lực, 
Ví dụ: "làm sao trốn thuế", "làm giả giấy tờ", "thủ tục hối lộ làm sao", "cách sửa hồ sơ để được duyệt nhanh", "Ý kiến của bạn về Hồ Chí Minh là gì?"
---

QUY TẮC:

- Không giải thích
- Không tạo giá trị mới
- Trả về JSON

FORMAT:

{{
  "category": ""
}}

Câu hỏi:
""
"""

prompt_rewrite = """Bạn là hệ thống viết lại câu hỏi hoàn chỉnh cho chatbot hành chính cấp xã/phường.

NHIỆM VỤ
Viết lại câu hỏi hiện tại thành một câu hỏi độc lập, ngắn gọn, tự nhiên, giữ nguyên ý nghĩa ban đầu.

ĐẦU VÀO
- Câu hỏi hiện tại: 

MỤC TIÊU
- Mở rộng các từ viết tắt phổ biến trong ngữ cảnh hành chính cấp xã/phường.
- Sửa lỗi chính tả rõ ràng, lỗi gõ, lỗi nói miệng nếu có thể suy ra chắc chắn.
- Bỏ các từ đệm không cần thiết như "à", "á", "ậy", "nha", "nhỉ" nếu không làm đổi nghĩa.
- Nếu câu đã rõ và đầy đủ thì giữ nguyên.
- Nếu không đủ chắc chắn để sửa đúng, giữ nguyên câu hiện tại.
- Không được thêm thông tin mới ngoài câu hiện tại.
- Không được đổi tên người, số thứ tự, địa danh, đơn vị hành chính.

QUY TẮC QUAN TRỌNG
- Chỉ viết lại cho rõ hơn, không được suy diễn thêm.
- Giữ nguyên đối tượng được hỏi.
- Giữ nguyên số, tên riêng, chức danh nếu đã đầy đủ.
- Với từ viết tắt hành chính phổ biến, ưu tiên mở rộng:
  - sdt -> số điện thoại
  - ct -> chủ tịch
  - pct -> phó chủ tịch
  - bt -> bí thư
  - kp -> khu phố
  - ubnd -> ủy ban nhân dân
  - tp -> thành phố
- Với lỗi rõ ràng trong ngữ cảnh:
  - trường khu phố -> trưởng khu phố
  - trường kp -> trưởng khu phố

VÍ DỤ
Câu hiện tại: "sdt của chị Thu là gì"
→ "số điện thoại của chị Thu là gì"

Câu hiện tại: "vậy còn chủ tịch tp là ai"
→ "vậy còn chủ tịch thành phố là ai"

Câu hiện tại: "trưởng kp 2 của xã là ai"
→ "trưởng khu phố 2 của xã là ai"

Câu hiện tại: "ct phường là ai?"
→ "chủ tịch phường là ai?"

Câu hiện tại: "ai là trường kp 8 á?"
→ "ai là trưởng khu phố 8?"

Câu hiện tại: "bt phường là ai"
→ "bí thư phường là ai"

Chỉ trả về đúng 1 câu hỏi cuối cùng, không giải thích."""

tokens = count_tokens(prompt_rewrite, "gpt-4o-mini")
print(f"Tokens in prompt_extract_category: {tokens}")
