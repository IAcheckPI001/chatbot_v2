

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


def detect_query(query: str, context) -> Dict:

    prompt = f"""
Bạn là bộ phân loại nội dung cho chatbot hành chính cấp phường.

NHIỆM VỤ:
Phân loại câu hỏi của người dùng thành đúng 1 trong 4 loại sau:

1. "banned"
   - Nội dung phản động
   - Xuyên tạc chính quyền
   - Kích động, chống đối nhà nước
   - Xúc phạm lãnh đạo, cán bộ
   - Nội dung vi phạm pháp luật

2. "answerable"
- Câu hỏi phù hợp với chatbot
- Và tài liệu bên dưới đã đủ thông tin để trả lời trực tiếp

3. "qa_need_info"
- Câu hỏi phù hợp với chatbot
- Nhưng còn thiếu thông tin quan trọng để xác định đúng đối tượng cần tra cứu
- Và cần hỏi lại người dùng 1 ý ngắn gọn mới trả lời được
Ví dụ:
- "tôi muốn liên hệ với khu phố, thì gặp ai" → qa_need_info
- "nộp hồ sơ thì mất bao lâu sẽ xử lý" → qa_need_info (vì còn thiếu thông tin thủ tục gì)
- "anh Hiệp là ai" → chỉ là qa_need_info nếu tài liệu không đủ xác định anh Hiệp là ai

4. "out_of_scope"
- Câu hỏi không liên quan lĩnh vực chatbot hành chính cấp phường
- Hoặc tài liệu bên dưới không đủ liên quan để trả lời
- Và cũng không phải trường hợp chỉ cần hỏi thêm 1 thông tin ngắn là giải quyết được

QUY TẮC:
- Ưu tiên xét theo thứ tự:
  1. banned
  2. answerable
  3. qa_need_info
  4. out_of_scope
- Chỉ chọn 1 nhãn
- Không giải thích
- Chỉ trả về JSON hợp lệ
- Không dùng markdown, không dùng ```json

Trả về đúng format:
{{
  "intent": "banned | answerable | qa_need_info | out_of_scope"
}}

Câu hỏi người dùng:
"{query}"

Tài liệu tìm được:
{context}
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content
        data = json.loads(raw)

        return data.get("intent") or query
    except:
        return query

CATEGORIES = [
    "thong_tin_tong_quan",
    "to_chuc_bo_may",
    "thu_tuc_hanh_chinh",
    "phan_anh_kien_nghi",
    "tuong_tac"
]

SUBJECT_TONG_QUAN = [
    "gioi_thieu_dia_phuong",
    "lich_su_hanh_chinh",
    "dia_ly",
    "thong_ke",
    "giao_thong",
    "lich_lam_viec",
    "thong_tin_lien_he",
    "dich_vu_cong_truc_tuyen"
]

SUBJECT_THU_TUC = [
    "tu_phap_ho_tich",
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

SUBJECT_TO_CHUC_BO_MAY = [
    "chuc_vu",
    "nhan_su"    
]

SUBJECT_PHAN_ANH_KIEN_NGHI = [
    "ha_tang",
    "moi_truong",
    "an_ninh_trat_tu",
    "giao_thong",
    "do_thi",
    "khieu_nai_to_cao",
    "he_thong"
]

SUBJECTS = [
    "tu_phap_ho_tich",
    "thong_tin_khu_pho",
    "lich_lam_viec",
    "chuc_vu",
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
    prompt = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

NHIỆM VỤ
Xác định category và subject của câu hỏi.

CATEGORY (chỉ chọn 1):

1. thu_tuc_hanh_chinh  
Câu hỏi về hồ sơ, đăng ký, cấp giấy, thủ tục, nộp ở đâu, cần giấy tờ gì.

2. to_chuc_bo_may  
Câu hỏi về cán bộ, chức danh, ai phụ trách, ai là chủ tịch, phó chủ tịch.

3. thong_tin_tong_quan  
Thông tin chung: địa chỉ, khu phố, giờ làm việc, số điện thoại.

4. phan_anh_kien_nghi
Câu hỏi dùng để phản ánh, báo sự cố, báo vi phạm, kiến nghị xử lý một vấn đề công cộng hoặc vi phạm đang xảy ra tại địa phương, cần cơ quan chức năng kiểm tra hoặc xử lý.

5. tuong_tac (tương tác chung, không thuộc 4 category trên, ví dụ: "cảm ơn", "xin chào", "mày là chatbot à")
---

SUBJECT

Nếu category = thu_tuc_hanh_chinh

- tu_phap_ho_tich (khai sinh, khai tử, kết hôn, chứng thực, tạm trú, tạm vắng, giám hộ, nhận cha mẹ con, nuôi con nuôi)
- doanh_nghiep (đăng ký kinh doanh, hộ kinh doanh)
- giao_thong_van_tai (đăng ký phương tiện, đăng kiểm, giấy phép lái xe, vận tải, bến bãi, hàng không)
- dat_dai (sổ đỏ, quyền sử dụng đất)
- xay_dung_nha_o (giấy phép xây dựng, sửa chữa, cải tạo, hoàn công, nhà ở, chung cư, quy hoạch xây dựng)
- dau_tu (chủ trương đầu tư, giấy chứng nhận đăng ký đầu tư, ưu đãi đầu tư, dự án đầu tư)
- giao_duc_dao_tao (cơ sở giáo dục, hoạt động giáo dục, văn bằng, chứng chỉ, tuyển sinh, chuyển trường, học bổng)
- lao_dong_viec_lam (hợp đồng lao động, tranh chấp lao động, an toàn lao động, việc làm, đào tạo nghề, lao động nước ngoài)
- bao_hiem_an_sinh (BHXH, BHYT, hộ nghèo, trợ cấp xã hội, nhà ở xã hội, người vô gia cư)
- y_te (an toàn thực phẩm, trang thiết bị y tế, an toàn thực phẩm, dịch bệnh)
- tai_nguyen_moi_truong (môi trường, tài nguyên nước, khoáng sản, biến đổi khí hậu, thiên tai)
- cong_thuong (rượu, thuốc lá, điện lực, hóa chất, xúc tiến thương mại, quản lý thị trường, xuất nhập khẩu)
- van_hoa_the_thao_du_lich (văn hóa, nghệ thuật biểu diễn, quảng cáo, xuất bản, thể thao, du lịch, lễ hội, di sản)
- tai_chinh_thue_phi (thuế, phí, lệ phí, hải quan, ngân sách, tài sản công)
- khoa_hoc_cong_nghe (khoa học công nghệ, sở hữu trí tuệ, chuyển giao công nghệ)
- thong_tin_truyen_thong (báo chí, phát thanh, truyền hình, mạng xã hội, an toàn thông tin)
- nong_nghiep (trồng trọt, chăn nuôi, thủy sản, thú y)

Nếu category = thong_tin_tong_quan

- gioi_thieu_dia_phuong
- lich_su_hanh_chinh
- dia_ly (vị trí, địa chỉ, địa lý, tiếp giáp, nằm ở đâu, thuộc quận nào)
- thong_ke (số lượng thống kê về dân số, kinh tế, xã hội, khu phố, diện tích... của địa phương)
- giao_thong
- lich_lam_viec
- thong_tin_lien_he (không chứa chủ thể là người, ví dụ: "số điện thoại của UBND", "địa chỉ email của phường", "cách liên hệ với phường")

Nếu category = to_chuc_bo_may

- nhan_su
- chuc_vu

Nếu category = phan_anh_kien_nghi

- ha_tang (điện, nước, cống thoát nước, đường hư, ngập nước, chiếu sáng công cộng, công trình công cộng hư hỏng)
- moi_truong (rác thải, ô nhiễm, mùi hôi, nước thải, vệ sinh môi trường)
- an_ninh_trat_tu (mất trật tự, gây rối, cờ bạc, đánh nhau, tụ tập, trộm cắp, an ninh khu vực)
- do_thi (lấn chiếm vỉa hè, xây dựng trái phép, quảng cáo sai quy định, mỹ quan đô thị)
- giao_thong (kẹt xe, đậu xe sai quy định, tai nạn, biển báo, tín hiệu giao thông, lấn chiếm lòng lề đường)
- khieu_nai_to_cao (khiếu nại, tố cáo về cán bộ, dịch vụ công, tham nhũng, tiêu cực, vi phạm pháp luật)

---

QUY TẮC

- Chỉ chọn subject phù hợp với category
- Nếu câu hỏi vừa có dấu hiệu thủ tục vừa có nội dung báo sự cố/vấn đề đang xảy ra thực tế, ưu tiên chọn phan_anh_kien_nghi.
- Nếu không chắc chắn, hãy chọn subject gần nhất theo lĩnh vực của câu hỏi.
- Không giải thích
- Không tạo giá trị mới
- Trả về JSON

FORMAT

{{
  "category": "",
  "subject": ""
}}

Câu hỏi:
"{query}"
"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        category = data.get("category")
        subject = data.get("subject")

        print(category, subject)

        if category == "thu_tuc_hanh_chinh" and subject in SUBJECT_THU_TUC:
            print(category, subject)
            return category, subject
        
        if category == "to_chuc_bo_may" and subject in SUBJECT_TO_CHUC_BO_MAY:
            print(category, subject)
            return category, subject
        
        if category == "thong_tin_tong_quan" and subject in SUBJECT_TONG_QUAN:
            print(category, subject)
            return category, subject
        
        if category == "phan_anh_kien_nghi" and subject in SUBJECT_PHAN_ANH_KIEN_NGHI:
            print(category, subject)
            return category, subject
        
        if category == "tuong_tac":
            print(category, subject)
            return category, subject

        # Nếu LLM trả sai → fallback None
        return None, None

    except Exception as e:
        print("LLM classify error:", e)
        return None, None

# def classify_llm(query: str):
#     prompt = f"""
# Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

# BƯỚC 1: Chọn category (chỉ 1 trong 3):
# - thong_tin_tong_quan
# - to_chuc_bo_may (bao gồm ai phụ trách, đảm nhiệm, vai trò, chức danh/bí thư, chủ tịch, Phó chủ tịch, giám đốc, phó giám đốc, trưởng phòng, Phó trưởng phòng/công chức, viên chức, cán bộ, chuyên viên)
# - thu_tuc_hanh_chinh

# BƯỚC 2: Chọn subject PHÙ HỢP VỚI category:

# Nếu category = thu_tuc_hanh_chinh
# Chỉ được chọn 1 subject trong danh sách:
# - tu_phap_ho_tich
# - doanh_nghiep
# - giao_thong_van_tai
# - dat_dai
# - xay_dung_nha_o
# - dau_tu
# - lao_dong_viec_lam
# - bao_hiem_an_sinh
# - giao_duc_dao_tao
# - y_te
# - tai_nguyen_moi_truong
# - van_hoa_the_thao_du_lich
# - khoa_hoc_cong_nghe
# - thong_tin_truyen_thong
# - nong_nghiep
# - cong_thuong
# - tai_chinh_thue_phi

# Nếu category = thong_tin_tong_quan
# Chỉ được chọn 1 subject trong danh sách:
# - tong_quan (thông tin về xã/phường, địa lý, đặc điểm)
# - thong_tin_khu_pho (thông tin chi tiết về 1 khu phố nào đó)
# - lich_lam_viec
# - thong_tin_lien_he (không chứa chủ thể là người)

# Nếu category = to_chuc_bo_may
# Chỉ được chọn 1 subject trong danh sách:
# - nhan_su
# - chuc_vu

# Nếu category = phan_anh_kien_nghi
# Chỉ được chọn 1 subject trong danh sách:
# - tong_quan

# QUY TẮC:
# - Mỗi field chỉ là 1 chuỗi duy nhất.
# - Phải chọn đúng subject theo category
# - Không được trả về mảng.
# - Không giải thích.
# - Không được tạo giá trị ngoài danh sách.

# Chỉ trả về JSON đúng format:

# {{
#   "category": "",
#   "subject": ""
# }}

# Câu hỏi: "{query}"
# """

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


def classify_subject_bo_may(query: str, category: str):
    prompt = f"""
Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

Chọn subject PHÙ HỢP VỚI category là "{category}":

Chỉ được chọn 1 subject trong danh sách:
- nhan_su (ví dụ: phụ trách, đảm nhiệm, vai trò)
- chuc_vu (ví dụ: bí thư, chủ tịch, Phó chủ tịch, giám đốc, phó giám đốc, trưởng phòng, Phó trưởng phòng/công chức, viên chức, cán bộ, chuyên viên,...)

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

def classify_subject_QA(query: str, category: str):
    prompt = f"""
Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

Chọn subject PHÙ HỢP VỚI category là "{category}":

Chỉ được chọn 1 subject trong danh sách:
- thong_tin_khu_pho
- lich_lam_viec
- thong_tin_lien_he
- tong_quan

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

# def rewrite_query(query: str, last_question: str) -> str:
#     prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

# Mục tiêu:
# - Biến câu hỏi hiện tại thành câu hỏi ĐỘC LẬP, đủ chủ thể/đối tượng.
# - Nếu câu hiện tại thiếu đối tượng (ví dụ: "vậy nộp online được không"), bạn PHẢI thêm đối tượng từ lịch sử (ví dụ: "thủ tục làm giấy khai sinh").
# - Không bịa thêm thông tin.

# Lịch sử gần nhất:
# Người dùng hỏi là: {last_question}

# Câu hỏi hiện tại:
# {query}

# Chỉ trả về 1 câu hỏi đã viết lại, không giải thích."""
#     try:
#         response = llm_rewrite.invoke(prompt)
#         return response.content.strip()
#     except:
#         return query


def rewrite_query(query: str, last_question: str) -> str:
    prompt = f"""
Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

Mục tiêu:
- Biến câu hỏi hiện tại thành câu hỏi ĐỘC LẬP nếu câu hỏi hiện tại thiếu đối tượng.
- Nếu câu hỏi hiện tại đã đầy đủ chủ thể hoặc có đối tượng mới → GIỮ NGUYÊN câu hỏi.
- KHÔNG được suy diễn thêm thông tin.
- KHÔNG được thay đổi ý nghĩa câu hỏi.
- KHÔNG được thay đổi tên người, địa điểm hoặc đối tượng mới trong câu hỏi.

Quy tắc:
1. Nếu câu hỏi hiện tại là câu hỏi tiếp nối (ví dụ: "làm ở đâu", "bao lâu", "cần giấy tờ gì") → thêm đối tượng từ lịch sử.
2. Nếu câu hỏi hiện tại đã có đối tượng rõ ràng → giữ nguyên.
3. Nếu câu hỏi hiện tại nhắc đến đối tượng mới → bỏ qua lịch sử và giữ nguyên.

Ví dụ:
Lịch sử: "đăng ký khai sinh"
Câu hỏi: "làm ở đâu"
→ "đăng ký khai sinh làm ở đâu"

Lịch sử: "chị Thu là ai"
Câu hỏi: "anh Hiệp là ai"
→ "anh Hiệp là ai"

Lịch sử gần nhất:
{last_question}

Câu hỏi hiện tại:
{query}

Chỉ trả về câu hỏi cuối cùng. Không giải thích.
"""
    try:
        response = llm_rewrite.invoke(prompt)
        return response.content.strip()
    except:
        return query

def llm_get_info(query: str) -> str:
    prompt = f"""
Bạn là chatbot hành chính cấp xã.

Hãy xác định câu hỏi của người dùng có thiếu thông tin để trả lời hay không.

- Nếu không thiếu thông tin:
  trả về: "DU_THONG_TIN"
- Nếu thiếu thông tin:
  chỉ trả về đúng 1 câu hỏi ngắn để hỏi lại người dùng.
- Không trả lời lan man.
- Không thêm giải thích.
- Không thêm ký hiệu đầu dòng.

Ưu tiên hỏi thông tin còn thiếu quan trọng nhất:
- khu phố số mấy
- ấp nào
- xã/phường nào
- chức danh nào
- bộ phận nào
- thủ tục cụ thể nào

Ví dụ:
Người dùng: "tôi muốn liên hệ với khu phố, thì gặp ai"
Kết quả: "Dạ hiện tại anh/chị đang ở khu phố số mấy ạ?"

Người dùng: "tôi muốn làm giấy khai sinh"
Kết quả: "Dạ anh/chị muốn đăng ký khai sinh mới hay đăng ký lại khai sinh ạ?"

Người dùng: "{query}"
Kết quả:
"""
    return prompt

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