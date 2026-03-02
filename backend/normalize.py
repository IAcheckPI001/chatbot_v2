
import re
from embedding import get_embedding, cosine

## rewrite check block

MAIN_ENTITIES = [
    # Địa phương
    "xa ba diem",
    "xa",
    "phuong",

    # Cơ quan
    "ubnd",
    "hdnd",

    # Lãnh đạo
    "chu tich",
    "pho chu tich",
    "bi thu",
    "pho bi thu",

    # Khu vực
    "khu pho",
    "kp",

    # Thông tin chung
    "dan so",
    "dien tich",
    "dia chi",
]

STRONG_TRIGGERS = [
    "bao nhieu",
    "o dau",
    "the nao",
    "lien he",
    "so dien thoai",
    "dia chi",
    "bao lau",
    "mat bao lau",
    "xu ly bao lau",
    "online",
    "nop online",
    "duoc khong",
    "co duoc khong"
]

WEAK_TRIGGERS = [
    "con",
    "vay",
    "sao",
    "ay",
    "do",
    "kia"
]

## blacklist block

BANNED_KEYWORDS = [

    "sex", "18+", "khiêu dâm",
    "giết người", "ấu dâm",
    "tình dục", "hiếp dâm",
    "hack ngân hàng", "clip nóng"
    
    "chính phủ lật đổ", "biểu tình",
    "chống phá nhà nước", "đánh bom",
    "biểu tình lật đổ", "chính trị quốc tế",
    "bầu cử tổng thống", "quốc hội Mỹ", "NATO",
    "chiến tranh Ukraine",
    "vũ khí trái phép", "đảng cộng sản",
    "chế bom", "thuốc nổ"
    
    "con mẹ mày", "thằng chó", "đồ rác rưởi",
    "đồ khốn", "chatbot ngu", "đm", "dm"

]

NORMALIZED_BANNED = [
    "sex", "18+", "khieu dam",
    "giet nguoi", "au dam",
    "tinh duc", "hiep dam",
    "hack ngan hang", "clip nong"
    
    "chinh phu lat do", "bieu tinh",
    "chong pha nha nuoc", "danh bom",
    "bieu tinh lat do", "chinh tri quoc te",
    "bau cu tong thong", "quoc hoi My", "NATO",
    "chien tranh Ukraine",
    "vu khi trai phep", "dang cong san",
    "che bom", "thuoc no"
    
    "con me may", "thang cho", "do rac ruoi",
    "đo khon", "chatbot ngu"
]


## sym block

SINGLE_TOKEN_MAP = {
    "ubnd": "ủy ban nhân dân",
    "hdnd": "hội đồng nhân dân",
    "pct": "phó chủ tịch",
    "cccd": "căn cước công dân",
    "cmnd": "chứng minh nhân dân",
    "hk": "hộ khẩu",
    "gks": "giấy khai sinh",
    "gkt": "giấy khai tử",
    "dkkh": "đăng ký kết hôn",
    "tthc": "thủ tục hành chính",
    "gcn": "giấy chứng nhận",
    "gpkd": "giấy phép kinh doanh",
    "hkd": "hộ kinh doanh",
    "htx": "hợp tác xã",
    "bhxh": "bảo hiểm xã hội",
    "bhyt": "bảo hiểm y tế",
    "pccc": "phòng cháy chữa cháy",
    "dktt": "đăng ký tạm trú",
    "dktv": "đăng ký tạm vắng",
    "dkks": "đăng ký khai sinh",
    "dkkt": "đăng ký khai tử",
    "sdt": "số điện thoại",
    "sđt": "số điện thoại",
    "kp": "khu phố"
}


def expand_abbreviations(text: str, mapping: dict) -> str:
    """
    Expand abbreviations using word-boundary regex.
    Safe for production use.
    """

    if not text:
        return text

    # Lower text để đồng bộ
    text_lower = text.lower()

    # Sort theo độ dài key giảm dần
    # Tránh trường hợp 'hk' match trước 'hkd'
    sorted_items = sorted(mapping.items(), key=lambda x: -len(x[0]))

    for abbr, full in sorted_items:
        pattern = r'\b' + re.escape(abbr) + r'\b'
        text_lower = re.sub(pattern, full, text_lower, flags=re.IGNORECASE)

    return text_lower

def expand_context_sensitive(text: str) -> str:
    text = text.lower()

    # Expand ks nếu đứng sau giay|giấy|lam|làm|dk|đăng ký
    text = re.sub(
        r'\b(giay|giấy|lam|làm|dk|đăng ký)\s+ks\b',
        r'\1 khai sinh',
        text
    )

    text = re.sub(
        r'\b(giay|giấy|lam|làm|dk|đăng ký)\s+kt\b',
        r'\1 khai tử',
        text
    )

    return text

def is_short(q, max_words=7):
    return len(q.split()) <= max_words

def has_trigger(q):
    q = q.lower()
    return any(t in q for t in STRONG_TRIGGERS)

def has_weak_trigger(q):
    q = q.lower()
    return any(t in q for t in WEAK_TRIGGERS)

def contains_main_entity(q):
    q = q.lower()
    return any(e in q for e in MAIN_ENTITIES)

def looks_incomplete(q):
    q = q.lower().strip()
    return q.endswith("?") and len(q.split()) <= 5


def should_rewrite(q):

    if not is_short(q):
        return False

    if contains_main_entity(q):
        return False

    if has_trigger(q) or looks_incomplete(q):
        return True
    
    if has_weak_trigger(q) and len(q.split()) <= 4:
        return True

    return False


def check_rewrite(q_norm, query_embedding, last_a_emb):

    # if last_q_emb is None or last_a_emb is None:
    #     return False

    # sim_q = cosine(current_emb, last_q_emb)
    sim_a = cosine(query_embedding, last_a_emb)

    context_sim = sim_a

    # context_sim = max(sim_q, sim_a)
    # print(context_sim)

    # Case 1: rất liên quan
    if context_sim > 0.75:
        return True

    # Case 2: trung bình + rule
    if context_sim > 0.55:
        if should_rewrite(q_norm):
            return True
    
    # 3️⃣ NEW: câu cực generic nhưng rõ follow-up
    if should_rewrite(q_norm):
        return True

    return False