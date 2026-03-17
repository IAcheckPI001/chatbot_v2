
import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from corn import supabase
from embedding import get_embedding
from utils import normalize_text, prepare_subject_keywords, SUBJECT_KEYWORDS
from test_demo import classify_v2

load_dotenv()

PREPARED = prepare_subject_keywords(SUBJECT_KEYWORDS)

llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.0,
    model_kwargs={
        "response_format": {"type": "json_object"}
    },
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

def classify_llm(user_query: str):
    prompt = f"""Bạn là bộ trích xuất metadata thủ tục hành chính cho chatbot hành chính cấp phường.

NHIỆM VỤ
Từ câu hỏi của người dùng, trả về DUY NHẤT 1 JSON object hợp lệ theo schema:

{{
  "query_mode": "single_procedure" | "multi_procedure",
  "unit": [
    {{
      "procedure": "tên thủ tục chính đã được chuẩn hóa, ngắn gọn, ổn định; ưu tiên dùng cách gọi gần với tên thủ tục hành chính hơn là cách nói tự nhiên của người dân",
      "subject": chọn 1 trong DANH SÁCH subject hợp lệ hoặc Null,
      "procedure_action": "gia_tri_hop_le" | null,
      "special_contexts": []
    }}
  ]
}}

QUY TẮC BẮT BUỘC

1. Chỉ trả về JSON object, không giải thích, không markdown.
2. Không lặp procedure.
3. Nếu query_mode = "single_procedure" thì unit phải có đúng 1 phần tử.
4. Nếu query_mode = "multi_procedure" thì unit phải có từ 2 phần tử trở lên.
5. Không tự tạo giá trị ngoài danh sách cho trước.
6. Nếu không xác định rõ procedure_action thì trả null.
7. special_contexts phải là mảng, nếu không có thì trả [].

CÁCH XÁC ĐỊNH query_mode

- single_procedure:
  dùng khi câu hỏi chỉ có 1 nhu cầu hành chính chính, nhắc đến một thủ tục cụ thể rõ ràng, Nếu chỉ là biến thể của cùng một thủ tục (ví dụ: có yếu tố nước ngoài, mất giấy tờ, quá hạn), vẫn là single_procedure.

- multi_procedure:
  chỉ dùng khi người dùng thực sự hỏi đồng thời từ 2 thủ tục trở lên, hoặc so sánh / nối tiếp nhiều thủ tục độc lập
  
NGUYÊN TẮC QUAN TRỌNG

1. Ưu tiên xác định THỦ TỤC CHÍNH người dùng muốn làm.
2. Điều kiện, giấy tờ bị mất, bị sai, bị thiếu... không tự động làm thành multi_procedure.
3. Không suy diễn thêm thủ tục phụ nếu người dùng không hỏi trực tiếp.
4. Nếu câu hỏi có một thủ tục chính và một điều kiện để xét thủ tục đó, vẫn là single_procedure.
5. "procedure" phải là tên thủ tục chuẩn và chính xác, ví dụ:
   - "làm khai sinh" -> "đăng ký khai sinh"
   - "làm lại khai sinh" -> "đăng ký lại khai sinh" (vì nó thuộc hộ tịch)
   - "xin bản sao giấy khai sinh" -> "cấp bản sao trích lục hộ tịch"
   - "bán nhà" -> "chuyển nhượng quyền sử dụng đất"
   - "mất cccd" -> "cấp lại CCCD" (vì nó thuộc cơ quan công an)
   - "ly hôn" -> "giải quyết ly hôn" (vì ly hôn không phải là một thủ tục đăng ký hành chính)
6. procedure_action là hành động chính người dùng đang hỏi tới, không phải luôn luôn là "dang_ky_moi".
7. special_contexts chỉ được chọn trong danh sách hợp lệ bên dưới.


CÁCH XÁC ĐỊNH procedure_action

- "đăng ký lại", "làm lại" => dang_ky_lai,
- "cấp lại" => cap_lai
- "bản sao", "trích lục" => cap_ban_sao
- "cấp giấy phép" => cap_phep
- "thay đổi" => thay_doi
- "cải chính", "đính chính" => cai_chinh
- "bổ sung" => bo_sung
- "xác nhận" => xac_nhan
- "ghi vào sổ" => ghi_vao_so
- "giải quyết" => giai_quyet
- "thông báo" => thong_bao
- "hỗ trợ" => ho_tro
- "trợ cấp" => tro_cap
- "chấm dứt" => cham_dut
- "tạm ngừng" => tam_ngung
- "tiếp tục kinh doanh" => tiep_tuc
- "chấp thuận" => chap_thuan
- "thỏa thuận" => thoa_thuan
- "công bố lại" => cong_bo_lai
- "công bố" => cong_bo
- "công nhận" => cong_nhan
- "thanh toán" => thanh_toan
- "chuyển trường" => chuyen_truong
- "tuyển sinh" => tuyen_sinh
- "xét tuyển" => xet_tuyen
- "xét cấp" => xet_cap
- "phê duyệt" => phe_duyet
- "can thiệp" => can_thiep
- "thu hồi" => thu_hoi
- "giao" => giao
- "hủy bỏ" => huy_bo
- "cấm tiếp xúc" => cam_tiep_xuc
- nếu chỉ hỏi thủ tục cơ bản, mặc định là dang_ky_moi khi phù hợp
- nếu không rõ thì null

DANH SÁCH special_contexts HỢP LỆ
- yeu_to_nuoc_ngoai
- khu_vuc_bien_gioi
- da_co_ho_so_giay_to_ca_nhan
- uy_quyen
- chon_quoc_tich
- qua_han_dang_ky
- mat_so_ho_tich_va_ban_chinh

CÁCH XÁC ĐỊNH special_contexts

- có "yếu tố nước ngoài", "người nước ngoài" => yeu_to_nuoc_ngoai
- có "khu vực biên giới", "xã biên giới" => khu_vuc_bien_gioi
- có "đã có hồ sơ", "đã có giấy tờ cá nhân" => da_co_ho_so_giay_to_ca_nhan
- có "ủy quyền" => uy_quyen
- có "chọn quốc tịch" => chon_quoc_tich
- có "quá hạn", "trễ hạn" => qua_han_dang_ky
- có "mất sổ hộ tịch", "mất bản chính" trong ngữ cảnh đăng ký lại => mat_so_ho_tich_va_ban_chinh

DANH SÁCH subject HỢP LỆ
- tu_phap_ho_tich (khai sinh, tạm trú, tạm vắng, giám hộ, nhận cha mẹ con, nuôi con nuôi)
- doanh_nghiep (đăng ký kinh doanh, hộ kinh doanh)
- giao_thong_van_tai
- dat_dai
- xay_dung_nha_o
- dau_tu
- giao_duc_dao_tao
- lao_dong_viec_lam (hợp đồng lao động, an toàn lao động, bảo hộ lao động, hòa giải viên)
- bao_hiem_an_sinh (BHXH, BHYT, hộ nghèo, trợ cấp xã hội, nhà ở xã hội, người vô gia cư, mai táng phí)
- y_te (an toàn thực phẩm, trang thiết bị y tế, an toàn thực phẩm, dịch bệnh)
- tai_nguyen_moi_truong
- cong_thuong (rượu, thuốc lá)
- van_hoa_the_thao_du_lich
- tai_chinh_thue_phi
- khoa_hoc_cong_nghe
- thong_tin_truyen_thong
- nong_nghiep

Ví dụ:

Câu hỏi: "Mất giấy khai sinh có đăng ký kết hôn được không"
{{
    "query_mode": "multi_procedure",
    "unit": [
        {{
            'procedure': 'đăng ký kết hôn',
            'subject': 'tu_phap_ho_tich',
            'procedure_action': 'dang_ky_moi',
            'special_contexts': []
        }}
        ,{{
            'procedure': 'đăng ký lại khai sinh',
            'subject': 'tu_phap_ho_tich',
            'procedure_action': 'dang_ky_lai',
            'special_contexts': []
        }}
    ]
}}

Câu hỏi: "tôi muốn mở quán ăn nhỏ thì có cần xin giấy phép gì không?"
{{
    "query_mode": "single_procedure",
    "unit": [
        {{
            'procedure': 'đăng ký hộ kinh doanh',
            'subject': 'doanh_nghiep',
            'procedure_action': 'dang_ky_moi',
            'special_contexts': []
        }}
    ]
}}

Câu hỏi: "con tôi 6 tuổi vào lớp 1 thì hồ sơ thế nào?"
{{
  "query_mode": "single_procedure",
  "unit": [
    {{
      "procedure": "đăng ký tuyển sinh lớp 1",
      "subject": "giao_duc_dao_tao",
      "procedure_action": "tuyen_sinh",
      "special_contexts": []
    }}
  ],
}}

Câu hỏi: "làm khai sinh bình thường và khai sinh có người nước ngoài thì khác nhau thế nào"
{{
    'query_mode': 'multi_procedure', 
    'unit': [
        {{
            'procedure': 'đăng ký khai sinh', 
            'subject': 'tu_phap_ho_tich',
            'procedure_action': 'dang_ky_moi', 
            'special_contexts': []
        }}, 
        {{
            'procedure': 'đăng ký khai sinh có yếu tố nước ngoài', 
            'subject': 'tu_phap_ho_tich',
            'procedure_action': 'dang_ky_moi', 
            'special_contexts': ['yeu_to_nuoc_ngoai']
        }}], 
}}
QUERY: {user_query}
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        print("\nLLM xác đinh:", data)
        return data

    except Exception as e:
        print("LLM classify error:", e)
        return None



# def classify_llm(user_query: str):
#     prompt = f"""Bạn là bộ trích xuất metadata cho câu hỏi về THỦ TỤC HÀNH CHÍNH của chatbot hành chính cấp phường.

# NHIỆM VỤ
# Phân tích câu hỏi của người dùng và trả về DUY NHẤT 1 JSON object hợp lệ theo schema sau:

# {{
#   "query_mode": "single_procedure" | "multi_procedure",
#   "unit": [
#     {{
#       "procedure": "tên thủ tục chính đã được chuẩn hóa, ngắn gọn, ổn định",
#       "subject": "1 giá trị hợp lệ trong danh sách subject",
#       "procedure_action": "gia_tri_hop_le" | null,
#       "special_contexts": []
#     }}
#   ]
# }}

# QUY TẮC BẮT BUỘC

# 1. Chỉ trả về JSON object, không giải thích, không markdown.
# 2. Không trả thêm text ngoài JSON.
# 3. Không lặp procedure trong unit.
# 4. Nếu query_mode = "single_procedure":
#    - unit phải có đúng 1 phần tử
# 5. Nếu query_mode = "multi_procedure":
#    - unit phải có từ 2 phần tử trở lên
# 6. Không suy diễn thêm procedure phụ nếu người dùng không hỏi trực tiếp.
# 7. Không tự tạo giá trị ngoài danh sách cho trước.
# 8. Nếu không xác định rõ procedure_action thì trả null.
# 9. special_contexts phải luôn là mảng; nếu không có thì trả [] và phải liên quan trực tiếp đến procedure.

# --------------------------------
# II. CÁCH XÁC ĐỊNH query_mode
# --------------------------------

# - single_procedure:
#   dùng khi câu hỏi chỉ có 1 nhu cầu hành chính chính, nhắc đến một thủ tục cụ thể rõ ràng, Nếu chỉ là biến thể của cùng một thủ tục (ví dụ: có yếu tố nước ngoài, mất giấy tờ, quá hạn), vẫn là single_procedure.

# - multi_procedure:
#   chỉ dùng khi người dùng thực sự hỏi đồng thời từ 2 thủ tục trở lên, hoặc so sánh / nối tiếp nhiều thủ tục độc lập

# --------------------------------
# III. NGUYÊN TẮC XÁC ĐỊNH procedure
# --------------------------------

# 1. Ưu tiên xác định THỦ TỤC CHÍNH mà người dùng đang muốn thực hiện.
# 2. "procedure" phải là tên thủ tục chuẩn hóa, ngắn gọn, ổn định, gần với tên thủ tục hành chính.
# 3. Ưu tiên chuẩn hóa về tên thủ tục chính thức hơn là giữ nguyên cách nói dân dã.
# 4. Không suy diễn thêm thủ tục phụ nếu người dùng không hỏi trực tiếp.

# Ví dụ chuẩn hóa:
# - "con tôi 6 tuổi vào lớp 1 thì cần giấy tờ gì?" -> "tuyển sinh tiểu học"
# - "làm lại khai sinh" -> "đăng ký lại khai sinh"
# - "xin bản sao giấy khai sinh" -> "cấp bản sao trích lục hộ tịch"
# - "làm giấy độc thân" -> "cấp giấy xác nhận tình trạng hôn nhân"
# - "bán nhà" -> "chuyển nhượng quyền sử dụng đất"
# - "mở quán ăn nhỏ" -> "đăng ký hộ kinh doanh"
# - "xin giấy phép bán rượu" -> "cấp giấy phép kinh doanh rượu"
# - "mất cccd" -> "cấp lại CCCD"
# - "ly hôn" -> "giải quyết ly hôn"

# --------------------------------
# IV. CÁCH XÁC ĐỊNH procedure_action
# --------------------------------

# - "đăng ký lại", "làm lại" => dang_ky_lai,
# - "cấp lại" => cap_lai
# - "bản sao", "trích lục" => cap_ban_sao
# - "cấp giấy phép" => cap_phep
# - "thay đổi" => thay_doi
# - "cải chính", "đính chính" => cai_chinh
# - "bổ sung" => bo_sung
# - "xác nhận" => xac_nhan
# - "ghi vào sổ" => ghi_vao_so
# - "giải quyết" => giai_quyet
# - "thông báo" => thong_bao
# - "hỗ trợ" => ho_tro
# - "trợ cấp" => tro_cap
# - "chấm dứt" => cham_dut
# - "tạm ngừng" => tam_ngung
# - "tiếp tục kinh doanh" => tiep_tuc
# - "chấp thuận" => chap_thuan
# - "thỏa thuận" => thoa_thuan
# - "công bố lại" => cong_bo_lai
# - "công bố" => cong_bo
# - "công nhận" => cong_nhan
# - "chuyển trường" => chuyen_truong
# - "tuyển sinh" => tuyen_sinh
# - "xét tuyển" => xet_tuyen
# - "xét cấp" => xet_cap
# - "phê duyệt" => phe_duyet
# - "can thiệp" => can_thiep
# - "thu hồi" => thu_hoi
# - "giao tài sản" => giao
# - "hủy bỏ" => huy_bo
# - "cấm tiếp xúc" => cam_tiep_xuc
# - nếu chỉ hỏi thủ tục cơ bản, mặc định là dang_ky_moi khi phù hợp
# - nếu không rõ thì null

# --------------------------------
# V. DANH SÁCH special_contexts HỢP LỆ
# --------------------------------

# - yeu_to_nuoc_ngoai
# - khu_vuc_bien_gioi
# - da_co_ho_so_giay_to_ca_nhan
# - uy_quyen
# - chon_quoc_tich
# - qua_han_dang_ky
# - mat_so_ho_tich_va_ban_chinh

# CÁCH XÁC ĐỊNH:
# - có "yếu tố nước ngoài", "người nước ngoài" -> yeu_to_nuoc_ngoai
# - có "khu vực biên giới", "xã biên giới" -> khu_vuc_bien_gioi
# - có "đã có hồ sơ", "đã có giấy tờ cá nhân" -> da_co_ho_so_giay_to_ca_nhan
# - có "ủy quyền" -> uy_quyen
# - có "chọn quốc tịch" -> chon_quoc_tich
# - có "quá hạn", "trễ hạn" -> qua_han_dang_ky
# - có "mất sổ hộ tịch", "mất bản chính" trong ngữ cảnh đăng ký lại -> mat_so_ho_tich_va_ban_chinh

# --------------------------------
# VI. DANH SÁCH subject HỢP LỆ
# --------------------------------

# - tu_phap_ho_tich (khai sinh, khai tử, kết hôn, chứng thực, tạm trú, tạm vắng, giám hộ, nhận cha mẹ con, nuôi con nuôi)
# - doanh_nghiep (đăng ký kinh doanh, hộ kinh doanh)
# - giao_thong_van_tai (đăng ký phương tiện, đăng kiểm, giấy phép lái xe, vận tải, bến bãi, hàng không)
# - dat_dai (sổ đỏ, quyền sử dụng đất)
# - xay_dung_nha_o (giấy phép xây dựng, sửa chữa, cải tạo, hoàn công, nhà ở, chung cư, quy hoạch xây dựng)
# - dau_tu (chủ trương đầu tư, giấy chứng nhận đăng ký đầu tư, ưu đãi đầu tư, dự án đầu tư)
# - giao_duc_dao_tao (cơ sở giáo dục, hoạt động giáo dục, văn bằng, chứng chỉ, tuyển sinh, chuyển trường, học bổng)
# - lao_dong_viec_lam (hợp đồng lao động, tranh chấp lao động, an toàn lao động, việc làm, đào tạo nghề)
# - bao_hiem_an_sinh (BHXH, BHYT, hộ nghèo, trợ cấp xã hội, nhà ở xã hội, người vô gia cư)
# - y_te (an toàn thực phẩm, trang thiết bị y tế, an toàn thực phẩm, dịch bệnh)
# - tai_nguyen_moi_truong (môi trường, tài nguyên nước, khoáng sản, biến đổi khí hậu, thiên tai)
# - cong_thuong (rượu, thuốc lá, điện lực, hóa chất, xúc tiến thương mại, quản lý thị trường, xuất nhập khẩu)
# - van_hoa_the_thao_du_lich (văn hóa, nghệ thuật biểu diễn, quảng cáo, xuất bản, thể thao, du lịch)
# - tai_chinh_thue_phi (thuế, phí, lệ phí, hải quan, ngân sách, tài sản công)
# - khoa_hoc_cong_nghe (khoa học công nghệ, sở hữu trí tuệ, chuyển giao công nghệ)
# - thong_tin_truyen_thong (báo chí, phát thanh, truyền hình)
# - nong_nghiep (trồng trọt, chăn nuôi)

# --------------------------------
# VII. NGUYÊN TẮC ƯU TIÊN KHI MƠ HỒ
# --------------------------------

# 1. Ưu tiên thủ tục trung tâm mà người dùng muốn làm nhất.
# 2. Không thêm thủ tục phụ chỉ để “hỗ trợ trả lời”.
# 3. Nếu không chắc chắn procedure_action thì để null.
# 4. Nếu không chắc special_contexts thì để [].
# 5. Chỉ dùng multi_procedure khi thật sự có nhiều thủ tục độc lập được hỏi trực tiếp.

# --------------------------------
# VIII. VÍ DỤ
# --------------------------------

# Câu hỏi: "mở quán ăn nhỏ thì có cần đăng ký gì không"
# {{
#   "query_mode": "single_procedure",
#   "unit": [
#     {{
#       "procedure": "đăng ký hộ kinh doanh",
#       "subject": "doanh_nghiep",
#       "procedure_action": "dang_ky_moi",
#       "special_contexts": []
#     }}
#   ]
# }}

# Câu hỏi: "Mình đổi CCCD rồi thì sổ đỏ có cần đổi theo không?"
# {{
#   "query_mode": "single_procedure",
#   "unit": [
#     {{
#       "procedure": "đăng ký biến động đất đai",
#       "subject": "dat_dai",
#       "procedure_action": "thay_doi",
#       "special_contexts": []
#     }}
#   ]
# }}

# Câu hỏi: "khai sinh thường và khai sinh có yếu tố nước ngoài khác nhau thế nào"
# {{
#   "query_mode": "multi_procedure",
#   "unit": [
#     {{
#       "procedure": "đăng ký khai sinh",
#       "subject": "tu_phap_ho_tich",
#       "procedure_action": "dang_ky_moi",
#       "special_contexts": []
#     }},
#     {{
#       "procedure": "đăng ký khai sinh",
#       "subject": "tu_phap_ho_tich",
#       "procedure_action": "dang_ky_moi",
#       "special_contexts": ["yeu_to_nuoc_ngoai"]
#     }}
#   ]
# }}

# Câu hỏi: "mất giấy khai sinh có đăng ký kết hôn được không"
# {{
#   "query_mode": "single_procedure",
#   "unit": [
#     {{
#       "procedure": "đăng ký kết hôn",
#       "subject": "tu_phap_ho_tich",
#       "procedure_action": "dang_ky_moi",
#       "special_contexts": []
#     }}
#   ]
# }}

# QUERY: {user_query}
# """
#     try:
#         response = llm.invoke(prompt)
#         raw = response.content.strip()

#         data = json.loads(raw)

#         print("\nLLM xác đinh:", data)
#         return data

#     except Exception as e:
#         print("LLM classify error:", e)
#         return None



def classify_with_tong_quan(query: str):
#     prompt = f"""Bạn là bộ tách ý hỏi và gán subject cho chatbot hành chính cấp xã/phường.

# NHIỆM VỤ
# - Xác định câu hỏi có 1 ý hay nhiều ý.
# - Tách thành các ý nhỏ, ngắn gọn, đầy đủ nghĩa.
# - Gán đúng 1 subject cho từng ý.

# SUBJECT HỢP LỆ
# - gioi_thieu_dia_phuong (giới )
# - lich_su_hanh_chinh
# - dia_ly (vị trí, địa chỉ, địa lý, tiếp giáp, nằm ở đâu, thuộc quận nào)
# - thong_ke (chỉ dùng cho số liệu thống kê chung của địa phương như dân số, diện tích, số hộ, kinh tế - xã hội.)
# - co_cau_to_chuc (cơ cấu tổ chức, bộ máy, các phòng ban, bộ phận chuyên môn, đơn vị trực thuộc của UBND xã/phường; quan hệ thuộc đơn vị nào, gồm những bộ phận nào, được tổ chức ra sao.)
# - don_vi_khu_pho_ap (câu hỏi về khu phố, ấp, tổ dân phố, tổ nhân dân)
# - giao_thong
# - lich_lam_viec
# - thong_tin_lien_he (hotline, số điện thoại, email, website của UBND)

# QUY TẮC
# - Nếu không xác định chắc chắn subject nào thì trả subject = null.
# - Nếu chỉ có 1 ý chính thì vẫn trả về mảng units gồm 1 phần tử.
# - Nếu có nhiều ý, tách thành nhiều units.
# - Mỗi unit phải ngắn gọn nhưng đủ nghĩa.
# - Không giải thích.
# - Chỉ trả về JSON hợp lệ.

# FORMAT
# {{
#   "query_mode": "single_intent" | "multi_intent" | None,
#   "units": [
#     {{"text": "...", "subject": "..."}}
#   ]
# }}

# VÍ DỤ

# Query: ngày hôm nay có phải ngày bầu cử không

# {{
#     "query_mode": "single_intent", 
#     "units": [
#      {{"text": "ngày hôm nay có phải ngày bầu cử không", "subject": None}}
#     ]
# }}

# Câu hỏi: "địa chỉ ubnd và đường dây nóng"
# {{
#   "query_mode": "multi_intent",
#   "units": [
#     {{"text": "địa chỉ ubnd", "subject": "dia_ly"}},
#     {{"text": "đường dây nóng của ubnd", "subject": "thong_tin_lien_he"}}
#   ]
# }}

# Câu hỏi: "gioi thieu ngan gon ve xa ba diem"
# {{
#   "query_mode": "single_intent",
#   "units": [
#     {{"text": "giới thiệu ngắn gọn về xã Ba Điểm", "subject": "gioi_thieu_dia_phuong"}}
#   ]
# }}

# Câu hỏi:
# "{query}"
# """

# def classify_with_tong_quan(query: str):
    prompt = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp xã/phường.

NHIỆM VỤ
Xác định subject của câu hỏi.

SUBJECT (chỉ chọn 1):

- gioi_thieu_dia_phuong
- lich_su_hanh_chinh
- dia_ly (vị trí, địa lý, tiếp giáp, nằm ở đâu, thuộc quận nào)
- thong_ke (chỉ dùng cho số liệu thống kê chung của địa phương như dân số, diện tích, số hộ, kinh tế - xã hội)
- co_cau_to_chuc (cơ cấu tổ chức, bộ máy, các phòng ban, bộ phận chuyên môn, đơn vị trực thuộc của UBND xã/phường; quan hệ thuộc đơn vị nào, gồm những bộ phận nào, được tổ chức ra sao.)
- giao_thong
- lich_lam_viec
- thong_tin_lien_he (địa chỉ của xã/phường, hotline, số điện thoại, email, website của UBND)

Ví dụ:
Câu hỏi: "UBND xã Bà Điểm có những bộ phận nào?"
{{
  "subject": "co_cau_to_chuc"
}}

Câu hỏi: "địa chỉ ubnd, xã nằm ở đâu"
{{
  "subject": "thong_tin_lien_he"
}}


---

QUY TẮC

- Không giải thích
- Không tạo giá trị mới
- Trả về JSON

FORMAT

{{
  "subject": ""
}}

Câu hỏi:
"{query}"
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)
        subject = data.get("subject") if data.get("subject") != "" else None
        return subject

    except Exception as e:
        print("LLM classify error:", e)
        return None



def classify_with_phan_anh(query: str):
    prompt = f"""Bạn là bộ phân loại câu hỏi cho chatbot hành chính cấp xã/phường.

NHIỆM VỤ
Xác định xem câu hỏi có thuộc nhóm phản ánh/kiến nghị/khiếu nại/tố cáo hay không.
Nếu có, xác định đúng 1 subject phù hợp nhất.

SUBJECT HỢP LỆ
- ha_tang
- moi_truong
- an_ninh_trat_tu
- do_thi
- giao_thong
- khieu_nai_to_cao

ĐỊNH NGHĨA NGẮN GỌN

- ha_tang: điện, nước, cống thoát nước, đèn đường, đường hư, ngập nước, hạ tầng công cộng hư hỏng
- moi_truong: rác thải, ô nhiễm, mùi hôi, tiếng ồn môi trường, nước thải, vệ sinh môi trường
- an_ninh_trat_tu: gây rối, đánh nhau, cờ bạc, trộm cắp, tụ tập mất trật tự, mất an ninh khu vực
- do_thi: lấn chiếm vỉa hè, xây dựng trái phép, quảng cáo sai quy định, mỹ quan đô thị, trật tự đô thị
- giao_thong: kẹt xe, đậu xe sai quy định, biển báo, tín hiệu giao thông, tai nạn, cản trở lưu thông
- khieu_nai_to_cao: khiếu nại, tố cáo, phản ánh về cán bộ, công chức, cơ quan nhà nước, dịch vụ công, tham nhũng, tiêu cực, hành vi vi phạm pháp luật trong thực thi công vụ

QUY TẮC PHÂN LOẠI

1. Chỉ chọn subject nếu câu hỏi thực sự là phản ánh, kiến nghị, khiếu nại, tố cáo hoặc báo sự việc cần cơ quan xử lý.
2. Nếu câu hỏi là hỏi thông tin, hỏi thủ tục, hỏi liên hệ, hỏi giờ làm việc, hỏi cán bộ là ai, thì không thuộc nhóm này.
3. Nếu câu hỏi có nhiều vấn đề, chọn subject của vấn đề chính mà người dùng muốn cơ quan xử lý nhất.
4. Nếu câu hỏi nhắm vào cán bộ, công chức, cơ quan nhà nước, dịch vụ công, hành vi nhũng nhiễu, tham nhũng, chậm trễ, tiêu cực, thì ưu tiên khieu_nai_to_cao.
5. Nếu câu hỏi phản ánh hành vi ngoài xã hội như đánh nhau, cờ bạc, gây rối, trộm cắp, tụ tập mất trật tự thì ưu tiên an_ninh_trat_tu.
6. Nếu câu hỏi phản ánh hiện trạng vật lý của hạ tầng như cống nghẹt, đèn hỏng, đường hư, ngập nước, thì ưu tiên ha_tang.
7. Nếu câu hỏi phản ánh rác, mùi hôi, ô nhiễm, nước thải, vệ sinh, thì ưu tiên moi_truong.
8. Nếu câu hỏi phản ánh lấn chiếm vỉa hè, xây dựng trái phép, quảng cáo sai quy định, mỹ quan đô thị, thì ưu tiên do_thi.
9. Nếu câu hỏi phản ánh đậu xe sai quy định, ùn tắc, biển báo, tín hiệu giao thông, cản trở lưu thông, thì ưu tiên giao_thong.
10. Nếu không thuộc nhóm phản ánh/kiến nghị/khiếu nại/tố cáo, trả subject = null.

TRẢ VỀ DUY NHẤT JSON:
{{
  "subject": "ha_tang|moi_truong|an_ninh_trat_tu|do_thi|giao_thong|khieu_nai_to_cao"|null
}}

Ví dụ:
Câu hỏi: "Đèn đường trước nhà tôi hỏng mấy ngày rồi chưa ai sửa"
{{
    "subject": "ha_tang"
}}

Câu hỏi: "hàng xóm hát karaoke ồn quá, nên báo công an hay ủy ban"
{{
    "subject": "an_ninh_trat_tu"
}}

Câu hỏi: "Có người xây nhà lấn sang hẻm"
{{"subject": "do_thi"}}

Câu hỏi: "Xe tải đậu chắn hết đường đi"
{{"subject": "giao_thong"}}

Câu hỏi: "bạn tôi bị đuổi ra khỏi nhà giờ thành vô gia cư, giờ cần liên ai để giúp"
{{
    "subject": null
}}

Câu hỏi:
"{query}"
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        print("\nLLM xác đinh:", data)
        subject = data.get("subject") if data.get("subject") == "" else None
        return subject

    except Exception as e:
        print("LLM classify error:", e)
        return None

def classify_with_tuong_tac(query: str):
    prompt = f"""Bạn là bộ phân loại tương tác ngắn cho chatbot hành chính cấp xã/phường.

NHIỆM VỤ
Xác định câu người dùng có phải tương tác ngắn/phụ trợ hay không.
Nếu có, chọn đúng 1 subject.
Nếu không, trả về null.

SUBJECT HỢP LỆ
- chao_hoi
- cam_on_tam_biet
- phan_nan_buc_xuc
- xuc_pham_vi_pham

QUY ƯỚC
- chao_hoi: chào, mở lời xã giao
- cam_on_tam_biet: cảm ơn, tạm biệt, kết thúc
- phan_nan_buc_xuc: phàn nàn, khó chịu, chê câu trả lời
- xuc_pham_vi_pham: chửi bới, xúc phạm, đe dọa

LUẬT QUAN TRỌNG
1. Nếu là câu hỏi nghiệp vụ/thủ tục/thông tin hành chính chính thì trả về null.
2. Nếu vừa có xã giao vừa có câu hỏi nghiệp vụ thì trả về null.
3. Ưu tiên nhãn theo thứ tự:
   xuc_pham_vi_pham > phan_nan_buc_xuc > cam_on_tam_biet > chao_hoi

TRẢ VỀ DUY NHẤT JSON:
{{
  "subject": "chao_hoi" | "cam_on_tam_biet" | "phan_nan_buc_xuc" | "xuc_pham_vi_pham" | null
}}

VÍ DỤ
"chào bạn" -> {{"subject": "chao_hoi"}}
"cảm ơn nhé" -> {{"subject": "cam_on_tam_biet"}}
"trả lời khó hiểu vậy" -> {{"subject": "phan_nan_buc_xuc"}}
"mày ngu quá" -> {{"subject": "xuc_pham_vi_pham"}}
"thủ tục khai sinh ở đâu" -> {{"subject": null}}

Câu hỏi:
"{query}"
"""
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        data = json.loads(raw)

        print("\nLLM xác đinh:", data)

        subject = data.get("subject") if data.get("subject") == "" else None
        return subject

    except Exception as e:
        print("LLM classify error:", e)
        return None



def export_metadata_filter_chunk(category, query):
    meta = classify_llm(query)

    if not meta or not isinstance(meta, dict):
        return []

    query_mode = meta.get("query_mode")
    # print(f"Query mode: {query_mode}")

    procedures = meta.get("unit") or []
    if not procedures:
        return []

    chunk_response = []

    if query_mode == "single_procedure":
        # print(f"Thủ tục chính: {procedures[0]['procedure']} - {procedures[0]['subject']}") 
        procedure_action = procedures[0].get("procedure_action")
        special_contexts = procedures[0].get("special_contexts") or []
        response = supabase.rpc(
            "search_documents_full_hybrid_v7",
            {
                "p_query_format": normalize_text(query),
                "p_query_embedding": get_embedding(procedures[0]['procedure']),
                "p_tenant": "xa_ba_diem",
                "p_category": category,
                "p_subject": procedures[0]['subject'],
                "p_procedure": normalize_text(procedures[0]['procedure']),
                "p_procedure_action": procedure_action,
                "p_special_contexts": special_contexts,
                "p_limit": 4
            }
        ).execute()


        chunks = response.data or []
        chunk_response = chunks
        # print(chunk_response[0]["text_content"]) if chunk_response else print("Không tìm thấy đoạn văn bản nào liên quan.")
        # print(f"=> Subject:                   {procedure_action}")
        # print(f"=> Procedure_action:          {special_contexts}")
        # print(f"Tìm thấy {len(chunk_response)} đoạn văn bản liên quan:")
        # print(chunk_response[0]) if chunk_response else print("Không tìm thấy đoạn văn bản nào liên quan.") 
    else:
        # print("Các thủ tục chính:")
        for proc in procedures:
            # print(f"Thủ tục chính: {proc['procedure']} - {proc['subject']}")

            response = supabase.rpc(
                "search_documents_full_hybrid_v7",
                {
                    "p_query_format": normalize_text(proc['procedure']),
                    "p_query_embedding": get_embedding(proc['procedure']),
                    "p_tenant": "xa_ba_diem",
                    "p_category": category,
                    "p_subject": proc['subject'],
                    "p_procedure": normalize_text(proc['procedure']),
                    "p_procedure_action": proc['procedure_action'],
                    "p_special_contexts": proc['special_contexts'],
                    "p_limit": 1
                }
            ).execute()


            chunks = response.data or []

            if chunks:
                chunk_response.append(chunks[0])
            # print(chunks[0]["text_content"]) if chunks else print("Không tìm thấy đoạn văn bản nào liên quan.")
            # print(f"=> Subject:                   {proc['procedure_action']}")
            # print(f"=> Procedure_action:          {proc['special_contexts']}")
            # print(chunk_response[0]) if chunk_response else print("Không tìm thấy đoạn văn bản nào liên quan.")
        
    return chunk_response

# from model import llm_answer

if __name__ == "__main__":
    TEST_THONG_TIN_TONG_QUAN = [
        # "khu phố nào có di tích vườn cau đỏ",
        # "vườn cau đỏ là khu di tích hả",
        # "vườn cau đỏ ở đâu",
        "bộ phận công an xã thuộc ấp bắc lân à?",
    ]
    for query in TEST_THONG_TIN_TONG_QUAN:
        print("\n====================\n")
        print(f"Query: {query}")
        data = classify_with_tong_quan(query)
        subject = data.get("subject")
        # units = data.get("units") or []

        # for i, unit in enumerate(units):

        #     subject = unit.get("subject")

        #     if subject is None:
        #         print(f"Unit {i+1}: {unit.get('text')} - Subject: None")
        #         continue

        #     print(f"Unit {i+1}: {unit.get('text')} - Subject: {subject}")
            


                


        
        
    #     print("\n====================\n")
    #     print("Câu hỏi:", query)
    #     chunks = export_metadata_filter_chunk("thu_tuc_hanh_chinh", query)
    #     context = "\n\n".join(
    #         f"### Chunk {i+1}\n{chunk['text_content']}"
    #         for i, chunk in enumerate(chunks[:5])
    #     )
        

    #     answer = llm_answer(query, context)
    #     print("\n====================\n")
    #     print("Final answer:", answer)
#         meta = classify_llm(query)

#         query_mode = meta.get("query_mode")
#         print(f"Query mode: {query_mode}")

#         procedures = meta["unit"]
#         procedure_action = meta["procedure_action"]
#         special_contexts = meta["special_contexts"]

#         normalized_query = normalize_text(query)

#         res = classify_v2(normalized_query, PREPARED)
#         category, subject = res["category"], res["subject"]

#         print(f"Phân loại chủ đề: {category} - {subject}")

#         if query_mode == "single_procedure":
#             print(f"Thủ tục chính: {procedures[0]['procedure']} - {procedures[0]['subject']}")
#             response = supabase.rpc(
#                 "search_documents_full_hybrid_v7",
#                 {
#                     "p_query_format": normalized_query,
#                     "p_query_embedding": get_embedding(procedures[0]['procedure']),
#                     "p_tenant": "xa_ba_diem",
#                     "p_category": category,
#                     "p_subject": procedures[0]['subject'] if procedures[0]['subject'] != subject else subject,
#                     "p_procedure": normalize_text(procedures[0]['procedure']),
#                     "p_procedure_action": procedure_action,
#                     "p_special_contexts": special_contexts,
#                     "p_limit": 5
#                 }
#             ).execute()


#             chunks = response.data or []
#             print(f"Tìm thấy {len(chunks)} đoạn văn bản liên quan:")
#             print(chunks[0]) if chunks else print("Không tìm thấy đoạn văn bản nào liên quan.") 
#         else:
#             print("Các thủ tục chính:")
#             for proc in procedures:
#                 print(f"Thủ tục chính: {proc['procedure']} - {proc['subject']}")

#                 response = supabase.rpc(
#                     "search_documents_full_hybrid_v7",
#                     {
#                         "p_query_format": normalize_text(proc['procedure']),
#                         "p_query_embedding": get_embedding(proc['procedure']),
#                         "p_tenant": "xa_ba_diem",
#                         "p_category": category,
#                         "p_subject": proc['subject'],
#                         "p_procedure": normalize_text(proc['procedure']),
#                         "p_procedure_action": procedure_action,
#                         "p_special_contexts": special_contexts,
#                         "p_limit": 5
#                     }
#                 ).execute()


#                 chunks = response.data or []
#                 print(chunks[0]) if chunks else print("Không tìm thấy đoạn văn bản nào liên quan.")
