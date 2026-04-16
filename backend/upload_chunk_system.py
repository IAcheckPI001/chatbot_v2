


import json
import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List
# from to_chuc_doan_the_v6 import extract_intent_with_known_org
from schema_validate_intent_meta_V2 import build_intent_and_meta_extraction_chunk_v2


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_query_hints(chunk_text: str, org_type: str) -> List[dict]:
    system_prompt = """
Bạn là bộ tạo câu hỏi truy vấn giả lập cho chatbot.

MỤC TIÊU
Sinh ra 2 đến 3 câu hỏi thực tế mà người dùng có thể hỏi, và chunk tri thức đã cho có thể dùng để trả lời.

NHIỆM VỤ
- Đọc chunk và hiểu nội dung chính.
- Tạo ra các câu hỏi tự nhiên, ngắn gọn, sát thực tế người dùng.
- Câu hỏi phải phản ánh đúng các ý chính mà chunk có thể trả lời.
- Ưu tiên câu hỏi giúp hệ thống retrieval tìm đúng chunk này.
- Có thể bao phủ cả nội dung chính và 1-2 ý phụ quan trọng nếu chúng xuất hiện rõ trong chunk.
- Không bịa ra thông tin không có trong chunk.
- Không tạo câu hỏi quá rộng nếu chunk chỉ trả lời được một phần nhỏ.
- Không tạo câu hỏi trùng nhau về nghĩa.

QUY TẮC
1. Câu hỏi phải là câu người dùng thật có thể hỏi.
2. Ưu tiên ngôn ngữ tự nhiên, phổ biến, dễ gặp.
3. Nếu chunk nói về thủ tục, nên sinh câu hỏi về:
   - điều kiện
   - hồ sơ
   - quy trình
   - thời hạn / lệ phí nếu có
4. Nếu chunk nói về nhân sự, nên sinh câu hỏi về:
   - ai là ...
   - danh sách ...
   - gồm những ai
5. Nếu chunk nói về thông tin chung, nên sinh câu hỏi về:
   - là gì
   - tên đầy đủ
   - chức năng / nhiệm vụ
   - địa chỉ / liên hệ nếu có
6. Nếu chunk nói về quyền lợi / hỗ trợ, nên sinh câu hỏi về:
   - được gì
   - có quyền gì
   - được hỗ trợ gì
7. Nếu chunk có ngoại lệ hoặc trường hợp đặc biệt quan trọng, có thể sinh 1 câu hỏi riêng cho ngoại lệ đó.

ĐỊNH DẠNG OUTPUT
Chỉ trả JSON hợp lệ:
{
  "organization_type": "...",
  "query_hints": ["...", "...", "..."]
}
""".strip()

    user_prompt = f"""
Hãy sinh 3-5 câu hỏi thực tế có thể hỏi tới chunk sau.

INPUT
- organization_type: "{org_type}"
- chunk_text: "{chunk_text}"

YÊU CẦU
- Chỉ trả 3-5 câu hỏi
- Câu hỏi phải khác nhau về mục đích hỏi
- Không giải thích
- Chỉ trả JSON
""".strip()

    queries = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=queries,
        temperature=0.0,
        response_format={"type": "json_object"},  # 🔥 ép JSON
    )

    content = response.choices[0].message.content

    try:
        parsed = json.loads(content)
    except Exception:
        # fallback nếu LLM trả lỗi format
        return {
            "organization_type": org_type,
            "query_hints": []
        }

    return parsed

def extract_intent_and_meta(chunk_content: str, org_type: str):

    context = build_intent_and_meta_extraction_chunk_v2(chunk_content, org_type)

    # print(f"Câu hỏi 1 -> token: {count_tokens(context)}")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=context,
        temperature=0.0,
        response_format={"type": "json_object"},  # 🔥 ép JSON
    )

    content = response.choices[0].message.content

    try:
        parsed = json.loads(content)
    except Exception:
        # fallback nếu LLM trả lỗi format
        return {
            "organization_type": org_type,
            "meta": {},
            "confidence": 0.0,
            "needs_clarification": True
        }

    return parsed

    # meta_payload = build_meta_payload(intent, fields)
    # primary_values = meta_payload["primary_values"][0]
    # mode_values = meta_payload["mode_values"]

    # return intent, primary_values, mode_values

# if __name__ == "__main__":
#     chunk_content = """Chức vụ hiển thị: Chủ tịch hội nông dân xã Mức chức vụ: chính Họ tên: (ông) Hồ Vũ Nam Chức vụ khác: Ủy viên ban chấp hành Đảng bộ xã, Phó chủ tịch Ủy ban mặt trận tổ quốc xã Số điện thoại: (chưa công bố)"""
#     org_type = "mttq"
#     result = extract_intent_and_meta(chunk_content, org_type)
#     print(f"Intent: {result['intent']}")
#     print(f"Primary Values: {result['meta']}")
    # queries = generate_query_hints(chunk_content, org_type)
    # print(f"Query Hints: {queries['query_hints']}")
