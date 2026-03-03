

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
    prompt = f"""
Bạn là bộ phân loại nội dung cho chatbot hành chính cấp phường.

NHIỆM VỤ:
Chỉ phân loại câu hỏi thành một trong 3 loại sau:

1. "complaint"
   - Phản ánh dịch vụ hành chính
   - Góp ý, khiếu nại, bức xúc
   - Phàn nàn thái độ cán bộ
   - Phản ánh chậm trễ, sai sót

2. "banned"
   - Nội dung phản động
   - Xuyên tạc chính quyền
   - Kích động, chống đối nhà nước
   - Xúc phạm lãnh đạo, cán bộ
   - Nội dung vi phạm pháp luật

3. "qa"
   - Tất cả các câu hỏi còn lại

QUY TẮC:
- Không giải thích.
- Không thêm nội dung khác.
- Chỉ trả về JSON đúng format.

Trả về:
{{
  "intent": "complaint | banned | qa"
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

CATEGORIES = [
    "thong_tin_phuong",
    "thu_tuc_hanh_chinh"
]

SUBJECTS = [
    "tu_phap_ho_tich",
"thong_tin_khu_pho",
"lich_lam_viec",
"lanh_dao",
"thong_tin_lien_he",
"tong_quan",
"nhan_su",
"doanh_nghiep",
"giao_thong_van_tai",
"dat_dai",
"xay_dung_nha_o",
"dau_tu",
"lao_dong_viec_lam",
"bao_hiem_an_sinh",
"giao_duc_dao_tao",
"y_te",
"tai_nguyen_moi_truong",
"van_hoa_the_thao_du_lich",
"khoa_hoc_cong_nghe",
"thong_tin_truyen_thong",
"nong_nghiep",
"cong_thuong",
"tai_chinh_thue_phi",
]

def classify_llm(query: str):
    prompt = f"""
Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

BƯỚC 1: Chọn category (chỉ 1 trong 2):
- thong_tin_phuong
- thu_tuc_hanh_chinh

BƯỚC 2: Chọn subject PHÙ HỢP VỚI category:

Nếu category = thu_tuc_hanh_chinh
Chỉ được chọn 1 subject trong danh sách:
- tu_phap_ho_tich
- doanh_nghiep
- giao_thong_van_tai
- dat_dai
- xay_dung_nha_o
- dau_tu
- lao_dong_viec_lam
- bao_hiem_an_sinh
- giao_duc_dao_tao
- y_te
- tai_nguyen_moi_truong
- van_hoa_the_thao_du_lich
- khoa_hoc_cong_nghe
- thong_tin_truyen_thong
- nong_nghiep
- cong_thuong
- tai_chinh_thue_phi

Nếu category = thong_tin_phuong
Chỉ được chọn 1 subject trong danh sách:
- thong_tin_khu_pho
- lich_lam_viec
- thong_tin_lien_he
- tong_quan
- lanh_dao
- nhan_su

QUY TẮC:
- Mỗi field chỉ là 1 chuỗi duy nhất.
- Không được trả về mảng.
- Không giải thích.
- Không được tạo giá trị ngoài danh sách.

Chỉ trả về JSON đúng format:

{{
  "category": "",
  "subject": ""
}}

Câu hỏi: "{query}"
"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        category = data.get("category")
        subject = data.get("subject")

        # Validate output
        if category in CATEGORIES and subject in SUBJECTS:
            return category, subject
        
        print(category, subject)

        # Nếu LLM trả sai → fallback None
        return None, None

    except Exception as e:
        print("LLM classify error:", e)
        return None, None



def classify_subject(query: str):
    prompt = f"""
Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

Chọn subject PHÙ HỢP VỚI category:

Nếu category = thu_tuc_hanh_chinh
Chỉ được chọn 1 subject trong danh sách:
- tu_phap_ho_tich
- doanh_nghiep
- giao_thong_van_tai
- dat_dai
- xay_dung_nha_o
- dau_tu
- lao_dong_viec_lam
- bao_hiem_an_sinh
- giao_duc_dao_tao
- y_te
- tai_nguyen_moi_truong
- van_hoa_the_thao_du_lich
- khoa_hoc_cong_nghe
- thong_tin_truyen_thong
- nong_nghiep
- cong_thuong
- tai_chinh_thue_phi

Nếu category = thong_tin_phuong
Chỉ được chọn 1 subject trong danh sách:
- thong_tin_khu_pho
- lich_lam_viec
- thong_tin_lien_he
- tong_quan
- lanh_dao
- nhan_su

QUY TẮC:
- Mỗi field chỉ là 1 chuỗi duy nhất.
- Không được trả về mảng.
- Không giải thích.
- Không được tạo giá trị ngoài danh sách.

Chỉ trả về JSON đúng format:

{{
  "subject": "",
  "category": "",
}}

Câu hỏi: "{query}"
"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        category = data.get("category")
        subject = data.get("subject")

        # Validate output
        if category in CATEGORIES and subject in SUBJECTS:
            return category, subject
        
        # Nếu LLM trả sai → fallback None
        return None, None

    except Exception as e:
        print("LLM classify error:", e)
        return None, None


def classify_subject_QA(query: str, category: str):
    prompt = f"""
Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

Chọn subject PHÙ HỢP VỚI category là "{category}":

Chỉ được chọn 1 subject trong danh sách:
- thong_tin_khu_pho
- lich_lam_viec
- thong_tin_lien_he
- tong_quan
- lanh_dao
- nhan_su

QUY TẮC:
- Mỗi field chỉ là 1 chuỗi duy nhất.
- Không được trả về mảng.
- Không giải thích.
- Không được tạo giá trị ngoài danh sách.

Chỉ trả về JSON đúng format:

{{
  "subject": ""
}}

Câu hỏi: "{query}"
"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        subject = data.get("subject")

        # Validate output
        if subject in SUBJECTS:
            return subject
        
        # Nếu LLM trả sai → fallback None
        return None

    except Exception as e:
        print("LLM classify error:", e)
        return None

def classify_subject_procedure(query: str, category: str):
    prompt = f"""
Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

Chọn subject PHÙ HỢP VỚI category là "{category}":

Chỉ được chọn 1 subject trong danh sách:
- tu_phap_ho_tich
- doanh_nghiep
- giao_thong_van_tai
- dat_dai
- xay_dung_nha_o
- dau_tu
- lao_dong_viec_lam
- bao_hiem_an_sinh
- giao_duc_dao_tao
- y_te
- tai_nguyen_moi_truong
- van_hoa_the_thao_du_lich
- khoa_hoc_cong_nghe
- thong_tin_truyen_thong
- nong_nghiep
- cong_thuong
- tai_chinh_thue_phi

QUY TẮC:
- Mỗi field chỉ là 1 chuỗi duy nhất.
- Không được trả về mảng.
- Không giải thích.
- Không được tạo giá trị ngoài danh sách.

Chỉ trả về JSON đúng format:

{{
  "subject": ""
}}

Câu hỏi: "{query}"
"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        subject = data.get("subject")

        # Validate output
        if subject in SUBJECTS:
            return subject
        
        # Nếu LLM trả sai → fallback None
        return None

    except Exception as e:
        print("LLM classify error:", e)
        return None
    
# def detect_query(query: str) -> Dict:
#     prompt = f"""Bạn là bộ phân loại intent cho chatbot hành chính phường.

# PHẠM VI CHATBOT:
# - Thủ tục hành chính
# - Lãnh đạo, cơ cấu UBND
# - Thông tin về xã/ phường
# - Giấy tờ hộ tịch, cư trú
# - Phản ánh dịch vụ hành chính
# - Các chức vụ cán bộ phường/xã

# NGOÀI PHẠM VI:
# - Giá vàng, chứng khoán
# - Tin tức thời sự
# - Thời tiết
# - Kiến thức chung
# - Hỏi về lập trình, toán, sức khỏe
# - Nội dung không liên quan đến UBND

# Phân loại câu hỏi sau thành một trong 3 loại:
# - qa
# - complaint
# - out_of_scope

# Chỉ trả về JSON:
# {{
#   "intent": ""
# }}

# Câu hỏi: "{query}"
# """
    
#     try:
#         response = llm.invoke(prompt)
#         raw = response.content
#         data = json.loads(raw)

#         return data.get("intent") or query
#     except:
#         return query

def rewrite_query(query: str, last_question: str, last_answer: str) -> str:
    prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

Mục tiêu:
- Biến câu hỏi hiện tại thành câu hỏi ĐỘC LẬP, đủ chủ thể/đối tượng.
- Nếu câu hiện tại thiếu đối tượng (ví dụ: "vậy nộp online được không"), bạn PHẢI thêm đối tượng từ lịch sử (ví dụ: "thủ tục làm giấy khai sinh").
- Không bịa thêm thông tin.

Lịch sử gần nhất:
Người dùng hỏi là: {last_question}

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
Không được tự ý bổ sung quy định pháp luật ngoài tài liệu.

Nếu tài liệu có thông tin liên quan trực tiếp hoặc gián tiếp đến câu hỏi,
hãy trả lời dựa trên nội dung đó.

Nếu tài liệu hoàn toàn không liên quan đến câu hỏi,
trả lời đúng nguyên văn:
"Hiện chưa có thông tin trong hệ thống."

=== TÀI LIỆU ===
{context}

=== CÂU HỎI ===
{question}

Yêu cầu:
- Trả lời ngắn gọn, rõ ràng.
- Không suy diễn ngoài tài liệu.
- Nếu câu hỏi hỏi về việc kinh doanh mà tài liệu nói về đăng ký hộ kinh doanh,
  hãy giải thích dựa trên thủ tục đó."""
    try:
        response = llm_generate.invoke(prompt)
        return response.content.strip()
    except:
        return question