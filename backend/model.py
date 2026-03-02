

import os
import json
from typing import Dict
from dotenv import load_dotenv

from openai import OpenAI
from langchain_openai import ChatOpenAI

load_dotenv()


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.0,
    max_tokens=50,
    model_kwargs={
        "response_format": {"type": "json_object"}
    },
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

llm_rewrite = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.0,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

llm_generate = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.3,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


def detect_query(query: str) -> Dict:
    prompt = f"""Bạn là bộ phân loại intent cho chatbot hành chính phường.

PHẠM VI CHATBOT:
- Thủ tục hành chính
- Lãnh đạo, cơ cấu UBND
- Thông tin về xã/ phường
- Giấy tờ hộ tịch, cư trú
- Phản ánh dịch vụ hành chính

NGOÀI PHẠM VI:
- Giá vàng, chứng khoán
- Tin tức thời sự
- Thời tiết
- Kiến thức chung
- Hỏi về lập trình, toán, sức khỏe
- Nội dung không liên quan đến UBND

Phân loại câu hỏi sau thành một trong 3 loại:
- qa
- complaint
- out_of_scope

Chỉ trả về JSON:
{{
  "intent": ""
}}

Câu hỏi: "{query}"
"""
    
    try:
        response = llm.invoke(prompt)
        raw = response.content
        data = json.loads(raw)

        return data.get("intent") or query
    except:
        return query

def rewrite_query(query: str, last_question: str, last_answer: str) -> str:
    prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

Mục tiêu:
- Biến câu hỏi hiện tại thành câu hỏi ĐỘC LẬP, đủ chủ thể/đối tượng.
- Nếu câu hiện tại thiếu đối tượng (ví dụ: "vậy nộp online được không"), bạn PHẢI thêm đối tượng từ lịch sử (ví dụ: "thủ tục làm giấy khai sinh").
- Không bịa thêm thông tin.

Lịch sử gần nhất:
Người dùng: {last_question}
Trợ lý: {last_answer}

Câu hỏi hiện tại:
{query}

Chỉ trả về 1 câu hỏi đã viết lại, không giải thích."""
    try:
        response = llm_rewrite.invoke(prompt)
        return response.content.strip()
    except:
        return query


def llm_answer(question: str, context: str) -> str:
    prompt = f"""Bạn là chatbot hành chính cấp xã.

Chỉ được sử dụng thông tin trong tài liệu bên dưới để trả lời.
Không được thêm thông tin ngoài tài liệu.
Nếu tài liệu không chứa thông tin cần thiết, trả lời:
"Hiện chưa có thông tin trong hệ thống."

=== TÀI LIỆU ===
{context}

=== CÂU HỎI ===
{question}

Trả lời ngắn gọn, rõ ràng, dễ hiểu cho người dân."""
    try:
        response = llm_generate.invoke(prompt)
        return response.content.strip()
    except:
        return question