import re
import unicodedata
from typing import Optional, List

PROVINCE_CITY_NAMES = {
    "ha noi",
    "hue",
    "hai phong",
    "da nang",
    "can tho",
    "ho chi minh",

    "cao bang",
    "lai chau",
    "dien bien",
    "son la",
    "lang son",
    "quang ninh",
    "thanh hoa",
    "nghe an",
    "ha tinh",

    "tuyen quang",
    "lao cai",
    "thai nguyen",
    "phu tho",
    "bac ninh",
    "hung yen",
    "ninh binh",

    "quang tri",
    "quang ngai",
    "gia lai",
    "khanh hoa",
    "lam dong",

    "tay ninh",
    "dong thap",
    "vinh long",
    "an giang",
    "ca mau"
}

PROVINCE_LEVEL_PATTERNS = [
    "tinh uy",
    "thanh uy",
    "so ban nganh",
    "cong an tinh",
    "cong an thanh pho"
]

def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def contains_any(text: str, phrases: List[str]) -> bool:
    for p in phrases:
        p = normalize_text(p)
        if re.search(rf"\b{re.escape(p)}\b", text):
            return True
    return False

def detect_scope_trung_uong(q: str) -> bool:
    q = normalize_text(q)

    exact_patterns = [
        "tong bi thu",
        "chu tich nuoc",
        "thu tuong",
        "chu tich quoc hoi",
        "bo chinh tri",
        "ban bi thu",
        "trung uong",

        "quoc hoi",
        "uy ban thuong vu quoc hoi",
        "chinh phu",
        "toa an nhan dan toi cao",
        "vien kiem sat nhan dan toi cao",
        "kiem toan nha nuoc",
        "hoi dong bau cu quoc gia",
    ]

    ministry_patterns = [
        "bo truong",
        "thu truong",
    ]

    for p in exact_patterns:
        if re.search(rf"\b{re.escape(p)}\b", q):
            return True

    for p in ministry_patterns:
        if re.search(rf"\b{re.escape(p)}\b", q):
            return True

    return False

def extract_scope(query: str, tenant_aliases: List[str] = []) -> Optional[str]:
    q = normalize_text(query)

    if detect_scope_trung_uong(q):
        return "quoc_gia"

    # 1. Nếu chủ thể chính là tỉnh/thành và đang hỏi thống kê/đếm
    if contains_any(q, PROVINCE_CITY_NAMES) and re.search(r"\b(co bao nhieu|co nhung|gom nhung|danh sach)\b", q):
        return "tinh_thanh"

    # 2. Nếu có alias tenant hiện tại thì ưu tiên tenant scope
    if contains_any(q, tenant_aliases):
        return "xa_phuong"

    # 3. Nếu hỏi trực tiếp cấp xã/phường
    if re.search(r"\b(xa|phuong|thi tran)\b", q):
        return "xa_phuong"

    # ✅ 4. NEW: keyword cấp tỉnh (tỉnh uỷ, sở, công an tỉnh…)
    for p in PROVINCE_LEVEL_PATTERNS:
        if re.search(rf"\b{re.escape(p)}\b", q):
            return "tinh_thanh"

    # 5. Nếu hỏi trực tiếp cấp tỉnh/thành phố
    if re.search(r"\b(tinh|thanh pho)\b", q):
        return "tinh_thanh"

    # 6. Nếu có tên tỉnh/thành cụ thể
    for name in PROVINCE_CITY_NAMES:
        name_n = normalize_text(name)
        if re.search(rf"\b{re.escape(name_n)}\b", q):
            return "tinh_thanh"

    # 7. fallback theo tenant hiện tại
    return "xa_phuong"


# tests = [
#     "bí thư thành phố là ai",
#     "chủ tịch tỉnh là ai",
#     "công an tỉnh nào có nhiều chiến sĩ nhất",
#     "tỉnh nào có nhiều dân nhất",
#     "chủ tịch ubnd là ai",
# ]

# from corn import supabase

# for t in tests:
#     scope = extract_scope(t)
#     print(t, "=>", scope)
#     response = supabase.rpc(
#         "resolve_target_tenant_code",
#         {
#             "p_current_tenant_code": "xabadiemgovvn",
#             "p_target_scope": scope
#         }
#     ).execute()

#     # print(response.data)


