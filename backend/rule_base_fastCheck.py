import re
import unicodedata
from functools import lru_cache
from typing import List, Tuple, Dict, Optional


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize(text: str) -> str:
    t = text.lower().strip()
    t = strip_accents(t).replace("đ", "d")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


@lru_cache(maxsize=1024)
def _phrase_regex(kw: str):
    return re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")


def contains_phrase(q: str, kw: str) -> bool:
    return _phrase_regex(kw).search(q) is not None


def score_keywords(q: str, strong: List[str], med: List[str]) -> Tuple[int, List[Tuple[str, str, int]]]:
    score = 0
    hits: List[Tuple[str, str, int]] = []

    for kw in strong:
        if contains_phrase(q, kw):
            score += 3
            hits.append(("strong", kw, 3))

    for kw in med:
        if contains_phrase(q, kw):
            score += 2
            hits.append(("medium", kw, 2))

    return score, hits


# =========================
# 1. Nhóm chu_de_cam
# =========================
BANNED_STRONG = [
    "danh bom", "che tao bom", "lam bom", "mua ma tuy", "ban ma tuy",
    "hack facebook", "hack tai khoan", "lam giay to gia", "giay to gia",
    "gia chu ky", "lam gia con dau", "ma doc", "virus may tinh",
    "tan cong ddos", "che tao no", "hack wifi", "chiem doat tai khoan",
    "tan cong mang", "vu khi tu che", "thuoc doc", "mua sung",
]

BANNED_MED = [
    "hack", "ma tuy", "bom", "vu khi", "ddos", "virus", "xam nhap trai phep",
]


# =========================
# 2. Nhóm tuong_tac
# =========================
INTERACT_GREETING_STRONG = [
    "xin chao", "chao", "hello", "hi", "alo", "chao ban", "bot oi", "ad oi",
]
INTERACT_GREETING_MED = [
    "xin chao ban", "helo", "hello bot", "chao ad", "xin chao bot",
]

INTERACT_THANKS_BYE_STRONG = [
    "cam on", "cam on ban", "thank you", "ok cam on", "tam biet", "bye", "goodbye", "thanks",
]
INTERACT_THANKS_BYE_MED = [
    "cam on nhe", "hen gap lai",
]

INTERACT_BOT_CAPABILITY_STRONG = [
    "ban la ai", "ban co the lam gi", "ban giup duoc gi",
    "co ai tra loi khong", "bot co ho tro gi", "bot lam duoc gi",
]
INTERACT_BOT_CAPABILITY_MED = [
    "ban ho tro duoc gi", "day la bot gi", "giup duoc gi",
]

INTERACT_COMPLAINT_STRONG = [
    "tra loi cham", "sao khong tra loi", "tra loi kho hieu",
    "tra loi chan", "ho tro te", "tra loi khong dung",
    "toi hoi mai khong duoc", "bot loi", "phan hoi cham",
]
INTERACT_COMPLAINT_MED = [
    "tra loi lau", "bot cham", "khong hieu gi", "noi kho hieu",
    "khong dung y", "tra loi linh tinh", "ho tro kem",
]

INTERACT_INSULT_STRONG = [
    "bot ngu", "may ngu", "tra loi ngu", "do vo dung", "ngu nhu bo",
]
INTERACT_INSULT_MED = [
    "ngu", "dien a", "xam", "ngu vay", "vo dung",
]


# =========================
# 3. Tín hiệu nghiệp vụ
# Có các tín hiệu này thì không bắt thành tuong_tac
# =========================
BUSINESS_HINTS = [
    "o dau", "dia chi", "so dien thoai", "lien he", "thu tuc", "ho so",
    "giay to", "bao lau", "le phi", "nop", "dang ky", "cap lai", "xac nhan",
    "khai sinh", "ket hon", "tam tru", "cu tru", "can cuoc", "phan anh",
    "kien nghi", "khieu nai", "to cao", "ubnd", "xa", "phuong",
]


PURE_SOCIAL_PATTERNS = [
    r"^(xin chao|chao|hello|hi|alo|chao ban|bot oi|ad oi|xin chao bot)$",
    r"^(cam on|cam on ban|thank you|ok cam on|tam biet|bye|goodbye|thanks)$",
]

PURE_SOCIAL_REGEXES = [re.compile(pat) for pat in PURE_SOCIAL_PATTERNS]
PURE_SOCIAL_THANKS_BYE_REGEX = re.compile(PURE_SOCIAL_PATTERNS[1])
ILLICIT_INTENT_REGEX = re.compile(r"\b(cach|lam sao|lam sao de|huong dan|chi toi|mua o dau|tao|che tao)\b")
ILLICIT_TARGET_REGEX = re.compile(r"\b(hack|bom|ma tuy|vu khi|ddos|virus|giay to gia)\b")


def classify_interaction_subtype(
    q: str,
    token_count: int
) -> Tuple[Optional[str], int, List[Tuple[str, str, int]], bool]:
    """
    Trả về:
    - interaction_type
    - interact_score
    - interact_hits
    - has_business_signal
    """
    has_business_signal = any(contains_phrase(q, kw) for kw in BUSINESS_HINTS)

    greet_score, greet_hits = score_keywords(q, INTERACT_GREETING_STRONG, INTERACT_GREETING_MED)
    thanks_score, thanks_hits = score_keywords(q, INTERACT_THANKS_BYE_STRONG, INTERACT_THANKS_BYE_MED)
    bot_score, bot_hits = score_keywords(q, INTERACT_BOT_CAPABILITY_STRONG, INTERACT_BOT_CAPABILITY_MED)
    complaint_score, complaint_hits = score_keywords(q, INTERACT_COMPLAINT_STRONG, INTERACT_COMPLAINT_MED)
    insult_score, insult_hits = score_keywords(q, INTERACT_INSULT_STRONG, INTERACT_INSULT_MED)

    for pat in PURE_SOCIAL_REGEXES:
        if pat.fullmatch(q):
            if PURE_SOCIAL_THANKS_BYE_REGEX.fullmatch(q):
                thanks_score += 2
                thanks_hits.append(("pattern", "pure_social_thanks_bye", 2))
            else:
                greet_score += 2
                greet_hits.append(("pattern", "pure_social_greeting", 2))

    is_short = token_count <= 8

    # Ưu tiên subtype mạnh hơn trước
    if insult_score >= 4 and is_short and not has_business_signal:
        return "xuc_pham", insult_score, insult_hits, has_business_signal

    if complaint_score >= 3 and is_short and not has_business_signal:
        return "phan_nan", complaint_score, complaint_hits, has_business_signal

    if bot_score >= 3 and not has_business_signal:
        return "hoi_kha_nang_bot", bot_score, bot_hits, has_business_signal

    if thanks_score >= 3 and is_short and not has_business_signal:
        return "cam_on_tam_biet", thanks_score, thanks_hits, has_business_signal

    if greet_score >= 3 and is_short and not has_business_signal:
        return "chao_hoi", greet_score, greet_hits, has_business_signal

    return None, 0, [], has_business_signal


def classify_category_fast(query: str) -> Dict:
    q = normalize(query)
    token_count = len(q.split())

    banned_score, banned_hits = score_keywords(q, BANNED_STRONG, BANNED_MED)

    # Bonus khi có ý đồ thực hiện hành vi cấm
    if ILLICIT_INTENT_REGEX.search(q):
        if ILLICIT_TARGET_REGEX.search(q):
            banned_score += 2
            banned_hits.append(("pattern", "illicit_intent", 2))

    # 1) Ưu tiên chu_de_cam
    if banned_score >= 4:
        return {
            "label": "chu_de_cam",
            "interaction_type": None,
            "scores": {
                "chu_de_cam": banned_score,
                "tuong_tac": 0,
            },
            "debug_hits": {
                "chu_de_cam": banned_hits,
                "tuong_tac": [],
            },
            "normalized_query": q,
            "token_count": token_count,
            "has_business_signal": False,
        }

    # 2) Kiểm tra tuong_tac
    interaction_type, interact_score, interact_hits, has_business_signal = classify_interaction_subtype(
        q=q,
        token_count=token_count
    )

    label = "tuong_tac" if interaction_type is not None else None

    return {
        "label": label,
        "interaction_type": interaction_type,
        "scores": {
            "chu_de_cam": banned_score,
            "tuong_tac": interact_score,
        },
        "debug_hits": {
            "chu_de_cam": banned_hits,
            "tuong_tac": interact_hits,
        },
        "normalized_query": q,
        "token_count": token_count,
        "has_business_signal": has_business_signal,
    }
# if __name__ == "__main__":
#     test_cases = [
#     ("Xin chào", "tuong_tac", "chao_hoi"),
#     ("Chào bạn", "tuong_tac", "chao_hoi"),
#     ("hello", "tuong_tac", "chao_hoi"),
#     ("hi", "tuong_tac", "chao_hoi"),
#     ("alo", "tuong_tac", "chao_hoi"),
#     ("bot ơi", "tuong_tac", "chao_hoi"),
#     ("ad ơi", "tuong_tac", "chao_hoi"),

#     ("Cảm ơn", "tuong_tac", "cam_on_tam_biet"),
#     ("Cảm ơn bạn", "tuong_tac", "cam_on_tam_biet"),
#     ("ok cảm ơn", "tuong_tac", "cam_on_tam_biet"),
#     ("bye", "tuong_tac", "cam_on_tam_biet"),
#     ("tạm biệt", "tuong_tac", "cam_on_tam_biet"),
#     ("thanks", "tuong_tac", "cam_on_tam_biet"),

#     ("bạn là ai", "tuong_tac", "hoi_kha_nang_bot"),
#     ("bạn có thể làm gì", "tuong_tac", "hoi_kha_nang_bot"),
#     ("bot có hỗ trợ gì", "tuong_tac", "hoi_kha_nang_bot"),
#     ("có ai trả lời không", "tuong_tac", "hoi_kha_nang_bot"),
#     ("bot làm được gì", "tuong_tac", "hoi_kha_nang_bot"),

#     ("trả lời chậm", "tuong_tac", "phan_nan"),
#     ("sao không trả lời", "tuong_tac", "phan_nan"),
#     ("trả lời khó hiểu", "tuong_tac", "phan_nan"),
#     ("trả lời không đúng", "tuong_tac", "phan_nan"),
#     ("bot lỗi", "tuong_tac", "phan_nan"),
#     ("hỗ trợ tệ", "tuong_tac", "phan_nan"),
#     ("phản hồi chậm", "tuong_tac", "phan_nan"),

#     ("bot ngu", "tuong_tac", "xuc_pham"),
#     ("mày ngu", "tuong_tac", "xuc_pham"),
#     ("trả lời ngu", "tuong_tac", "xuc_pham"),
#     ("đồ vô dụng", "tuong_tac", "xuc_pham"),
#     ("ngu vậy", "tuong_tac", "xuc_pham"),
#     ("ngu như bò", "tuong_tac", "xuc_pham"),

#     ("xin chào, tôi cần biết xã nằm ở đâu", None, None),
#     ("chào bạn, thủ tục khai sinh thế nào", None, None),
#     ("bot ơi cho tôi hỏi địa chỉ ubnd ở đâu", None, None),
#     ("cảm ơn, cho tôi hỏi lệ phí đăng ký khai sinh", None, None),
#     ("bye, nhưng cho tôi xin số điện thoại liên hệ", None, None),
#     ("bạn có thể làm gì cho tôi về thủ tục khai sinh", None, None),
#     ("trả lời chậm quá, tôi muốn phản ánh cán bộ", None, None),
#     ("ngu vậy nhưng cho tôi hỏi thủ tục kết hôn", None, None),

#     ("cách hack facebook", "chu_de_cam", None),
#     ("làm sao để hack wifi", "chu_de_cam", None),
#     ("mua ma túy ở đâu", "chu_de_cam", None),
#     ("chế tạo bom như thế nào", "chu_de_cam", None),
#     ("giấy tờ giả làm sao", "chu_de_cam", None),

#     ("cho tôi biết địa chỉ ủy ban", None, None),
#     ("thủ tục khai sinh cần gì", None, None),
#     ("tôi muốn phản ánh đường hư", None, None),
#     ("hồ sơ đăng ký tạm trú gồm gì", None, None),
#     ("lệ phí cấp lại căn cước là bao nhiêu", None, None),
#     ("xin chào bot", "tuong_tac", "chao_hoi"),
# ]

#     for i, (query, exp_label, exp_type) in enumerate(test_cases, 1):
#         result = classify_category_fast(query)
#         print(f"Question: {query}")
#         print(f"Label: {result['label']}")
#         print(f"Interaction type: {result['interaction_type']}")
#         print(f"Scores: {result['scores']}")
#         print(f"Debug hits: {result['debug_hits']}")
#         print("-" * 80)