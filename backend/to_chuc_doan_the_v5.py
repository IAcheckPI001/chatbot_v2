

import re
import unicodedata
from dataclasses import dataclass
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
# 1) LEGACY KEYWORDS (GIỮ LẠI ĐỂ DÙNG CHO SCORE/FALLBACK)
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
            "doan phi",
            "chuyen sinh hoat doan",
            "hoc cam tinh doan",
            "lop cam tinh doan",
        ],
        "weak": [
            "doan vien",
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
            "doan"
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
            "chu tich mttq",
        ],
        "weak": [],
    },
    "ubnd": {
        "strong": [
            "ubnd",
            "uy ban nhan dan",
            "tru so ubnd",
        ],
        "weak": [
            "phuong",
            "xa",
            "thi tran",
        ],
    },
}

AMBIGUOUS_WEAK_KEYWORDS = {
    "doan vien",
    "hoi vien",
}

SAFE_WEAK_KEYWORD_SCORE = 1.5
AMBIGUOUS_WEAK_KEYWORD_SCORE = 0.75
STRONG_KEYWORD_SCORE = 3


SUBJECT_STANDARD_KEYWORDS = {
    "gioi_thieu_chung": [
        "gioi thieu",
        "tong quan",
        "la to chuc gi",
        "la gi",
    ],
    "chuc_nang_nhiem_vu": [
        "chuc nang",
        "nhiem vu",
        "vai tro",
        "phu trach gi",
        "lam gi",
        "hoat dong nhu the nao",
    ],
    "co_cau_to_chuc": [
        "co cau",
        "gom nhung bo phan nao",
        "to chuc ra sao",
        "chi hoi",
        "chi doan",
        "bo phan",
        "cap tren",
        "co so",
    ],
    "chuc_vu": [
        "chu tich",
        "pho chu tich",
        "bi thu",
        "pho bi thu",
        "lanh dao",
        "nhan su",
        "ai la ai",
        "la ai",
        "ai dung dau",
        "ai giu chuc vu gi",
    ],
    "thong_tin_lien_he": [
        "dia chi",
        "so dien thoai",
        "email",
        "website",
        "hotline",
        "gio lam viec",
        "lam viec gio nao",
        "o dau",
    ],
    "hoi_vien_doi_tuong_phuc_vu": [
        "hoi vien",
        "doan vien",
        "doi tuong",
        "danh cho ai",
        "ai duoc",
        "ai co the tham gia",
        "nghia vu",
        "trach nhiem",
    ],
    "hoat_dong_phong_trao": [
        "hoat dong",
        "phong trao",
        "chien dich",
        "su kien",
        "chuong trinh dang trien khai",
    ],
    "chuong_trinh_ho_tro": [
        "ho tro gi",
        "duoc ho tro gi",
        "quyen loi",
        "loi ich",
        "duoc gi",
        "huong gi",
        "bao ve ai",
        "co quyen gi",
    ],
    "thu_tuc_quy_trinh": [
        "tham gia nhu the nao",
        "dang ky",
        "vao doan",
        "vao cong doan",
        "ket nap",
        "gia nhap",
        "chuyen sinh hoat",
        "chuyen doan",
        "hoc cam tinh",
        "can gi",
        "ho so gi",
        "thu tuc",
        "quy trinh",
        "dieu kien",
    ],
    "quy_dinh_huong_dan": [
        "van ban",
        "huong dan",
        "quy dinh",
        "quyet dinh",
        "kinh phi",
        "hoi phi",
        "doan phi",
        "cong doan phi",
        "2 phan tram",
        "dong bao nhieu",
        "co bi phat khong",
    ],
}

SUBJECT_KEYWORD_SCORE = 3


TOPIC_HINT_KEYWORDS = {
    "ket_nap_doan": [
        "ket nap doan",
        "vao doan",
        "tham gia doan",
        "tro thanh doan vien",
        "thu tuc ket nap doan",
        "quy trinh ket nap doan",
        "ai duoc ket nap doan",
        "dieu kien vao doan",
        "bao nhieu tuoi duoc vao doan",
        "15 tuoi vao doan",
        "16 tuoi vao doan",
        "30 tuoi vao doan",
        "qua tuoi doan",
        "bao lau duoc ket nap doan",
        "bao lau xet vao doan",
    ],
    "doan_phi": [
        "doan phi",
        "dong doan phi",
        "mien doan phi",
    ],
    "cap_lai_ho_so_doan": [
        "cap lai ho so doan",
        "cap lai doan",
        "mat so doan",
        "mat so doan vien",
        "mat ho so doan",
        "lam lai so doan",
        "lam lai the doan vien",
        "mat the doan vien",
        "lam lai ho so doan",
    ],
    "chuyen_sinh_hoat_doan": [
        "chuyen sinh hoat doan",
        "chuyen doan",
        "giay chuyen doan",
        "mat giay chuyen doan",
        "chuyen truong co can chuyen doan",
    ],
    "nghia_vu_doan_vien": [
        "nghia vu doan vien",
        "doan vien co nghia vu gi",
        "doan vien phai lam gi",
        "khong sinh hoat doan co sao khong",
    ],
    "loi_ich_doan_vien": [
        "loi ich doan vien",
        "quyen loi doan vien",
        "doan vien duoc gi",
        "doan vien co loi ich gi",
    ],
    "hoc_cam_tinh_doan": [
        "hoc cam tinh doan",
        "lop cam tinh doan",
        "cam tinh doan",
        "hoc lop doan",
    ],
    "xoa_ten_doan": [
        "xoa ten doan",
        "bi xoa doan",
        "khi nao bi xoa doan",
        "co bi xoa ten doan khong",
    ],
    "ket_nap_cong_doan": [
        "gia nhap cong doan",
        "tham gia cong doan",
        "vao cong doan",
        "thu tuc vao cong doan",
        "dieu kien tham gia cong doan",
        "lam sao de vao cong doan",
        "co bat buoc tham gia cong doan khong",
        "khong vao cong doan co sao khong",
        "nguoi lao dong co phai vao cong doan khong",
    ],
    "kinh_phi_cong_doan": [
        "kinh phi cong doan",
        "phi cong doan",
        "cong doan phi",
        "ai phai dong cong doan",
        "nguoi lao dong co dong cong doan khong",
        "cong ty dong cong doan bao nhieu",
        "2 phan tram cong doan",
        "khong dong cong doan co bi phat khong",
        "cong ty khong dong cong doan bi gi",
        "tron dong cong doan co sao khong",
    ],
    "quyen_loi_cong_doan_vien": [
        "quyen loi cong doan",
        "quyen loi cong doan vien",
        "cong doan bao ve ai",
        "cong doan co quyen gi",
    ],
    "co_cau_lanh_dao_cong_doan": [
        "ai dung dau cong doan",
        "chu tich cong doan",
        "pho chu tich cong doan",
    ],
    "tham_gia_hoi_phu_nu": [
        "tham gia hoi phu nu",
        "vao hoi phu nu",
        "ket nap hoi phu nu",
    ],
    "hoi_phi_phu_nu": [
        "hoi phi phu nu",
    ],
    "quyen_loi_hoi_vien": [
        "quyen loi hoi vien",
        "quyen loi hoi vien phu nu",
    ]
}

TOPIC_HINT_TO_SUBJECT_STANDARD = {
    "ket_nap_doan": "thu_tuc_quy_trinh",
    "doan_phi": "quy_dinh_huong_dan",
    "cap_lai_ho_so_doan": "quy_dinh_huong_dan",
    "chuyen_sinh_hoat_doan": "thu_tuc_quy_trinh",
    "nghia_vu_doan_vien": "hoi_vien_doi_tuong_phuc_vu",
    "loi_ich_doan_vien": "chuong_trinh_ho_tro",
    "hoc_cam_tinh_doan": "thu_tuc_quy_trinh",
    "xoa_ten_doan": "quy_dinh_huong_dan",

    "ket_nap_cong_doan": "thu_tuc_quy_trinh",
    "kinh_phi_cong_doan": "quy_dinh_huong_dan",
    "quyen_loi_cong_doan_vien": "chuong_trinh_ho_tro",
    "co_cau_lanh_dao_cong_doan": "chuc_vu",

    "tham_gia_hoi_phu_nu": "thu_tuc_quy_trinh",
    "hoi_phi_phu_nu": "quy_dinh_huong_dan",
    "quyen_loi_hoi_vien": "chuong_trinh_ho_tro",
}

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
}


# =========================================================
# 2) SPAN-BASED MATCHER
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
    # -------------------------
    # TOPIC - RẤT MẠNH
    # -------------------------
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

    # -------------------------
    # ORGANIZATION
    # -------------------------
    {"text": "doan thanh nien cong san ho chi minh", "kind": "organization", "label": "doan_thanh_nien", "priority": 70},
    {"text": "doan thanh nien", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "doan tn", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "dtn", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "chi doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "bi thu doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},
    {"text": "pho bi thu doan", "kind": "organization", "label": "doan_thanh_nien", "priority": 65},

    {"text": "cong doan co so", "kind": "organization", "label": "cong_doan", "priority": 70},
    {"text": "cong doan", "kind": "organization", "label": "cong_doan", "priority": 60},

    {"text": "hoi lien hiep phu nu", "kind": "organization", "label": "hoi_phu_nu", "priority": 70},
    {"text": "chi hoi phu nu", "kind": "organization", "label": "hoi_phu_nu", "priority": 70},
    {"text": "hoi phu nu", "kind": "organization", "label": "hoi_phu_nu", "priority": 60},

    {"text": "uy ban mat tran to quoc", "kind": "organization", "label": "mttq", "priority": 70},
    {"text": "mat tran to quoc", "kind": "organization", "label": "mttq", "priority": 65},
    {"text": "mttq", "kind": "organization", "label": "mttq", "priority": 60},

    # -------------------------
    # SUBJECT GENERIC - CHỈ FALLBACK
    # -------------------------
    {"text": "ai dung dau", "kind": "subject_generic", "label": "chuc_vu", "priority": 20},
    {"text": "la ai", "kind": "subject_generic", "label": "chuc_vu", "priority": 15},

    {"text": "chuc nang", "kind": "subject_generic", "label": "chuc_nang_nhiem_vu", "priority": 20},
    {"text": "nhiem vu", "kind": "subject_generic", "label": "chuc_nang_nhiem_vu", "priority": 20},
    {"text": "vai tro", "kind": "subject_generic", "label": "chuc_nang_nhiem_vu", "priority": 20},
    {"text": "lam gi", "kind": "subject_generic", "label": "chuc_nang_nhiem_vu", "priority": 10},
    {"text": "hoat dong nhu the nao", "kind": "subject_generic", "label": "chuc_nang_nhiem_vu", "priority": 10},

    {"text": "co cau", "kind": "subject_generic", "label": "co_cau_to_chuc", "priority": 20},
    {"text": "bo phan", "kind": "subject_generic", "label": "co_cau_to_chuc", "priority": 20},
    {"text": "chi hoi", "kind": "subject_generic", "label": "co_cau_to_chuc", "priority": 20},
    {"text": "chi doan", "kind": "subject_generic", "label": "co_cau_to_chuc", "priority": 20},
    {"text": "cap tren", "kind": "subject_generic", "label": "co_cau_to_chuc", "priority": 20},
    {"text": "co so", "kind": "subject_generic", "label": "co_cau_to_chuc", "priority": 20},

    {"text": "quyen loi", "kind": "subject_generic", "label": "chuong_trinh_ho_tro", "priority": 20},
    {"text": "loi ich", "kind": "subject_generic", "label": "chuong_trinh_ho_tro", "priority": 20},
    {"text": "duoc gi", "kind": "subject_generic", "label": "chuong_trinh_ho_tro", "priority": 15},
    {"text": "huong gi", "kind": "subject_generic", "label": "chuong_trinh_ho_tro", "priority": 15},
    {"text": "bao ve ai", "kind": "subject_generic", "label": "chuong_trinh_ho_tro", "priority": 20},
    {"text": "co quyen gi", "kind": "subject_generic", "label": "chuong_trinh_ho_tro", "priority": 20},

    {"text": "nghia vu", "kind": "subject_generic", "label": "hoi_vien_doi_tuong_phuc_vu", "priority": 20},
    {"text": "trach nhiem", "kind": "subject_generic", "label": "hoi_vien_doi_tuong_phuc_vu", "priority": 20},
    {"text": "doan vien", "kind": "subject_generic", "label": "hoi_vien_doi_tuong_phuc_vu", "priority": 5},
    {"text": "hoi vien", "kind": "subject_generic", "label": "hoi_vien_doi_tuong_phuc_vu", "priority": 5},

    {"text": "dang ky", "kind": "subject_generic", "label": "thu_tuc_quy_trinh", "priority": 20},
    {"text": "thu tuc", "kind": "subject_generic", "label": "thu_tuc_quy_trinh", "priority": 20},
    {"text": "quy trinh", "kind": "subject_generic", "label": "thu_tuc_quy_trinh", "priority": 20},
    {"text": "dieu kien", "kind": "subject_generic", "label": "thu_tuc_quy_trinh", "priority": 20},
    {"text": "ho so", "kind": "subject_generic", "label": "thu_tuc_quy_trinh", "priority": 15},

    {"text": "cong doan phi", "kind": "subject_generic", "label": "quy_dinh_huong_dan", "priority": 30},
    {"text": "kinh phi", "kind": "subject_generic", "label": "quy_dinh_huong_dan", "priority": 20},
    {"text": "2 phantram", "kind": "subject_generic", "label": "quy_dinh_huong_dan", "priority": 20},
    {"text": "dong bao nhieu", "kind": "subject_generic", "label": "quy_dinh_huong_dan", "priority": 20},
    {"text": "co bi phat khong", "kind": "subject_generic", "label": "quy_dinh_huong_dan", "priority": 20},
    {"text": "doan phi", "kind": "subject_generic", "label": "quy_dinh_huong_dan", "priority": 15},

    {"text": "la gi", "kind": "subject_generic", "label": "gioi_thieu_chung", "priority": 1},
]


def find_phrase_matches(q_norm: str) -> List[PhraseMatch]:
    out: List[PhraseMatch] = []
    for item in PHRASE_DEFS:
        pattern = phrase_pattern(item["text"])
        for m in re.finditer(pattern, q_norm):
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
# 3) COMPAT HELPERS
# =========================================================

def contains_phrase(q_norm: str, phrase: str) -> bool:
    return re.search(phrase_pattern(phrase), q_norm) is not None


def contains_any(q_norm: str, keywords: List[str]) -> bool:
    return any(contains_phrase(q_norm, kw) for kw in keywords)


def scan_keywords_once(q_norm: str):
    # v5: dùng matcher mới rồi convert về set để các hàm legacy dùng tiếp
    raw_matches = find_phrase_matches(q_norm)
    resolved_matches = resolve_phrase_matches(raw_matches)
    return {m.text for m in resolved_matches}


# =========================================================
# 4) INTENT FLAGS
# =========================================================

def detect_intent_flags(q_norm: str) -> dict:
    return {
        "so_sanh": any(contains_phrase(q_norm, x) for x in [
            "khac nhau", "khac gi", "phan biet", "so sanh", "giong nhau"
        ]),
        "bat_buoc": any(contains_phrase(q_norm, x) for x in [
            "bat buoc", "co phai", "co can", "co duoc bat buoc"
        ]),
        "mat_cap_lai": any(contains_phrase(q_norm, x) for x in [
            "mat so", "cap lai", "mat ho so", "lam lai ho so", "lam lai", "mat the"
        ]),
        "quyen_loi": any(contains_phrase(q_norm, x) for x in [
            "quyen loi", "loi ich", "duoc gi", "huong gi", "bao ve ai", "co quyen gi"
        ]),
        "nghia_vu": any(contains_phrase(q_norm, x) for x in [
            "nghia vu", "trach nhiem", "phai lam gi"
        ]),
        "lien_he": any(contains_phrase(q_norm, x) for x in [
            "dia chi", "so dien thoai", "email", "hotline", "o dau"
        ]),
        "chuc_vu": any(contains_phrase(q_norm, x) for x in [
            "chu tich", "pho chu tich", "bi thu", "pho bi thu", "lanh dao", "nhan su", "ai dung dau"
        ]),
    }


# =========================================================
# 5) ORGANIZATION / CATEGORY / TOPIC
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


def extract_topic_hint_v5(resolved_matches: List[PhraseMatch]) -> dict:
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


def extract_category_for_organization(q_norm: str, organization_type: str = None, subject: str = None) -> dict:
    if organization_type in {"cong_doan", "hoi_phu_nu", "doan_thanh_nien", "mttq"}:
        if subject in {"chuc_vu", "co_cau_to_chuc"}:
            return {
                "category": "to_chuc_bo_may",
                "confidence": 0.95,
                "need_llm_category": False,
                "source": "rule_base_by_subject",
            }

        if contains_any(q_norm, [
            "chu tich", "pho chu tich", "bi thu", "pho bi thu",
            "lanh dao", "nhan su", "ai la ai", "la ai", "ai dung dau",
            "co cau", "bo phan", "chi hoi", "chi doan"
        ]):
            return {
                "category": "to_chuc_bo_may",
                "confidence": 0.9,
                "need_llm_category": False,
                "source": "rule_base_by_organization_type",
            }

        return {
            "category": "thong_tin_tong_quan",
            "confidence": 0.8,
            "need_llm_category": False,
            "source": "rule_base_by_organization_type",
        }

    return {
        "category": None,
        "confidence": 0.0,
        "need_llm_category": True,
        "source": "rule_base_none",
    }


def lock_subject_by_topic(topic_hint: Optional[str]) -> Optional[str]:
    if not topic_hint:
        return None
    return TOPIC_HINT_TO_SUBJECT_STANDARD.get(topic_hint)


# =========================================================
# 6) SUBJECT
# =========================================================

GENERIC_LOW_PRIORITY_KEYWORDS = {
    "la gi",
    "lam gi",
    "doan vien",
    "hoi vien",
}


def extract_subject_standard(
    q_norm: str,
    hits: Set[str],
    category: str = None,
    topic_hint: str = None,
    intent_flags: Optional[dict] = None,
) -> dict:
    MIN_STRONG_SCORE = 6
    MIN_MARGIN = 2

    GENERIC_ONLY_KEYWORDS = {
        "la gi",
        "lam gi",
        "doan vien",
        "hoi vien",
    }

    # -----------------------------------------------------
    # HIGH-PRIORITY OVERRIDES
    # -----------------------------------------------------
    if contains_any(q_norm, [
        "lam lai the doan vien",
        "lam lai so doan",
        "mat the doan vien",
        "mat so doan",
        "mat ho so doan",
        "cap lai ho so doan",
        "lam lai ho so doan",
    ]):
        return {
            "subject": "quy_dinh_huong_dan",
            "subject_score": 8,
            "subject_hits": ["override:cap_lai_ho_so_doan_like"],
            "subject_scores": {"quy_dinh_huong_dan": 8},
            "need_llm_subject": False,
            "decision_mode": "override_accept",
            "decision_reason": "document_reissue_pattern",
        }

    if (
        "doan vien" in q_norm
        and contains_any(q_norm, ["loi ich", "quyen loi", "duoc gi", "huong gi"])
    ):
        return {
            "subject": "chuong_trinh_ho_tro",
            "subject_score": 8,
            "subject_hits": ["override:member_benefit_pattern"],
            "subject_scores": {"chuong_trinh_ho_tro": 8},
            "need_llm_subject": False,
            "decision_mode": "override_accept",
            "decision_reason": "member_benefit_pattern",
        }

    if (
        "doan vien" in q_norm
        and contains_any(q_norm, ["nghia vu", "trach nhiem", "phai lam gi"])
    ):
        return {
            "subject": "hoi_vien_doi_tuong_phuc_vu",
            "subject_score": 8,
            "subject_hits": ["override:member_obligation_pattern"],
            "subject_scores": {"hoi_vien_doi_tuong_phuc_vu": 8},
            "need_llm_subject": False,
            "decision_mode": "override_accept",
            "decision_reason": "member_obligation_pattern",
        }

    if contains_any(q_norm, [
        "2 phan tram",
        "cong doan phi",
        "kinh phi cong doan",
        "dong cong doan",
        "dong bao nhieu",
        "co bi phat khong",
    ]):
        if contains_any(q_norm, ["cong doan", "kinh phi", "phi", "dong", "2 phan tram"]):
            return {
                "subject": "quy_dinh_huong_dan",
                "subject_score": 8,
                "subject_hits": ["override:financial_compliance_pattern"],
                "subject_scores": {"quy_dinh_huong_dan": 8},
                "need_llm_subject": False,
                "decision_mode": "override_accept",
                "decision_reason": "financial_or_compliance_pattern",
            }

    # -----------------------------------------------------
    # LOCK BY TOPIC
    # -----------------------------------------------------
    locked_subject = lock_subject_by_topic(topic_hint)
    if locked_subject:
        return {
            "subject": locked_subject,
            "subject_score": 10,
            "subject_hits": [f"locked_by_topic:{topic_hint}"],
            "subject_scores": {locked_subject: 10},
            "need_llm_subject": False,
            "decision_mode": "locked_by_topic",
            "decision_reason": f"topic_hint={topic_hint}",
        }

    # -----------------------------------------------------
    # CANDIDATES
    # -----------------------------------------------------
    if category == "to_chuc_bo_may":
        candidate_subjects = [
            "chuc_vu",
            "co_cau_to_chuc",
            "chuc_nang_nhiem_vu",
        ]
    elif category == "thong_tin_tong_quan":
        candidate_subjects = [
            "gioi_thieu_chung",
            "chuc_nang_nhiem_vu",
            "thong_tin_lien_he",
            "hoi_vien_doi_tuong_phuc_vu",
            "hoat_dong_phong_trao",
            "chuong_trinh_ho_tro",
            "thu_tuc_quy_trinh",
            "quy_dinh_huong_dan",
        ]
    else:
        return {
            "subject": None,
            "subject_score": 0,
            "subject_hits": [],
            "subject_scores": {},
            "need_llm_subject": True,
            "decision_mode": "no_category",
            "decision_reason": "category_none_or_unsupported",
        }

    # -----------------------------------------------------
    # SCORE
    # -----------------------------------------------------
    subject_scores = {}
    subject_hits = {}
    subject_generic_hits = {}

    for subject in candidate_subjects:
        matched = [kw for kw in SUBJECT_STANDARD_KEYWORDS[subject] if kw in hits]
        score = 0
        generic_hits = []
        non_generic_hits = []

        for kw in matched:
            if kw in GENERIC_ONLY_KEYWORDS:
                score += 1
                generic_hits.append(kw)
            else:
                score += SUBJECT_KEYWORD_SCORE
                non_generic_hits.append(kw)

        subject_scores[subject] = score
        subject_hits[subject] = matched
        subject_generic_hits[subject] = {
            "generic": generic_hits,
            "non_generic": non_generic_hits,
        }

    if intent_flags:
        if intent_flags.get("quyen_loi") and "chuong_trinh_ho_tro" in subject_scores:
            subject_scores["chuong_trinh_ho_tro"] += 2
        if intent_flags.get("nghia_vu") and "hoi_vien_doi_tuong_phuc_vu" in subject_scores:
            subject_scores["hoi_vien_doi_tuong_phuc_vu"] += 2
        if intent_flags.get("lien_he") and "thong_tin_lien_he" in subject_scores:
            subject_scores["thong_tin_lien_he"] += 2
        if intent_flags.get("chuc_vu") and "chuc_vu" in subject_scores:
            subject_scores["chuc_vu"] += 2

    ranked = sorted(subject_scores.items(), key=lambda x: x[1], reverse=True)

    best_subject = ranked[0][0] if ranked else None
    best_subject_score = ranked[0][1] if ranked else 0

    second_subject = ranked[1][0] if len(ranked) > 1 else None
    second_subject_score = ranked[1][1] if len(ranked) > 1 else 0

    margin = best_subject_score - second_subject_score

    best_hits = subject_hits.get(best_subject, []) if best_subject else []
    best_non_generic_hits = subject_generic_hits.get(best_subject, {}).get("non_generic", []) if best_subject else []

    is_generic_only = (
        best_subject is not None
        and len(best_hits) > 0
        and len(best_non_generic_hits) == 0
    )

    # -----------------------------------------------------
    # HARD REJECT
    # -----------------------------------------------------
    if (
        best_subject == "gioi_thieu_chung"
        and contains_any(q_norm, ["2 phan tram", "kinh phi", "phi", "dong", "co bi phat khong"])
    ):
        return {
            "subject": None,
            "subject_score": best_subject_score,
            "subject_hits": best_hits,
            "subject_scores": subject_scores,
            "need_llm_subject": True,
            "decision_mode": "reject_to_llm",
            "decision_reason": "generic_intro_blocked_by_financial_context",
        }

    if (
        best_subject == "hoi_vien_doi_tuong_phuc_vu"
        and "doan vien" in q_norm
        and contains_any(q_norm, ["loi ich", "quyen loi", "duoc gi", "huong gi"])
    ):
        return {
            "subject": None,
            "subject_score": best_subject_score,
            "subject_hits": best_hits,
            "subject_scores": subject_scores,
            "need_llm_subject": True,
            "decision_mode": "reject_to_llm",
            "decision_reason": "member_benefit_should_not_map_to_member_object_group",
        }

    if (
        best_subject == "chuc_nang_nhiem_vu"
        and "doan vien" in q_norm
        and contains_any(q_norm, ["nghia vu", "trach nhiem", "phai lam gi"])
    ):
        return {
            "subject": None,
            "subject_score": best_subject_score,
            "subject_hits": best_hits,
            "subject_scores": subject_scores,
            "need_llm_subject": True,
            "decision_mode": "reject_to_llm",
            "decision_reason": "member_obligation_should_not_map_to_org_function",
        }

    # -----------------------------------------------------
    # HARD ACCEPT
    # -----------------------------------------------------
    if (
        best_subject is not None
        and best_subject_score >= MIN_STRONG_SCORE
        and margin >= MIN_MARGIN
        and not is_generic_only
    ):
        return {
            "subject": best_subject,
            "subject_score": best_subject_score,
            "subject_hits": best_hits,
            "subject_scores": subject_scores,
            "need_llm_subject": False,
            "decision_mode": "strong_score_accept",
            "decision_reason": {
                "best_subject": best_subject,
                "best_score": best_subject_score,
                "second_subject": second_subject,
                "second_score": second_subject_score,
                "margin": margin,
                "generic_only": is_generic_only,
            },
        }

    # -----------------------------------------------------
    # SAFE ACCEPT
    # -----------------------------------------------------
    if category == "to_chuc_bo_may":
        if (
            contains_any(q_norm, ["chu tich", "pho chu tich", "bi thu", "pho bi thu", "ai dung dau"])
            and margin >= 2
        ):
            return {
                "subject": "chuc_vu",
                "subject_score": 4,
                "subject_hits": [],
                "subject_scores": subject_scores,
                "need_llm_subject": False,
                "decision_mode": "safe_heuristic_accept",
                "decision_reason": "clear_leadership_pattern",
            }

        if (
            contains_any(q_norm, ["co cau", "bo phan", "chi hoi", "chi doan", "cap tren", "co so"])
            and margin >= 2
        ):
            return {
                "subject": "co_cau_to_chuc",
                "subject_score": 4,
                "subject_hits": [],
                "subject_scores": subject_scores,
                "need_llm_subject": False,
                "decision_mode": "safe_heuristic_accept",
                "decision_reason": "clear_structure_pattern",
            }

    if category == "thong_tin_tong_quan":
        if (
            contains_any(q_norm, ["dia chi", "so dien thoai", "email", "o dau", "gio lam viec"])
            and margin >= 2
        ):
            return {
                "subject": "thong_tin_lien_he",
                "subject_score": 4,
                "subject_hits": [],
                "subject_scores": subject_scores,
                "need_llm_subject": False,
                "decision_mode": "safe_heuristic_accept",
                "decision_reason": "clear_contact_pattern",
            }

    # -----------------------------------------------------
    # REJECT
    # -----------------------------------------------------
    return {
        "subject": None,
        "subject_score": best_subject_score,
        "subject_hits": best_hits,
        "subject_scores": subject_scores,
        "need_llm_subject": True,
        "decision_mode": "reject_to_llm",
        "decision_reason": {
            "best_subject": best_subject,
            "best_score": best_subject_score,
            "second_subject": second_subject,
            "second_score": second_subject_score,
            "margin": margin,
            "generic_only": is_generic_only,
            "min_strong_score": MIN_STRONG_SCORE,
            "min_margin": MIN_MARGIN,
        },
    }


# =========================================================
# 7) MAIN DETECTOR V5
# =========================================================

def detect_organization_metadata_fast_v5(q_norm: str) -> dict:

    raw_matches = find_phrase_matches(q_norm)
    resolved_matches = resolve_phrase_matches(raw_matches)
    resolved_hits = {m.text for m in resolved_matches}

    topic_result = extract_topic_hint_v5(resolved_matches)
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

    intent_flags = detect_intent_flags(q_norm)

    category_result = extract_category_for_organization(
        q_norm=q_norm,
        organization_type=organization_type,
        subject=None,
    )
    category = category_result["category"]

    subject_result = extract_subject_standard(
        q_norm=q_norm,
        hits=resolved_hits,
        category=category,
        topic_hint=topic_hint,
        intent_flags=intent_flags,
    )
    subject = subject_result["subject"]

    # derive lại category nếu subject cho thấy bo may rõ hơn
    category_result = extract_category_for_organization(
        q_norm=q_norm,
        organization_type=organization_type,
        subject=subject,
    )
    category = category_result["category"]

    matched = organization_type in {"cong_doan", "hoi_phu_nu", "doan_thanh_nien", "mttq"}

    base = 0.25
    if organization_type:
        base += 0.25
    if category is not None:
        base += 0.15
    if subject is not None:
        base += 0.20
    if topic_hint is not None:
        base += 0.10
    if conflict:
        base -= 0.20
    confidence = round(max(0.0, min(base, 0.98)), 3)

    return {
        "matched": matched,
        "organization_type": organization_type,
        "category": category,
        "subject": subject,
        "topic_hint": topic_hint,
        "intent_flags": intent_flags,
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
            "subject_hits": subject_result["subject_hits"],
            "subject_scores": subject_result["subject_scores"],
            "topic_conflict": topic_result["topic_conflict"],
            "subject_decision_mode": subject_result.get("decision_mode"),
            "subject_decision_reason": subject_result.get("decision_reason"),
        },
        "need_llm_organization_type": need_llm_organization_type,
        "need_llm_category": category_result["need_llm_category"],
        "need_llm_subject": subject_result["need_llm_subject"],
        "conflict": conflict,
        "source": {
            "organization_type": organization_source,
            "category": category_result["source"],
            "topic": topic_result["topic_source"],
            "subject": subject_result.get("decision_mode"),
        }
    }


# =========================================================
# 8) TEST MAIN
# =========================================================

# if __name__ == "__main__":
#     for q in [
#         "bí thư phường là ai"
        
#     ]:
#         result = detect_organization_metadata_fast_v5(q)

#         print(f"Question: {q}")
#         print(f"Domain: {result['organization_type']}")
#         print(f"Category: {result['category']}")
#         print(f"Subject: {result['subject']}")
#         print(f"Topic hint: {result['topic_hint']}")
#         print(f"Need LLM Organization Type: {result['need_llm_organization_type']}")
#         print(f"Need LLM Category: {result['need_llm_category']}")
#         print(f"Need LLM Subject: {result['need_llm_subject']}")
#         print(f"signals.resolved_matches: {result['signals']['resolved_matches']}")
#         print(f"subject_decision_mode: {result['signals']['subject_decision_mode']}")
#         print(f"subject_decision_reason: {result['signals']['subject_decision_reason']}")
#         print(f"Source: {result['source']}")
#         print("-" * 50)