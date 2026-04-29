

import re
import unicodedata
from functools import lru_cache


# =========================
# CORE NORMALIZE
# =========================

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("Đ", "D").replace("đ", "d")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# =========================
# MAP / RULES
# =========================

# Token an toàn: expand gần như luôn đúng
SAFE_SINGLE_TOKEN_MAP = {
    "ubnd": "ủy ban nhân dân",
    "hdnd": "hội đồng nhân dân",
    "ct": "chủ tịch",
    "pct": "phó chủ tịch",
    "pbt": "phó bí thư",
    "cccd": "căn cước công dân",
    "cmnd": "chứng minh nhân dân",
    "gks": "giấy khai sinh",
    "gkt": "giấy khai tử",
    "dkkh": "đăng ký kết hôn",
    "tthc": "thủ tục hành chính",
    "gcn": "giấy chứng nhận",
    "gpkd": "giấy phép kinh doanh",
    "hkd": "hộ kinh doanh",
    "bhxh": "bảo hiểm xã hội",
    "bhyt": "bảo hiểm y tế",
    "pccc": "phòng cháy chữa cháy",
    "dktt": "đăng ký tạm trú",
    "dktv": "đăng ký tạm vắng",
    "dkks": "đăng ký khai sinh",
    "dkkt": "đăng ký khai tử",
    "sdt": "số điện thoại",
    "kp": "khu phố",
    "onl": "trực tuyến",
    "online": "trực tuyến",
}

# Token mơ hồ: chỉ expand khi có ngữ cảnh hành chính rõ
AMBIGUOUS_SINGLE_TOKEN_MAP = {
    "hk": "hộ khẩu",
}

# Không dùng "dc/đc" ở đây vì quá dễ đụng nghĩa "được"


POLITE_PREFIX_PATTERNS = [
    r"^\s*(dạ|ạ|alo|xin chào|chào ad|chào admin|chào bạn|em chào|cho em hỏi|cho tôi hỏi|xin hỏi|vui lòng cho hỏi|tôi muốn hỏi|mình muốn hỏi)\s+",
]

FILLER_ENDINGS = [
    r"\b(nha|nhỉ|ha|ơi|ạ|á|à)\b$"
]

CLEAR_TYPO_RULES = [
    (r"\btruong\s+kp\b", "trưởng khu phố"),
    (r"\btruong\s+khu\s+pho\b", "trưởng khu phố"),
    (r"\btrường\s+kp\b", "trưởng khu phố"),
    (r"\btrường\s+khu\s+phố\b", "trưởng khu phố"),
    (r"\bpho\s+bi\s+thu\b", "phó bí thư"),
    (r"\bchu\s+tich\b", "chủ tịch"),
    (r"\bso\s+dt\b", "số điện thoại"),
    (r"\bnop\s+onl\b", "nộp trực tuyến"),
    (r"\bho\s+so\s+onl\b", "hồ sơ trực tuyến"),
]

# Đã sửa lỗi thiếu dấu phẩy
BANNED_KEYWORDS_V2 = [
    "sex",
    "khiêu dâm",
    "giết người",
    "ấu dâm",
    "tình dục",
    "hiếp dâm",
    "hack ngân hàng",
    "clip nóng",
    "chính phủ lật đổ",
    "biểu tình",
    "chống phá nhà nước",
    "đánh bom",
    "biểu tình lật đổ",
    "chính trị quốc tế",
    "bầu cử tổng thống",
    "quốc hội mỹ",
    "nato",
    "chiến tranh ukraine",
    "vũ khí trái phép",
    "đảng cộng sản",
    "chế bom",
    "thuốc nổ",
    "con mẹ mày",
    "thằng chó",
    "đồ rác rưởi",
    "đồ khốn",
    "chatbot ngu",
    "đm",
    "dm",
]


# =========================
# PRECOMPILE
# =========================

NORMALIZED_SAFE_MAP = {
    normalize_text(k): v for k, v in SAFE_SINGLE_TOKEN_MAP.items()
}
NORMALIZED_AMBIG_MAP = {
    normalize_text(k): v for k, v in AMBIGUOUS_SINGLE_TOKEN_MAP.items()
}
NORMALIZED_BANNED = [normalize_text(x) for x in BANNED_KEYWORDS_V2]

SAFE_TOKEN_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, NORMALIZED_SAFE_MAP), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

AMBIG_TOKEN_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, NORMALIZED_AMBIG_MAP), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

ANY_ABBR_TOKEN_PATTERN = re.compile(
    r"\b("
    + "|".join(
        sorted(
            map(
                re.escape,
                list(NORMALIZED_SAFE_MAP)
                + list(NORMALIZED_AMBIG_MAP)
                + ["dk", "đk", "ks", "kt", "kh", "tt", "tv", "bh", "kd"]
            ),
            key=len,
            reverse=True,
        )
    )
    + r")\b",
    re.IGNORECASE,
)


# =========================
# HELPERS
# =========================

def dedup_consecutive_ngrams(text: str, max_n: int = 4):
    """
    Gộp lặp cụm liên tiếp kiểu:
    - "cho tôi hỏi cho tôi hỏi"
    - "khai sinh khai sinh"
    - "sdt sdt sdt ubnd"
    """
    toks = text.split()
    if len(toks) < 2:
        return text, False

    changed = False

    while True:
        updated = False
        new_tokens = []
        i = 0
        n_tokens = len(toks)

        while i < n_tokens:
            reduced = False
            max_here = min(max_n, (n_tokens - i) // 2)

            for n in range(max_here, 0, -1):
                seg = toks[i:i+n]
                if seg == toks[i+n:i+2*n]:
                    new_tokens.extend(seg)
                    i += 2 * n

                    while i + n <= n_tokens and seg == toks[i:i+n]:
                        i += n

                    updated = True
                    reduced = True
                    break

            if not reduced:
                new_tokens.append(toks[i])
                i += 1

        toks = new_tokens
        changed = changed or updated

        if not updated:
            break

    return " ".join(toks), changed


def simplify_noise(text: str) -> str:
    text = text.strip()

    # gom dấu câu lặp
    text = re.sub(r"[!?.,;:]{2,}", lambda m: m.group(0)[0], text)

    # chỉ gom lặp nguyên âm, tránh phá từ viết tắt kiểu cccd
    text = re.sub(
        r"([aeiouyAEIOUYàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữ])\1{2,}",
        r"\1\1",
        text,
    )

    return collapse_spaces(text)


def strip_polite_prefixes(text: str) -> str:
    prev = None
    cur = text

    while prev != cur:
        prev = cur
        for pat in POLITE_PREFIX_PATTERNS:
            cur = re.sub(pat, "", cur, flags=re.IGNORECASE)

    for pat in FILLER_ENDINGS:
        cur = re.sub(pat, "", cur, flags=re.IGNORECASE).strip()

    return cur


def apply_clear_typos(text: str) -> str:
    out = text
    for pat, repl in CLEAR_TYPO_RULES:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def canonical_prefix(norm_token: str) -> str:
    mapping = {
        "dk": "đăng ký",
        "đk": "đăng ký",
        "dang ky": "đăng ký",
        "đăng ký": "đăng ký",
        "giay": "giấy",
        "giấy": "giấy",
        "lam": "làm",
        "làm": "làm",
    }
    return mapping.get(norm_token, norm_token)


def replace_proc_abbr(match, expansion: str) -> str:
    prefix_raw = match.group(1)
    again = (match.group(2) or "").strip()

    prefix = canonical_prefix(normalize_text(prefix_raw))

    if again:
        return f"{prefix} lại {expansion}"
    return f"{prefix} {expansion}"


CONTEXT_RULES = [
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký)\s+hộ\s+kd\b", re.IGNORECASE),
        lambda m: "đăng ký hộ kinh doanh",
    ),
    (
        re.compile(r"\bhộ\s+kd\b", re.IGNORECASE),
        lambda m: "hộ kinh doanh",
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký)\s+kd\b", re.IGNORECASE),
        lambda m: "đăng ký kinh doanh",
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký)\s+bao\s*hiem\b", re.IGNORECASE),
        lambda m: "đăng ký bảo hiểm",
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký|giấy|giay|làm|lam)\s+((?:lại|lai)\s+)?ks\b", re.IGNORECASE),
        lambda m: replace_proc_abbr(m, "khai sinh"),
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký|giấy|giay|làm|lam)\s+((?:lại|lai)\s+)?kt\b", re.IGNORECASE),
        lambda m: replace_proc_abbr(m, "khai tử"),
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký)\s+kh\b", re.IGNORECASE),
        lambda m: "đăng ký kết hôn",
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký)\s+tt\b", re.IGNORECASE),
        lambda m: "đăng ký tạm trú",
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký)\s+tv\b", re.IGNORECASE),
        lambda m: "đăng ký tạm vắng",
    ),
    (
        re.compile(r"\b(dk|đk|dang ky|đăng ký)\s+bh\b", re.IGNORECASE),
        lambda m: "đăng ký bảo hiểm",
    ),
    (
        re.compile(r"\bnop\s+onl\b", re.IGNORECASE),
        lambda m: "nộp trực tuyến",
    ),
    (
        re.compile(r"\bho\s+so\s+onl\b", re.IGNORECASE),
        lambda m: "hồ sơ trực tuyến",
    ),
]


def apply_context_rules(text: str) -> str:
    out = text
    for pat, repl in CONTEXT_RULES:
        out = pat.sub(repl, out)
    return out


def replace_safe_tokens(text: str) -> str:
    return SAFE_TOKEN_PATTERN.sub(
        lambda m: NORMALIZED_SAFE_MAP[normalize_text(m.group(0))],
        text,
    )


def should_expand_ambiguous(norm_text: str) -> bool:
    """
    Chỉ expand hk -> hộ khẩu khi có ngữ cảnh hành chính rõ.
    """
    return bool(
        re.search(
            r"\b(dang ky|đăng ký|dk|đk|so|sổ|cap|cấp|tach|tách|nhap|nhập|chuyen|chuyển|thuong tru|thường trú|tam tru|tạm trú|ho khau|hộ khẩu)\b",
            norm_text,
        )
    )


def replace_ambiguous_tokens(text: str) -> str:
    norm = normalize_text(text)
    if should_expand_ambiguous(norm):
        return AMBIG_TOKEN_PATTERN.sub(
            lambda m: NORMALIZED_AMBIG_MAP[normalize_text(m.group(0))],
            text,
        )
    return text


def contains_banned(text: str) -> bool:
    norm = normalize_text(text)
    return any(k in norm for k in NORMALIZED_BANNED)


# =========================
# MAIN
# =========================

@lru_cache(maxsize=20000)
def normalize_query_v2(query: str) -> dict:
    """
    Trả về:
    {
        raw: str,
        cleaned: str,
        expanded: str,
        normalized: str,
        contains_banned: bool,
        had_abbreviation: bool,
        had_repetition_cleanup: bool,
        token_count: int
    }
    """
    raw = query or ""

    if not raw.strip():
        return {
            "raw": raw,
            "cleaned": "",
            "expanded": "",
            "normalized": "",
            "contains_banned": False,
            "had_abbreviation": False,
            "had_repetition_cleanup": False,
            "token_count": 0,
        }

    step = simplify_noise(raw)
    deduped, had_dedup = dedup_consecutive_ngrams(step, max_n=4)

    step = strip_polite_prefixes(deduped)
    step = apply_clear_typos(step)
    cleaned = collapse_spaces(step)

    expanded = cleaned
    had_abbreviation = False

    # short-circuit: chỉ chạy expand khi thực sự có dấu hiệu viết tắt / context rút gọn
    if ANY_ABBR_TOKEN_PATTERN.search(normalize_text(expanded)):
        before_norm = normalize_text(expanded)

        expanded = apply_context_rules(expanded)
        expanded = replace_safe_tokens(expanded)
        expanded = replace_ambiguous_tokens(expanded)

        # chạy thêm 1 lượt để bắt case sinh ra sau expansion
        expanded = apply_context_rules(expanded)
        expanded = apply_clear_typos(expanded)

        had_abbreviation = normalize_text(expanded) != before_norm

    expanded = collapse_spaces(expanded)
    normalized = normalize_text(expanded)

    return {
        "raw": raw,
        "cleaned": cleaned,
        "expanded": expanded,
        "normalized": normalized,
        "contains_banned": contains_banned(expanded),
        "had_abbreviation": had_abbreviation,
        "had_repetition_cleanup": had_dedup,
        "token_count": len(normalized.split()),
    }

# if __name__ == "__main__":
#     test_cases = [
#     # "ubnd xa sdt bn",
#     # "so dt ubnd xa la gi",
#     # "số đt ubnd xã bà điểm",
#     # "sdt ubnd ba diem",
#     # "so dien thoai uy ban",
#     # "uy ban co hotline ko",
#     # "co sdt lien he khong",

#     # "dang ky khai sinh can gi",
#     # "dang ky ks can gi",
#     # "dk ks can gi",
#     # "dk khai sinh can j",
#     # "dk ks can j vay",
#     # "khai sinh can nhung gi",

#     # "dang ky ket hon can gi",
#     # "dk kh can gi",
#     # "dk ket hon can j",
#     "lam giay ket hon can gi",

#     "dang ky tam tru can gi",
#     "dk tt can gi",
#     "tam tru can giay to gi",
#     "cho tôi hỏi ubnd xã ở đâu vậy ạ",
#     "cho mình hỏi sdt ubnd với",
#     "cho em xin số điện thoại ubnd xã",
#     "ubnd xã ở đâu vậy bạn",
#     "ubnd xã mình ở đâu á",

#     "cho hỏi khai sinh cần gì",
#     "cho mình hỏi khai sinh cần giấy tờ gì",
#     "khai sinh á cần gì vậy",
#     "làm khai sinh cần những gì",

#     "cho hỏi đăng ký kết hôn cần gì",
#     "kết hôn cần giấy tờ gì vậy",
#     "muốn đăng ký kết hôn thì sao",

#     "tạm trú cần làm sao",
#     "muốn đăng ký tạm trú thì làm gì",
#     "ct xã là ai",          # chủ tịch
#     "phó ct xã là ai",      # phó chủ tịch
#     "bí thư xã là ai",
#     "phó bí thư là ai",
#     "trưởng công an xã là ai",

#     "ubnd xã có những ai",
#     "danh sách cán bộ xã",
#     "cơ cấu tổ chức ubnd xã",

#     "địa chỉ ubnd xã",
#     "ubnd xã nằm ở đâu",
#     "đường đi ubnd xã",
#      "ubnd xã ở đâu và sdt là gì",
#     "cho tôi xin địa chỉ và số điện thoại ubnd xã",
#     "khai sinh cần gì và nộp ở đâu",
#     "đăng ký kết hôn cần gì và làm bao lâu",

#     "ai là chủ tịch xã và liên hệ sao",
#     "làm giấy khai sinh cần chuẩn bị gì",
#     "hồ sơ để làm khai sinh gồm gì",
#     "muốn đăng ký khai sinh cần giấy tờ gì",

#     "thủ tục kết hôn cần những gì",
#     "đi đăng ký kết hôn cần gì",
#     "muốn cưới hợp pháp cần giấy tờ gì",

#     "đăng ký tạm trú cần chuẩn bị gì",
#     "ở tạm thì cần đăng ký gì",
#     "học kỳ này thế nào",
#     "giá vàng hôm nay",
#     "thời tiết hôm nay",
#     "mua iphone ở đâu",
#     "cách nấu bò kho",
#     "đm chatbot ngu",
#     "bot như cc",
#     "trả lời ngu vậy",
#     "mày biết gì không",
#     "nói chuyện như cl",

#     "alo alo alo alo",
#     "test test test",
#     "làm lại cần gì",          # không rõ cái gì
#     "cần giấy tờ gì",          # thiếu context
#     "ở đâu vậy",               # thiếu subject
#     "ai là ai",                # vô nghĩa

#     "đăng ký cần gì",
#     "ubnd ba diem o dau",
#     "ubnd xa bdiem o dau",
#     "ubnd xa bd o dau",
#     "xa ba diem o dau",

#     "truong kp 8 la ai",
#     "kp8 truong la ai",
#     "dang ki khia sinh can gi",
#     "dang ky ket hon can nhug gi",
#     "tam tru can j v",
#     "ubnd o dau vayy",
#     "so dien thoai ubnnd",
# ]

#     # for q in test_cases:
#     #     print(normalize_query_v2(q))
#     for item in test_cases:
#         print(f"Input: {item}")
#         print(normalize_query_v2(item))
#         print("-" * 50)
            