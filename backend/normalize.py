
import re
from embedding import cosine
from functools import lru_cache
import unicodedata

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
    # "ubnd": "uy ban nhan dan",
    # "hdnd": "hoi dong nhan dan",
    "pct": "pho chu tich",
    "pbt": "pho bi thu",
    "cccd": "can cuoc cong dan",
    "cmnd": "chung minh nhan dan",
    "hk": "ho khau",
    "gks": "giay khai sinh",
    "gkt": "giay khai tu",
    "dkkh": "dang ky ket hon",
    "tthc": "thu tuc hanh chinh",
    "gcn": "giay chung nhan",
    "gpkd": "giay phep kinh doanh",
    "hkd": "ho kinh doanh",
    "htx": "hop tac xa",
    "bhxh": "bao hiem xa hoi",
    "bhyt": "bao hiem y te",
    "pccc": "phong chay chua chay",
    "dktt": "dang ky tam tru",
    "dktv": "dang ky tam vang",
    "dkks": "dang ky khai sinh",
    "dkkt": "dang ky khai tu",
    "sdt": "so dien thoai",
    "kp": "khu pho"
}

CONTEXT_RULES = [
    (r"\b(dk|dang ky)\s+ho\s+kd\b", r"dang ky ho kinh doanh"),
    (r"\bho\s+kd\b", r"ho kinh doanh"),
    (r"\b(dk|dang ky)\s+kd\b", r"\1 kinh doanh"),
    (r"\b(dk|dang ky|giay|lam)\s+ks\b", r"\1 khai sinh"),
    (r"\b(dk|dang ky|giay|lam)\s+kt\b", r"\1 khai tu"),
    (r"\b(dk|dang ky)\s+kh\b", r"\1 ket hon"),
    (r"\b(dk|dang ky)\s+tt\b", r"\1 tam tru"),
    (r"\b(dk|dang ky)\s+tv\b", r"\1 tam vang"),
    (r"\b(dk|dang ky)\s+bh\b", r"\1 bao hiem")
]

NEGATIVE_CONTEXT = {
    "hk": ["hoc sinh", "mon toan", "hoc ky"],
    "ks": ["ky su", "khach san"],
    "kt": ["ky thuat", "kiem tra", "ke toan", "kinh te"],
}

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('Đ', 'D').replace('đ', 'd')
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()

class AbbreviationResolver:

    def __init__(self, mapping: dict = {}, context_rules: list = []):
        # Mapping phải là KHÔNG DẤU
        self.mapping = mapping

        # Build single token regex (1 lần duy nhất)
        keys = sorted(mapping.keys(), key=len, reverse=True)
        pattern = r'\b(' + '|'.join(map(re.escape, keys)) + r')\b'
        self.abbr_pattern = re.compile(pattern, re.IGNORECASE)

        # SHORT detect (token <= 4 ký tự)
        short_keys = [k for k in keys if len(k) <= 4]
        short_pattern = r'\b(' + '|'.join(map(re.escape, short_keys)) + r')\b'
        self.short_pattern = re.compile(short_pattern, re.IGNORECASE)

        # Compile context rules
        self.context_rules = [
            (re.compile(p, re.IGNORECASE), r)
            for p, r in context_rules
        ]

    # ------------------------
    # DETECT QUICK
    # ------------------------
    def should_expand(self, text: str) -> bool:
        return bool(self.short_pattern.search(text))

    # ------------------------
    # CONTEXT EXPAND
    # ------------------------
    def expand_context(self, text: str) -> str:
        for pattern, repl in self.context_rules:
            text = pattern.sub(repl, text)
        return text

    # ------------------------
    # SINGLE TOKEN EXPAND
    # ------------------------
    def expand_single(self, text: str) -> str:
        tokens = text.split()

        def replacer(match):
            word = match.group(0).lower()

            if word in NEGATIVE_CONTEXT:
                idx = tokens.index(word)
                window = " ".join(tokens[max(0, idx-2): idx+3])
                for phrase in NEGATIVE_CONTEXT[word]:
                    if phrase in window:
                        return word

            return self.mapping.get(word, word)

        return self.abbr_pattern.sub(replacer, text)

    # ------------------------
    # MAIN PROCESS
    # ------------------------
    @lru_cache(maxsize=5000)
    def process(self, user_message: str) -> dict:
        raw = user_message
        normalized = normalize_text(raw)

        expanded = normalized

        # LUÔN chạy context rule
        expanded = self.expand_context(expanded)

        # Sau đó mới expand single
        expanded = self.expand_single(expanded)

        return {
            "raw": raw,
            "normalized": normalized,
            "expanded": expanded
        }

# def expand_abbreviations(text: str, mapping: dict) -> str:
#     """
#     Expand abbreviations using word-boundary regex.
#     Safe for production use.
#     """

#     if not text:
#         return text

#     # Lower text để đồng bộ
#     text_lower = text.lower()

#     # Sort theo độ dài key giảm dần
#     # Tránh trường hợp 'hk' match trước 'hkd'
#     sorted_items = sorted(mapping.items(), key=lambda x: -len(x[0]))

#     for abbr, full in sorted_items:
#         pattern = r'\b' + re.escape(abbr) + r'\b'
#         text_lower = re.sub(pattern, full, text_lower, flags=re.IGNORECASE)

#     return text_lower

# def expand_context_sensitive(text: str) -> str:
#     text = text.lower()

#     # Expand ks nếu đứng sau giay|giấy|lam|làm|dk|đăng ký
#     text = re.sub(
#         r'\b(giay|giấy|lam|làm|dk|đăng ký)\s+ks\b',
#         r'\1 khai sinh',
#         text
#     )

#     text = re.sub(
#         r'\b(giay|giấy|lam|làm|dk|đăng ký)\s+kt\b',
#         r'\1 khai tử',
#         text
#     )

#     return text

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

    if query_embedding is None or last_a_emb is None:
        return False

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