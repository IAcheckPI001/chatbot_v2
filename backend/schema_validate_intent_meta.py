from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
from openai import OpenAI
from costing import count_tokens

import json
import os

from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# =========================================================
# 0) ORG / INTENT CONSTANTS
# =========================================================

ORG_UBND = "ubnd"
ORG_DANG_UY = "dang_uy"
ORG_DOAN_THANH_NIEN = "doan_thanh_nien"
ORG_HOI_PHU_NU = "hoi_phu_nu"
ORG_MTTQ = "mttq"
ORG_CONG_DOAN = "cong_doan"

ALL_ORG_TYPES = [
    ORG_UBND,
    ORG_DANG_UY,
    ORG_DOAN_THANH_NIEN,
    ORG_HOI_PHU_NU,
    ORG_MTTQ,
    ORG_CONG_DOAN,
]

INTENT_TRA_CUU_THONG_TIN = "tra_cuu_thong_tin"
INTENT_HOI_NHAN_SU = "hoi_nhan_su"
INTENT_HOI_THU_TUC = "hoi_thu_tuc"
INTENT_PHAN_ANH_KIEN_NGHI = "phan_anh_kien_nghi"
INTENT_SINH_HOAT_DANG = "sinh_hoat_dang"
INTENT_QUYEN_LOI_HO_TRO = "quyen_loi_ho_tro"
INTENT_THAM_GIA_TO_CHUC = "tham_gia_to_chuc"

ALL_INTENTS = [
    INTENT_TRA_CUU_THONG_TIN,
    INTENT_HOI_NHAN_SU,
    INTENT_HOI_THU_TUC,
    INTENT_PHAN_ANH_KIEN_NGHI,
    INTENT_SINH_HOAT_DANG,
    INTENT_QUYEN_LOI_HO_TRO,
    INTENT_THAM_GIA_TO_CHUC,
]

ORG_INTENTS: Dict[str, List[str]] = {
    ORG_UBND: [
        INTENT_TRA_CUU_THONG_TIN,
        INTENT_HOI_NHAN_SU,
        INTENT_HOI_THU_TUC,
        INTENT_PHAN_ANH_KIEN_NGHI,
    ],
    ORG_DANG_UY: [
        INTENT_TRA_CUU_THONG_TIN,
        INTENT_HOI_NHAN_SU,
        INTENT_SINH_HOAT_DANG,
    ],
    ORG_DOAN_THANH_NIEN: [
        INTENT_TRA_CUU_THONG_TIN,
        INTENT_HOI_NHAN_SU,
        INTENT_QUYEN_LOI_HO_TRO,
        INTENT_THAM_GIA_TO_CHUC,
    ],
    ORG_HOI_PHU_NU: [
        INTENT_TRA_CUU_THONG_TIN,
        INTENT_HOI_NHAN_SU,
        INTENT_QUYEN_LOI_HO_TRO,
        INTENT_THAM_GIA_TO_CHUC,
    ],
    ORG_MTTQ: [
        INTENT_TRA_CUU_THONG_TIN,
        INTENT_HOI_NHAN_SU,
        INTENT_QUYEN_LOI_HO_TRO,
        INTENT_THAM_GIA_TO_CHUC,
    ],
    ORG_CONG_DOAN: [
        INTENT_TRA_CUU_THONG_TIN,
        INTENT_HOI_NHAN_SU,
        INTENT_QUYEN_LOI_HO_TRO,
        INTENT_THAM_GIA_TO_CHUC,
        INTENT_PHAN_ANH_KIEN_NGHI,
    ],
}


# =========================================================
# 1) META ENUM CONSTANTS
# =========================================================

# ---------- Common query modes ----------
QUERY_MODE_INFO = "info"
QUERY_MODE_LIST = "list"
QUERY_MODE_COUNT = "count"
QUERY_MODE_IDENTITY = "identity"
QUERY_MODE_CONTACT = "contact"
QUERY_MODE_TITLE = "title"
QUERY_MODE_PROCEDURE = "procedure"
QUERY_MODE_CONDITION = "condition"
QUERY_MODE_DOCUMENT_REQUIRED = "document_required"
QUERY_MODE_FEE = "fee"
QUERY_MODE_DEADLINE = "deadline"
QUERY_MODE_MEMBERSHIP_RULE = "membership_rule"
QUERY_MODE_BENEFIT_SCOPE = "benefit_scope"


COMMON_PERSON_QUERY_MODES = [
    QUERY_MODE_IDENTITY,
    QUERY_MODE_LIST,
    QUERY_MODE_CONTACT,
    QUERY_MODE_TITLE,
    QUERY_MODE_COUNT,
]

COMMON_PARTICIPATION_QUERY_MODES = [
    QUERY_MODE_PROCEDURE,
    QUERY_MODE_CONDITION,
    QUERY_MODE_DOCUMENT_REQUIRED,
    QUERY_MODE_FEE,
    QUERY_MODE_DEADLINE,
    QUERY_MODE_MEMBERSHIP_RULE
]

COMMON_BENEFIT_QUERY_MODES = [
    QUERY_MODE_INFO,
    QUERY_MODE_LIST,
    QUERY_MODE_CONDITION,
    QUERY_MODE_BENEFIT_SCOPE,
    QUERY_MODE_FEE,
]

# ---------- UBND: tra_cuu_thong_tin ----------
UBND_INFO_ENTITIES = [
    "contact_info",
    "neighborhood",
    "local_overview",
    "work_schedule",
    "public_facility",
    "election_result",
]

UBND_INFO_FIELDS = [
    "address",
    "phone_hotline",
    "website",
    "email",
    "count",
    "list",
    "info",
    "office_hours",
    "reception_schedule",
    "weekend_service",
    "holiday_schedule",
    "result",
    "area",
    "location",
    "population",
    "boundaries",
    "history",
    "economy",
    "infrastructure",
]

# ---------- UBND: hoi_nhan_su ----------
UBND_PERSON_ROLES = [
    "lanh_dao",
    "chu_tich_hdnd",
    "pho_chu_tich_hdnd",
    "chu_tich_ubnd",
    "pho_chu_tich_ubnd",
    "truong_khu_pho",
    "truong_ap",
    "cong_chuc_tu_phap_ho_tich",
    "cong_chuc_dia_chinh",
    "cong_chuc_van_hoa_xa_hoi",
    "cong_an_xa",
    "chi_huy_truong_quan_su",
]

# ---------- UBND: hoi_thu_tuc ----------
UBND_PROCEDURE_GROUPS = [
    "tu_phap_ho_tich",
    "doanh_nghiep",
    "giao_thong_van_tai",
    "dat_dai",
    "xay_dung_nha_o",
    "dau_tu",
    "giao_duc_dao_tao",
    "lao_dong_viec_lam",
    "bao_hiem_an_sinh",
    "y_te",
    "tai_nguyen_moi_truong",
    "cong_thuong",
    "van_hoa_the_thao_du_lich",
    "tai_chinh_thue_phi",
    "khoa_hoc_cong_nghe",
    "thong_tin_truyen_thong",
    "nong_nghiep",
]

UBND_PROCEDURE_SPECIAL_CONTEXTS = [
    "yeu_to_nuoc_ngoai",
    "uy_quyen",
    "qua_han_dang_ky",
    "khu_vuc_bien_gioi",
    "mat_so_ho_tich_va_ban_chinh",
    "dang_ky",
    "dang_ky_lai",
    "cap_lai",
    "cap_doi",
    "cap_ban_sao",
    "cap_phep",
    "thay_doi",
    "bo_sung",
    "cai_chinh",
    "thu_hoi",
    "huy_bo",
    "xac_nhan",
    "ghi_vao_so",
    "ho_tro",
    "tro_cap",
    "cham_dut",
    "tam_ngung",
    "tiep_tuc"
]

# ---------- Feedback ----------
COMMON_FEEDBACK_SUBTYPES = [
    "phan_anh",
    "kien_nghi",
    "khieu_nai",
    "to_cao",
]

UBND_FEEDBACK_DOMAINS = [
    "moi_truong",
    "ha_tang_do_thi",
    "giao_thong",
    "an_ninh_trat_tu",
    "thu_tuc_hanh_chinh",
]

# ---------- Dang uy ----------
DANG_UY_INFO_ENTITIES = [
    "organization_overview",
    "organization_structure",
    "party_activity_info",
    "document_info",
    "contact_info",
]

DANG_UY_INFO_FIELDS = [
    "info",
    "list",
    "count",
    "address",
    "phone_hotline",
    "email",
    "website",
]

DANG_UY_PERSON_ROLES = [
    "bi_thu_dang_uy",
    "pho_bi_thu_dang_uy",
    "lanh_dao_dang_uy",
]

DANG_UY_ACTIVITY_TOPICS = [
    "ket_nap_dang",
    "chuyen_sinh_hoat_dang",
    "dang_phi",
]

DANG_UY_ACTIVITY_QUERY_MODES = [
    QUERY_MODE_PROCEDURE,
    QUERY_MODE_CONDITION,
    QUERY_MODE_DOCUMENT_REQUIRED,
    QUERY_MODE_FEE,
    QUERY_MODE_DEADLINE,
]

# ---------- Mass org common: info ----------
MASS_ORG_INFO_ENTITIES = [
    "organization_overview",
    "activity_info",
    "support_info",
    "member_info",
    "contact_info",
]

MASS_ORG_INFO_FIELDS = [
    "info",
    "list",
    "count",
    "address",
    "phone_hotline",
    "email",
    "website",
]

# ---------- Doan thanh nien ----------
DOAN_PERSON_ROLES = [
    "bi_thu_doan",
    "pho_bi_thu_doan",
    "ban_chap_hanh_doan",
    "lanh_dao_doan",
]

DOAN_BENEFIT_TOPICS = [
    "quyen_loi_doan_vien",
    "nghia_vu_doan_vien",
    "ho_tro_doan_vien",
]

DOAN_PARTICIPATION_TOPICS = [
    "ket_nap_doan",
    "chuyen_sinh_hoat_doan",
    "cap_lai_so_doan",
    "cap_lai_the_doan",
    "hoc_cam_tinh_doan",
    "dong_doan_phi",
]

# ---------- Hoi phu nu ----------
HPN_PERSON_ROLES = [
    "chu_tich_hoi_phu_nu",
    "pho_chu_tich_hoi_phu_nu",
    "ban_chap_hanh_hoi_phu_nu",
    "lanh_dao_hoi_phu_nu",
]

HPN_BENEFIT_TOPICS = [
    "quyen_loi_hoi_vien_phu_nu",
    "ho_tro_hoi_vien_phu_nu",
]

HPN_PARTICIPATION_TOPICS = [
    "tham_gia_hoi_phu_nu",
    "dong_hoi_phi_phu_nu",
]

# ---------- MTTQ ----------
MTTQ_PERSON_ROLES = [
    "chu_tich_mttq",
    "pho_chu_tich_mttq",
    "ban_thuong_truc_mttq",
    "lanh_dao_mttq",
]

# MTTQ_BENEFIT_TOPICS = [
#     "ho_tro_nguoi_dan",
#     "vai_tro_bao_ve_quyen_loi_cong_dong",
# ]
MTTQ_BENEFIT_TOPICS = [
    "bao_ve_quyen_loi_nhan_dan",
    "dai_dien_y_chi_nguyen_vong_nhan_dan",
    "giam_sat_phan_bien_xa_hoi",
    "quyen_trach_nhiem_to_chuc_thanh_vien",
    "phan_anh_kien_nghi_cua_nhan_dan"
]

# MTTQ_PARTICIPATION_TOPICS = [
#     "tham_gia_mat_tran",
# ]
MTTQ_PARTICIPATION_TOPICS = [
    "gia_nhap_thanh_vien_mttq",
    "thoi_lam_thanh_vien_mttq",
    "tham_gia_hoat_dong_mat_tran"
]

# ---------- Cong doan ----------
CONG_DOAN_PERSON_ROLES = [
    "chu_tich_cong_doan",
    "pho_chu_tich_cong_doan",
    "ban_chap_hanh_cong_doan",
    "lanh_dao_cong_doan",
]

CONG_DOAN_BENEFIT_TOPICS = [
    "quyen_loi_cong_doan_vien",
    "bao_ve_nguoi_lao_dong",
    "ho_tro_nguoi_lao_dong",
]

CONG_DOAN_PARTICIPATION_TOPICS = [
    "ket_nap_cong_doan",
    "dong_cong_doan_phi",
]

CONG_DOAN_FEEDBACK_DOMAINS = [
    "tien_luong",
    "bao_hiem_xa_hoi",
    "dieu_kien_lao_dong",
    "hop_dong_lao_dong",
    "quyen_loi_nguoi_lao_dong",
]



SCORING_CONFIG = {
    ("ubnd", "tra_cuu_thong_tin"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.07,
        "meta_cap": 0.22,
    },
    ("ubnd", "hoi_nhan_su"): {
        "w_intent": 0.05,
        "w_primary": 0.16,
        "w_mode": 0.06,
        "meta_cap": 0.22,
    },
    ("ubnd", "hoi_thu_tuc"): {
        "w_intent": 0.05,
        "w_primary": 0.16,
        "w_mode": 0.06,
        "meta_cap": 0.22,
    },
    ("ubnd", "phan_anh_kien_nghi"): {
        "w_intent": 0.05,
        "w_primary": 0.17,
        "w_mode": 0.05,
        "meta_cap": 0.22,
    },
    ("dang_uy", "tra_cuu_thong_tin"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.07,
        "meta_cap": 0.22,
    },
    ("dang_uy", "hoi_nhan_su"): {
        "w_intent": 0.05,
        "w_primary": 0.16,
        "w_mode": 0.06,
        "meta_cap": 0.22,
    },
    ("dang_uy", "sinh_hoat_dang"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.06,
        "meta_cap": 0.21,
    },
    ("doan_thanh_nien", "tra_cuu_thong_tin"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.07,
        "meta_cap": 0.22,
    },
    ("doan_thanh_nien", "hoi_nhan_su"): {
        "w_intent": 0.05,
        "w_primary": 0.16,
        "w_mode": 0.06,
        "meta_cap": 0.22,
    },
    ("doan_thanh_nien", "quyen_loi_ho_tro"): {
        "w_intent": 0.05,
        "w_primary": 0.14,
        "w_mode": 0.06,
        "meta_cap": 0.20,
    },
    ("doan_thanh_nien", "tham_gia_to_chuc"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.06,
        "meta_cap": 0.21,
    },
    
    ("hoi_phu_nu", "tra_cuu_thong_tin"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.07,
        "meta_cap": 0.22,
    },
    ("hoi_phu_nu", "hoi_nhan_su"): {
        "w_intent": 0.05,
        "w_primary": 0.16,
        "w_mode": 0.06,
        "meta_cap": 0.22,
    },
    ("hoi_phu_nu", "quyen_loi_ho_tro"): {
        "w_intent": 0.05,
        "w_primary": 0.14,
        "w_mode": 0.06,
        "meta_cap": 0.20,
    },
    ("hoi_phu_nu", "tham_gia_to_chuc"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.06,
        "meta_cap": 0.21,
    },

    ("cong_doan", "tra_cuu_thong_tin"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.06,
        "meta_cap": 0.22,
    },
    ("cong_doan", "hoi_nhan_su"): {
        "w_intent": 0.05,
        "w_primary": 0.16,
        "w_mode": 0.06,
        "meta_cap": 0.23,
    },
    ("cong_doan", "quyen_loi_ho_tro"): {
        "w_intent": 0.05,
        "w_primary": 0.14,
        "w_mode": 0.06,
        "meta_cap": 0.20,
    },
    ("cong_doan", "tham_gia_to_chuc"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.06,
        "meta_cap": 0.21,
    },
    ("cong_doan", "phan_anh_kien_nghi"): {
        "w_intent": 0.05,
        "w_primary": 0.13,
        "w_mode": 0.05,
        "meta_cap": 0.18,
    },

    ("mttq", "tra_cuu_thong_tin"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.06,
        "meta_cap": 0.22,
    },
    ("mttq", "hoi_nhan_su"): {
        "w_intent": 0.05,
        "w_primary": 0.16,
        "w_mode": 0.06,
        "meta_cap": 0.23,
    },
    ("mttq", "quyen_loi_ho_tro"): {
        "w_intent": 0.05,
        "w_primary": 0.14,
        "w_mode": 0.06,
        "meta_cap": 0.20,
    },
    ("mttq", "tham_gia_to_chuc"): {
        "w_intent": 0.05,
        "w_primary": 0.15,
        "w_mode": 0.06,
        "meta_cap": 0.21,
    }

}


# =========================================================
# 2) SCHEMA HELPERS
# =========================================================

def _make_array_enum_property(values: List[str], min_items: int = 1) -> Dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "string",
            "enum": values,
        },
        "minItems": min_items,
    }


def _make_object_schema(
    *,
    properties: Dict[str, Any],
    required: List[str],
) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _make_enum_property(values: List[str]) -> Dict[str, Any]:
    return {
        "type": "string",
        "enum": values,
    }


def _make_meta_prompt_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for field_name, field_def in schema["properties"].items():
        field_type = field_def.get("type")
        if field_type == "string":
            compact[field_name] = list(field_def.get("enum", []))
        elif field_type == "array":
            compact[field_name] = list(field_def.get("items", {}).get("enum", []))
    return compact


# =========================================================
# 3) META SCHEMAS BY (ORG, INTENT)
# =========================================================

PRIMARY_KEYS = ["entity", "role", "topic", "domain", "procedure_group"]
MODE_KEYS = ["fields", "query_mode", "special_contexts", "subtype"]

UBND_INFO_SCHEMA = _make_object_schema(
    properties={
        "entity": _make_enum_property(UBND_INFO_ENTITIES),
        "fields": _make_array_enum_property(UBND_INFO_FIELDS),
    },
    required=["entity", "fields"],
)

UBND_PERSON_SCHEMA = _make_object_schema(
    properties={
        "role": _make_enum_property(UBND_PERSON_ROLES),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

UBND_PROCEDURE_SCHEMA = _make_object_schema(
    properties={
        "procedure_group": _make_enum_property(UBND_PROCEDURE_GROUPS),
        "special_contexts": _make_array_enum_property(UBND_PROCEDURE_SPECIAL_CONTEXTS, min_items=0),
    },
    required=["procedure_group", "special_contexts"],
)

UBND_FEEDBACK_SCHEMA = _make_object_schema(
    properties={
        "domain": _make_enum_property(UBND_FEEDBACK_DOMAINS),
        "subtype": _make_array_enum_property(COMMON_FEEDBACK_SUBTYPES),
    },
    required=["domain", "subtype"],
)

DANG_UY_INFO_SCHEMA = _make_object_schema(
    properties={
        "entity": _make_enum_property(DANG_UY_INFO_ENTITIES),
        "fields": _make_array_enum_property(DANG_UY_INFO_FIELDS),
    },
    required=["entity", "fields"],
)

DANG_UY_PERSON_SCHEMA = _make_object_schema(
    properties={
        "role": _make_enum_property(DANG_UY_PERSON_ROLES),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

DANG_UY_ACTIVITY_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(DANG_UY_ACTIVITY_TOPICS),
        "query_mode": _make_array_enum_property(DANG_UY_ACTIVITY_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

MASS_ORG_INFO_SCHEMA = _make_object_schema(
    properties={
        "entity": _make_enum_property(MASS_ORG_INFO_ENTITIES),
        "fields": _make_array_enum_property(MASS_ORG_INFO_FIELDS),
    },
    required=["entity", "fields"],
)

DOAN_PERSON_SCHEMA = _make_object_schema(
    properties={
        "role": _make_enum_property(DOAN_PERSON_ROLES),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

DOAN_BENEFIT_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(DOAN_BENEFIT_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

DOAN_JOIN_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(DOAN_PARTICIPATION_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_PARTICIPATION_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

HPN_PERSON_SCHEMA = _make_object_schema(
    properties={
        "role": _make_enum_property(HPN_PERSON_ROLES),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

HPN_BENEFIT_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(HPN_BENEFIT_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

HPN_JOIN_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(HPN_PARTICIPATION_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_PARTICIPATION_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

MTTQ_PERSON_SCHEMA = _make_object_schema(
    properties={
        "role": _make_enum_property(MTTQ_PERSON_ROLES),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

MTTQ_BENEFIT_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(MTTQ_BENEFIT_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

MTTQ_JOIN_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(MTTQ_PARTICIPATION_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_PARTICIPATION_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

CONG_DOAN_PERSON_SCHEMA = _make_object_schema(
    properties={
        "role": _make_enum_property(CONG_DOAN_PERSON_ROLES),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

CONG_DOAN_BENEFIT_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(CONG_DOAN_BENEFIT_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

CONG_DOAN_JOIN_SCHEMA = _make_object_schema(
    properties={
        "topic": _make_enum_property(CONG_DOAN_PARTICIPATION_TOPICS),
        "query_mode": _make_array_enum_property(COMMON_PARTICIPATION_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

CONG_DOAN_FEEDBACK_SCHEMA = _make_object_schema(
    properties={
        "domain": _make_enum_property(CONG_DOAN_FEEDBACK_DOMAINS),
        "subtype": _make_array_enum_property(COMMON_FEEDBACK_SUBTYPES),
    },
    required=["domain", "subtype"],
)

META_SCHEMA_REGISTRY: Dict[Tuple[str, str], Dict[str, Any]] = {
    (ORG_UBND, INTENT_TRA_CUU_THONG_TIN): UBND_INFO_SCHEMA,
    (ORG_UBND, INTENT_HOI_NHAN_SU): UBND_PERSON_SCHEMA,
    (ORG_UBND, INTENT_HOI_THU_TUC): UBND_PROCEDURE_SCHEMA,
    (ORG_UBND, INTENT_PHAN_ANH_KIEN_NGHI): UBND_FEEDBACK_SCHEMA,

    (ORG_DANG_UY, INTENT_TRA_CUU_THONG_TIN): DANG_UY_INFO_SCHEMA,
    (ORG_DANG_UY, INTENT_HOI_NHAN_SU): DANG_UY_PERSON_SCHEMA,
    (ORG_DANG_UY, INTENT_SINH_HOAT_DANG): DANG_UY_ACTIVITY_SCHEMA,

    (ORG_DOAN_THANH_NIEN, INTENT_TRA_CUU_THONG_TIN): MASS_ORG_INFO_SCHEMA,
    (ORG_DOAN_THANH_NIEN, INTENT_HOI_NHAN_SU): DOAN_PERSON_SCHEMA,
    (ORG_DOAN_THANH_NIEN, INTENT_QUYEN_LOI_HO_TRO): DOAN_BENEFIT_SCHEMA,
    (ORG_DOAN_THANH_NIEN, INTENT_THAM_GIA_TO_CHUC): DOAN_JOIN_SCHEMA,

    (ORG_HOI_PHU_NU, INTENT_TRA_CUU_THONG_TIN): MASS_ORG_INFO_SCHEMA,
    (ORG_HOI_PHU_NU, INTENT_HOI_NHAN_SU): HPN_PERSON_SCHEMA,
    (ORG_HOI_PHU_NU, INTENT_QUYEN_LOI_HO_TRO): HPN_BENEFIT_SCHEMA,
    (ORG_HOI_PHU_NU, INTENT_THAM_GIA_TO_CHUC): HPN_JOIN_SCHEMA,

    (ORG_MTTQ, INTENT_TRA_CUU_THONG_TIN): MASS_ORG_INFO_SCHEMA,
    (ORG_MTTQ, INTENT_HOI_NHAN_SU): MTTQ_PERSON_SCHEMA,
    (ORG_MTTQ, INTENT_QUYEN_LOI_HO_TRO): MTTQ_BENEFIT_SCHEMA,
    (ORG_MTTQ, INTENT_THAM_GIA_TO_CHUC): MTTQ_JOIN_SCHEMA,

    (ORG_CONG_DOAN, INTENT_TRA_CUU_THONG_TIN): MASS_ORG_INFO_SCHEMA,
    (ORG_CONG_DOAN, INTENT_HOI_NHAN_SU): CONG_DOAN_PERSON_SCHEMA,
    (ORG_CONG_DOAN, INTENT_QUYEN_LOI_HO_TRO): CONG_DOAN_BENEFIT_SCHEMA,
    (ORG_CONG_DOAN, INTENT_THAM_GIA_TO_CHUC): CONG_DOAN_JOIN_SCHEMA,
    (ORG_CONG_DOAN, INTENT_PHAN_ANH_KIEN_NGHI): CONG_DOAN_FEEDBACK_SCHEMA,
}


# =========================================================
# 4) PROMPT SCHEMA BUILDERS
# =========================================================

def get_allowed_intents(org_type: str) -> List[str]:
    return list(ORG_INTENTS.get(org_type, []))


def get_meta_schema(org_type: str, intent: str) -> Optional[Dict[str, Any]]:
    schema = META_SCHEMA_REGISTRY.get((org_type, intent))
    return deepcopy(schema) if schema else None


def get_meta_schema_prompt(org_type: str, intent: Optional[str] = None) -> Dict[str, Any]:
    """
    Return a compact prompt-friendly schema.

    - If intent is provided: return schema for exactly (org_type, intent)
    - If intent is None: return allowed intents and compact schemas for each intent
    """
    if org_type not in ALL_ORG_TYPES:
        raise ValueError(f"Unsupported org_type: {org_type}")

    if intent is not None:
        if intent not in ORG_INTENTS.get(org_type, []):
            raise ValueError(f"Intent '{intent}' is not allowed for org_type '{org_type}'")

        schema = get_meta_schema(org_type, intent)
        if not schema:
            raise ValueError(f"No meta schema found for ({org_type}, {intent})")

        return {
            "organization_type": org_type,
            "intent": intent,
            "meta_schema": _make_meta_prompt_schema(schema),
        }

    allowed_intents = get_allowed_intents(org_type)
    schemas_by_intent: Dict[str, Dict[str, Any]] = {}
    for allowed_intent in allowed_intents:
        schema = get_meta_schema(org_type, allowed_intent)
        if schema:
            schemas_by_intent[allowed_intent] = _make_meta_prompt_schema(schema)

    return {
        "organization_type": org_type,
        "allowed_intents": allowed_intents,
        "schemas_by_intent": schemas_by_intent,
    }


# =========================================================
# 5) VALIDATION HELPERS
# =========================================================

def _validate_string_enum(field_name: str, value: Any, allowed_values: List[str], errors: List[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"meta.{field_name} must be a string")
        return
    if value not in allowed_values:
        errors.append(
            f"meta.{field_name} invalid value '{value}', allowed={allowed_values}"
        )


def _validate_array_enum(field_name: str, value: Any, allowed_values: List[str], errors: List[str], min_items: int = 1) -> None:
    if not isinstance(value, list):
        errors.append(f"meta.{field_name} must be an array")
        return

    if len(value) < min_items:
        errors.append(f"meta.{field_name} must contain at least {min_items} item(s)")
        return

    seen_invalid = [item for item in value if not isinstance(item, str) or item not in allowed_values]
    if seen_invalid:
        errors.append(
            f"meta.{field_name} contains invalid value(s) {seen_invalid}, allowed={allowed_values}"
        )


def _validate_meta_against_schema(meta: Any, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if not isinstance(meta, dict):
        return False, ["meta must be an object"]

    allowed_fields = set(schema["properties"].keys())
    required_fields = set(schema.get("required", []))
    actual_fields = set(meta.keys())

    missing = sorted(required_fields - actual_fields)
    unexpected = sorted(actual_fields - allowed_fields)

    if missing:
        errors.append(f"meta missing required field(s): {missing}")
    if unexpected:
        errors.append(f"meta contains unexpected field(s): {unexpected}")

    for field_name, field_def in schema["properties"].items():
        if field_name not in meta:
            continue

        field_type = field_def.get("type")
        if field_type == "string":
            _validate_string_enum(field_name, meta[field_name], field_def.get("enum", []), errors)
        elif field_type == "array":
            _validate_array_enum(
                field_name,
                meta[field_name],
                field_def.get("items", {}).get("enum", []),
                errors,
                min_items=field_def.get("minItems", 0),
            )
        else:
            errors.append(f"Unsupported schema type for field '{field_name}': {field_type}")

    return len(errors) == 0, errors


# =========================================================
# 6) MAIN VALIDATOR
# =========================================================

def validate_llm_meta_output(
    output: Dict[str, Any],
    *,
    expected_org_type: Optional[str] = None,
    expected_intent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate LLM output for both modes:

    Mode A:
        expected_org_type is set
        expected_intent is set
        -> meta only needs to match that schema

    Mode B:
        expected_org_type is set
        expected_intent is None
        -> intent must be valid for org, then meta must match inferred schema

    Returns:
        {
          "ok": bool,
          "normalized": {...} | None,
          "errors": [...],
          "schema_key": (org_type, intent) | None,
        }
    """
    errors: List[str] = []

    if not isinstance(output, dict):
        return {
            "ok": False,
            "normalized": None,
            "errors": ["output must be a dict"],
            "schema_key": None,
        }

    organization_type = output.get("organization_type")
    intent = output.get("intent")
    meta = output.get("meta")
    confidence = output.get("confidence")
    needs_clarification = output.get("needs_clarification")
    clarification_reason = output.get("clarification_reason")

    if expected_org_type is not None:
        if organization_type != expected_org_type:
            errors.append(
                f"organization_type must be '{expected_org_type}', got '{organization_type}'"
            )
    else:
        if organization_type not in ALL_ORG_TYPES:
            errors.append(f"organization_type invalid: '{organization_type}'")

    effective_org_type = expected_org_type or organization_type

    if expected_intent is not None:
        if intent != expected_intent:
            errors.append(f"intent must be '{expected_intent}', got '{intent}'")
    else:
        if effective_org_type is None:
            errors.append("cannot validate intent because organization_type is missing")
        else:
            allowed_intents = ORG_INTENTS.get(effective_org_type, [])
            if intent not in allowed_intents:
                errors.append(
                    f"intent '{intent}' is not allowed for organization_type '{effective_org_type}', allowed={allowed_intents}"
                )

    effective_intent = expected_intent or intent

    if confidence is not None and not isinstance(confidence, (int, float)):
        errors.append("confidence must be a number")
    elif isinstance(confidence, (int, float)) and not (0.0 <= float(confidence) <= 1.0):
        errors.append("confidence must be within [0.0, 1.0]")

    if needs_clarification is not None and not isinstance(needs_clarification, bool):
        errors.append("needs_clarification must be a boolean")

    if clarification_reason is not None and not isinstance(clarification_reason, str):
        errors.append("clarification_reason must be a string or null")

    schema_key: Optional[Tuple[str, str]] = None
    if effective_org_type and effective_intent:
        schema_key = (effective_org_type, effective_intent)
        schema = META_SCHEMA_REGISTRY.get(schema_key)
        if not schema:
            errors.append(f"no schema found for ({effective_org_type}, {effective_intent})")
        else:
            meta_ok, meta_errors = _validate_meta_against_schema(meta, schema)
            if not meta_ok:
                errors.extend(meta_errors)

    ok = len(errors) == 0
    normalized = None
    if ok:
        normalized = {
            "organization_type": effective_org_type,
            "intent": effective_intent,
            "meta": deepcopy(meta),
            "confidence": float(confidence) if confidence is not None else None,
            "needs_clarification": bool(needs_clarification) if needs_clarification is not None else False,
            "clarification_reason": clarification_reason,
        }

    return {
        "ok": ok,
        "normalized": normalized,
        "errors": errors,
        "schema_key": schema_key,
    }

# def extract_primary_and_modes(meta_result: dict):
#     meta = meta_result.get("meta", {})

#     primary_value = None
#     mode_values = []

#     for key in PRIMARY_KEYS:
#         if key in meta and meta[key]:
#             primary_value = meta[key]
#             break

#     for key in MODE_KEYS:
#         if key in meta and meta[key]:
#             value = meta[key]
#             if isinstance(value, list):
#                 mode_values.extend(value)
#             else:
#                 mode_values.append(value)

#     return primary_value, mode_values
from normalize import ensure_list_str
def build_meta_payload(intent: str, meta: dict) -> dict:
    primary_values = []
    mode_values = []

    if intent == "tra_cuu_thong_tin":
        primary_values = ensure_list_str(meta.get("entity"))
        mode_values = ensure_list_str(meta.get("fields"))
    elif intent == "hoi_nhan_su":
        primary_values = ensure_list_str(meta.get("role"))
        mode_values = ensure_list_str(meta.get("query_mode"))

    elif intent == "hoi_thu_tuc":
        primary_values = ensure_list_str(meta.get("procedure_group"))
        mode_values = ensure_list_str(meta.get("special_contexts", []))

    elif intent == "phan_anh_kien_nghi":
        primary_values = ensure_list_str(meta.get("domain"))
        mode_values = ensure_list_str(meta.get("subtype"))

    elif intent in {"sinh_hoat_dang", "quyen_loi_ho_tro", "tham_gia_to_chuc"}:
        primary_values = ensure_list_str(meta.get("topic"))
        mode_values = ensure_list_str(meta.get("query_mode"))

    return {
        "primary_values": primary_values,
        "mode_values": mode_values,
    }

def build_meta_extraction_messages(query: str, org_type: str, intent: str) -> List[dict]:
    schema_payload = get_meta_schema_prompt(org_type, intent=intent)

    system_prompt = """
Bạn là bộ trích xuất metadata cho chatbot hành chính/tổ chức.

NHIỆM VỤ
- Chỉ trích xuất metadata theo đúng organization_type và intent đã được cung cấp.
- Giữ nguyên organization_type và intent đã cho.
- Không suy diễn vượt quá nội dung câu hỏi.
- Chỉ chọn giá trị nằm trong schema được cung cấp.
- Nếu một field trong schema là array, luôn trả về JSON array, kể cả khi chỉ có 1 giá trị.
- Nếu không đủ cơ sở để chọn chắc chắn, vẫn phải chọn giá trị gần nhất hợp lệ nhất trong schema, nhưng confidence phải thấp hơn.
- Không tạo thêm field ngoài schema.
- Không giải thích.
- Chỉ trả về đúng 1 JSON object hợp lệ.

QUY TẮC BẮT BUỘC
1. organization_type phải giữ nguyên như input.
2. intent phải giữ nguyên như input.
3. meta phải đúng schema.
4. Mọi giá trị string phải thuộc enum được cung cấp.
5. Mọi giá trị array phải là mảng các enum hợp lệ.
6. Nếu câu hỏi quá ngắn hoặc mơ hồ, không được bịa thêm ngữ cảnh.
7. needs_clarification chỉ bật true khi câu hỏi không đủ thông tin để chọn meta một cách hợp lý.

ĐỊNH DẠNG OUTPUT
{
  "organization_type": "...",
  "intent": "...",
  "meta": {...},
  "confidence": 0.0,
  "needs_clarification": false
}
""".strip()

    user_prompt = f"""
Trích xuất metadata cho câu hỏi sau.

INPUT
- query: "{query}"
- organization_type: "{org_type}"
- intent: "{intent}"

META_SCHEMA
{json.dumps(schema_payload["meta_schema"], ensure_ascii=False)}

YÊU CẦU CHỌN META
- Chỉ dùng giá trị trong META_SCHEMA
- Không thêm field ngoài schema
- Nếu query hỏi chính về đối tượng nào, chọn meta_primary tương ứng rõ nhất
- Nếu query có nhiều tín hiệu, ưu tiên tín hiệu trực tiếp nhất trong câu
- Nếu query hỏi "cần gì", "hồ sơ gì", "giấy tờ gì" => ưu tiên query_mode / context liên quan document_required
- Nếu query hỏi "điều kiện" => ưu tiên condition
- Nếu query hỏi "bao lâu", "khi nào", "thời hạn" => ưu tiên deadline nếu schema có
- Nếu query hỏi "lệ phí", "đóng bao nhiêu" => ưu tiên fee nếu schema có
- Nếu query hỏi "ai", "là ai", "gồm những ai", "danh sách" => ưu tiên query_mode thuộc nhân sự phù hợp
- Nếu query hỏi "địa chỉ", "số điện thoại", "email", "website" => ưu tiên field/contact phù hợp

Chỉ trả JSON.
""".strip()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    return messages


def build_intent_and_meta_extraction_messages(query: str, org_type: str) -> List[dict]:
    schema_payload = get_meta_schema_prompt(org_type, intent=None)

    system_prompt = """
Bạn là bộ trích xuất intent và metadata cho chatbot hành chính/tổ chức.

NHIỆM VỤ
- Chỉ chọn intent thuộc danh sách allowed_intents.
- Sau khi chọn intent, trích xuất meta đúng schema của intent đó.
- Không suy diễn vượt quá nội dung câu hỏi.
- Chỉ chọn giá trị nằm trong schema được cung cấp.
- Nếu một field trong schema là array, luôn trả về JSON array, kể cả khi chỉ có 1 giá trị.
- Không tạo thêm field ngoài schema.
- Không giải thích.
- Chỉ trả về đúng 1 JSON object hợp lệ.

QUY TẮC BẮT BUỘC
1. organization_type phải giữ nguyên như input.
2. intent phải thuộc allowed_intents.
3. meta phải đúng schema của intent đã chọn.
4. Mọi giá trị string phải thuộc enum được cung cấp.
5. Mọi giá trị array phải là mảng các enum hợp lệ.
6. Nếu câu hỏi quá ngắn hoặc mơ hồ, không được bịa thêm ngữ cảnh.
7. needs_clarification chỉ bật true khi câu hỏi không đủ thông tin để chọn intent hoặc meta một cách hợp lý.

ĐỊNH DẠNG OUTPUT
{
  "organization_type": "...",
  "intent": "...",
  "meta": {...},
  "confidence": 0.0,
  "needs_clarification": false
}
""".strip()

    user_prompt = f"""
Trích xuất intent và metadata cho câu hỏi sau.

INPUT
- query: "{query}"
- organization_type: "{org_type}"

ALLOWED_INTENTS
{json.dumps(schema_payload["allowed_intents"], ensure_ascii=False)}

SCHEMAS_BY_INTENT
{json.dumps(schema_payload["schemas_by_intent"], ensure_ascii=False)}

YÊU CẦU CHỌN INTENT
- Chỉ chọn 1 intent phù hợp nhất với ý chính của câu hỏi.
- Nếu câu hỏi hỏi về "ai", "là ai", "gồm những ai", "danh sách", "có mấy" => ưu tiên hoi_nhan_su nếu intent này được phép.
- Nếu câu hỏi hỏi về "cần gì", "hồ sơ gì", "giấy tờ gì", "thủ tục", "quy trình", "điều kiện", "bao lâu", "lệ phí" => ưu tiên intent thủ tục/tham gia/sinh hoạt tương ứng.
- Nếu câu hỏi hỏi về "quyền lợi", "được gì", "được hỗ trợ gì", "được hưởng gì", "nghĩa vụ" => ưu tiên quyen_loi_ho_tro nếu intent này được phép.
- Nếu câu hỏi hỏi về "phản ánh", "kiến nghị", "khiếu nại", "tố cáo" => ưu tiên phan_anh_kien_nghi nếu intent này được phép.
- Nếu câu hỏi hỏi về thông tin chung như địa chỉ, số điện thoại, email, website, chức năng, nhiệm vụ, hoạt động => ưu tiên tra_cuu_thong_tin nếu intent này được phép.

YÊU CẦU CHỌN META
- Chỉ dùng schema của intent đã chọn.
- Không thêm field ngoài schema.
- Nếu query có nhiều tín hiệu, ưu tiên tín hiệu trực tiếp nhất trong câu.
- Nếu query hỏi "cần gì", "hồ sơ gì", "giấy tờ gì" => ưu tiên query_mode / context liên quan document_required nếu schema có.
- Nếu query hỏi "điều kiện" => ưu tiên condition nếu schema có.
- Nếu query hỏi "bao lâu", "khi nào", "thời hạn" => ưu tiên deadline nếu schema có.
- Nếu query hỏi "lệ phí", "đóng bao nhiêu", "miễn phí không" => ưu tiên fee nếu schema có.
- Nếu query hỏi "địa chỉ", "số điện thoại", "email", "website" => ưu tiên field/contact phù hợp nếu schema có.

Chỉ trả JSON.
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

def classify_meta_with_intent(query: str, org_type: str, intent: str):

    context = build_meta_extraction_messages(query, org_type, intent)

    # print(f"Câu hỏi 1 -> token: {count_tokens(context)}")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=context,
        temperature=0.0,
        response_format={"type": "json_object"},  # 🔥 ép JSON
    )

    content = response.choices[0].message.content

    try:
        parsed = json.loads(content)
    except Exception:
        # fallback nếu LLM trả lỗi format
        return {
            "organization_type": org_type,
            "intent": intent,
            "meta": {},
            "confidence": 0.0,
            "needs_clarification": True
        }

    return parsed

def classify_meta_without_intent(query: str, org_type: str):

    context = build_intent_and_meta_extraction_messages(query, org_type)

    # print(f"Câu hỏi 1 -> token: {count_tokens(context)}")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=context,
        temperature=0.0,
        response_format={"type": "json_object"},  # 🔥 ép JSON
    )

    content = response.choices[0].message.content

    try:
        parsed = json.loads(content)
    except Exception:
        # fallback nếu LLM trả lỗi format
        return {
            "organization_type": org_type,
            "meta": {},
            "confidence": 0.0,
            "needs_clarification": True
        }

    return parsed


def build_meta_extraction_chunk(chunk_text: str, org_type: str, intent: str) -> List[dict]:
    schema_payload = get_meta_schema_prompt(org_type, intent=intent)

    system_prompt = """
Bạn là bộ gán metadata cho chunk tri thức trong kho dữ liệu của chatbot.

NHIỆM VỤ
- Chỉ trích xuất metadata theo đúng organization_type và intent đã được cung cấp.
- Giữ nguyên organization_type và intent đã cho.
- Chỉ chọn giá trị nằm trong schema được cung cấp.
- Không suy diễn vượt quá nội dung chunk.
- Ưu tiên nội dung xuất hiện trực tiếp trong chunk.
- Nếu chunk chứa nhiều ý, chỉ chọn 1 primary field phản ánh nội dung chính nhất.
- Chỉ các field được định nghĩa là array trong schema mới được trả về mảng.
- Nếu một field trong schema là array, luôn trả về JSON array, kể cả khi chỉ có 1 giá trị.
- Không tạo thêm field ngoài schema.
- Không giải thích.
- Chỉ trả về đúng 1 JSON object hợp lệ.

QUY TẮC BẮT BUỘC
1. organization_type và intent phải giữ nguyên như input.
2. meta phải đúng schema.
3. Mọi giá trị string phải thuộc enum được cung cấp.
4. Mọi giá trị array phải là mảng các enum hợp lệ.
5. Không được biến một giá trị enum thành tên field mới.
6. Nếu chunk nói chủ yếu về chức năng, nhiệm vụ, giới thiệu, liên hệ, cơ cấu, hoạt động chung của tổ chức thì ưu tiên hiểu là thông tin chung, không tự chuyển sang quyền lợi/hỗ trợ chỉ vì có một vài cụm từ liên quan.

ĐỊNH DẠNG OUTPUT
{
  "organization_type": "...",
  "intent": "...",
  "meta": {...},
  "confidence": 0.0
}
""".strip()

    user_prompt = f"""
Gán metadata cho chunk tri thức sau.

INPUT
- chunk_text: "{chunk_text}"
- organization_type: "{org_type}"
- intent: "{intent}"

META_SCHEMA
{json.dumps(schema_payload["meta_schema"], ensure_ascii=False)}

YÊU CẦU CHỌN META
- Chỉ dùng giá trị trong META_SCHEMA.
- Không thêm field ngoài schema.
- Chỉ chọn 1 primary field trực tiếp nhất.
- Các field phụ chỉ lấy khi xuất hiện rõ trong chunk.
- Nếu chunk chủ yếu liệt kê hồ sơ/giấy tờ => ưu tiên document_required nếu schema có.
- Nếu chunk chủ yếu nói về điều kiện => ưu tiên condition nếu schema có.
- Nếu chunk chủ yếu nói về lệ phí/đoàn phí/hội phí/đảng phí => ưu tiên fee nếu schema có.
- Nếu chunk chủ yếu nói về thời hạn/thời gian => ưu tiên deadline nếu schema có.
- Nếu chunk chủ yếu nói về địa chỉ/liên hệ => ưu tiên field/contact phù hợp nếu schema có.
- Nếu chunk vừa có nhiều ý phụ, chỉ chọn primary theo nội dung chiếm trọng tâm lớn nhất của chunk.

Chỉ trả JSON.
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


# def build_intent_and_meta_extraction_chunk(chunk_text: str, org_type: str) -> List[dict]:
#     schema_payload = get_meta_schema_prompt(org_type, intent=None)

#     system_prompt = """
# Bạn là bộ gán metadata cho chunk tri thức trong kho dữ liệu của chatbot.

# MỤC TIÊU
# Gán metadata sao cho chunk có thể được truy xuất đúng nhất khi người dùng đặt câu hỏi thực tế.

# CÁCH LÀM BẮT BUỘC
# Bạn phải phân tích NGẦM theo quy trình sau, nhưng KHÔNG được in các bước phân tích ra output:
# 1. Xác định nội dung chính nhất của chunk.
# 2. Hình dung 3-5 câu hỏi thực tế mà người dùng có thể hỏi và chunk này có thể dùng để trả lời.
# 3. Dựa trên nhóm câu hỏi giả định đó, chọn đúng 1 intent phù hợp nhất với chunk.
# 4. Dựa trên intent đã chọn, gán meta theo đúng schema của intent đó.
# 5. Nếu chunk có nhiều ý, chỉ chọn intent và primary field phản ánh phần nội dung chính nhất; các ý phụ chỉ dùng để bổ sung field phụ nếu xuất hiện rõ.

# NGUYÊN TẮC PHÂN LOẠI
# - Ưu tiên khả năng phục vụ truy vấn thực tế của người dùng, không chỉ nhìn từ khóa bề mặt.
# - Không suy diễn vượt quá nội dung chunk.
# - Ưu tiên nội dung xuất hiện trực tiếp trong chunk.
# - Nếu chunk là nội dung tổng hợp nhiều vai trò/chức danh nhưng cùng nói về một nhóm lãnh đạo, và schema primary chỉ cho phép 1 giá trị, phải chọn nhãn bao quát nhất.
# - Nếu chunk là roster/danh sách tổng hợp nhiều chức danh cùng nhóm, không trả về nhiều primary values cho field dạng string.
# - Nếu chunk chứa cả nội dung chính và ví dụ/ngoại lệ/trường hợp đặc biệt, intent và primary phải bám theo nội dung chính, không bám theo ngoại lệ.

# QUY TẮC CHỌN INTENT
# 1. Nếu chunk chủ yếu nói về giới thiệu chung, tên đầy đủ, khái niệm, bản chất tổ chức, chức năng, nhiệm vụ, vai trò chung, địa chỉ, liên hệ, cơ cấu, hoạt động chung => ưu tiên tra_cuu_thong_tin.
# 2. Chỉ chọn hoi_nhan_su khi chunk chủ yếu nói về người giữ chức vụ, danh sách cán bộ, ban chấp hành, ban lãnh đạo, vai trò nhân sự cụ thể.
# 3. Chỉ chọn quyen_loi_ho_tro khi chunk thật sự mô tả quyền lợi, nghĩa vụ, hỗ trợ, chế độ dành cho đối tượng thụ hưởng.
# 4. Chỉ chọn tham_gia_to_chuc khi chunk chủ yếu nói về điều kiện, hồ sơ, quy trình, thủ tục tham gia, kết nạp, chuyển sinh hoạt, cấp lại giấy tờ, đóng phí.
# 5. Chỉ chọn phan_anh_kien_nghi khi chunk chủ yếu nói về phản ánh, kiến nghị, khiếu nại, tố cáo.
# 6. Nếu không đủ chắc chắn, vẫn chọn intent gần nhất nhưng confidence phải thấp.

# QUY TẮC CHỌN META
# - Chỉ dùng schema của intent đã chọn.
# - Chỉ chọn 1 primary field trực tiếp nhất.
# - Các field phụ chỉ lấy khi xuất hiện rõ trong chunk và có giá trị cho retrieval.
# - Nếu chunk chủ yếu liệt kê hồ sơ/giấy tờ => ưu tiên document_required nếu schema có.
# - Nếu chunk chủ yếu nói về điều kiện/đối tượng áp dụng => ưu tiên condition nếu schema có.
# - Nếu chunk chủ yếu nói về lệ phí/đoàn phí/hội phí/đảng phí => ưu tiên fee nếu schema có.
# - Nếu chunk chủ yếu nói về thời hạn/thời gian => ưu tiên deadline nếu schema có.
# - Nếu chunk chủ yếu nói về danh sách => ưu tiên list nếu schema có query mode / fields tương ứng.
# - Nếu chunk chủ yếu nói về “ai là”, “gồm những ai”, “ban nào gồm ai” => ưu tiên identity hoặc list tùy schema.
# - Nếu chunk chủ yếu nói về liên hệ => ưu tiên field/contact phù hợp nếu schema có.

# QUY TẮC RẤT QUAN TRỌNG VỀ SCHEMA
# - Chỉ được dùng đúng các field có trong schema của intent đã chọn.
# - Không được tạo field mới.
# - Không được biến một GIÁ TRỊ enum thành tên field mới.
# - Nếu schema có:
#   {
#     "entity": [...],
#     "fields": [...]
#   }
#   thì "info", "list", "count", "address", "phone_hotline", "email", "website"
#   là giá trị của field "fields", không phải tên field mới.
# - Ví dụ đúng:
#   "meta": {"entity": "organization_overview", "fields": ["info"]}
# - Ví dụ sai:
#   "meta": {"entity": "organization_overview", "info": "..."}
# - Meta chỉ chứa nhãn phân loại, không chứa câu mô tả tự do.
# - Không được chép lại nguyên văn nội dung chunk vào meta.
# - Các field primary như entity, role, topic, domain, procedure_group phải là 1 string duy nhất, không phải mảng, trừ khi schema cho phép mảng.

# QUY TẮC CHO CHUNK TỔNG HỢP
# - Nếu chunk là danh sách tổng hợp nhiều chức vụ cùng nhóm lãnh đạo, hãy chọn role bao quát nhất như "lanh_dao_doan", không trả nhiều role.
# - Chỉ chọn role cụ thể như "bi_thu_doan", "pho_bi_thu_doan" khi chunk chủ yếu nói riêng về đúng vai trò đó.
# - Nếu chunk vừa có quy trình chính vừa có các trường hợp ngoại lệ, primary vẫn phải phản ánh thủ tục chính; các trường hợp ngoại lệ chỉ ảnh hưởng field phụ nếu thật sự rõ.

# ĐỊNH DẠNG OUTPUT
# Chỉ trả về đúng 1 JSON object hợp lệ:
# {
#   "organization_type": "...",
#   "intent": "...",
#   "meta": {...},
#   "confidence": 0.0
# }
# """.strip()

#     user_prompt = f"""
# Gán metadata cho chunk tri thức sau.

# INPUT
# - chunk_text: "{chunk_text}"
# - organization_type: "{org_type}"

# ALLOWED_INTENTS
# {json.dumps(schema_payload["allowed_intents"], ensure_ascii=False)}

# SCHEMAS_BY_INTENT
# {json.dumps(schema_payload["schemas_by_intent"], ensure_ascii=False)}

# YÊU CẦU THỰC HIỆN
# - Hãy phân tích chunk theo hướng: "người dùng có thể hỏi gì để chunk này trở thành câu trả lời phù hợp".
# - Từ đó chọn 1 intent và meta giúp retrieval chính xác nhất.
# - Không xuất ra các câu hỏi giả định, không giải thích, chỉ trả JSON cuối cùng.
# - Nếu chunk thiên về thông tin giới thiệu/khái niệm/tên đầy đủ/chức năng chung => thường nghiêng về tra_cuu_thong_tin.
# - nếu chunk nói về đại diện, bảo vệ quyền lợi Nhân dân, giám sát, phản biện, phản ánh kiến nghị của Nhân dân thì có thể xếp vào quyen_loi_ho_tro hoặc tra_cuu_thong_tin tùy nội dung là vai trò chung hay quyền/trách nhiệm cụ thể.
# - Nếu chunk thiên về điều kiện/hồ sơ/quy trình/chuyển sinh hoạt/cấp lại/đóng phí => thường nghiêng về tham_gia_to_chuc.
# - Nếu chunk thiên về danh sách người/chức danh/ban lãnh đạo => thường nghiêng về hoi_nhan_su.

# Chỉ trả JSON.
# """.strip()

#     return [
#         {"role": "system", "content": system_prompt},
#         {"role": "user", "content": user_prompt},
#     ]





# =========================================================
# 7) OPTIONAL EXAMPLE USAGE
# =========================================================

# if __name__ == "__main__":
#     # print("=== Prompt schema: fixed org + fixed intent ===")
#     # print(get_meta_schema_prompt(ORG_UBND, INTENT_HOI_THU_TUC))

#     # print("\n=== Prompt schema: fixed org, infer intent ===")
#     print(get_meta_schema_prompt("dang_uy", intent=None))
    # test_cases = [
    # A. UBND + hoi_thu_tuc
    # "Thủ tục cấp lại giấy khai sinh cần giấy tờ gì",
    # "Làm lại giấy khai sinh mất bao lâu",
    # "Cấp đổi căn cước cần lệ phí bao nhiêu",
    # "Đăng ký khai sinh cho con cần hồ sơ gì",
    # "Xác nhận tình trạng hôn nhân cần điều kiện gì",

    # # B. UBND + hoi_nhan_su
    # "Chủ tịch UBND phường là ai",
    # "Phó chủ tịch UBND là ai",
    # "Danh sách lãnh đạo UBND gồm những ai",
    # "Số điện thoại của chủ tịch UBND là gì",
    # "UBND có mấy phó chủ tịch",

    # # C. UBND + tra_cuu_thong_tin
    # "Địa chỉ UBND phường ở đâu",
    # "Email liên hệ của ủy ban là gì",
    # "Giờ làm việc của UBND như thế nào",
    # "Phường có bao nhiêu khu phố",
    # "Danh sách các khu phố của phường",

    # # D. UBND + phan_anh_kien_nghi
    # "Tôi muốn phản ánh ổ gà trước nhà",
    # "Tôi muốn khiếu nại việc chậm giải quyết hồ sơ",
    # "Tôi muốn tố cáo hành vi xả rác ra kênh",
    # "Tôi muốn góp ý về thái độ tiếp dân",
    # "Tôi muốn phản ánh mất an ninh trật tự trong khu phố",

    # E. Đảng ủy + sinh_hoat_dang
    # "Chuyển sinh hoạt đảng cần hồ sơ gì",
    # "Kết nạp đảng cần điều kiện gì",
    # "Đóng đảng phí như thế nào",
    # "Thời hạn chuyển sinh hoạt đảng là bao lâu",
    # "Kết nạp đảng cần những bước nào",

    # # F. Đoàn thanh niên + tham_gia_to_chuc
    # "Vào đoàn cần điều kiện gì",
    # "Kết nạp đoàn cần hồ sơ gì",
    # "Chuyển sinh hoạt đoàn cần thủ tục gì",
    # "Mất sổ đoàn thì cấp lại thế nào",
    # "Đóng đoàn phí bao nhiêu",

    # # G. Đoàn thanh niên + quyen_loi_ho_tro
    # "Đoàn viên có quyền lợi gì",
    # "Đoàn viên có nghĩa vụ gì",
    # "Đoàn viên được hỗ trợ gì và có được miễn đoàn phí không",
    # "Đoàn viên có được tham gia hoạt động gì",
    # "Đoàn viên có được miễn đoàn phí không",
    "tham gia đoàn thanh niên khác gì so với công đoàn"

    # # H. Công đoàn + phan_anh_kien_nghi
    # "Tôi muốn khiếu nại công ty chậm đóng BHXH",
    # "Tôi muốn phản ánh công ty nợ lương",
    # "Tôi muốn tố cáo công ty cho thôi việc trái luật",
    # "Tôi muốn phản ánh điều kiện lao động không an toàn",
    # "Tôi muốn kiến nghị về hợp đồng lao động không đúng quy định",
# ]
#     ORG_UBND = "doan_thanh_nien"
#     # INTENT_HOI_THU_TUC = "quyen_loi_ho_tro"
#     for query in test_cases:

#         result = classify_meta_without_intent(query, ORG_UBND)
#         print(f"Query: {query}")
#         print(result)
#         print("-" * 50)

    # sample_output = {
    #     "organization_type": "cong_doan",
    #     "intent": "phan_anh_kien_nghi",
    #     "meta": {
    #         "domain": "bao_hiem_xa_hoi",
    #         "subtype": ["khieu_nai"],
    #     },
    #     "confidence": 0.94,
    #     "needs_clarification": False,
    #     "clarification_reason": None,
    # }

    # print("\n=== Validate output ===")
    # print(validate_llm_meta_output(sample_output, expected_org_type=ORG_CONG_DOAN))
