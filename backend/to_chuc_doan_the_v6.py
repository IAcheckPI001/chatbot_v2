import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Set, Dict, Optional


# =========================================================
# 0) NORMALIZE
# =========================================================

def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# =========================================================
# 1) ORGANIZATION KEYWORDS
# =========================================================

ORGANIZATION_TYPE_KEYWORDS = {
    "doan_thanh_nien": {
        "strong": [
            "doan thanh nien",
            "doan thanh nien cong san ho chi minh",
            "doan tn",
            "dtn",
            "chi doan",
            "bi thu doan",
            "pho bi thu doan",
            "bi thu chi doan",
            "pho bi thu chi doan",
            "doan phi",
            "chuyen sinh hoat doan",
            "hoc cam tinh doan",
            "lop cam tinh doan",
            "doan vien"
        ],
        "weak": [
            "vao doan",
            "tham gia doan",
            "ket nap doan",
            "sinh hoat doan",
            "chuyen doan",
            "giay chuyen doan",
            "nghia vu doan vien",
            "quyen loi doan vien",
            "loi ich doan vien",
            "cap lai doan",
            "mat so doan",
            "the doan",
            "so doan",
            "xoa ten doan",
        ],
    },
    "cong_doan": {
        "strong": [
            "cong doan",
            "cong doan co so",
            "chu tich cong doan",
            "pho chu tich cong doan",
            "kinh phi cong doan",
            "cong doan phi",
            "quyen loi cong doan",
        ],
        "weak": [
            "cong doan vien",
            "gia nhap cong doan",
            "tham gia cong doan",
            "vao cong doan",
            "phi cong doan",
            "2 phan tram cong doan",
            "dong cong doan",
        ],
    },
    "hoi_phu_nu": {
        "strong": [
            "hoi phu nu",
            "hoi lien hiep phu nu",
            "hlhpn",
            "chi hoi phu nu",
            "chu tich hoi phu nu",
            "hoi phi phu nu",
        ],
        "weak": [
            "hoi vien phu nu",
            "tham gia hoi phu nu",
            "sinh hoat hoi phu nu",
            "quyen loi hoi vien",
        ],
    },
    "mttq": {
        "strong": [
            "mttq",
            "mat tran to quoc",
            "uy ban mat tran to quoc",
            "uy ban mat tran",
            "chu tich mttq",
            "chu tich mat tran",
        ],
        "weak": [
            "mat tran",
            "pho chu tich mat tran",
            "tham gia mat tran",
            "ho tro cua mat tran",
        ],
    },
    "ubnd": {
        "strong": [
            "ubnd",
            "uy ban nhan dan",
            "uy ban",
            "tru so ubnd",
            "tru so uy ban",
            "van phong ubnd",
            "ubnd xa",
            "ubnd phuong",
            "ubnd thi tran",
        ],
        "weak": [
            "phuong",
            "xa",
            "thi tran",
            "uy ban xa",
            "uy ban phuong",
            "uy ban thi tran",
        ],
    },
    "dang_uy": {
        "strong": [
            "dang uy",
            "dang bo",
            "chi bo",
            "bi thu dang uy",
            "pho bi thu dang uy",
            "bi thu chi bo",
            "pho bi thu chi bo",
            "sinh hoat dang",
            "chuyen sinh hoat dang",
            "dang phi",
        ],
        "weak": [
            "dang vien",
            "chi uy",
            "nghi quyet",
            "ket nap dang",
            "sinh hoat chi bo",
        ],
    },
}

AMBIGUOUS_WEAK_KEYWORDS = {
    "doan vien",
    "hoi vien",
    "dang vien",
}

SAFE_WEAK_KEYWORD_SCORE = 1.5
AMBIGUOUS_WEAK_KEYWORD_SCORE = 0.75
STRONG_KEYWORD_SCORE = 3


# =========================================================
# 2) ORGANIZATION -> ALLOWED INTENTS
# =========================================================

ORG_INTENTS = {
    "ubnd": {
        "tra_cuu_thong_tin",
        "hoi_nhan_su",
        "hoi_thu_tuc",
        "phan_anh_kien_nghi",
    },
    "dang_uy": {
        "tra_cuu_thong_tin",
        "hoi_nhan_su",
        "sinh_hoat_dang",
    },
    "doan_thanh_nien": {
        "tra_cuu_thong_tin",
        "hoi_nhan_su",
        "quyen_loi_ho_tro",
        "tham_gia_to_chuc",
    },
    "hoi_phu_nu": {
        "tra_cuu_thong_tin",
        "hoi_nhan_su",
        "quyen_loi_ho_tro",
        "tham_gia_to_chuc",
    },
    "mttq": {
        "tra_cuu_thong_tin",
        "hoi_nhan_su",
        "quyen_loi_ho_tro",
        "tham_gia_to_chuc",
    },
    "cong_doan": {
        "tra_cuu_thong_tin",
        "hoi_nhan_su",
        "quyen_loi_ho_tro",
        "tham_gia_to_chuc",
        "phan_anh_kien_nghi"
    },
}


HIGH_PRECISION_INTENTS = {
    "hoi_nhan_su",
    "hoi_thu_tuc",
    "phan_anh_kien_nghi",
    "sinh_hoat_dang",
    "quyen_loi_ho_tro",
    "tham_gia_to_chuc",
}

LOW_PRECISION_INTENTS = {
    "tra_cuu_thong_tin",
}


# =========================================================
# 3) INTENT KEYWORDS
# =========================================================

INTENT_KEYWORDS_COMMON = {
    "tra_cuu_thong_tin": [
        "tong quan",
        "la to chuc gi",
        "chuc nang",
        "nhiem vu",
        "vai tro",
        "dia chi",
        "so dien thoai",
        "email",
        "website",
        "hotline",
        "gio lam viec",
        "o dau",
        "co cau",
        "bo phan",
        "thong tin",
        "hoat dong gi",
        "thong tin chung",
        "doi tuong",
        "doi tuong phuc vu"
    ],
    "hoi_nhan_su": [
        "ai dung dau",
        "lanh dao",
        "chu tich",
        "pho chu tich",
        "bi thu",
        "pho bi thu",
        "uy vien",
        "can bo",
        "ban chap hanh",
        "truong ban",
        "pho ban",
        "giu chuc gi",
        "danh sach lanh dao",
    ],
}

INTENT_KEYWORDS_UBND = {
    "hoi_thu_tuc": [
        "thu tuc",
        "ho so",
        "giay to",
        "can gi",
        "quy trinh",
        "dieu kien",
        "nop o dau",
        "nop online",
        "thoi gian giai quyet",
        "le phi",
        "phi",
        "mau don",
        "mau to khai",
        "dang ky",
        "xac nhan",
        "cap lai",
        "xin",
    ],
    "phan_anh_kien_nghi": [
        "phan anh",
        "kien nghi",
        "khieu nai",
        "to cao",
        "gop y",
        "phan anh hien truong",
        "bao cao vi pham",
    ],
}

INTENT_KEYWORDS_CONG_DOAN_COMPLAINT = {
    "phan_anh_kien_nghi": [
        "phan anh",
        "kien nghi",
        "khieu nai",
        "to cao",
        "bao cao vi pham",
        "cham dong bhxh",
        "no bhxh",
        "khong dong bhxh",
        "bao hiem xa hoi",
        "tien luong",
        "no luong",
        "cham luong",
        "khong tra luong",
        "hop dong lao dong",
        "dieu kien lao dong",
        "quay roi noi lam viec",
        "sa thai trai luat",
        "cho thoi viec trai luat",
    ]
}

INTENT_KEYWORDS_DANG_UY = {
    "sinh_hoat_dang": [
        "sinh hoat dang",
        "chuyen sinh hoat dang",
        "dang vien",
        "chi bo",
        "chi uy",
        "dang phi",
        "ket nap dang",
        "hoc nghi quyet",
        "nghi quyet",
        "xep loai dang vien",
        "sinh hoat chi bo",
    ],
}

INTENT_KEYWORDS_MASS_ORGS = {
    "quyen_loi_ho_tro": [
        "quyen loi",
        "loi ich",
        "duoc gi",
        "huong gi",
        "ho tro gi",
        "che do",
        "bao ve ai",
        "co quyen gi",
        "tro cap",
        "nghia vu",
        "trach nhiem",
    ],
    "tham_gia_to_chuc": [
        "tham gia",
        "gia nhap",
        "ket nap",
        "dieu kien tham gia",
        "thu tuc vao",
        "quy trinh tham gia",
        "chuyen sinh hoat",
        "chuyen doan",
        "hoc cam tinh",
        "lop cam tinh",
        "vao doan",
        "vao cong doan",
        "vao hoi phu nu",
        "tham gia mat tran",
    ],
}


# =========================================================
# 4) TOPIC HINTS
# =========================================================

TOPIC_TO_ORG = {
    "ket_nap_doan": "doan_thanh_nien",
    "doan_phi": "doan_thanh_nien",
    "cap_lai_ho_so_doan": "doan_thanh_nien",
    "chuyen_sinh_hoat_doan": "doan_thanh_nien",
    "nghia_vu_doan_vien": "doan_thanh_nien",
    "loi_ich_doan_vien": "doan_thanh_nien",
    "hoc_cam_tinh_doan": "doan_thanh_nien",
    "xoa_ten_doan": "doan_thanh_nien",

    "ket_nap_cong_doan": "cong_doan",
    "kinh_phi_cong_doan": "cong_doan",
    "quyen_loi_cong_doan_vien": "cong_doan",
    "co_cau_lanh_dao_cong_doan": "cong_doan",

    "tham_gia_hoi_phu_nu": "hoi_phu_nu",
    "hoi_phi_phu_nu": "hoi_phu_nu",
    "quyen_loi_hoi_vien": "hoi_phu_nu",

    "sinh_hoat_dang_chi_tiet": "dang_uy",
}

TOPIC_TO_INTENT = {
    "ket_nap_doan": "tham_gia_to_chuc",
    "doan_phi": "quyen_loi_ho_tro",
    "cap_lai_ho_so_doan": "tham_gia_to_chuc",
    "chuyen_sinh_hoat_doan": "tham_gia_to_chuc",
    "nghia_vu_doan_vien": "quyen_loi_ho_tro",
    "loi_ich_doan_vien": "quyen_loi_ho_tro",
    "hoc_cam_tinh_doan": "tham_gia_to_chuc",
    "xoa_ten_doan": "quyen_loi_ho_tro",

    "ket_nap_cong_doan": "tham_gia_to_chuc",
    "kinh_phi_cong_doan": "quyen_loi_ho_tro",
    "quyen_loi_cong_doan_vien": "quyen_loi_ho_tro",
    "co_cau_lanh_dao_cong_doan": "hoi_nhan_su",

    "tham_gia_hoi_phu_nu": "tham_gia_to_chuc",
    "hoi_phi_phu_nu": "quyen_loi_ho_tro",
    "quyen_loi_hoi_vien": "quyen_loi_ho_tro",

    "sinh_hoat_dang_chi_tiet": "sinh_hoat_dang",
}


# =========================================================
# 5) SPAN-BASED MATCHER
# =========================================================

@dataclass
class PhraseMatch:
    text: str
    kind: str
    label: str
    priority: int
    start: int
    end: int


def phrase_pattern(phrase: str) -> str:
    return r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"


PHRASE_DEFS = [
    # =====================================================
    # TOPIC - VERY STRONG
    # =====================================================

    {"text": "cong doan phi", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "2 phan tram cong doan", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "kinh phi cong doan", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "ai phai dong cong doan", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "nguoi lao dong co dong cong doan khong", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "cong ty dong cong doan bao nhieu", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "khong dong cong doan co bi phat khong", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "cong ty khong dong cong doan bi gi", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},
    {"text": "tron dong cong doan co sao khong", "kind": "topic", "label": "kinh_phi_cong_doan", "priority": 100},

    {"text": "lam lai the doan vien", "kind": "topic", "label": "cap_lai_ho_so_doan", "priority": 100},
    {"text": "lam lai so doan", "kind": "topic", "label": "cap_lai_ho_so_doan", "priority": 100},
    {"text": "mat the doan vien", "kind": "topic", "label": "cap_lai_ho_so_doan", "priority": 100},
    {"text": "mat so doan", "kind": "topic", "label": "cap_lai_ho_so_doan", "priority": 100},
    {"text": "mat ho so doan", "kind": "topic", "label": "cap_lai_ho_so_doan", "priority": 100},
    {"text": "cap lai ho so doan", "kind": "topic", "label": "cap_lai_ho_so_doan", "priority": 100},
    {"text": "lam lai ho so doan", "kind": "topic", "label": "cap_lai_ho_so_doan", "priority": 100},

    {"text": "mat giay chuyen doan", "kind": "topic", "label": "chuyen_sinh_hoat_doan", "priority": 100},
    {"text": "chuyen truong co can chuyen doan", "kind": "topic", "label": "chuyen_sinh_hoat_doan", "priority": 100},
    {"text": "chuyen sinh hoat doan", "kind": "topic", "label": "chuyen_sinh_hoat_doan", "priority": 95},
    {"text": "giay chuyen doan", "kind": "topic", "label": "chuyen_sinh_hoat_doan", "priority": 95},
    {"text": "chuyen doan", "kind": "topic", "label": "chuyen_sinh_hoat_doan", "priority": 85},

    {"text": "thu tuc ket nap doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "quy trinh ket nap doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "ai duoc ket nap doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "bao lau duoc ket nap doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "bao lau xet vao doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "dieu kien vao doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "bao nhieu tuoi duoc vao doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "15 tuoi vao doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "16 tuoi vao doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "30 tuoi vao doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "qua tuoi doan", "kind": "topic", "label": "ket_nap_doan", "priority": 100},
    {"text": "ket nap doan", "kind": "topic", "label": "ket_nap_doan", "priority": 95},
    {"text": "vao doan", "kind": "topic", "label": "ket_nap_doan", "priority": 85},

    {"text": "hoc cam tinh doan", "kind": "topic", "label": "hoc_cam_tinh_doan", "priority": 100},
    {"text": "lop cam tinh doan", "kind": "topic", "label": "hoc_cam_tinh_doan", "priority": 100},
    {"text": "hoc lop doan", "kind": "topic", "label": "hoc_cam_tinh_doan", "priority": 95},

    {"text": "dong doan phi", "kind": "topic", "label": "doan_phi", "priority": 100},
    {"text": "mien doan phi", "kind": "topic", "label": "doan_phi", "priority": 100},
    {"text": "doan phi", "kind": "topic", "label": "doan_phi", "priority": 90},

    {"text": "quyen loi doan vien", "kind": "topic", "label": "loi_ich_doan_vien", "priority": 100},
    {"text": "loi ich doan vien", "kind": "topic", "label": "loi_ich_doan_vien", "priority": 100},
    {"text": "doan vien duoc gi", "kind": "topic", "label": "loi_ich_doan_vien", "priority": 100},
    {"text": "doan vien co loi ich gi", "kind": "topic", "label": "loi_ich_doan_vien", "priority": 100},

    {"text": "nghia vu doan vien", "kind": "topic", "label": "nghia_vu_doan_vien", "priority": 100},
    {"text": "doan vien co nghia vu gi", "kind": "topic", "label": "nghia_vu_doan_vien", "priority": 100},
    {"text": "doan vien phai lam gi", "kind": "topic", "label": "nghia_vu_doan_vien", "priority": 100},
    {"text": "khong sinh hoat doan co sao khong", "kind": "topic", "label": "nghia_vu_doan_vien", "priority": 95},

    {"text": "co bi xoa ten doan khong", "kind": "topic", "label": "xoa_ten_doan", "priority": 100},
    {"text": "khi nao bi xoa doan", "kind": "topic", "label": "xoa_ten_doan", "priority": 100},
    {"text": "xoa ten doan", "kind": "topic", "label": "xoa_ten_doan", "priority": 95},
    {"text": "bi xoa doan", "kind": "topic", "label": "xoa_ten_doan", "priority": 95},

    {"text": "co bat buoc tham gia cong doan khong", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 100},
    {"text": "khong vao cong doan co sao khong", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 100},
    {"text": "nguoi lao dong co phai vao cong doan khong", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 100},
    {"text": "thu tuc vao cong doan", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 100},
    {"text": "dieu kien tham gia cong doan", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 100},
    {"text": "lam sao de vao cong doan", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 100},
    {"text": "gia nhap cong doan", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 95},
    {"text": "vao cong doan", "kind": "topic", "label": "ket_nap_cong_doan", "priority": 90},

    {"text": "cong doan bao ve ai", "kind": "topic", "label": "quyen_loi_cong_doan_vien", "priority": 100},
    {"text": "cong doan co quyen gi", "kind": "topic", "label": "quyen_loi_cong_doan_vien", "priority": 100},
    {"text": "quyen loi cong doan vien", "kind": "topic", "label": "quyen_loi_cong_doan_vien", "priority": 95},
    {"text": "quyen loi cong doan", "kind": "topic", "label": "quyen_loi_cong_doan_vien", "priority": 90},

    {"text": "ai dung dau cong doan", "kind": "topic", "label": "co_cau_lanh_dao_cong_doan", "priority": 100},
    {"text": "pho chu tich cong doan", "kind": "topic", "label": "co_cau_lanh_dao_cong_doan", "priority": 95},
    {"text": "chu tich cong doan", "kind": "topic", "label": "co_cau_lanh_dao_cong_doan", "priority": 90},

    {"text": "tham gia hoi phu nu", "kind": "topic", "label": "tham_gia_hoi_phu_nu", "priority": 95},
    {"text": "vao hoi phu nu", "kind": "topic", "label": "tham_gia_hoi_phu_nu", "priority": 95},
    {"text": "ket nap hoi phu nu", "kind": "topic", "label": "tham_gia_hoi_phu_nu", "priority": 95},

    {"text": "hoi phi phu nu", "kind": "topic", "label": "hoi_phi_phu_nu", "priority": 95},

    {"text": "quyen loi hoi vien", "kind": "topic", "label": "quyen_loi_hoi_vien", "priority": 95},
    {"text": "quyen loi hoi vien phu nu", "kind": "topic", "label": "quyen_loi_hoi_vien", "priority": 95},

    {"text": "sinh hoat dang", "kind": "topic", "label": "sinh_hoat_dang_chi_tiet", "priority": 100},
    {"text": "chuyen sinh hoat dang", "kind": "topic", "label": "sinh_hoat_dang_chi_tiet", "priority": 100},
    {"text": "dang phi", "kind": "topic", "label": "sinh_hoat_dang_chi_tiet", "priority": 95},
    {"text": "ket nap dang", "kind": "topic", "label": "sinh_hoat_dang_chi_tiet", "priority": 95},
    {"text": "dang vien", "kind": "topic", "label": "sinh_hoat_dang_chi_tiet", "priority": 75},

    # =====================================================
    # ORGANIZATION
    # =====================================================

    {"text": "doan thanh nien cong san ho chi minh", "kind": "organization", "label": "doan_thanh_nien", "priority": 70},
    {"text": "doan thanh nien", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "doan tn", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "dtn", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "chi doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "bi thu doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "pho bi thu doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "bi thu chi doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 72},
    {"text": "pho bi thu chi doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 72},
    {"text": "doan vien", "kind": "organization", "label": "doan_thanh_nien", "priority": 45},

    {"text": "cong doan co so", "kind": "organization", "label": "cong_doan", "priority": 70},
    {"text": "cong doan", "kind": "organization", "label": "cong_doan", "priority": 60},

    {"text": "hoi lien hiep phu nu", "kind": "organization", "label": "hoi_phu_nu", "priority": 70},
    {"text": "chi hoi phu nu", "kind": "organization", "label": "hoi_phu_nu", "priority": 70},
    {"text": "hoi phu nu", "kind": "organization", "label": "hoi_phu_nu", "priority": 60},
    {"text": "hlhpn", "kind": "organization", "label": "hoi_phu_nu", "priority": 60},

    {"text": "uy ban mat tran to quoc", "kind": "organization", "label": "mttq", "priority": 75},
    {"text": "mat tran to quoc", "kind": "organization", "label": "mttq", "priority": 70},
    {"text": "uy ban mat tran", "kind": "organization", "label": "mttq", "priority": 72},
    {"text": "chu tich mat tran", "kind": "organization", "label": "mttq", "priority": 72},
    {"text": "pho chu tich mat tran", "kind": "organization", "label": "mttq", "priority": 68},
    {"text": "mttq", "kind": "organization", "label": "mttq", "priority": 60},
    {"text": "mat tran", "kind": "organization", "label": "mttq", "priority": 52},

    {"text": "uy ban nhan dan", "kind": "organization", "label": "ubnd", "priority": 75},
    {"text": "tru so uy ban", "kind": "organization", "label": "ubnd", "priority": 75},
    {"text": "van phong ubnd", "kind": "organization", "label": "ubnd", "priority": 75},
    {"text": "uy ban xa", "kind": "organization", "label": "ubnd", "priority": 72},
    {"text": "uy ban phuong", "kind": "organization", "label": "ubnd", "priority": 72},
    {"text": "uy ban thi tran", "kind": "organization", "label": "ubnd", "priority": 72},
    {"text": "uy ban", "kind": "organization", "label": "ubnd", "priority": 55},

    {"text": "bi thu dang uy", "kind": "organization", "label": "dang_uy", "priority": 75},
    {"text": "pho bi thu dang uy", "kind": "organization", "label": "dang_uy", "priority": 75},
    {"text": "bi thu chi bo", "kind": "organization", "label": "dang_uy", "priority": 75},
    {"text": "pho bi thu chi bo", "kind": "organization", "label": "dang_uy", "priority": 75},
    {"text": "dang uy", "kind": "organization", "label": "dang_uy", "priority": 70},
    {"text": "dang bo", "kind": "organization", "label": "dang_uy", "priority": 65},
    {"text": "chi bo", "kind": "organization", "label": "dang_uy", "priority": 65},

    # =====================================================
    # INTENT DIRECT PHRASES
    # =====================================================

    {"text": "ai dung dau", "kind": "intent", "label": "hoi_nhan_su", "priority": 80},
    {"text": "dung dau la ai", "kind": "intent", "label": "hoi_nhan_su", "priority": 80},
    {"text": "ai la ai", "kind": "intent", "label": "hoi_nhan_su", "priority": 80},
    {"text": "la ai", "kind": "intent", "label": "hoi_nhan_su", "priority": 60},
    {"text": "lanh dao", "kind": "intent", "label": "hoi_nhan_su", "priority": 70},
    {"text": "chu tich", "kind": "intent", "label": "hoi_nhan_su", "priority": 60},
    {"text": "pho chu tich", "kind": "intent", "label": "hoi_nhan_su", "priority": 60},
    {"text": "bi thu", "kind": "intent", "label": "hoi_nhan_su", "priority": 65},
    {"text": "pho bi thu", "kind": "intent", "label": "hoi_nhan_su", "priority": 65},
    {"text": "giu chuc gi", "kind": "intent", "label": "hoi_nhan_su", "priority": 75},
    {"text": "danh sach lanh dao", "kind": "intent", "label": "hoi_nhan_su", "priority": 80},

    {"text": "thu tuc", "kind": "intent", "label": "hoi_thu_tuc", "priority": 85},
    {"text": "ho so", "kind": "intent", "label": "hoi_thu_tuc", "priority": 75},
    {"text": "giay to", "kind": "intent", "label": "hoi_thu_tuc", "priority": 75},
    {"text": "quy trinh", "kind": "intent", "label": "hoi_thu_tuc", "priority": 75},
    {"text": "dieu kien", "kind": "intent", "label": "hoi_thu_tuc", "priority": 75},
    {"text": "thoi gian giai quyet", "kind": "intent", "label": "hoi_thu_tuc", "priority": 85},
    {"text": "le phi", "kind": "intent", "label": "hoi_thu_tuc", "priority": 80},
    {"text": "mau don", "kind": "intent", "label": "hoi_thu_tuc", "priority": 80},
    {"text": "mau to khai", "kind": "intent", "label": "hoi_thu_tuc", "priority": 80},
    {"text": "nop o dau", "kind": "intent", "label": "hoi_thu_tuc", "priority": 80},
    {"text": "cap lai", "kind": "intent", "label": "hoi_thu_tuc", "priority": 70},
    {"text": "xac nhan", "kind": "intent", "label": "hoi_thu_tuc", "priority": 70},

    {"text": "phan anh", "kind": "intent", "label": "phan_anh_kien_nghi", "priority": 90},
    {"text": "kien nghi", "kind": "intent", "label": "phan_anh_kien_nghi", "priority": 90},
    {"text": "khieu nai", "kind": "intent", "label": "phan_anh_kien_nghi", "priority": 90},
    {"text": "to cao", "kind": "intent", "label": "phan_anh_kien_nghi", "priority": 90},
    {"text": "gop y", "kind": "intent", "label": "phan_anh_kien_nghi", "priority": 75},
    {"text": "phan anh hien truong", "kind": "intent", "label": "phan_anh_kien_nghi", "priority": 100},

    {"text": "quyen loi", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 75},
    {"text": "loi ich", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 75},
    {"text": "duoc gi", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 65},
    {"text": "huong gi", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 65},
    {"text": "ho tro gi", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 80},
    {"text": "co quyen gi", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 80},
    {"text": "bao ve ai", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 80},
    {"text": "che do", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 70},
    {"text": "tro cap", "kind": "intent", "label": "quyen_loi_ho_tro", "priority": 70},

    {"text": "tham gia", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 70},
    {"text": "gia nhap", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 80},
    {"text": "ket nap", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 85},
    {"text": "thu tuc vao", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 80},
    {"text": "quy trinh tham gia", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 80},
    {"text": "chuyen sinh hoat", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 70},
    {"text": "hoc cam tinh", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 80},
    {"text": "dieu kien tham gia", "kind": "intent", "label": "tham_gia_to_chuc", "priority": 85},

    {"text": "sinh hoat dang", "kind": "intent", "label": "sinh_hoat_dang", "priority": 95},
    {"text": "chuyen sinh hoat dang", "kind": "intent", "label": "sinh_hoat_dang", "priority": 100},
    {"text": "dang phi", "kind": "intent", "label": "sinh_hoat_dang", "priority": 95},
    {"text": "ket nap dang", "kind": "intent", "label": "sinh_hoat_dang", "priority": 90},
    {"text": "hoc nghi quyet", "kind": "intent", "label": "sinh_hoat_dang", "priority": 90},
    {"text": "nghi quyet", "kind": "intent", "label": "sinh_hoat_dang", "priority": 70},

    {"text": "tong quan", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 40},
    {"text": "la gi", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 25},
    {"text": "la to chuc gi", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 55},
    {"text": "chuc nang", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 40},
    {"text": "nhiem vu", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 40},
    {"text": "dia chi", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 40},
    {"text": "so dien thoai", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 40},
    {"text": "email", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 40},
    {"text": "gio lam viec", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 40},
    {"text": "o dau", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 35},
    {"text": "lam gi", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 35},
    {"text": "lam nhung viec gi", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 45},
    {"text": "hoat dong gi", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 45},
    {"text": "thong tin chung", "kind": "intent", "label": "tra_cuu_thong_tin", "priority": 45},
]

COMPILED_PHRASE_DEFS = [
    (re.compile(phrase_pattern(item["text"])), item)
    for item in PHRASE_DEFS
]


@lru_cache(maxsize=2048)
def _compiled_phrase_regex(phrase: str):
    return re.compile(phrase_pattern(phrase))


def find_phrase_matches(q_norm: str) -> List[PhraseMatch]:
    out: List[PhraseMatch] = []
    for pattern, item in COMPILED_PHRASE_DEFS:
        for m in pattern.finditer(q_norm):
            out.append(
                PhraseMatch(
                    text=item["text"],
                    kind=item["kind"],
                    label=item["label"],
                    priority=item["priority"],
                    start=m.start(),
                    end=m.end(),
                )
            )
    return out


def overlaps(a: PhraseMatch, b: PhraseMatch) -> bool:
    return not (a.end <= b.start or b.end <= a.start)


def resolve_phrase_matches(matches: List[PhraseMatch]) -> List[PhraseMatch]:
    matches = sorted(matches, key=lambda x: (-x.priority, -(x.end - x.start), x.start))
    selected: List[PhraseMatch] = []
    for m in matches:
        if not any(overlaps(m, s) for s in selected):
            selected.append(m)
    return sorted(selected, key=lambda x: x.start)


# =========================================================
# 6) HELPERS
# =========================================================

def contains_phrase(q_norm: str, phrase: str) -> bool:
    return _compiled_phrase_regex(phrase).search(q_norm) is not None


def contains_any(q_norm: str, keywords: List[str]) -> bool:
    return any(contains_phrase(q_norm, kw) for kw in keywords)


def scan_keywords_once(q_norm: str):
    raw_matches = find_phrase_matches(q_norm)
    resolved_matches = resolve_phrase_matches(raw_matches)
    return {m.text for m in resolved_matches}


def get_intent_keywords_for_org(org: str) -> Dict[str, List[str]]:
    common = {
        "tra_cuu_thong_tin": INTENT_KEYWORDS_COMMON["tra_cuu_thong_tin"],
        "hoi_nhan_su": INTENT_KEYWORDS_COMMON["hoi_nhan_su"],
    }

    if org == "ubnd":
        return {
            **common,
            "hoi_thu_tuc": INTENT_KEYWORDS_UBND["hoi_thu_tuc"],
            "phan_anh_kien_nghi": INTENT_KEYWORDS_UBND["phan_anh_kien_nghi"],
        }

    if org == "dang_uy":
        return {
            **common,
            "sinh_hoat_dang": INTENT_KEYWORDS_DANG_UY["sinh_hoat_dang"],
        }

    if org in {"doan_thanh_nien", "hoi_phu_nu", "mttq"}:
        return {
            **common,
            "quyen_loi_ho_tro": INTENT_KEYWORDS_MASS_ORGS["quyen_loi_ho_tro"],
            "tham_gia_to_chuc": INTENT_KEYWORDS_MASS_ORGS["tham_gia_to_chuc"],
        }
    
    if org == "cong_doan":
        return {
            **common,
            "quyen_loi_ho_tro": INTENT_KEYWORDS_MASS_ORGS["quyen_loi_ho_tro"],
            "tham_gia_to_chuc": INTENT_KEYWORDS_MASS_ORGS["tham_gia_to_chuc"],
            "phan_anh_kien_nghi": INTENT_KEYWORDS_CONG_DOAN_COMPLAINT["phan_anh_kien_nghi"],
        }


    return common


# =========================================================
# 7) ORGANIZATION EXTRACTION
# =========================================================

def extract_organization_type_legacy(q_norm: str, hits: Set[str]) -> dict:
    organization_scores = {}
    organization_hits = {}

    for org, groups in ORGANIZATION_TYPE_KEYWORDS.items():
        strong_hits = [kw for kw in groups["strong"] if kw in hits]
        weak_hits = [kw for kw in groups["weak"] if kw in hits]

        weak_score = 0.0
        for kw in weak_hits:
            if kw in AMBIGUOUS_WEAK_KEYWORDS:
                weak_score += AMBIGUOUS_WEAK_KEYWORD_SCORE
            else:
                weak_score += SAFE_WEAK_KEYWORD_SCORE

        score = len(strong_hits) * STRONG_KEYWORD_SCORE + weak_score
        organization_scores[org] = score
        organization_hits[org] = {
            "strong": strong_hits,
            "weak": weak_hits,
        }

    best_org = max(organization_scores, key=organization_scores.get) if organization_scores else None
    best_org_score = organization_scores.get(best_org, 0)
    top_orgs = [org for org, s in organization_scores.items() if s == best_org_score and s > 0]

    conflict = len(top_orgs) >= 2
    need_llm = False
    source = None
    organization_type = None

    if conflict:
        need_llm = True
        source = "rule_base_conflict"
    elif best_org_score >= 3:
        organization_type = best_org
        source = "rule_base_strong"
    elif best_org_score > 0:
        organization_type = best_org
        source = "rule_base_weak"
        need_llm = True
    else:
        source = "rule_base_none"
        need_llm = True

    return {
        "organization_type": organization_type,
        "organization_scores": organization_scores,
        "organization_hits": organization_hits,
        "best_organization_type": best_org,
        "best_organization_score": best_org_score,
        "conflict": conflict,
        "need_llm_organization_type": need_llm,
        "source": source,
    }


def validate_mttq_precision(
    q_norm: str,
    organization_type: Optional[str],
    organization_hits: Dict[str, Dict[str, List[str]]],
) -> bool:
    if organization_type != "mttq":
        return True

    strong_hits = organization_hits.get("mttq", {}).get("strong", [])
    weak_hits = organization_hits.get("mttq", {}).get("weak", [])

    if strong_hits:
        return True

    if "mat tran" in weak_hits:
        if contains_any(q_norm, [
            "chu tich",
            "pho chu tich",
            "ho tro",
            "quyen loi",
            "tham gia",
            "dia chi",
            "la gi",
            "la to chuc gi",
            "lam gi",
            "lam nhung viec gi",
            "hoat dong gi",
        ]):
            return True
        return False

    return False


def validate_doan_precision(
    q_norm: str,
    organization_type: Optional[str],
    organization_hits: Dict[str, Dict[str, List[str]]],
) -> bool:
    if organization_type != "doan_thanh_nien":
        return True

    strong_hits = organization_hits.get("doan_thanh_nien", {}).get("strong", [])
    if strong_hits:
        return True

    strong_context = [
        "doan vien",
        "ket nap doan",
        "vao doan",
        "chi doan",
        "bi thu doan",
        "pho bi thu doan",
        "bi thu chi doan",
        "pho bi thu chi doan",
        "doan phi",
        "chuyen doan",
        "so doan",
        "hoc cam tinh doan",
    ]

    matched_count = sum(1 for x in strong_context if contains_phrase(q_norm, x))
    return matched_count >= 2


def post_validate_organization_type(
    q_norm: str,
    organization_type: Optional[str],
    organization_hits: Dict[str, Dict[str, List[str]]],
) -> dict:
    if organization_type == "mttq":
        if not validate_mttq_precision(q_norm, organization_type, organization_hits):
            return {
                "organization_type": None,
                "need_llm_organization_type": True,
                "source": "post_validate_reject_mttq",
            }

    if organization_type == "doan_thanh_nien":
        if not validate_doan_precision(q_norm, organization_type, organization_hits):
            return {
                "organization_type": None,
                "need_llm_organization_type": True,
                "source": "post_validate_reject_doan",
            }
    

    return {
        "organization_type": organization_type,
        "need_llm_organization_type": False,
        "source": "post_validate_accept",
    }


def extract_topic_hint_v7(resolved_matches: List[PhraseMatch]) -> dict:
    topics = [m for m in resolved_matches if m.kind == "topic"]

    if not topics:
        return {
            "topic_hint": None,
            "topic_hint_score": 0,
            "topic_hint_hits": [],
            "topic_scores": {},
            "topic_conflict": False,
            "topic_source": "none",
        }

    top = topics[0]
    second = topics[1] if len(topics) > 1 else None

    topic_conflict = False
    if second and second.priority == top.priority and second.label != top.label:
        topic_conflict = True

    return {
        "topic_hint": None if topic_conflict else top.label,
        "topic_hint_score": top.priority,
        "topic_hint_hits": [top.text],
        "topic_scores": {m.label: m.priority for m in topics},
        "topic_conflict": topic_conflict,
        "topic_source": "resolved_phrase",
    }


# =========================================================
# 8) INTENT EXTRACTION
# =========================================================

def extract_intent_by_organization(
    q_norm: str,
    resolved_matches: List[PhraseMatch],
    hits: Set[str],
    organization_type: Optional[str],
    topic_hint: Optional[str],
) -> dict:
    HIGH_MIN_SCORE = 6
    HIGH_MIN_MARGIN = 2

    LOW_MIN_SCORE = 8
    LOW_MIN_MARGIN = 3
    LOW_MIN_HITS = 2

    if topic_hint:
        locked_intent = TOPIC_TO_INTENT.get(topic_hint)
        if locked_intent:
            return {
                "intent": locked_intent,
                "intent_score": 10,
                "intent_hits": [f"locked_by_topic:{topic_hint}"],
                "intent_scores": {locked_intent: 10},
                "need_llm_intent": False,
                "decision_mode": "locked_by_topic",
                "decision_reason": f"topic_hint={topic_hint}",
                "source": "locked_by_topic",
            }

    if not organization_type:
        return {
            "intent": None,
            "intent_score": 0,
            "intent_hits": [],
            "intent_scores": {},
            "need_llm_intent": True,
            "decision_mode": "no_organization_type",
            "decision_reason": "organization_type_none",
            "source": "rule_base_none",
        }

    allowed_intents = ORG_INTENTS.get(organization_type, set())
    if not allowed_intents:
        return {
            "intent": None,
            "intent_score": 0,
            "intent_hits": [],
            "intent_scores": {},
            "need_llm_intent": True,
            "decision_mode": "no_allowed_intents",
            "decision_reason": f"organization_type={organization_type}",
            "source": "rule_base_none",
        }

    intent_scores = {intent: 0 for intent in allowed_intents}
    intent_hits_map = {intent: [] for intent in allowed_intents}

    for m in resolved_matches:
        if m.kind == "intent" and m.label in allowed_intents:
            intent_scores[m.label] += m.priority
            intent_hits_map[m.label].append(m.text)

    keyword_groups = get_intent_keywords_for_org(organization_type)
    for intent, keywords in keyword_groups.items():
        if intent not in allowed_intents:
            continue

        matched_keywords = [kw for kw in keywords if kw in hits]
        intent_scores[intent] += len(matched_keywords) * 3
        intent_hits_map[intent].extend(matched_keywords)

    # ---------------------------------------------
    # HIGH-PRECISION OVERRIDES ONLY
    # ---------------------------------------------
    if organization_type == "ubnd":
        if contains_any(q_norm, [
            "phan anh hien truong", "phan anh", "kien nghi", "khieu nai", "to cao"
        ]):
            return {
                "intent": "phan_anh_kien_nghi",
                "intent_score": 8,
                "intent_hits": ["override:public_feedback_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "public_feedback_pattern",
                "source": "override_accept",
            }

        if contains_any(q_norm, [
            "thu tuc", "ho so", "giay to", "quy trinh", "dieu kien",
            "thoi gian giai quyet", "le phi", "mau don", "nop o dau"
        ]):
            return {
                "intent": "hoi_thu_tuc",
                "intent_score": 8,
                "intent_hits": ["override:procedure_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "procedure_pattern",
                "source": "override_accept",
            }

    if organization_type == "dang_uy":
        if contains_any(q_norm, [
            "sinh hoat dang", "chuyen sinh hoat dang", "dang phi", "ket nap dang",
            "nghi quyet", "dang vien", "chi bo", "chi uy"
        ]):
            return {
                "intent": "sinh_hoat_dang",
                "intent_score": 8,
                "intent_hits": ["override:dang_activity_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "dang_activity_pattern",
                "source": "override_accept",
            }
    
    if organization_type == "cong_doan":
        if contains_any(q_norm, [
            "phan anh", "kien nghi", "khieu nai", "to cao", "bao cao vi pham",
            "cham dong bhxh", "no bhxh", "khong dong bhxh", "bao hiem xa hoi",
            "tien luong", "no luong", "cham luong", "khong tra luong",
            "hop dong lao dong", "dieu kien lao dong", "quay roi noi lam viec",
            "sa thai trai luat", "cho thoi viec trai luat"
        ]):
            return {
                "intent": "phan_anh_kien_nghi",
                "intent_score": 8,
                "intent_hits": ["override:cong_doan_complaint_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "cong_doan_complaint_pattern",
                "source": "override_accept",
            }

    if organization_type in {"doan_thanh_nien", "hoi_phu_nu", "mttq", "cong_doan"}:
        if contains_any(q_norm, [
            "quyen loi", "loi ich", "ho tro gi", "duoc gi", "huong gi",
            "co quyen gi", "bao ve ai", "che do", "tro cap"
        ]):
            return {
                "intent": "quyen_loi_ho_tro",
                "intent_score": 8,
                "intent_hits": ["override:benefit_support_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "benefit_support_pattern",
                "source": "override_accept",
            }

        join_org_strong_patterns = [
            "tham gia",
            "gia nhap",
            "ket nap",
            "thu tuc vao",
            "dieu kien tham gia",
            "quy trinh tham gia",
            "vao doan",
            "vao cong doan",
            "vao hoi phu nu",
            "tham gia mat tran",
        ]
        join_org_support_patterns = [
            "chuyen sinh hoat",
            "chuyen doan",
            "hoc cam tinh",
            "lop cam tinh",
            "mat the",
            "mat so",
            "cap lai",
        ]

        strong_count = sum(1 for x in join_org_strong_patterns if contains_phrase(q_norm, x))
        support_count = sum(1 for x in join_org_support_patterns if contains_phrase(q_norm, x))

        if strong_count >= 1 or support_count >= 2:
            return {
                "intent": "tham_gia_to_chuc",
                "intent_score": 8,
                "intent_hits": ["override:join_org_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": {
                    "strong_count": strong_count,
                    "support_count": support_count,
                },
                "source": "override_accept",
            }

    ranked = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)

    best_intent = ranked[0][0] if ranked else None
    best_intent_score = ranked[0][1] if ranked else 0

    second_intent = ranked[1][0] if len(ranked) > 1 else None
    second_intent_score = ranked[1][1] if len(ranked) > 1 else 0

    margin = best_intent_score - second_intent_score
    best_hits = intent_hits_map.get(best_intent, []) if best_intent else []

    if best_intent in HIGH_PRECISION_INTENTS:
        if best_intent_score >= HIGH_MIN_SCORE and margin >= HIGH_MIN_MARGIN:
            return {
                "intent": best_intent,
                "intent_score": best_intent_score,
                "intent_hits": best_hits,
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "strong_score_accept",
                "decision_reason": {
                    "best_intent": best_intent,
                    "best_score": best_intent_score,
                    "second_intent": second_intent,
                    "second_score": second_intent_score,
                    "margin": margin,
                    "precision_mode": "high",
                },
                "source": "rule_base_strong",
            }

    if best_intent in LOW_PRECISION_INTENTS:
        if (
            best_intent_score >= LOW_MIN_SCORE
            and margin >= LOW_MIN_MARGIN
            and len(best_hits) >= LOW_MIN_HITS
        ):
            return {
                "intent": best_intent,
                "intent_score": best_intent_score,
                "intent_hits": best_hits,
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "strong_score_accept_low_precision",
                "decision_reason": {
                    "best_intent": best_intent,
                    "best_score": best_intent_score,
                    "second_intent": second_intent,
                    "second_score": second_intent_score,
                    "margin": margin,
                    "hit_count": len(best_hits),
                    "precision_mode": "low",
                },
                "source": "rule_base_strong",
            }

    if best_intent_score > 0:
        return {
            "intent": None,
            "intent_score": best_intent_score,
            "intent_hits": best_hits,
            "intent_scores": intent_scores,
            "need_llm_intent": True,
            "decision_mode": "weak_or_ambiguous_to_llm",
            "decision_reason": {
                "best_intent": best_intent,
                "best_score": best_intent_score,
                "second_intent": second_intent,
                "second_score": second_intent_score,
                "margin": margin,
            },
            "source": "rule_base_weak",
        }

    return {
        "intent": None,
        "intent_score": 0,
        "intent_hits": [],
        "intent_scores": intent_scores,
        "need_llm_intent": True,
        "decision_mode": "reject_to_llm",
        "decision_reason": "no_intent_signal",
        "source": "rule_base_none",
    }


# =========================================================
# 9) MAIN DETECTOR
# =========================================================

def detect_organization_intent_fast_v7(q_norm: str) -> dict:

    raw_matches = find_phrase_matches(q_norm)
    resolved_matches = resolve_phrase_matches(raw_matches)
    resolved_hits = {m.text for m in resolved_matches}

    topic_result = extract_topic_hint_v7(resolved_matches)
    topic_hint = topic_result["topic_hint"]

    if topic_hint:
        organization_type = TOPIC_TO_ORG.get(topic_hint)
        organization_source = "derived_from_topic"
        need_llm_organization_type = False
        conflict = topic_result["topic_conflict"]
        organization_scores = {}
        organization_hits = {}
    else:
        org_result = extract_organization_type_legacy(q_norm=q_norm, hits=resolved_hits)
        organization_type = org_result["organization_type"]
        organization_source = org_result["source"]
        need_llm_organization_type = org_result["need_llm_organization_type"]
        conflict = org_result["conflict"]
        organization_scores = org_result["organization_scores"]
        organization_hits = org_result["organization_hits"]

        post_org = post_validate_organization_type(
            q_norm=q_norm,
            organization_type=organization_type,
            organization_hits=organization_hits,
        )

        if post_org["organization_type"] is None:
            organization_type = None
            need_llm_organization_type = True
            organization_source = post_org["source"]
        else:
            organization_type = post_org["organization_type"]

    intent_result = extract_intent_by_organization(
        q_norm=q_norm,
        resolved_matches=resolved_matches,
        hits=resolved_hits,
        organization_type=organization_type,
        topic_hint=topic_hint,
    )
    intent = intent_result["intent"]

    matched = organization_type in {
        "ubnd", "dang_uy", "doan_thanh_nien", "hoi_phu_nu", "mttq", "cong_doan"
    }

    base = 0.25
    if organization_type:
        base += 0.30
    if intent is not None:
        base += 0.30
    if topic_hint is not None:
        base += 0.10
    if conflict:
        base -= 0.20
    if need_llm_organization_type:
        base -= 0.10
    if intent_result["need_llm_intent"]:
        base -= 0.10

    confidence = round(max(0.0, min(base, 0.98)), 3)

    return {
        "matched": matched,
        "organization_type": organization_type,
        "intent": intent,
        "topic_hint": topic_hint,
        "confidence": confidence,
        "signals": {
            "q_norm": q_norm,
            "raw_matches": [
                {
                    "text": m.text,
                    "kind": m.kind,
                    "label": m.label,
                    "priority": m.priority,
                    "start": m.start,
                    "end": m.end,
                } for m in raw_matches
            ],
            "resolved_matches": [
                {
                    "text": m.text,
                    "kind": m.kind,
                    "label": m.label,
                    "priority": m.priority,
                    "start": m.start,
                    "end": m.end,
                } for m in resolved_matches
            ],
            "hits": list(resolved_hits),
            "organization_hits": organization_hits,
            "organization_scores": organization_scores,
            "topic_hint_hits": topic_result["topic_hint_hits"],
            "topic_scores": topic_result["topic_scores"],
            "intent_hits": intent_result["intent_hits"],
            "intent_scores": intent_result["intent_scores"],
            "topic_conflict": topic_result["topic_conflict"],
            "intent_decision_mode": intent_result.get("decision_mode"),
            "intent_decision_reason": intent_result.get("decision_reason"),
        },
        "need_llm_organization_type": need_llm_organization_type,
        "need_llm_intent": intent_result["need_llm_intent"],
        "conflict": conflict,
        "source": {
            "organization_type": organization_source,
            "topic": topic_result["topic_source"],
            "intent": intent_result["source"],
        }
    }


from typing import Optional, Set, List, Dict

def extract_intent_with_known_org(
    query: str,
    organization_type: str,
) -> dict:
    """
    Rule-base extract intent when organization_type is already known.

    Input:
        - query: raw user query
        - organization_type: one of allowed org types

    Output:
        {
            "intent": str | None,
            "intent_score": int | float,
            "intent_hits": list[str],
            "intent_scores": dict[str, float],
            "need_llm_intent": bool,
            "decision_mode": str,
            "decision_reason": str | dict,
            "source": str,
        }
    """

    q_norm = normalize_text(query)

    HIGH_MIN_SCORE = 6
    HIGH_MIN_MARGIN = 2

    LOW_MIN_SCORE = 8
    LOW_MIN_MARGIN = 3
    LOW_MIN_HITS = 2

    raw_matches = find_phrase_matches(q_norm)
    resolved_matches = resolve_phrase_matches(raw_matches)
    resolved_hits = {m.text for m in resolved_matches}

    topic_result = extract_topic_hint_v7(resolved_matches)
    topic_hint = topic_result["topic_hint"]

    if topic_hint:
        locked_intent = TOPIC_TO_INTENT.get(topic_hint)
        if locked_intent and locked_intent in ORG_INTENTS.get(organization_type, set()):
            return {
                "intent": locked_intent,
                "intent_score": 10,
                "intent_hits": [f"locked_by_topic:{topic_hint}"],
                "intent_scores": {locked_intent: 10},
                "need_llm_intent": False,
                "decision_mode": "locked_by_topic",
                "decision_reason": f"topic_hint={topic_hint}",
                "source": "locked_by_topic",
            }

    if not organization_type:
        return {
            "intent": None,
            "intent_score": 0,
            "intent_hits": [],
            "intent_scores": {},
            "need_llm_intent": True,
            "decision_mode": "no_organization_type",
            "decision_reason": "organization_type_none",
            "source": "rule_base_none",
        }

    allowed_intents = ORG_INTENTS.get(organization_type, set())
    if not allowed_intents:
        return {
            "intent": None,
            "intent_score": 0,
            "intent_hits": [],
            "intent_scores": {},
            "need_llm_intent": True,
            "decision_mode": "no_allowed_intents",
            "decision_reason": f"organization_type={organization_type}",
            "source": "rule_base_none",
        }

    intent_scores = {intent: 0 for intent in allowed_intents}
    intent_hits_map = {intent: [] for intent in allowed_intents}

    # 1) direct phrase intent matches
    for m in resolved_matches:
        if m.kind == "intent" and m.label in allowed_intents:
            intent_scores[m.label] += m.priority
            intent_hits_map[m.label].append(m.text)

    # 2) keyword group matches
    keyword_groups = get_intent_keywords_for_org(organization_type)
    for intent, keywords in keyword_groups.items():
        if intent not in allowed_intents:
            continue

        matched_keywords = [kw for kw in keywords if kw in resolved_hits]
        intent_scores[intent] += len(matched_keywords) * 3
        intent_hits_map[intent].extend(matched_keywords)

    # ---------------------------------------------
    # HIGH-PRECISION OVERRIDES
    # ---------------------------------------------
    if organization_type == "ubnd":
        if contains_any(q_norm, [
            "phan anh hien truong", "phan anh", "kien nghi", "khieu nai", "to cao"
        ]):
            return {
                "intent": "phan_anh_kien_nghi",
                "intent_score": 8,
                "intent_hits": ["override:public_feedback_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "public_feedback_pattern",
                "source": "override_accept",
            }

        if contains_any(q_norm, [
            "thu tuc", "ho so", "giay to", "quy trinh", "dieu kien",
            "thoi gian giai quyet", "le phi", "mau don", "nop o dau"
        ]):
            return {
                "intent": "hoi_thu_tuc",
                "intent_score": 8,
                "intent_hits": ["override:procedure_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "procedure_pattern",
                "source": "override_accept",
            }

    if organization_type == "dang_uy":
        if contains_any(q_norm, [
            "sinh hoat dang", "chuyen sinh hoat dang", "dang phi", "ket nap dang",
            "nghi quyet", "dang vien", "chi bo", "chi uy"
        ]):
            return {
                "intent": "sinh_hoat_dang",
                "intent_score": 8,
                "intent_hits": ["override:dang_activity_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "dang_activity_pattern",
                "source": "override_accept",
            }

    if organization_type == "cong_doan":
        if contains_any(q_norm, [
            "phan anh", "kien nghi", "khieu nai", "to cao", "bao cao vi pham",
            "cham dong bhxh", "no bhxh", "khong dong bhxh", "bao hiem xa hoi",
            "tien luong", "no luong", "cham luong", "khong tra luong",
            "hop dong lao dong", "dieu kien lao dong", "quay roi noi lam viec",
            "sa thai trai luat", "cho thoi viec trai luat"
        ]):
            return {
                "intent": "phan_anh_kien_nghi",
                "intent_score": 8,
                "intent_hits": ["override:cong_doan_complaint_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "cong_doan_complaint_pattern",
                "source": "override_accept",
            }

    if organization_type in {"doan_thanh_nien", "hoi_phu_nu", "mttq", "cong_doan"}:
        if contains_any(q_norm, [
            "quyen loi", "loi ich", "ho tro gi", "duoc gi", "huong gi",
            "co quyen gi", "bao ve ai", "che do", "tro cap"
        ]):
            return {
                "intent": "quyen_loi_ho_tro",
                "intent_score": 8,
                "intent_hits": ["override:benefit_support_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": "benefit_support_pattern",
                "source": "override_accept",
            }

        join_org_strong_patterns = [
            "tham gia",
            "gia nhap",
            "ket nap",
            "thu tuc vao",
            "dieu kien tham gia",
            "quy trinh tham gia",
            "vao doan",
            "vao cong doan",
            "vao hoi phu nu",
            "tham gia mat tran",
        ]
        join_org_support_patterns = [
            "chuyen sinh hoat",
            "chuyen doan",
            "hoc cam tinh",
            "lop cam tinh",
            "mat the",
            "mat so",
            "cap lai",
        ]

        strong_count = sum(1 for x in join_org_strong_patterns if contains_phrase(q_norm, x))
        support_count = sum(1 for x in join_org_support_patterns if contains_phrase(q_norm, x))

        if strong_count >= 1 or support_count >= 2:
            return {
                "intent": "tham_gia_to_chuc",
                "intent_score": 8,
                "intent_hits": ["override:join_org_pattern"],
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "override_accept",
                "decision_reason": {
                    "strong_count": strong_count,
                    "support_count": support_count,
                },
                "source": "override_accept",
            }

    # ---------------------------------------------
    # SCORE-BASED DECISION
    # ---------------------------------------------
    ranked = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)

    best_intent = ranked[0][0] if ranked else None
    best_intent_score = ranked[0][1] if ranked else 0

    second_intent = ranked[1][0] if len(ranked) > 1 else None
    second_intent_score = ranked[1][1] if len(ranked) > 1 else 0

    margin = best_intent_score - second_intent_score
    best_hits = intent_hits_map.get(best_intent, []) if best_intent else []

    if best_intent in HIGH_PRECISION_INTENTS:
        if best_intent_score >= HIGH_MIN_SCORE and margin >= HIGH_MIN_MARGIN:
            return {
                "intent": best_intent,
                "intent_score": best_intent_score,
                "intent_hits": best_hits,
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "strong_score_accept",
                "decision_reason": {
                    "best_intent": best_intent,
                    "best_score": best_intent_score,
                    "second_intent": second_intent,
                    "second_score": second_intent_score,
                    "margin": margin,
                    "precision_mode": "high",
                },
                "source": "rule_base_strong",
            }

    if best_intent in LOW_PRECISION_INTENTS:
        if (
            best_intent_score >= LOW_MIN_SCORE
            and margin >= LOW_MIN_MARGIN
            and len(best_hits) >= LOW_MIN_HITS
        ):
            return {
                "intent": best_intent,
                "intent_score": best_intent_score,
                "intent_hits": best_hits,
                "intent_scores": intent_scores,
                "need_llm_intent": False,
                "decision_mode": "strong_score_accept_low_precision",
                "decision_reason": {
                    "best_intent": best_intent,
                    "best_score": best_intent_score,
                    "second_intent": second_intent,
                    "second_score": second_intent_score,
                    "margin": margin,
                    "hit_count": len(best_hits),
                    "precision_mode": "low",
                },
                "source": "rule_base_strong",
            }

    if best_intent_score > 0:
        return {
            "intent": None,
            "intent_score": best_intent_score,
            "intent_hits": best_hits,
            "intent_scores": intent_scores,
            "need_llm_intent": True,
            "decision_mode": "weak_or_ambiguous_to_llm",
            "decision_reason": {
                "best_intent": best_intent,
                "best_score": best_intent_score,
                "second_intent": second_intent,
                "second_score": second_intent_score,
                "margin": margin,
            },
            "source": "rule_base_weak",
        }

    return {
        "intent": None,
        "intent_score": 0,
        "intent_hits": [],
        "intent_scores": intent_scores,
        "need_llm_intent": True,
        "decision_mode": "reject_to_llm",
        "decision_reason": "no_intent_signal",
        "source": "rule_base_none",
    }