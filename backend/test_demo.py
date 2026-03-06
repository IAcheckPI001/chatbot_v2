


import re
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from utils import KHU_PHO_KEYWORDS, DS_KHU_PHO_KEYWORDS, KHU_PHO_POPULATION_KWS, LICH_LAM_VIEC_KEYWORDS, CHUC_VU_INFO_KEYWORDS, CONTACT_INFO_KEYWORDS, NHAN_SU_INFO_KEYWORDS, TONG_QUAN_INFO_KEYWORDS


PERSON_MARKERS = [
    "chi", "anh", "ong", "ba", "co", "chu", "em",
    "thay", "co giao",  # nếu bạn cần
]

PERSON_PHONE_PATTERNS = [
    r"\bso dien thoai cua\b",     # "số điện thoại của chị Lan"
    r"\bso cua\b",              # "sđt của..."
    r"\blien he (chi|anh|ong|ba)\b",
]

ORG_MARKERS = [
    "phuong", "xa", "ubnd", "uy ban", "mot cua", "bo phan mot cua",
    "duong day nong", "tong dai", "lien he phuong", "lien he xa"
]

LIFE_EVENT_KWS = [
    # Ho tich core
    "khai sinh",
    "khai tu",
    "ket hon",
    "trich luc",
    "xac nhan tinh trang hon nhan",
    "cai chinh ho tich",
    "thay doi ho tich",
    "nhan cha me con",
    "nuoi con nuoi",
    "quoc tich",

    # Chung thuc
    "chung thuc ban sao",
    "chung thuc chu ky",
    "chung thuc hop dong",

    # Giam ho
    "giam ho",
    "cham dut giam ho",
]

# PROCEDURE_INTENT_KWS = [
#     "dang ky", "lam sao", "lam the nao", "ho so", "nop o dau", "bao lau", "le phi"
# ]

PROCEDURE_INTENT_KWS = [
    "dang ky", "lam sao", "lam the nao", "ho so", "nop o dau", "bao lau", "le phi",
  "co can", "can khong", "can gi", "can nhung gi",
  "xin", "xin cap", "cap lai", "doi", "dieu chinh", "gia han",
  "tam ngung", "tiep tuc", "giai the", "cham dut",
  "thong bao", "cong bo", "cong bo lai"
]

def has_any(q_norm: str, kws: List[str]) -> bool:
    return any(kw_regex(k).search(q_norm) for k in kws)


def is_phone_of_person(q_norm: str) -> bool:
    # có "so dien thoai" hoặc "sdt"
    has_phone_kw = kw_regex("so dien thoai").search(q_norm) or kw_regex("so cua").search(q_norm)
    if not has_phone_kw:
        return False

    # nếu có dấu hiệu tổ chức (phường/xã/ubnd...) => không phải cá nhân
    if any(kw_regex(m).search(q_norm) for m in ORG_MARKERS):
        return False

    # nếu có dạng "số điện thoại của ..." hoặc "sđt của ..."
    if any(re.search(pat, q_norm) for pat in PERSON_PHONE_PATTERNS):
        return True

    # hoặc có xưng hô + tên gần đó (đơn giản: có marker "chi/anh/ong/ba" trong câu)
    if any(kw_regex(m).search(q_norm) for m in PERSON_MARKERS):
        return True

    return False

# -------------------------
# 1) Helpers: normalize + keyword matching
# -------------------------

def kw_regex(kw: str) -> re.Pattern:
    kw = re.escape(kw.strip())
    # match khi trước/sau là start/end hoặc non-word (space/punct)
    return re.compile(r"(?<!\w)" + kw + r"(?!\w)")

def match_keywords(q_norm: str, keywords: List[str]) -> List[str]:
    hits = []
    for kw in keywords:
        if kw and kw_regex(kw).search(q_norm):
            hits.append(kw)
    return hits

def score_keywords(q_norm: str, keywords: List[str]) -> int:
    return len(match_keywords(q_norm, keywords))


# -------------------------
# 2) Strong/Weak split for procedures (rất quan trọng)
# -------------------------

THU_TUC_KEYWORDS_STRONG = [
    "thu tuc",
    "ho so",
    "thanh phan ho so",
    "nop o dau",
    "noi nop",
    "thoi gian giai quyet",
    "bao lau",
    "le phi",
    "phi bao nhieu",
    "mau don",
    "don de nghi",
    "can cu phap ly",
    "nop truc tuyen",
    "truc tuyen",

    "dieu kien", "trinh tu", "cach thuc hien", "thuc hien nhu the nao",
    "ket qua", "co quan giai quyet", "co quan thuc hien"
]

# Giữ list weak từ list hiện tại của bạn (nhưng đừng cho nó quyết định 1 mình)
THU_TUC_KEYWORDS_WEAK = [
    "dang ky",
    "cap giay",
    "lam the nao",
    "giay to",
    "giay phep",
    "khai sinh",
    "khai tu",
    "ket hon",
    "chung thuc",
    "quy hoach dat",

    "xin", "cap lai", "doi", "dieu chinh", "gia han", "tam ngung", "giai the", "cham dut"
]

PROC_MIN_INTENT_KWS = [
    "thu tuc", "ho so", "giay to", "giay phep",
    "xin", "xin cap", "cap", "cap lai", "doi", "dieu chinh", "gia han",
    "dang ky", "nop o dau", "le phi", "bao lau",
    "co can", "can khong", "can gi", "can nhung gi"
]

# Một số câu hỏi định nghĩa => không nên auto coi là thủ tục nếu chỉ có topic (giảm false positive)
NON_PROC_PATTERNS = ["la gi", "nghia la gi", "tai sao", "vi sao", "khac gi", "so sanh"]

SPECIAL_TOPIC_TO_SUBJECT = {
    # Công thương: rượu/thuốc lá
    "cong_thuong": [
        "ruou", "ban ruou", "san xuat ruou", "kinh doanh ruou",
        "thuoc la", "ban thuoc la"
    ],

    # Đất đai: sổ đỏ / GCN / biến động / chuyển nhượng
    "dat_dai": [
        "so do", "so hong", "gcn", "giay chung nhan",
        "quyen su dung dat", "chuyen nhuong", "tang cho", "thua ke",
        "tach thua", "hop thua", "dang ky bien dong"
    ],

    # Xây dựng nhà ở
    "xay_dung_nha_o": [
        "giay phep xay dung", "xin phep xay dung", "cap phep xay dung",
        "hoan cong", "sua nha", "cai tao", "quy hoach xay dung"
    ],

    # Doanh nghiệp / HKD
    "doanh_nghiep": [
        "doanh nghiep", "dang ky kinh doanh", "gpkd",
        "ho kinh doanh", "hkd", "ma so thue",
        "giai the", "tam ngung", "thay doi dang ky"
    ],

    # Giao thông vận tải
    "giao_thong_van_tai": [
        "dang kiem", "dang ky xe", "bien so", "giay phep lai xe", "gplx",
        "kinh doanh van tai",   "dang ky xe",
        "xe co gioi",
        "dang kiem",
        "kiem dinh xe",
        "dang ky tau",
        "tau ca",
        "tau bien",
        "dang ky phuong tien",
        "bien so",
        "dang ky xe may",
        "dang ky o to"
    ],

    # Lao động việc làm
    "lao_dong_viec_lam": [
        "giay phep lao dong", "lao dong nuoc ngoai", "hop dong lao dong"
    ],

    # Y tế (để ý đừng dính 'thuoc la'!)
    "y_te": [
        "hanh nghe y", "hanh nghe duoc", "co so kham chua benh",
        "trang thiet bi y te", "my pham", "an toan thuc pham"
    ],

    # Bảo hiểm an sinh
    "bao_hiem_an_sinh": [
        "bao hiem xa hoi", "bhxh", "bao hiem y te", "bhyt",
        "bao hiem that nghiep", "tro cap", "bao tro xa hoi", "mai tang", "tien tuat",
        "nguoi vo gia cu", "vo gia cu"
        "nguoi lang thang",
        "bao tro xa hoi", "nguoi co cong", "tre em bi xam hai", "cham soc thay the", "can thiep tre em"
    ],

    # Tư pháp hộ tịch (nếu bạn muốn bridge luôn cho nhóm này)
    "tu_phap_ho_tich": [
        "khai sinh", "khai tu", "ket hon", "trich luc",
        "chung thuc", "quoc tich", "giam ho", "nhan cha me con", "nuoi con nuoi"
    ],
}

# -------------------------
# 3) Intent detection (giúp quyết định gộp chunk)
# -------------------------

ROLE_KEYWORDS = [
    "chu tich",
    "pho chu tich",
    "bi thu",
    "pho bi thu",
    "giam doc",
    "pho giam doc",
    "truong phong",
    "pho truong phong",
    "cong chuc",
    "vien chuc",
    "can bo",
    "chuyen vien",
]

LIST_JOINERS = ["va", "voi", "cung", "kem", "hay", "&"]


def detect_intent(q_norm: str, category: Optional[str]) -> str:
    # Liệt kê chức danh: có >=2 role keywords hoặc có joiner + role
    role_hits = match_keywords(q_norm, ROLE_KEYWORDS)
    joiner_hit = any(kw_regex(j).search(q_norm) for j in LIST_JOINERS)

    if len(role_hits) >= 2:
        return "list_roles"
    if len(role_hits) >= 1 and joiner_hit:
        return "list_roles"

    if category == "thu_tuc_hanh_chinh":
        return "procedure"
    return "general"


# -------------------------
# 4) detect_subject: bạn đã có, mình giữ nguyên ý tưởng của bạn
#    Chỉ khác: trả thêm signals để log
# -------------------------

def detect_special_subject_bridge(q_norm: str) -> Tuple[bool, Optional[str], List[str]]:
    # chặn các câu hỏi định nghĩa/giải thích chung
    if any(kw_regex(p).search(q_norm) for p in NON_PROC_PATTERNS):
        return False, None, []

    has_min_intent = any(kw_regex(k).search(q_norm) for k in PROC_MIN_INTENT_KWS)
    if not has_min_intent:
        return False, None, []

    # Ưu tiên cong_thuong trước để tránh 'thuoc' (y_te) ăn nhầm 'thuoc la'
    priority = ["cong_thuong", "dat_dai", "xay_dung_nha_o", "doanh_nghiep",
                "giao_thong_van_tai", "lao_dong_viec_lam", "bao_hiem_an_sinh", "y_te", "tu_phap_ho_tich"]

    for subject in priority:
        topic_kws = SPECIAL_TOPIC_TO_SUBJECT.get(subject, [])
        hits = [k for k in topic_kws if kw_regex(k).search(q_norm)]
        if hits:
            return True, subject, hits

    return False, None, []

def detect_subject_v2(text_norm: str, prepared_keywords: Dict[str, List[Tuple[str, int]]], min_score: int = 2):
    # override: thuoc la / ruou => cong_thuong
    if kw_regex("thuoc la").search(text_norm) or kw_regex("ruou").search(text_norm):
        return "cong_thuong", 1.0, ["override: thuoc la/ruou"]
    
    subject_scores = defaultdict(int)
    subject_hits = defaultdict(list)

    for subject, keywords in prepared_keywords.items():
        for kw, weight in keywords:
            pattern = kw_regex(kw)
            if pattern.search(text_norm):
                subject_scores[subject] += weight
                subject_hits[subject].append(kw)

    if not subject_scores:
        return None, 0.0, []

    best_subject = max(subject_scores, key=subject_scores.get)
    best_score = subject_scores[best_subject]

    if best_score < min_score:
        return None, 0.0, []

    total_score = sum(subject_scores.values())
    confidence = round(best_score / total_score, 3) if total_score else 0.0

    # trả list keyword đã match cho subject tốt nhất
    return best_subject, confidence, subject_hits[best_subject]


# -------------------------
# 5) classify_v2: trả category, subject, confidence, signals, intent, need_llm
# -------------------------

def classify_v2(q_norm: str, PREPARED: Dict[str, Any]):
    """
    Returns:
      {
        category, subject,
        confidence (0..1),
        signals: {bucket: [kw...]},
        intent,
        need_llm: bool,   # gợi ý có nên fallback LLM
        conflict: bool    # tín hiệu mâu thuẫn
      }
    """
    

    signals = {}

    # --- hits theo nhóm ---
    hits_thu_tuc_strong = match_keywords(q_norm, THU_TUC_KEYWORDS_STRONG)
    hits_thu_tuc_weak = match_keywords(q_norm, THU_TUC_KEYWORDS_WEAK)

    hits_chuc_vu = match_keywords(q_norm, CHUC_VU_INFO_KEYWORDS)       # list của bạn
    hits_nhan_su = match_keywords(q_norm, NHAN_SU_INFO_KEYWORDS)        # list của bạn
    hits_khu_pho = match_keywords(q_norm, KHU_PHO_KEYWORDS)             # list của bạn
    hits_contact = match_keywords(q_norm, CONTACT_INFO_KEYWORDS)        # list của bạn
    hits_lich = match_keywords(q_norm, LICH_LAM_VIEC_KEYWORDS)          # list của bạn
    hits_tong_quan = match_keywords(q_norm, TONG_QUAN_INFO_KEYWORDS)    # list của bạn

    # lưu signals để log
    if hits_thu_tuc_strong: signals["thu_tuc_strong"] = hits_thu_tuc_strong
    if hits_thu_tuc_weak: signals["thu_tuc_weak"] = hits_thu_tuc_weak
    if hits_chuc_vu: signals["chuc_vu"] = hits_chuc_vu
    if hits_nhan_su: signals["nhan_su"] = hits_nhan_su
    if hits_khu_pho: signals["khu_pho"] = hits_khu_pho
    if hits_contact: signals["contact"] = hits_contact
    if hits_lich: signals["lich"] = hits_lich
    if hits_tong_quan: signals["tong_quan"] = hits_tong_quan

    # --- scoring (có trọng số) ---
    # thủ tục: strong quan trọng hơn nhiều
    thu_tuc_score = len(hits_thu_tuc_strong) * 3 + len(hits_thu_tuc_weak) * 1
    lich_score = len(hits_lich) * 2
    contact_score = len(hits_contact) * 2
    chuc_vu_score = len(hits_chuc_vu) * 2
    nhan_su_score = len(hits_nhan_su) * 2
    khu_pho_score = len(hits_khu_pho) * 2
    tong_quan_score = len(hits_tong_quan) * 1

    # --- conflict detection ---
    # mâu thuẫn khi thủ tục mạnh nhưng đồng thời dính tổ chức/bộ máy mạnh (hoặc ngược lại)
    # conflict = False
    # if thu_tuc_score >= 3 and (chuc_vu_score >= 2 or nhan_su_score >= 2):
    #     conflict = True

    # --- quyết định category theo ưu tiên ---
    category = None
    subject = None
    confidence = 0.0
    need_llm = False

    # ✅ boost thủ tục nếu là combo (procedure intent + life event)
    weak_combo_boost = 0
    if has_any(q_norm, LIFE_EVENT_KWS) and has_any(q_norm, PROCEDURE_INTENT_KWS):
        weak_combo_boost = 2
        signals["thu_tuc_combo_boost"] = ["life_event + procedure_intent"]

    # ✅ tính score sau khi boost
    thu_tuc_score = len(hits_thu_tuc_strong) * 3 + len(hits_thu_tuc_weak) * 1 + weak_combo_boost

    has_strong = len(hits_thu_tuc_strong) >= 1
    has_combo = weak_combo_boost > 0
    weak_enough = len(hits_thu_tuc_weak) >= 2

    conflict = (not (has_strong or has_combo)) and (chuc_vu_score >= 2 or nhan_su_score >= 2) and thu_tuc_score >= 3

    other_max = max(lich_score, contact_score, chuc_vu_score, nhan_su_score, khu_pho_score, tong_quan_score)

    bridge_ok, bridge_subject, bridge_hits = detect_special_subject_bridge(q_norm)

    is_procedure = has_strong or has_combo or (weak_enough and thu_tuc_score >= other_max + 1)

    signals["scores"] = {
        "thu_tuc": thu_tuc_score,
        "contact": contact_score,
        "khu_pho": khu_pho_score,
        "nhan_su": nhan_su_score
    }
    if bridge_ok:
        signals["procedure_bridge"] = bridge_hits
        signals["procedure_bridge_subject"] = [bridge_subject]
        is_procedure = True 

    # 1) Thủ tục (chỉ chốt khi đủ mạnh)
    if is_procedure:  # ít nhất 1 strong (3 điểm) hoặc nhiều weak cộng lại
        
        category = "thu_tuc_hanh_chinh"

        # detect subject thủ tục từ SUBJECT_KEYWORDS
        subj, subj_conf, subj_hits = detect_subject_v2(q_norm, PREPARED, min_score=2)
        subject = subj
        if bridge_ok and bridge_subject:
            subject = bridge_subject
            signals["subject_override"] = ["bridge: special_topic + min_intent"]
            subj_conf = 1.0

        if subj_hits:
            signals["subject_hits"] = subj_hits

        # confidence tổng hợp: dựa trên strength + subj_conf
        # strong càng nhiều => càng cao
        base = min(1.0, 0.4 + 0.15 * len(hits_thu_tuc_strong) + 0.05 * len(hits_thu_tuc_weak))
        confidence = round(min(1.0, base * 0.7 + subj_conf * 0.3), 3)

        # nếu chưa ra subject mà chỉ có weak -> đẩy LLM
        if subject is None and len(hits_thu_tuc_strong) == 0:
            need_llm = True

    # 2) Lịch làm việc
    elif lich_score >= 2:
        category = "thong_tin_tong_quan"
        subject = "lich_lam_viec"
        confidence = 0.85

    # 4) Chức vụ / Nhân sự
    elif chuc_vu_score >= 2:
        category = "to_chuc_bo_may"
        subject = "chuc_vu"
        confidence = 0.8

    elif nhan_su_score >= 2:
        category = "to_chuc_bo_may"
        subject = "nhan_su"
        confidence = 0.75

            # 3) Liên hệ
    elif contact_score >= 2:
        category = "thong_tin_tong_quan"
        subject = "thong_tin_lien_he"
        confidence = 0.85
        if is_phone_of_person(q_norm):
            signals["person_phone"] = True

    # 5) Khu phố
    elif khu_pho_score >= 2:
        category = "thong_tin_tong_quan"
        subject = "thong_tin_khu_pho"

        if has_any(q_norm, DS_KHU_PHO_KEYWORDS) and has_any(q_norm, KHU_PHO_KEYWORDS):
            subject = "tong_quan"

        confidence = 0.75
    

        # if is_phone_of_person(q_norm):
            

    # 6) Tổng quan
    elif tong_quan_score >= 1:
        category = "thong_tin_tong_quan"
        subject = "tong_quan"
        confidence = 0.6

    else:
        need_llm = True

    # Nếu conflict hoặc confidence thấp -> gợi ý LLM
    if conflict:
        need_llm = True
    if category is not None and confidence < 0.55:
        need_llm = True

    intent = detect_intent(q_norm, category)

    return {
        "category": category,
        "subject": subject,
        "confidence": confidence,
        "signals": signals,
        "intent": intent,
        "need_llm": need_llm,
        "conflict": conflict
    }

# from normalize import normalize_text
# from utils import SUBJECT_KEYWORDS, prepare_subject_keywords
# from model import classify_llm
# from normalize import SINGLE_TOKEN_MAP, CONTEXT_RULES, AbbreviationResolver


# PREPARED = prepare_subject_keywords(SUBJECT_KEYWORDS)
# resolver = AbbreviationResolver(SINGLE_TOKEN_MAP, CONTEXT_RULES)


# if __name__ == '__main__':
#     while True:
#         user_message = input("Nhập câu hỏi test: ")
#         if user_message.lower() == "quit":
#             break

#         result = resolver.process(user_message)

#         user_message = result["expanded"]
#         normalized_query = result["normalized"]
#         print(normalized_query)

#         res = classify_v2(normalized_query, PREPARED)
#         category, subject = res["category"], res["subject"]

#         print(f"KW classify => Category: {category}, Subject: {subject}, conf: {res['confidence']}, intent: {res['intent']}, conflict: {res['conflict']}")
#         print(f"Signals: {res['signals']}")

#         if res["need_llm"]:
#             re_check = True
#             category_llm, subject_llm = classify_llm(user_message)
#             print(f'LLM classify => Category: {category_llm}, Subject: {subject_llm}')

#             # chỉ override khi LLM trả rõ ràng
#             category = category_llm or category
#             subject = subject_llm or subject

