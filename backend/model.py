

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

# llm_extract = ChatOpenAI(
#     model_name="gpt-4.1-nano",
#     temperature=0.0,
#     openai_api_key=os.getenv("OPENAI_API_KEY")
# )

llm = ChatOpenAI(
    model_name="gpt-4.1-mini",
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
    streaming=True,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


def _render_prompt_template(template: str, fallback_prompt: str, **values) -> str:
    if not template or not isinstance(template, str):
        return fallback_prompt

    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", "" if value is None else str(value))
    return rendered


def detect_query(query: str, context: str) -> str:
    prompt = f"""
Bạn là bộ phân loại nội dung cho chatbot hành chính cấp phường.

NHIỆM VỤ:
Phân loại câu hỏi thành đúng 1 nhãn:
- answerable
- out_of_scope

ĐỊNH NGHĨA:

1. answerable
- Tài liệu đủ để trả lời trực tiếp
- Hoặc đủ để trả lời theo điều kiện / phân nhánh hợp lý
- Hoặc đủ để xác định đúng người, đúng chức vụ, đúng đơn vị, đúng số điện thoại

2. out_of_scope
- Không liên quan chatbot hành chính cấp phường
- Hoặc tài liệu không liên quan
- Và không phải trường hợp chỉ cần hỏi thêm 1 thông tin ngắn

LUẬT ƯU TIÊN CAO:
- Nếu câu hỏi chứa đúng tên người và tài liệu có đúng tên đó kèm chức vụ / số điện thoại / đơn vị => bắt buộc chọn "answerable"
- Nếu câu hỏi hỏi một chức danh cụ thể và tài liệu có người giữ chức danh đó => bắt buộc chọn "answerable"
- Nếu câu hỏi hỏi số điện thoại của người hoặc chức danh và tài liệu có số điện thoại tương ứng => bắt buộc chọn "answerable"
- Nếu tài liệu đã đủ để nhận diện đúng người / đúng chức vụ thì không được chọn "out_of_scope"
- Chỉ chọn "out_of_scope" khi câu hỏi không liên quan đến nội dung được cung cấp

QUY TẮC:
- Ưu tiên theo thứ tự:
  1. answerable
  2. out_of_scope
- Không dùng kiến thức ngoài tài liệu
- Chỉ trả về JSON hợp lệ
- Không giải thích

Trả về đúng format:
{{
  "intent": answerable | out_of_scope"
}}

Câu hỏi:
"{query}"

Tài liệu:
{context}
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        data = json.loads(raw)
        return data.get("intent", "out_of_scope")
    except Exception as e:
        print("detect_query error:", e)
        print("raw:", raw if 'raw' in locals() else None)
        return "out_of_scope"

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
    # thong_tin_tong_quan
    "gioi_thieu_dia_phuong",
    "lich_su_hanh_chinh",
    "dia_ly",
    "thong_ke",
    "giao_thong",
    "lich_lam_viec",
    "thong_tin_lien_he",
    "dich_vu_cong_truc_tuyen",

    # thu_tuc_hanh_chinh
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

    # to_chuc_bo_may
    "chuc_vu",
    "nhan_su",

    # phan_anh_kien_nghi
    "ha_tang",
    "moi_truong",
    "an_ninh_trat_tu",
    "do_thi",
    "khieu_nai_to_cao",
    "he_thong",
]

# def classify_llm(query: str):
#     prompt = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

# NHIỆM VỤ
# Xác định category và subject của câu hỏi.

# CATEGORY (chỉ chọn 1):

# 1. thu_tuc_hanh_chinh  
# Câu hỏi về hồ sơ, đăng ký, cấp giấy, thủ tục, nộp ở đâu, cần giấy tờ gì.

# 2. to_chuc_bo_may  
# Câu hỏi về cán bộ, chức danh, ai phụ trách, ai là chủ tịch, phó chủ tịch.

# 3. thong_tin_tong_quan  
# Thông tin chung: địa chỉ, khu phố, giờ làm việc, số điện thoại.

# 4. phan_anh_kien_nghi
# Câu hỏi dùng để phản ánh, báo sự cố, báo vi phạm, kiến nghị xử lý một vấn đề công cộng hoặc vi phạm đang xảy ra tại địa phương, cần cơ quan chức năng kiểm tra hoặc xử lý.

# 5. tuong_tac (tương tác chung, không thuộc 4 category trên, ví dụ: "cảm ơn", "xin chào", "mày là chatbot à")
# ---

# SUBJECT

# Nếu category = thu_tuc_hanh_chinh

# - tu_phap_ho_tich (khai sinh, khai tử, kết hôn, chứng thực, tạm trú, tạm vắng, giám hộ, nhận cha mẹ con, nuôi con nuôi)
# - doanh_nghiep (đăng ký kinh doanh, hộ kinh doanh)
# - giao_thong_van_tai (đăng ký phương tiện, đăng kiểm, giấy phép lái xe, vận tải, bến bãi, hàng không)
# - dat_dai (sổ đỏ, quyền sử dụng đất)
# - xay_dung_nha_o (giấy phép xây dựng, sửa chữa, cải tạo, hoàn công, nhà ở, chung cư, quy hoạch xây dựng)
# - dau_tu (chủ trương đầu tư, giấy chứng nhận đăng ký đầu tư, ưu đãi đầu tư, dự án đầu tư)
# - giao_duc_dao_tao (cơ sở giáo dục, hoạt động giáo dục, văn bằng, chứng chỉ, tuyển sinh, chuyển trường, học bổng)
# - lao_dong_viec_lam (hợp đồng lao động, tranh chấp lao động, an toàn lao động, việc làm, đào tạo nghề, lao động nước ngoài)
# - bao_hiem_an_sinh (BHXH, BHYT, hộ nghèo, trợ cấp xã hội, nhà ở xã hội, người vô gia cư)
# - y_te (an toàn thực phẩm, trang thiết bị y tế, an toàn thực phẩm, dịch bệnh)
# - tai_nguyen_moi_truong (môi trường, tài nguyên nước, khoáng sản, biến đổi khí hậu, thiên tai)
# - cong_thuong (rượu, thuốc lá, điện lực, hóa chất, xúc tiến thương mại, quản lý thị trường, xuất nhập khẩu)
# - van_hoa_the_thao_du_lich (văn hóa, nghệ thuật biểu diễn, quảng cáo, xuất bản, thể thao, du lịch, lễ hội, di sản)
# - tai_chinh_thue_phi (thuế, phí, lệ phí, hải quan, ngân sách, tài sản công)
# - khoa_hoc_cong_nghe (khoa học công nghệ, sở hữu trí tuệ, chuyển giao công nghệ)
# - thong_tin_truyen_thong (báo chí, phát thanh, truyền hình, mạng xã hội, an toàn thông tin)
# - nong_nghiep (trồng trọt, chăn nuôi, thủy sản, thú y)

# Nếu category = thong_tin_tong_quan

# - gioi_thieu_dia_phuong
# - lich_su_hanh_chinh
# - dia_ly (vị trí, địa chỉ, địa lý, tiếp giáp, nằm ở đâu, thuộc quận nào)
# - thong_ke (số lượng thống kê về dân số, kinh tế, xã hội, khu phố, diện tích... của địa phương)
# - giao_thong
# - lich_lam_viec
# - thong_tin_lien_he (không chứa chủ thể là người, ví dụ: "số điện thoại của UBND", "địa chỉ email của phường", "cách liên hệ với phường")

# Nếu category = to_chuc_bo_may

# - nhan_su
# - chuc_vu

# Nếu category = phan_anh_kien_nghi

# - ha_tang (điện, nước, cống thoát nước, đường hư, ngập nước, chiếu sáng công cộng, công trình công cộng hư hỏng)
# - moi_truong (rác thải, ô nhiễm, mùi hôi, nước thải, vệ sinh môi trường)
# - an_ninh_trat_tu (mất trật tự, gây rối, cờ bạc, đánh nhau, tụ tập, trộm cắp, an ninh khu vực)
# - do_thi (lấn chiếm vỉa hè, xây dựng trái phép, quảng cáo sai quy định, mỹ quan đô thị)
# - giao_thong (kẹt xe, đậu xe sai quy định, tai nạn, biển báo, tín hiệu giao thông, lấn chiếm lòng lề đường)
# - khieu_nai_to_cao (khiếu nại, tố cáo về cán bộ, dịch vụ công, tham nhũng, tiêu cực, vi phạm pháp luật)


# Nếu category = tuong_tac

# - chao_hoi (các câu chào hỏi, tạm biệt, cảm ơn, xin lỗi, lịch sự xã giao)
# - phan_nan (các câu chửi thề, xúc phạm, khiêu khích, kích động, thù ghét, bạo lực)

# ---

# QUY TẮC

# - Chỉ chọn subject phù hợp với category
# - `thong_tin_lien_he` CHỈ dùng cho thông tin liên hệ của đơn vị/cơ quan (UBND/xã/phường: hotline, điện thoại văn phòng, email, website).
# - Nếu câu hỏi liên hệ gắn với cá nhân/chức danh (ví dụ: "số của anh A", "liên hệ chủ tịch") thì chọn `to_chuc_bo_may` với subject `nhan_su` hoặc `chuc_vu`, KHÔNG chọn `thong_tin_lien_he`.
# - Nếu câu hỏi vừa có dấu hiệu thủ tục vừa có nội dung báo sự cố/vấn đề đang xảy ra thực tế, ưu tiên chọn phan_anh_kien_nghi.
# - Nếu không chắc chắn, hãy chọn subject gần nhất theo lĩnh vực của câu hỏi.
# - Không giải thích
# - Không tạo giá trị mới
# - Trả về JSON

# FORMAT

# {{
#   "category": "",
#   "subject": ""
# }}

# Câu hỏi:
# "{query}"
# """

#     try:
#         response = llm.invoke(prompt)
#         raw = response.content.strip()

#         data = json.loads(raw)

#         category = data.get("category")
#         subject = data.get("subject")

#         print(category, subject)

#         if category == "thu_tuc_hanh_chinh" and subject in SUBJECT_THU_TUC:
#             print(category, subject)
#             return category, subject
        
#         if category == "to_chuc_bo_may" and subject in SUBJECT_TO_CHUC_BO_MAY:
#             print(category, subject)
#             return category, subject
        
#         if category == "thong_tin_tong_quan" and subject in SUBJECT_TONG_QUAN:
#             print(category, subject)
#             return category, subject
        
#         if category == "phan_anh_kien_nghi" and subject in SUBJECT_PHAN_ANH_KIEN_NGHI:
#             print(category, subject)
#             return category, subject
        
#         if category == "tuong_tac" and subject in ["chao_hoi", "phan_nan"]:
#             print(category, subject)
#             return category, subject

#         # Nếu LLM trả sai → fallback None
#         return None, None

#     except Exception as e:
#         print("LLM classify error:", e)
#         return None, None


def classify_category(query: str, prompt_template: str = None):
    default_prompt = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường/xã.

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
"{query}"
"""
    prompt = _render_prompt_template(prompt_template, default_prompt, query=query)
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        category = data.get("category")

        if category == "thu_tuc_hanh_chinh":
            print(category)
            return category

        if category == "to_chuc_bo_may":
            print(category)
            return category

        if category == "thong_tin_tong_quan":
            print(category)
            return category

        if category == "phan_anh_kien_nghi":
            print(category)
            return category

        if category == "tuong_tac":
            print(category)
            return category

        if category == "chu_de_cam":
            print(category)
            return category

        # Nếu LLM trả sai → fallback None
        return None

    except Exception as e:
        print("LLM classify error:", e)
        return None

def check_classify_phan_anh_kien_nghi(query: str):
    prompt = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

NHIỆM VỤ: Xác định category của câu hỏi.

CATEGORY (chỉ chọn 1):

1. thu_tuc_hanh_chinh  
Câu hỏi về quy trình / hồ sơ / đăng ký / cấp giấy / thủ tục / nộp ở đâu / cần giấy tờ gì

2. to_chuc_bo_may  
- Câu hỏi về con người cụ thể hoặc chức danh cụ thể:
  ai là ai, ai giữ chức vụ gì, ai phụ trách lĩnh vực nào, cán bộ nào phụ trách, số điện thoại / liên hệ của một cá nhân cụ thể.

3. thong_tin_tong_quan  
- Câu hỏi về thông tin chung của UBND/xã/phường hoặc đơn vị/bộ phận:
  địa chỉ, trụ sở, giờ làm việc, hotline, email, danh sách khu phố, số lượng khu phố, cơ cấu các bộ phận, thông tin liên hệ của cơ quan hoặc bộ phận.

4. tuong_tac
- Chào hỏi, cảm ơn, xin lỗi, nói chuyện xã giao, hỏi chơi, phàn nàn chung chung, chửi thề, xúc phạm, khiêu khích

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
"{query}"
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        category = data.get("category")

        if category == "thu_tuc_hanh_chinh":
            print(category)
            return category

        if category == "to_chuc_bo_may":
            print(category)
            return category

        if category == "thong_tin_tong_quan":
            print(category)
            return category

        if category == "tuong_tac":
            print(category)
            return category

        # Nếu LLM trả sai → fallback None
        return None

    except Exception as e:
        print("LLM classify error:", e)
        return None



def check_classify_tuong_tac(query: str):
    prompt = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp phường.

NHIỆM VỤ: Xác định category của câu hỏi.

CATEGORY (chỉ chọn 1):

1. thu_tuc_hanh_chinh  
Câu hỏi về quy trình / hồ sơ / đăng ký / cấp giấy / thủ tục / nộp ở đâu / cần giấy tờ gì

2. to_chuc_bo_may  
- Câu hỏi về con người cụ thể hoặc chức danh cụ thể:
  ai là ai, ai giữ chức vụ gì, ai phụ trách lĩnh vực nào, cán bộ nào phụ trách, số điện thoại / liên hệ của một cá nhân cụ thể.

3. thong_tin_tong_quan  
- Câu hỏi về thông tin chung của UBND/xã/phường hoặc đơn vị/bộ phận:
  địa chỉ, trụ sở, giờ làm việc, hotline, email, danh sách khu phố, số lượng khu phố, cơ cấu các bộ phận, thông tin liên hệ của cơ quan hoặc bộ phận.

4. phan_anh_kien_nghi
- Câu hỏi dùng để phản ánh, kiến nghị, tố cáo, khiếu nại, báo sự cố, báo vi phạm, đề nghị cơ quan chức năng kiểm tra hoặc xử lý một vấn đề thực tế tại địa phương.

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
"{query}"
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        category = data.get("category")

        if category == "thu_tuc_hanh_chinh":
            print(category)
            return category

        if category == "to_chuc_bo_may":
            print(category)
            return category

        if category == "thong_tin_tong_quan":
            print(category)
            return category

        if category == "phan_anh_kien_nghi":
            print(category)
            return category

        # Nếu LLM trả sai → fallback None
        return None

    except Exception as e:
        print("LLM classify error:", e)
        return None

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

    # try:
    #     response = llm.invoke(prompt)
    #     raw = response.content.strip()

    #     data = json.loads(raw)

    #     category = data.get("category")
    #     subject = data.get("subject")

    #     # Validate output
    #     if category in CATEGORIES and subject in SUBJECTS:
    #         return category, subject
        
    #     print(category, subject)

    #     # Nếu LLM trả sai → fallback None
    #     return None, None

    # except Exception as e:
    #     print("LLM classify error:", e)
    #     return None, None


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


# def rewrite_query(query: str, last_question: str) -> str:
#     prompt = f"""
# Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

# Mục tiêu:
# - Biến câu hỏi hiện tại thành câu hỏi ĐỘC LẬP nếu câu hỏi hiện tại thiếu đối tượng.
# - Nếu câu hỏi hiện tại đã đầy đủ chủ thể hoặc có đối tượng mới → GIỮ NGUYÊN câu hỏi.
# - KHÔNG được suy diễn thêm thông tin.
# - KHÔNG được thay đổi ý nghĩa câu hỏi.
# - KHÔNG được thay đổi tên người, địa điểm hoặc đối tượng mới trong câu hỏi.

# Quy tắc:
# 1. Nếu câu hỏi hiện tại là câu hỏi tiếp nối (ví dụ: "làm ở đâu", "bao lâu", "cần giấy tờ gì") → thêm đối tượng từ lịch sử.
# 2. Nếu câu hỏi hiện tại đã có đối tượng rõ ràng → giữ nguyên.
# 3. Nếu câu hỏi hiện tại nhắc đến đối tượng mới → bỏ qua lịch sử và giữ nguyên.

# Ví dụ:
# Lịch sử: "đăng ký khai sinh"
# Câu hỏi: "làm ở đâu"
# → "đăng ký khai sinh làm ở đâu"

# Lịch sử: "chị Thu là ai"
# Câu hỏi: "anh Hiệp là ai"
# → "anh Hiệp là ai"

# Lịch sử gần nhất:
# {last_question}

# Câu hỏi hiện tại:
# {query}

# Chỉ trả về câu hỏi cuối cùng. Không giải thích.
# """
#     try:
#         response = llm_rewrite.invoke(prompt)
#         return response.content.strip()
#     except:
#         return query
def rewrite_query(query: str, prompt_template: str = None) -> str:
    default_prompt = f"""Bạn là hệ thống viết lại câu hỏi hoàn chỉnh cho chatbot hành chính cấp xã/phường.

NHIỆM VỤ
Viết lại câu hỏi hiện tại thành một câu hỏi độc lập, ngắn gọn, tự nhiên, giữ nguyên ý nghĩa ban đầu.

ĐẦU VÀO
- Câu hỏi hiện tại: {query}

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

Chỉ trả về đúng 1 câu hỏi cuối cùng, không giải thích.
"""
    prompt = _render_prompt_template(
        prompt_template,
        default_prompt,
        query=query,
    )
    try:
        response = llm_rewrite.invoke(prompt)
        return response.content.strip()
    except:
        return query

def rewrite_query_history(query: str, last_question: str, prompt_template: str = None) -> str:
    default_prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

NHIỆM VỤ
Viết lại câu hỏi hiện tại thành đúng 1 câu hỏi độc lập, ngắn gọn, giữ nguyên ý nghĩa gốc.

ĐẦU VÀO
- Câu trước đó đã được viết lại đầy đủ: {last_question}
- Câu hỏi hiện tại: {query}

NGUYÊN TẮC CHUNG
- Chỉ dùng thông tin có trong 2 câu trên.
- Không bịa thêm thông tin mới.
- Nếu không đủ chắc chắn để viết lại đúng, giữ nguyên câu hiện tại.
- Nếu câu hiện tại đã là câu độc lập, giữ nguyên.
- Chỉ trả về đúng 1 câu hỏi cuối cùng, không giải thích.

ƯU TIÊN QUYẾT ĐỊNH
1. Nếu câu hiện tại là lời chào, cảm ơn, cảm thán, xác nhận ngắn, xúc phạm, hoặc quá mơ hồ không xác định chắc chắn được ý hỏi -> giữ nguyên.
2. Nếu câu hiện tại đã đủ chủ đề, đối tượng và ý định hỏi -> giữ nguyên.
3. Nếu câu hiện tại là câu tiếp nối thiếu chủ đề nhưng vẫn giữ ý hỏi cũ -> bổ sung chủ đề từ câu trước.
4. Nếu câu hiện tại đổi đối tượng mới nhưng giữ cách hỏi từ câu trước -> giữ mẫu hỏi cũ và thay đối tượng mới.
5. Nếu câu hiện tại chỉ còn trường thông tin cần hỏi (ví dụ: số điện thoại, địa chỉ, email, hotline, lệ phí, hồ sơ, giấy tờ, bao lâu, ở đâu, online được không) -> khôi phục câu hỏi đầy đủ từ câu trước nếu chắc chắn.
6. Nếu không chắc chắn -> giữ nguyên.

QUY TẮC BẮT BUỘC
- Không biến câu hỏi thông tin nhân sự thành câu hỏi thủ tục.
- Không biến câu hỏi thủ tục thành câu hỏi nhân sự.
- Không đổi tên người, chức danh, địa danh, số hiệu khu phố, số hiệu ấp.
- Không được làm mất các phần *phân biệt quan trọng* của thủ tục như: "lại", "cấp lại", "trích lục", "bản sao", "có yếu tố nước ngoài", "khu vực biên giới", "thường trú", "tạm trú".
- Không tự thêm các từ như "là gì", "ở đâu", "bao lâu", "như thế nào" nếu câu trước không cho thấy rõ ý định đó.
- Nếu sau "còn" là một chủ đề hoặc thủ tục mới rõ ràng, không được dùng chủ đề cũ. Khi thật sự rõ, chỉ giữ cách hỏi cũ và thay bằng chủ đề mới.
VÍ DỤ

1. Thiếu chủ đề
Câu trước: đăng ký khai sinh
Câu hiện tại: nộp online được không
Kết quả: đăng ký khai sinh nộp online được không

Câu trước: đăng ký lại khai sinh
Câu hiện tại: cần giấy tờ gì
Kết quả: đăng ký lại khai sinh cần giấy tờ gì

2. Đổi đối tượng nhưng giữ mẫu hỏi
Câu trước: đăng ký kết hôn làm sao/như thế nào
Câu hiện tại: còn mất cccd
Kết quả: còn mất cccd làm sao

Câu trước: ai là trưởng khu phố 1 của xã
Câu hiện tại: còn trưởng kp 2
Kết quả: ai là trưởng khu phố 2 của xã

3. Chỉ còn trường thông tin cần hỏi
Câu trước: địa chỉ ubnd xã ở đâu
Câu hiện tại: số điện thoại
Kết quả: số điện thoại của ubnd xã là gì

Câu trước: đăng ký khai sinh có yếu tố nước ngoài
Câu hiện tại: lệ phí bao nhiêu
Kết quả: đăng ký khai sinh có yếu tố nước ngoài lệ phí là bao nhiêu

4. Đại từ hồi chỉ
Câu trước: phó chủ tịch phụ trách văn hóa là ai
Câu hiện tại: số của người đó
Kết quả: số điện thoại của phó chủ tịch phụ trách văn hóa là gì

5. Chuyển chủ đề
Câu trước: xã hiện tại có những đặc điểm gì
Câu hiện tại: cần giấy tờ gì
Kết quả: cần giấy tờ gì

Câu trước: chủ tịch xã là ai
Câu hiện tại: thủ tục khai sinh cần gì
Kết quả: thủ tục khai sinh cần gì

6. Xã giao / cảm thán / quá mơ hồ
Câu trước: đăng ký khai sinh cần gì
Câu hiện tại: xin chào
Kết quả: xin chào

Câu trước: chủ tịch xã là ai
Câu hiện tại: ok vậy thôi
Kết quả: ok vậy thôi
"""
#     default_prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

# NHIỆM VỤ
# Viết lại câu hỏi hiện tại thành một câu hỏi độc lập, ngắn gọn, giữ nguyên ý nghĩa.

# ĐẦU VÀO
# - Câu trước đó đã được viết lại đầy đủ: {last_question}
# - Câu hỏi hiện tại: {query}

# MỤC TIÊU
# - Nếu câu hiện tại thiếu chủ đề / thiếu đối tượng / thiếu ý định hỏi, hãy dùng câu trước để bổ sung.
# - Nếu câu hiện tại đã là một câu độc lập -> giữ nguyên.
# - Bỏ các từ đệm không cần thiết như "à", "á", "ậy", "nha", "nhỉ" nếu không làm đổi nghĩa.
# - Nếu câu hiện tại có đối tượng mới nhưng đang kế thừa cách hỏi từ câu trước, hãy giữ cách hỏi cũ và thay đối tượng mới vào.
# - Nếu không đủ chắc chắn để viết lại đúng, giữ nguyên câu hiện tại.
# - Không được bịa thêm thông tin ngoài 2 câu đã cho.

# QUY TẮC
# 1. Nếu câu hiện tại là câu tiếp nối thiếu chủ đề
# Ví dụ: "ở đâu", "bao lâu", "nộp online được không", "cần giấy tờ gì"
# → thêm chủ đề từ câu trước.
# Câu trước: "đăng ký khai sinh"
# Câu hiện tại: "nộp online được không"
# → "đăng ký khai sinh nộp online được không"

# 2. Nếu câu hiện tại có đối tượng mới nhưng thiếu ý định hỏi
# Ví dụ: "còn anh Hiệp", "thế chị Thu", "còn trưởng kp 2", "còn ct", "ông ấy", "anh ấy", "cô ấy", "bà ấy"
# → giữ mẫu hỏi của câu trước và thay bằng đối tượng mới.
# Câu trước: "bí thư phường là ai"
# Câu hiện tại: "số của anh ấy là"
# → "số điện thoại của bí thư phường là"

# Câu trước: "sdt của chị Thu là gì"
# Câu hiện tại: "còn anh Hiệp"
# → "số điện thoại của anh Hiệp là gì"

# Câu trước: "ai là trưởng khu phố 1 của xã"
# Câu hiện tại: "còn trưởng kp 2"
# → "ai là trưởng khu phố 2 của xã"

# 3. Nếu câu hiện tại đã có đủ chủ đề và ý định hỏi
# → giữ nguyên.

# 4. Nếu câu hiện tại chuyển sang chủ đề khác
# → giữ nguyên, không dùng lịch sử.
# Câu trước: "xã hiện tại có những đặc điểm gì"
# Câu hiện tại: "cần giấy tờ gì"
# → "cần giấy tờ gì"

# 5. Nếu câu hiện tại là câu chào hỏi, cảm thán, xúc phạm, hoặc quá mơ hồ không thể xác định chắc chắn
# → giữ nguyên.

# Câu trước: "xã hiện tại có những đặc điểm gì"
# Câu hiện tại: "xin chào"
# → "xin chào"

# 6. Không biến câu hỏi thông tin nhân sự thành câu hỏi thủ tục.
# 7. Không biến câu hỏi thủ tục thành câu hỏi nhân sự.
# 8. Không đổi tên người, chức danh, địa danh, số hiệu khu phố.
# 9. Không thêm các phần như "là gì", "như thế nào", "ở đâu", "bao lâu" nếu câu trước không cho thấy rõ ý định đó.
# 10. Ưu tiên an toàn: nếu phân vân, giữ nguyên.

# Chỉ trả về đúng 1 câu hỏi cuối cùng, không giải thích.
# """

    prompt = _render_prompt_template(
        prompt_template,
        default_prompt,
        query=query,
        last_question=last_question,
    )
    try:
        response = llm_rewrite.invoke(prompt)
        return response.content.strip()
    except:
        return query

# def rewrite_query_history(query: str, last_question: str, prompt_template: str = None) -> str:
#     default_prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã/phường.

# Nhiệm vụ:
# Viết lại câu hỏi hiện tại thành 1 câu hỏi độc lập, ngắn gọn, đúng nghĩa, chỉ dựa vào:
# - Câu trước đó đã được viết lại đầy đủ: {last_question}
# - Câu hỏi hiện tại: {query}

# Mục tiêu:
# - Nếu câu hiện tại thiếu chủ đề, đối tượng hoặc ý định hỏi, dùng câu trước để bổ sung.
# - Nếu câu hiện tại đã đủ nghĩa và độc lập, giữ nguyên.
# - Nếu câu hiện tại có đối tượng mới nhưng đang kế thừa cách hỏi từ câu trước, giữ cách hỏi cũ và thay đối tượng mới.
# - Nếu câu hiện tại hỏi thuộc tính khác của cùng một chủ thể trong câu trước, giữ chủ thể đó và thay thuộc tính mới vào.
# - Nếu câu hiện tại dùng đại từ như "ông ấy", "anh ấy", "chị ấy", "cô ấy", "bà ấy", "người đó", "người này", "vị đó", và câu trước có 1 đối tượng rõ ràng, thay đại từ bằng đối tượng đó.
# - Bỏ các từ đệm không cần thiết như "à", "á", "ậy", "nha", "nhỉ" nếu không làm đổi nghĩa.
# - Không được bịa thêm thông tin ngoài 2 câu đã cho.
# - Nếu không chắc, giữ nguyên câu hiện tại.

# Luật:
# 1. Nếu câu hiện tại là câu tiếp nối thiếu chủ đề
# Ví dụ: "ở đâu", "bao lâu", "nộp online được không", "cần giấy tờ gì"
# → thêm chủ đề từ câu trước.

# 2. Nếu câu hiện tại có đối tượng mới nhưng thiếu ý định hỏi
# Ví dụ: "còn anh Hiệp", "thế chị Thu", "còn trưởng kp 2", "còn ct"
# → giữ mẫu hỏi của câu trước và thay đối tượng mới.

# 3. Nếu câu hiện tại hỏi thuộc tính khác của cùng một chủ thể
# Ví dụ: "dân số thì sao", "giờ làm việc thì sao", "số điện thoại nữa", "diện tích nữa"
# → giữ chủ thể ở câu trước và thay thuộc tính mới vào.

# 4. Nếu câu hiện tại dùng đại từ thay thế
# Ví dụ: "ông ấy", "anh ấy", "chị ấy", "bà ấy", "người đó", "người này"
# → thay bằng đối tượng rõ ràng ở câu trước nếu xác định chắc chắn.

# 5. Các từ nối tiếp như "còn", "vậy còn", "thế", "thì sao", "nữa" có thể là câu hỏi theo ngữ cảnh.

# 6. Nếu câu hiện tại đã có đủ chủ đề và ý định hỏi
# → giữ nguyên.

# 7. Nếu câu hiện tại chuyển sang chủ đề khác
# → giữ nguyên, không dùng lịch sử.

# 8. Nếu câu hiện tại là câu chào hỏi, cảm thán, xúc phạm, hoặc quá mơ hồ không thể xác định chắc chắn
# → giữ nguyên.

# 9. Không biến câu hỏi thủ tục thành câu hỏi nhân sự.
# 10. Không biến câu hỏi nhân sự thành câu hỏi thủ tục.
# 11. Không đổi tên người, chức danh, địa danh, tên đơn vị, số hiệu khu phố.
# 12. Không thêm thông tin không có trong 2 câu.
# 13. Ưu tiên an toàn: nếu phân vân, giữ nguyên câu hiện tại.

# Ví dụ:
# Câu trước: "đăng ký khai sinh"
# Câu hiện tại: "nộp online được không"
# → "đăng ký khai sinh nộp online được không"

# Câu trước: "sdt của chị Thu là gì"
# Câu hiện tại: "còn anh Hiệp"
# → "số điện thoại của anh Hiệp là gì"

# Câu trước: "bí thư phường là ai"
# Câu hiện tại: "số của ông ấy là gì"
# → "số điện thoại của bí thư phường là gì"

# Câu trước: "ai là trưởng khu phố 1 của xã"
# Câu hiện tại: "còn trưởng kp 2"
# → "ai là trưởng khu phố 2 của xã"

# Câu trước: "phường có diện tích bao nhiêu"
# Câu hiện tại: "dân số thì sao"
# → "phường có dân số bao nhiêu"

# Câu trước: "địa chỉ ubnd phường ở đâu"
# Câu hiện tại: "giờ làm việc thì sao"
# → "giờ làm việc của ubnd phường là gì"

# Câu trước: "xã hiện tại có những đặc điểm gì"
# Câu hiện tại: "cần giấy tờ gì"
# → "cần giấy tờ gì"

# Câu trước: bí thư phường là ai"
# Câu hiện tại: "xin chào"
# → "xin chào"

# Chỉ trả về đúng 1 câu hỏi cuối cùng, không giải thích."""
#     prompt = _render_prompt_template(
#         prompt_template,
#         default_prompt,
#         query=query,
#         last_question=last_question,
#     )
#     try:
#         response = llm_rewrite.invoke(prompt)
#         return response.content.strip()
#     except:
#         return query

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

def llm_answer_procedure(question: str, context: str, prompt_template: str = None) -> str:
    default_prompt = f"""Bạn là trợ lý chatbot hành chính cấp xã/phường, trả lời thân thiện, tự nhiên, dễ hiểu như đang hướng dẫn người dân.

Hãy trả lời chỉ dựa trên thông tin có trong tài liệu bên dưới.
Không thêm quy định, thủ tục, thời hạn, lệ phí hoặc cơ quan xử lý nếu tài liệu không nêu.

Nếu tài liệu đủ thông tin, hãy trả lời trực tiếp bằng văn phong tự nhiên, rõ ràng.
Nếu tài liệu chỉ khớp một phần nhưng vẫn có thể hướng dẫn người dùng, hãy trả lời theo hướng phù hợp nhất và nêu điều kiện ngắn gọn khi cần.
Chỉ khi tài liệu hoàn toàn không liên quan mới trả lời đúng nguyên văn:
Hiện chưa có thông tin trong hệ thống.

=== TÀI LIỆU ===
{context}

=== CÂU HỎI ===
{question}

Yêu cầu nội dung:
- Trả lời tự nhiên, thân thiện, không quá máy móc.
- Luôn mở đầu câu trả lời là "Thưa anh/chị," và kết thúc bằng "Thân mến!"
- Ưu tiên trả lời thẳng vào ý người dùng hỏi.
- Không cần luôn mở đầu bằng “Theo tài liệu”.
- Chỉ nêu điều kiện khi thật sự cần để tránh hiểu sai.
- Nếu tài liệu có nêu hồ sơ, nơi nộp, thời gian giải quyết thì có thể tóm tắt ngắn gọn.
- Không bịa thêm thông tin ngoài tài liệu.

Yêu cầu trình bày:
- Trình bày bằng markdown đơn giản, dễ đọc trên giao diện chat.
- Với câu hỏi ngắn và câu trả lời chỉ có 1 ý chính, trả lời thành 1 đoạn ngắn tự nhiên, không cần chia mục.
- Nếu câu trả lời có từ 2 ý trở lên, hãy tách thành các đoạn ngắn; mỗi đoạn nên thể hiện 1 ý chính.
- Ưu tiên câu ngắn, rõ ý; tránh viết 1 đoạn quá dài.
- Khi có danh sách hồ sơ, giấy tờ, bước thực hiện hoặc lưu ý, hãy dùng bullet list.
- Có thể in đậm các thông tin quan trọng hoặc các nhãn ngắn như: **Hồ sơ**, **Nơi nộp**, **Hình thức nộp**, **Thời gian giải quyết**, **Lưu ý**.
- Không lạm dụng tiêu đề lớn hoặc chia quá nhiều mục nhỏ.
- Chỉ dùng bảng markdown khi người dùng đang hỏi so sánh nhiều thủ tục hoặc nhiều phương án; nếu không, không dùng bảng.
- Không dùng ký hiệu, biểu tượng hoặc trang trí không cần thiết.
- Ưu tiên ngắn gọn, rõ ý, nhìn thoáng.

Quy tắc xét duyệt hồ sơ (BẮT BUỘC TUÂN THỦ STRICTLY):
- Các mục liệt kê trong phần "Hồ sơ gồm" là điều kiện bắt buộc.
- Ký tự "/" hoặc chữ "hoặc" có nghĩa là chỉ cần 1 trong các loại giấy tờ đó.
- NẾU người dùng hỏi về việc thiếu/mất một loại giấy tờ, bạn PHẢI trả lời rõ là KHÔNG THỂ thực hiện thủ tục, TRỪ KHI họ có giấy tờ thay thế hợp lệ ghi trong tài liệu.
- Ví dụ: Tài liệu ghi "CCCD/Hộ chiếu", nếu người dùng mất CCCD, phải hướng dẫn họ dùng Hộ chiếu thay thế. Nếu không có cả hai, không thể đăng ký.
"""
    prompt = _render_prompt_template(
        prompt_template,
        default_prompt,
        question=question,
        query=question,
        context=context,
    )
    try:
        response = llm_generate.invoke(prompt)
        print("LLM response:", response.content)
        return response.content.strip()
    except:
        return question


def llm_answer_procedure_stream(question: str, context: str, prompt_template: str = None):
    default_prompt = f"""Bạn là trợ lý chatbot hành chính cấp xã/phường, trả lời thân thiện, tự nhiên, dễ hiểu như đang hướng dẫn người dân.

Hãy trả lời chỉ dựa trên thông tin có trong tài liệu bên dưới.
Không thêm quy định, thủ tục, thời hạn, lệ phí hoặc cơ quan xử lý nếu tài liệu không nêu.

Nếu tài liệu đủ thông tin, hãy trả lời trực tiếp bằng văn phong tự nhiên, rõ ràng.
Nếu tài liệu chỉ khớp một phần nhưng vẫn có thể hướng dẫn người dùng, hãy trả lời theo hướng phù hợp nhất và nêu điều kiện ngắn gọn khi cần.
Chỉ khi tài liệu hoàn toàn không liên quan mới trả lời đúng nguyên văn:
"Hiện tại hệ thống đang bổ sung thêm thông tin, để hỗ trợ anh/chị tốt hơn ạ. Anh/chị còn câu hỏi nào thắc mắc không ạ?"

=== TÀI LIỆU ===
{context}

=== CÂU HỎI ===
{question}

Yêu cầu nội dung:
- Trả lời tự nhiên, thân thiện, không quá máy móc.
- Luôn mở đầu câu trả lời là "Thưa anh/chị," và kết thúc bằng "Thân mến!"
- Ưu tiên trả lời thẳng vào ý người dùng hỏi.
- Không cần luôn mở đầu bằng “Theo tài liệu”.
- Chỉ nêu điều kiện khi thật sự cần để tránh hiểu sai.
- Nếu tài liệu có nêu hồ sơ, nơi nộp, thời gian giải quyết thì có thể tóm tắt ngắn gọn.
- Không bịa thêm thông tin ngoài tài liệu.

Yêu cầu trình bày:
- Trình bày bằng markdown đơn giản, dễ đọc trên giao diện chat.
- Với câu hỏi ngắn và câu trả lời chỉ có 1 ý chính, trả lời thành 1 đoạn ngắn tự nhiên, không cần chia mục.
- Nếu câu trả lời có từ 2 ý trở lên, hãy tách thành các đoạn ngắn; mỗi đoạn nên thể hiện 1 ý chính.
- Ưu tiên câu ngắn, rõ ý; tránh viết 1 đoạn quá dài.
- Khi có danh sách hồ sơ, giấy tờ, bước thực hiện hoặc lưu ý, hãy dùng bullet list.
- Có thể in đậm các thông tin quan trọng hoặc các nhãn ngắn như: **Hồ sơ**, **Nơi nộp**, **Hình thức nộp**, **Thời gian giải quyết**, **Lưu ý**.
- Không lạm dụng tiêu đề lớn hoặc chia quá nhiều mục nhỏ.
- Chỉ dùng bảng markdown khi người dùng đang hỏi so sánh nhiều thủ tục hoặc nhiều phương án; nếu không, không dùng bảng.
- Không dùng ký hiệu, biểu tượng hoặc trang trí không cần thiết.
- Ưu tiên ngắn gọn, rõ ý, nhìn thoáng.

Quy tắc xét duyệt hồ sơ (BẮT BUỘC TUÂN THỦ STRICTLY):
- Các mục liệt kê trong phần "Hồ sơ gồm" là điều kiện bắt buộc.
- Ký tự "/" hoặc chữ "hoặc" có nghĩa là chỉ cần 1 trong các loại giấy tờ đó.
- NẾU người dùng hỏi về việc thiếu/mất một loại giấy tờ, bạn PHẢI trả lời rõ là KHÔNG THỂ thực hiện thủ tục, TRỪ KHI họ có giấy tờ thay thế hợp lệ ghi trong tài liệu.
- Ví dụ: Tài liệu ghi "CCCD/Hộ chiếu", nếu người dùng mất CCCD, phải hướng dẫn họ dùng Hộ chiếu thay thế. Nếu không có cả hai, không thể đăng ký.
"""
    prompt = _render_prompt_template(
        prompt_template,
        default_prompt,
        question=question,
        query=question,
        context=context,
    )

    try:
        for chunk in llm_generate.stream(prompt):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
    except Exception:
        yield question
    

def llm_answer(question: str, context: str, prompt_template: str = None) -> str:
    default_prompt = f"""Bạn là trợ lý chatbot hành chính cấp xã/phường, trả lời thân thiện, tự nhiên, dễ hiểu như đang hướng dẫn người dân.

Hãy trả lời chỉ dựa trên thông tin có trong tài liệu bên dưới.

Nếu tài liệu đủ thông tin, hãy trả lời trực tiếp bằng văn phong tự nhiên, rõ ràng.
Nếu tài liệu chỉ khớp một phần nhưng vẫn có thể hướng dẫn người dùng, hãy trả lời theo hướng phù hợp nhất và nêu điều kiện ngắn gọn khi cần.
Chỉ khi tài liệu hoàn toàn không liên quan mới trả lời đúng nguyên văn:
Hiện chưa có thông tin trong hệ thống.

=== TÀI LIỆU ===
{context}

=== CÂU HỎI ===
{question}

Yêu cầu nội dung:
- Trả lời tự nhiên, thân thiện, không quá máy móc.
- Luôn mở đầu bằng "Thưa anh/chị," và kết thúc bằng "Thân mến!"
- Ưu tiên trả lời thẳng vào đúng điều người dùng hỏi.
- Không cần luôn mở đầu bằng “Theo tài liệu”.
- Chỉ nêu điều kiện khi thật sự cần để tránh hiểu sai.
- Không bịa thêm thông tin ngoài tài liệu.

Yêu cầu trình bày:
- Dùng markdown đơn giản, dễ đọc trên giao diện chat.
- Với câu hỏi ngắn và câu trả lời ngắn, viết thành 1–2 đoạn ngắn tự nhiên.
- Sau câu "Thưa anh/chị," nên xuống dòng.
- Khi có từ 2 ý rõ ràng trở lên, có thể tách thành nhiều dòng ngắn.
- Không lạm dụng tiêu đề lớn hoặc chia quá nhiều mục nhỏ.
- Không dùng ký hiệu, biểu tượng hoặc trang trí không cần thiết.
- Ưu tiên ngắn gọn, rõ ý, nhìn thoáng.
"""
    prompt = _render_prompt_template(
        prompt_template,
        default_prompt,
        question=question,
        query=question,
        context=context,
    )
    try:
        response = llm_generate.invoke(prompt)
        print("LLM response:", response.content)
        return response.content.strip()
    except:
        return question


def llm_answer_stream(question: str, context: str, prompt_template: str = None) -> str:
    default_prompt = f"""Bạn là trợ lý chatbot hành chính cấp xã/phường, trả lời thân thiện, tự nhiên, dễ hiểu như đang hướng dẫn người dân.

Hãy trả lời chỉ dựa trên thông tin có trong tài liệu bên dưới.

Nếu tài liệu đủ thông tin, hãy trả lời trực tiếp bằng văn phong tự nhiên, rõ ràng.
Nếu tài liệu chỉ khớp một phần nhưng vẫn có thể hướng dẫn người dùng, hãy trả lời theo hướng phù hợp nhất và nêu điều kiện ngắn gọn khi cần.
Chỉ khi tài liệu hoàn toàn không liên quan mới trả lời đúng nguyên văn:
"Hiện tại hệ thống đang bổ sung thêm thông tin, để hỗ trợ anh/chị tốt hơn ạ. Anh/chị còn câu hỏi nào thắc mắc không ạ?"

=== TÀI LIỆU ===
{context}

=== CÂU HỎI ===
{question}

Yêu cầu nội dung:
- Trả lời tự nhiên, thân thiện, không quá máy móc.
- Luôn mở đầu bằng "Thưa anh/chị," và kết thúc bằng "Thân mến!"
- Ưu tiên trả lời thẳng vào đúng điều người dùng hỏi.
- Không cần luôn mở đầu bằng “Theo tài liệu”.
- Chỉ nêu điều kiện khi thật sự cần để tránh hiểu sai.
- Không bịa thêm thông tin ngoài tài liệu.

Yêu cầu trình bày:
- Dùng markdown đơn giản, dễ đọc trên giao diện chat.
- Với câu hỏi ngắn và câu trả lời ngắn, viết thành 1–2 đoạn ngắn tự nhiên.
- Sau câu "Thưa anh/chị," nên xuống dòng.
- Khi có từ 2 ý rõ ràng trở lên, có thể tách thành nhiều dòng ngắn.
- Không lạm dụng tiêu đề lớn hoặc chia quá nhiều mục nhỏ.
- Không dùng ký hiệu, biểu tượng hoặc trang trí không cần thiết.
- Ưu tiên ngắn gọn, rõ ý, nhìn thoáng.
"""
    prompt = _render_prompt_template(
        prompt_template,
        default_prompt,
        question=question,
        query=question,
        context=context,
    )
    try:
        for chunk in llm_generate.stream(prompt):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
    except Exception:
        yield question