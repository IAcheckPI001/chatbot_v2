
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
      "procedure": "tên thủ tục hành chính",
      "subject": chọn 1 trong DANH SÁCH subject hợp lệ
    }}
  ],
  "procedure_action": "gia_tri_hop_le" | null,
  "special_contexts": []
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
  dùng khi câu hỏi chỉ có 1 nhu cầu hành chính chính, dù có thêm điều kiện, giấy tờ, tình huống đi kèm.

- multi_procedure:
  chỉ dùng khi người dùng thực sự hỏi đồng thời từ 2 thủ tục trở lên, hoặc so sánh / nối tiếp nhiều thủ tục độc lập.

NGUYÊN TẮC QUAN TRỌNG

1. Ưu tiên xác định THỦ TỤC CHÍNH người dùng muốn làm.
2. Điều kiện, giấy tờ bị mất, bị sai, bị thiếu... không tự động làm thành multi_procedure.
3. Không suy diễn thêm thủ tục phụ nếu người dùng không hỏi trực tiếp.
4. Nếu câu hỏi có một thủ tục chính và một điều kiện để xét thủ tục đó, vẫn là single_procedure.
5. "procedure" phải là tên thủ tục chuẩn và chính xác, ví dụ:
   - "làm khai sinh" -> "đăng ký khai sinh"
   - "làm lại khai sinh" -> "đăng ký lại khai sinh"
   - "xin bản sao giấy khai sinh" -> "cấp bản sao trích lục hộ tịch"
   - "bán nhà" -> "chuyển nhượng quyền sử dụng đất"
6. procedure_action là hành động chính người dùng đang hỏi tới, không phải luôn luôn là "dang_ky_moi".
7. special_contexts chỉ được chọn trong danh sách hợp lệ bên dưới.
CÁCH XÁC ĐỊNH procedure_action

- "đăng ký lại", "làm lại" => dang_ky_lai,
- "cấp lại" => cap_lai
- "bản sao", "trích lục" => cap_ban_sao
- "cấp giấy phép" => cap_phep
- "thay đổi" => thay_doi
- "cải chính" => cai_chinh
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
- lao_dong_viec_lam
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
    "query_mode": "single_procedure",
    "unit": [
        {{
            'procedure': 'đăng ký kết hôn',
            'subject': 'tu_phap_ho_tich'
        }}
    ]
    'procedure_action': 'dang_ky_moi',
    'special_contexts': []
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



if __name__ == "__main__":
    TEST_BAO_HIEM_AN_SINH = [
        # "dăng ký khai sinh",
        # "con toi 6 tuổi vào lớp 1 thì hồ sơ thế nào?",
        # "Đậu và Khoai Tây là 2 người đồng tính muốn kết hôn thì cần giấy tờ gì",
        # "Mất giấy khai sinh có đăng ký kết hôn được không",
        # "Thủ tục thôi làm hòa giải viên cấp phường",
        # "con tôi vào lớp 1 thì đăng ký nộp hồ sơ ở đâu",
        "con tôi người nước ngoài thì làm khai sinh làm sao",
        "con tôi người nước ngoài tại biên giới thì làm khai sinh làm sao",
        # "mở quán rượu cần những giấy tờ gì"
    ]
    for query in TEST_BAO_HIEM_AN_SINH:
        meta = classify_llm(query)

        query_mode = meta.get("query_mode")
        print(f"Query mode: {query_mode}")

        procedures = meta["unit"]
        procedure_action = meta["procedure_action"]
        special_contexts = meta["special_contexts"]

        normalized_query = normalize_text(query)

        res = classify_v2(normalized_query, PREPARED)
        category, subject = res["category"], res["subject"]

        print(f"Phân loại chủ đề: {category} - {subject}")

        if query_mode == "single_procedure":
            print(f"Thủ tục chính: {procedures[0]['procedure']} - {procedures[0]['subject']}")
            response = supabase.rpc(
                "search_documents_full_hybrid_v6_have_meta",
                {
                    "p_query_format": normalized_query,
                    "p_query_embedding": get_embedding(procedures[0]['procedure']),
                    "p_tenant": "xa_ba_diem",
                    "p_category": category,
                    "p_subject": procedures[0]['subject'],
                    "p_procedure_action": procedure_action,
                    "p_special_contexts": special_contexts,
                    "p_limit": 5
                }
            ).execute()


            chunks = response.data or []
            print(f"Tìm thấy {len(chunks)} đoạn văn bản liên quan:")
            print(chunks[0])
        else:
            print("Các thủ tục chính:")
            for proc in procedures:
                print(f"Thủ tục chính: {proc['procedure']} - {proc['subject']}")

                response = supabase.rpc(
                    "search_documents_full_hybrid_v6_have_meta",
                    {
                        "p_query_format": normalize_text(proc['procedure']),
                        "p_query_embedding": get_embedding(proc['procedure']),
                        "p_tenant": "xa_ba_diem",
                        "p_category": category,
                        "p_subject": proc['subject'],
                        "p_procedure_action": procedure_action,
                        "p_special_contexts": special_contexts,
                        "p_limit": 5
                    }
                ).execute()


                chunks = response.data or []
                print(chunks[0])