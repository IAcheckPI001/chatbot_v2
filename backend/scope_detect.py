import re
import unicodedata
from typing import Optional, List

PROVINCE_CITY_NAMES = {
    "ha noi", "ho chi minh", "da nang", "can tho", "hai phong",
    "an giang", "ba ria vung tau", "bac giang", "bac kan", "bac lieu",
    "bac ninh", "ben tre", "binh dinh", "binh duong", "binh phuoc",
    "binh thuan", "ca mau", "cao bang", "dak lak", "dak nong", "dien bien",
    "dong nai", "dong thap", "gia lai", "ha giang", "ha nam", "ha tinh",
    "hai duong", "hau giang", "hoa binh", "hung yen", "khanh hoa",
    "kien giang", "kon tum", "lai chau", "lam dong", "lang son", "lao cai",
    "long an", "nam dinh", "nghe an", "ninh binh", "ninh thuan", "phu tho",
    "phu yen", "quang binh", "quang nam", "quang ngai", "quang ninh",
    "quang tri", "soc trang", "son la", "tay ninh", "thai binh",
    "thai nguyen", "thanh hoa", "thua thien hue", "tien giang",
    "tra vinh", "tuyen quang", "vinh long", "vinh phuc", "yen bai",
}

PROVINCE_CITY_ALIASES = {
    "tp.hcm": "ho chi minh",
    "tp hcm": "ho chi minh",
    "tphcm": "ho chi minh",
    "sai gon": "ho chi minh",
    "tp ho chi minh": "ho chi minh",
    "thanh pho ho chi minh": "ho chi minh",
    "hcm": "ho chi minh",
    "hn": "ha noi",
    "tp ha noi": "ha noi",
    "thanh pho ha noi": "ha noi",
    "tp da nang": "da nang",
    "thanh pho da nang": "da nang",
    "tp can tho": "can tho",
    "thanh pho can tho": "can tho",
    "tp hai phong": "hai phong",
    "thanh pho hai phong": "hai phong",
}

def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def replace_aliases(text: str) -> str:
    text = normalize_text(text)
    for alias, canonical in sorted(PROVINCE_CITY_ALIASES.items(), key=lambda x: -len(x[0])):
        alias_n = normalize_text(alias)
        canonical_n = normalize_text(canonical)
        text = re.sub(rf"\b{re.escape(alias_n)}\b", canonical_n, text)
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
        "pho chu tich nuoc",
        "thu tuong",
        "pho thu tuong",
        "chu tich quoc hoi",
        "pho chu tich quoc hoi",
        "bo chinh tri",
        "ban bi thu",
        "trung uong",

        "quoc hoi",
        "uy ban thuong vu quoc hoi",
        "chinh phu",
        "van phong chinh phu",

        "toa an nhan dan toi cao",
        "vien kiem sat nhan dan toi cao",
        "kiem toan nha nuoc",
        "hoi dong bau cu quoc gia",
    ]

    ministry_patterns = [
        "bo truong",
        "thu truong",
        "pho thu truong",
    ]

    for p in exact_patterns:
        if re.search(rf"\b{re.escape(p)}\b", q):
            return True

    for p in ministry_patterns:
        if re.search(rf"\b{re.escape(p)}\b", q):
            return True

    return False

def extract_scope(query: str, tenant_aliases: List[str] = []) -> Optional[str]:
    q = replace_aliases(query)

    if detect_scope_trung_uong(q):
        return "quoc_gia"

    # 1. Nếu chủ thể chính là tỉnh/thành và đang hỏi thống kê/đếm
    if contains_any(q, PROVINCE_CITY_NAMES) and re.search(r"\b(co bao nhieu|co nhung|gồm những|gom nhung|danh sach)\b", q):
        return "tinh_thanh"

    # 1. Nếu có alias tenant hiện tại thì ưu tiên tenant scope
    if contains_any(q, tenant_aliases):
        return "xa_phuong"

    # 2. Nếu hỏi trực tiếp cấp xã/phường
    if re.search(r"\b(xa|phuong|thi tran)\b", q):
        return "xa_phuong"

    # 4. Nếu hỏi trực tiếp cấp tỉnh/thành phố
    if re.search(r"\b(tinh|thanh pho)\b", q):
        return "tinh_thanh"

    # 5. Nếu có tên tỉnh/thành cụ thể
    for name in PROVINCE_CITY_NAMES:
        name_n = normalize_text(name)
        if re.search(rf"\b{re.escape(name_n)}\b", q):
            return "tinh_thanh"

    # 6. fallback theo tenant hiện tại
    return "xa_phuong"


# tests = [
#     "bí thư thành phố là ai"
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

#     print(response.data)


