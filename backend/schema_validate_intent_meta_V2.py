
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
from openai import OpenAI
import os
import json

from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ORG_UBND = "ubnd"
ORG_DANG_UY = "dang_uy"
ORG_DOAN_THANH_NIEN = "doan_thanh_nien"
ORG_HOI_PHU_NU = "hoi_phu_nu"
ORG_MTTQ = "mttq"
ORG_CONG_DOAN = "cong_doan"


INTENT_TRA_CUU_THONG_TIN = "tra_cuu_thong_tin"
INTENT_HOI_NHAN_SU = "hoi_nhan_su"
INTENT_HOI_THU_TUC = "hoi_thu_tuc"
INTENT_PHAN_ANH_KIEN_NGHI = "phan_anh_kien_nghi"
INTENT_SINH_HOAT_DANG = "sinh_hoat_dang"
INTENT_QUYEN_LOI_HO_TRO = "quyen_loi_ho_tro"
INTENT_THAM_GIA_TO_CHUC = "tham_gia_to_chuc"
QUERY_MODE_TITLE = "title"
QUERY_MODE_PROCEDURE = "procedure"
QUERY_MODE_CONDITION = "condition"
QUERY_MODE_DOCUMENT_REQUIRED = "document_required"
QUERY_MODE_FEE = "fee"
QUERY_MODE_DEADLINE = "deadline"

ALL_ORG_TYPES = [
    ORG_UBND,
    ORG_DANG_UY,
    ORG_DOAN_THANH_NIEN,
    ORG_HOI_PHU_NU,
    ORG_MTTQ,
    ORG_CONG_DOAN,
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
# V2 - COMMON QUERY MODES
# =========================================================

COMMON_PERSON_QUERY_MODES = [
    "identity",
    "list",
    "contact",
    "title",
    "count",
]

COMMON_BENEFIT_QUERY_MODES = [
    "info",
    "list",
    "condition",
    "benefit_scope",
    "fee",
]

COMMON_PARTICIPATION_QUERY_MODES = [
    "info",
    "procedure",
    "condition",
    "document_required",
    "fee",
    "deadline",
    "membership_rule",
]

# =========================================================
# V2 - COMMON INFO ENTITIES/FIELDS FOR MASS ORGS
# =========================================================

COMMON_MASS_INFO_ENTITIES_V2 = [
    "organization_overview",
    "role_mission",
    "principle_operation",
    "structure_organization",
    "member_info",
    "contact_info",
    "legal_document",
]

COMMON_MASS_INFO_FIELDS_V2 = [
    "info",
    "list",
    "count",
    "address",
    "phone_hotline",
    "email",
    "website",
    "legal_status",
    "coordination",
    "structure_levels",
    "standing_body",
    "served_objects",
    "member_scope",
    "document_reference",
]

DOAN_INFO_ENTITIES_V2 = COMMON_MASS_INFO_ENTITIES_V2
DOAN_INFO_FIELDS_V2 = COMMON_MASS_INFO_FIELDS_V2

HPN_INFO_ENTITIES_V2 = COMMON_MASS_INFO_ENTITIES_V2
HPN_INFO_FIELDS_V2 = COMMON_MASS_INFO_FIELDS_V2

MTTQ_INFO_ENTITIES_V2 = COMMON_MASS_INFO_ENTITIES_V2
MTTQ_INFO_FIELDS_V2 = COMMON_MASS_INFO_FIELDS_V2

CONG_DOAN_INFO_ENTITIES_V2 = COMMON_MASS_INFO_ENTITIES_V2
CONG_DOAN_INFO_FIELDS_V2 = COMMON_MASS_INFO_FIELDS_V2

# =========================================================
# V2 - INFO ENTITIES/FIELDS FOR UBND
# =========================================================
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

# =========================================================
# V2 - FEEDBACK TOPICS FOR UBND
# =========================================================
CONG_DOAN_FEEDBACK_DOMAINS = [
    "tien_luong",
    "bao_hiem_xa_hoi",
    "dieu_kien_lao_dong",
    "hop_dong_lao_dong",
    "quyen_loi_nguoi_lao_dong",
]

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
    "uy_vien_dang_uy",
    "uy_vien_ban_thuong_vu_dang_uy"
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

# =========================================================
# V2 - PERSON ROLES
# =========================================================

UBND_PERSON_ROLES = [
    "lanh_dao_ubnd",
    "lanh_dao_hdnd",
    "chu_tich_hdnd",
    "pho_chu_tich_hdnd",
    "chu_tich_ubnd",
    "pho_chu_tich_ubnd",
    "truong_khu_pho",
    "truong_ap",
    "truong_phong",
    "pho_truong_phong",
    "truong_ban",
    "pho_truong_ban",
    "chanh_van_phong",
    "pho_chanh_van_phong",
    "giam_doc",
    "pho_giam_doc"
]

DOAN_PERSON_ROLES_V2 = [
    "bi_thu_doan",
    "pho_bi_thu_doan",
    "ban_chap_hanh_doan",
    "ban_thuong_vu_doan",
    "lanh_dao_doan",
]

HPN_PERSON_ROLES_V2 = [
    "chu_tich_hoi_phu_nu",
    "pho_chu_tich_hoi_phu_nu",
    "ban_chap_hanh_hoi_phu_nu",
    "ban_thuong_vu_hoi_phu_nu",
    "lanh_dao_hoi_phu_nu",
]

MTTQ_PERSON_ROLES_V2 = [
    "chu_tich_mttq",
    "pho_chu_tich_mttq",
    "ban_thuong_truc_mttq",
    "uy_vien_uy_ban_mttq",
    "lanh_dao_mttq",
]

CONG_DOAN_PERSON_ROLES_V2 = [
    "chu_tich_cong_doan",
    "pho_chu_tich_cong_doan",
    "ban_chap_hanh_cong_doan",
    "ban_thuong_vu_cong_doan",
    "lanh_dao_cong_doan"
]

ALL_PERSON_ROLES = sorted(set(
    UBND_PERSON_ROLES
    + DANG_UY_PERSON_ROLES
    + DOAN_PERSON_ROLES_V2
    + HPN_PERSON_ROLES_V2
    + MTTQ_PERSON_ROLES_V2
    + CONG_DOAN_PERSON_ROLES_V2
))

# =========================================================
# V2 - BENEFIT TOPICS
# =========================================================



DOAN_BENEFIT_TOPICS_V2 = [
    "quyen_loi_doan_vien",
    "nghia_vu_doan_vien",
    "ho_tro_doan_vien",
    "chuong_trinh_ho_tro_thanh_nien",
]

HPN_BENEFIT_TOPICS_V2 = [
    "quyen_loi_hoi_vien_phu_nu",
    "nghia_vu_hoi_vien_phu_nu",
    "ho_tro_hoi_vien_phu_nu",
    "chuong_trinh_ho_tro_phu_nu",
]

MTTQ_BENEFIT_TOPICS_V2 = [
    "bao_ve_quyen_loi_nhan_dan",
    "dai_dien_y_chi_nguyen_vong_nhan_dan",
    "giam_sat_phan_bien_xa_hoi",
    "quyen_trach_nhiem_to_chuc_thanh_vien",
    "phan_anh_kien_nghi_cua_nhan_dan",
]

CONG_DOAN_BENEFIT_TOPICS_V2 = [
    "quyen_loi_cong_doan_vien",
    "nghia_vu_cong_doan_vien",
    "bao_ve_nguoi_lao_dong",
    "ho_tro_nguoi_lao_dong",
]


# =========================================================
# V2 - PARTICIPATION TOPICS
# =========================================================

DOAN_PARTICIPATION_TOPICS_V2 = [
    "ket_nap_doan",
    "chuyen_sinh_hoat_doan",
    "cap_lai_so_doan",
    "cap_lai_the_doan",
    "hoc_cam_tinh_doan",
    "dong_doan_phi",
]

HPN_PARTICIPATION_TOPICS_V2 = [
    "tham_gia_hoi_phu_nu",
    "sinh_hoat_hoi_phu_nu",
    "dong_hoi_phi_phu_nu",
]

MTTQ_PARTICIPATION_TOPICS_V2 = [
    "gia_nhap_thanh_vien_mttq",
    "thoi_lam_thanh_vien_mttq",
    "tham_gia_hoat_dong_mat_tran",
    "kien_toan_nhan_su_mttq"
]

CONG_DOAN_PARTICIPATION_TOPICS_V2 = [
    "ket_nap_cong_doan",
    "chuyen_sinh_hoat_cong_doan",
    "cap_lai_the_cong_doan",
    "dong_cong_doan_phi",
]



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

INFO_SCHEMA_REGISTRY_V2: Dict[str, Dict[str, Any]] = {
    ORG_DOAN_THANH_NIEN: _make_object_schema(
        properties={
            "entity": _make_enum_property(DOAN_INFO_ENTITIES_V2),
            "fields": _make_array_enum_property(DOAN_INFO_FIELDS_V2),
        },
        required=["entity", "fields"],
    ),
    ORG_HOI_PHU_NU: _make_object_schema(
        properties={
            "entity": _make_enum_property(HPN_INFO_ENTITIES_V2),
            "fields": _make_array_enum_property(HPN_INFO_FIELDS_V2),
        },
        required=["entity", "fields"],
    ),
    ORG_MTTQ: _make_object_schema(
        properties={
            "entity": _make_enum_property(MTTQ_INFO_ENTITIES_V2),
            "fields": _make_array_enum_property(MTTQ_INFO_FIELDS_V2),
        },
        required=["entity", "fields"],
    ),
    ORG_CONG_DOAN: _make_object_schema(
        properties={
            "entity": _make_enum_property(CONG_DOAN_INFO_ENTITIES_V2),
            "fields": _make_array_enum_property(CONG_DOAN_INFO_FIELDS_V2),
        },
        required=["entity", "fields"],
    ),
}

DOAN_INFO_SCHEMA_V2 = INFO_SCHEMA_REGISTRY_V2[ORG_DOAN_THANH_NIEN]
HPN_INFO_SCHEMA_V2 = INFO_SCHEMA_REGISTRY_V2[ORG_HOI_PHU_NU]
MTTQ_INFO_SCHEMA_V2 = INFO_SCHEMA_REGISTRY_V2[ORG_MTTQ]
CONG_DOAN_INFO_SCHEMA_V2 = INFO_SCHEMA_REGISTRY_V2[ORG_CONG_DOAN]


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

DOAN_PERSON_SCHEMA_V2 = _make_object_schema(
    properties={
        "role": _make_enum_property(DOAN_PERSON_ROLES_V2),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

DOAN_BENEFIT_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(DOAN_BENEFIT_TOPICS_V2),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

DOAN_JOIN_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(DOAN_PARTICIPATION_TOPICS_V2),
        "query_mode": _make_array_enum_property(COMMON_PARTICIPATION_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

HPN_PERSON_SCHEMA_V2 = _make_object_schema(
    properties={
        "role": _make_enum_property(HPN_PERSON_ROLES_V2),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

HPN_BENEFIT_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(HPN_BENEFIT_TOPICS_V2),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

HPN_JOIN_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(HPN_PARTICIPATION_TOPICS_V2),
        "query_mode": _make_array_enum_property(COMMON_PARTICIPATION_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

MTTQ_PERSON_SCHEMA_V2 = _make_object_schema(
    properties={
        "role": _make_enum_property(MTTQ_PERSON_ROLES_V2),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

MTTQ_BENEFIT_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(MTTQ_BENEFIT_TOPICS_V2),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

MTTQ_JOIN_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(MTTQ_PARTICIPATION_TOPICS_V2),
        "query_mode": _make_array_enum_property(COMMON_PARTICIPATION_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

CONG_DOAN_PERSON_SCHEMA_V2 = _make_object_schema(
    properties={
        "role": _make_enum_property(CONG_DOAN_PERSON_ROLES_V2),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)

CONG_DOAN_BENEFIT_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(CONG_DOAN_BENEFIT_TOPICS_V2),
        "query_mode": _make_array_enum_property(COMMON_BENEFIT_QUERY_MODES),
    },
    required=["topic", "query_mode"],
)

CONG_DOAN_JOIN_SCHEMA_V2 = _make_object_schema(
    properties={
        "topic": _make_enum_property(CONG_DOAN_PARTICIPATION_TOPICS_V2),
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

GLOBAL_PERSON_SCHEMA = _make_object_schema(
    properties={
        "role": _make_enum_property(ALL_PERSON_ROLES),
        "query_mode": _make_array_enum_property(COMMON_PERSON_QUERY_MODES),
    },
    required=["role", "query_mode"],
)


META_SCHEMA_REGISTRY_V2: Dict[Tuple[str, str], Dict[str, Any]] = {
    # UBND
    (ORG_UBND, INTENT_TRA_CUU_THONG_TIN): UBND_INFO_SCHEMA,
    (ORG_UBND, INTENT_HOI_NHAN_SU): UBND_PERSON_SCHEMA,
    (ORG_UBND, INTENT_HOI_THU_TUC): UBND_PROCEDURE_SCHEMA,
    (ORG_UBND, INTENT_PHAN_ANH_KIEN_NGHI): UBND_FEEDBACK_SCHEMA,

    # Đảng ủy
    (ORG_DANG_UY, INTENT_TRA_CUU_THONG_TIN): DANG_UY_INFO_SCHEMA,
    (ORG_DANG_UY, INTENT_HOI_NHAN_SU): DANG_UY_PERSON_SCHEMA,
    (ORG_DANG_UY, INTENT_SINH_HOAT_DANG): DANG_UY_ACTIVITY_SCHEMA,

    # Đoàn Thanh niên
    (ORG_DOAN_THANH_NIEN, INTENT_TRA_CUU_THONG_TIN): DOAN_INFO_SCHEMA_V2,
    (ORG_DOAN_THANH_NIEN, INTENT_HOI_NHAN_SU): DOAN_PERSON_SCHEMA_V2,
    (ORG_DOAN_THANH_NIEN, INTENT_QUYEN_LOI_HO_TRO): DOAN_BENEFIT_SCHEMA_V2,
    (ORG_DOAN_THANH_NIEN, INTENT_THAM_GIA_TO_CHUC): DOAN_JOIN_SCHEMA_V2,

    # Hội Phụ nữ
    (ORG_HOI_PHU_NU, INTENT_TRA_CUU_THONG_TIN): HPN_INFO_SCHEMA_V2,
    (ORG_HOI_PHU_NU, INTENT_HOI_NHAN_SU): HPN_PERSON_SCHEMA_V2,
    (ORG_HOI_PHU_NU, INTENT_QUYEN_LOI_HO_TRO): HPN_BENEFIT_SCHEMA_V2,
    (ORG_HOI_PHU_NU, INTENT_THAM_GIA_TO_CHUC): HPN_JOIN_SCHEMA_V2,

    # MTTQ
    (ORG_MTTQ, INTENT_TRA_CUU_THONG_TIN): MTTQ_INFO_SCHEMA_V2,
    (ORG_MTTQ, INTENT_HOI_NHAN_SU): MTTQ_PERSON_SCHEMA_V2,
    (ORG_MTTQ, INTENT_QUYEN_LOI_HO_TRO): MTTQ_BENEFIT_SCHEMA_V2,
    (ORG_MTTQ, INTENT_THAM_GIA_TO_CHUC): MTTQ_JOIN_SCHEMA_V2,

    # Công đoàn
    (ORG_CONG_DOAN, INTENT_TRA_CUU_THONG_TIN): CONG_DOAN_INFO_SCHEMA_V2,
    (ORG_CONG_DOAN, INTENT_HOI_NHAN_SU): CONG_DOAN_PERSON_SCHEMA_V2,
    (ORG_CONG_DOAN, INTENT_QUYEN_LOI_HO_TRO): CONG_DOAN_BENEFIT_SCHEMA_V2,
    (ORG_CONG_DOAN, INTENT_THAM_GIA_TO_CHUC): CONG_DOAN_JOIN_SCHEMA_V2,
    (ORG_CONG_DOAN, INTENT_PHAN_ANH_KIEN_NGHI): CONG_DOAN_FEEDBACK_SCHEMA,
}

META_SCHEMA_REGISTRY_FALLBACK: Dict[Tuple[str, str], Dict[str, Any]] = {
    # UBND
    (ORG_UBND, INTENT_TRA_CUU_THONG_TIN): UBND_INFO_SCHEMA,
    (ORG_UBND, INTENT_HOI_NHAN_SU): GLOBAL_PERSON_SCHEMA,
    (ORG_UBND, INTENT_HOI_THU_TUC): UBND_PROCEDURE_SCHEMA,
    (ORG_UBND, INTENT_PHAN_ANH_KIEN_NGHI): UBND_FEEDBACK_SCHEMA,

    # Đảng ủy
    (ORG_DANG_UY, INTENT_TRA_CUU_THONG_TIN): DANG_UY_INFO_SCHEMA,
    (ORG_DANG_UY, INTENT_HOI_NHAN_SU): GLOBAL_PERSON_SCHEMA,
    (ORG_DANG_UY, INTENT_SINH_HOAT_DANG): DANG_UY_ACTIVITY_SCHEMA,

    # Đoàn Thanh niên
    (ORG_DOAN_THANH_NIEN, INTENT_TRA_CUU_THONG_TIN): DOAN_INFO_SCHEMA_V2,
    (ORG_DOAN_THANH_NIEN, INTENT_HOI_NHAN_SU): GLOBAL_PERSON_SCHEMA,
    (ORG_DOAN_THANH_NIEN, INTENT_QUYEN_LOI_HO_TRO): DOAN_BENEFIT_SCHEMA_V2,
    (ORG_DOAN_THANH_NIEN, INTENT_THAM_GIA_TO_CHUC): DOAN_JOIN_SCHEMA_V2,

    # Hội Phụ nữ
    (ORG_HOI_PHU_NU, INTENT_TRA_CUU_THONG_TIN): HPN_INFO_SCHEMA_V2,
    (ORG_HOI_PHU_NU, INTENT_HOI_NHAN_SU): GLOBAL_PERSON_SCHEMA,
    (ORG_HOI_PHU_NU, INTENT_QUYEN_LOI_HO_TRO): HPN_BENEFIT_SCHEMA_V2,
    (ORG_HOI_PHU_NU, INTENT_THAM_GIA_TO_CHUC): HPN_JOIN_SCHEMA_V2,

    # MTTQ
    (ORG_MTTQ, INTENT_TRA_CUU_THONG_TIN): MTTQ_INFO_SCHEMA_V2,
    (ORG_MTTQ, INTENT_HOI_NHAN_SU): GLOBAL_PERSON_SCHEMA,
    (ORG_MTTQ, INTENT_QUYEN_LOI_HO_TRO): MTTQ_BENEFIT_SCHEMA_V2,
    (ORG_MTTQ, INTENT_THAM_GIA_TO_CHUC): MTTQ_JOIN_SCHEMA_V2,

    # Công đoàn
    (ORG_CONG_DOAN, INTENT_TRA_CUU_THONG_TIN): CONG_DOAN_INFO_SCHEMA_V2,
    (ORG_CONG_DOAN, INTENT_HOI_NHAN_SU): GLOBAL_PERSON_SCHEMA,
    (ORG_CONG_DOAN, INTENT_QUYEN_LOI_HO_TRO): CONG_DOAN_BENEFIT_SCHEMA_V2,
    (ORG_CONG_DOAN, INTENT_THAM_GIA_TO_CHUC): CONG_DOAN_JOIN_SCHEMA_V2,
    (ORG_CONG_DOAN, INTENT_PHAN_ANH_KIEN_NGHI): CONG_DOAN_FEEDBACK_SCHEMA,
}

def get_allowed_intents(org_type: str) -> List[str]:
    return list(ORG_INTENTS.get(org_type, []))

def get_meta_schema(org_type: str, intent: str, org_type_is_fallback: bool = False) -> Optional[Dict[str, Any]]:
    if org_type_is_fallback:
        schema = META_SCHEMA_REGISTRY_FALLBACK.get((org_type, intent))
        return deepcopy(schema) if schema else None
    
    schema = META_SCHEMA_REGISTRY_V2.get((org_type, intent))
    return deepcopy(schema) if schema else None

def get_meta_schema_prompt(org_type: str, intent: Optional[str] = None, org_type_is_fallback: bool = False) -> Dict[str, Any]:
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

        schema = get_meta_schema(org_type, intent, org_type_is_fallback)
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
        schema = get_meta_schema(org_type, allowed_intent, org_type_is_fallback)
        if schema:
            schemas_by_intent[allowed_intent] = _make_meta_prompt_schema(schema)

    return {
        "organization_type": org_type,
        "allowed_intents": allowed_intents,
        "schemas_by_intent": schemas_by_intent,
    }





def build_meta_extraction_messages(query: str, org_type: str, intent: str, org_type_is_fallback: bool = False) -> List[dict]:
    schema_payload = get_meta_schema_prompt(org_type, intent=intent, org_type_is_fallback=org_type_is_fallback)

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
- Nếu query hỏi "địa chỉ", "số điện thoại", "email", "website" => ưu tiên field/contact phù hợp

Chỉ trả JSON.
""".strip()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    return messages


def build_intent_and_meta_extraction_messages(query: str, org_type: str, org_type_is_fallback: bool = False) -> List[dict]:
    schema_payload = get_meta_schema_prompt(org_type, intent=None, org_type_is_fallback=org_type_is_fallback)

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
- Nếu câu hỏi có từ "nhân sự" nhưng hỏi "kiện toàn", "bổ sung", "thay thế", "quy trình", "thủ tục", "hồ sơ", "cách thực hiện" trong Ban Thường trực/Ủy ban MTTQ => ưu tiên tham_gia_to_chuc, không chọn hoi_nhan_su.
- Nếu câu hỏi hỏi về người/cán bộ hoặc danh sách nhóm người, bao gồm hỏi người đó là ai, giữ chức vụ gì, thuộc bộ phận nào, số điện thoại, email, thông tin liên hệ của người đó => ưu tiên hoi_nhan_su nếu intent này được phép.
- Nếu câu hỏi hỏi về "cần gì", "hồ sơ gì", "giấy tờ gì", "thủ tục", "quy trình", "điều kiện", "bao lâu", "lệ phí" => ưu tiên intent thủ tục/tham gia/sinh hoạt tương ứng.
- Nếu câu hỏi hỏi về "quyền lợi", "được gì", "được hỗ trợ gì", "được hưởng gì", "nghĩa vụ", "giám sát phản biện", "phản ánh kiến nghị của Nhân dân", "đại diện ý chí nguyện vọng" => ưu tiên quyen_loi_ho_tro nếu intent này được phép.
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

def classify_meta_with_intent(query: str, org_type: str, intent: str, org_type_is_fallback: bool = False):

    context = build_meta_extraction_messages(query, org_type, intent, org_type_is_fallback)

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

def classify_meta_without_intent(query: str, org_type: str, org_type_is_fallback: bool = False):

    context = build_intent_and_meta_extraction_messages(query, org_type, org_type_is_fallback)

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


def build_intent_and_meta_extraction_chunk_v2(chunk_text: str, org_type: str) -> List[dict]:
    schema_payload = get_meta_schema_prompt(org_type, intent=None)

    org_specific_notes = {
        "doan_thanh_nien": """
GHI CHÚ RIÊNG CHO ĐOÀN THANH NIÊN
- Nếu chunk nói về giới thiệu tổ chức, lịch sử, nguyên tắc hoạt động, cơ cấu, đối tượng Đoàn hướng tới, kênh thông tin, điều lệ, văn bản => thường nghiêng về tra_cuu_thong_tin.
- Nếu chunk nói về bí thư, phó bí thư, ban chấp hành, ban thường vụ, lãnh đạo Đoàn => nghiêng về hoi_nhan_su.
- Nếu chunk nói về quyền lợi đoàn viên, nghĩa vụ đoàn viên, hỗ trợ đoàn viên, chương trình hỗ trợ thanh niên => nghiêng về quyen_loi_ho_tro.
- Nếu chunk nói về kết nạp Đoàn, học cảm tình Đoàn, chuyển sinh hoạt Đoàn, cấp lại sổ/thẻ Đoàn, đóng đoàn phí => nghiêng về tham_gia_to_chuc.
""".strip(),

        "hoi_phu_nu": """
GHI CHÚ RIÊNG CHO HỘI PHỤ NỮ
- Nếu chunk nói về giới thiệu Hội, vai trò chung, cơ cấu, đối tượng phụ nữ/hội viên, thông tin liên hệ, điều lệ/văn bản => thường nghiêng về tra_cuu_thong_tin.
- Nếu chunk nói về chủ tịch, phó chủ tịch, ban chấp hành, ban thường vụ, lãnh đạo Hội => nghiêng về hoi_nhan_su.
- Nếu chunk nói về quyền lợi hội viên, nghĩa vụ hội viên, hỗ trợ hội viên, chương trình hỗ trợ phụ nữ => nghiêng về quyen_loi_ho_tro.
- Nếu chunk nói về tham gia Hội, sinh hoạt Hội, hội phí => nghiêng về tham_gia_to_chuc.
""".strip(),

        "mttq": """
GHI CHÚ RIÊNG CHO MTTQ
- Nếu chunk nói về giới thiệu chung, tính chất tổ chức, cơ cấu, thành viên, thông tin liên hệ, điều lệ/văn bản => thường nghiêng về tra_cuu_thong_tin.
- Nếu chunk nói về chủ tịch, phó chủ tịch, ban thường trực, ủy viên, lãnh đạo MTTQ => nghiêng về hoi_nhan_su.
- Nếu chunk nói về bảo vệ quyền lợi Nhân dân, đại diện ý chí nguyện vọng Nhân dân, giám sát, phản biện xã hội, phản ánh kiến nghị của Nhân dân => có thể nghiêng về quyen_loi_ho_tro.
- Tuy nhiên, nếu nội dung chỉ mô tả vai trò/chức năng chung của MTTQ mà không nhấn mạnh quyền/trách nhiệm cụ thể, vẫn ưu tiên tra_cuu_thong_tin với entity=role_mission.
- Nếu chunk nói về gia nhập thành viên MTTQ, thôi làm thành viên, tham gia hoạt động Mặt trận => nghiêng về tham_gia_to_chuc.
""".strip(),

        "cong_doan": """
GHI CHÚ RIÊNG CHO CÔNG ĐOÀN
- Nếu chunk nói về giới thiệu Công đoàn, vai trò chung, nguyên tắc, cơ cấu, đoàn viên/người lao động, liên hệ, điều lệ/văn bản => thường nghiêng về tra_cuu_thong_tin.
- Nếu chunk nói về chủ tịch, phó chủ tịch, ban chấp hành, ban thường vụ, lãnh đạo Công đoàn => nghiêng về hoi_nhan_su.
- Nếu chunk nói về quyền lợi công đoàn viên, nghĩa vụ công đoàn viên, bảo vệ người lao động, hỗ trợ người lao động => nghiêng về quyen_loi_ho_tro.
- Nếu chunk nói về kết nạp Công đoàn, chuyển sinh hoạt Công đoàn, cấp lại thẻ Công đoàn, đóng công đoàn phí => nghiêng về tham_gia_to_chuc.
- Nếu chunk nói về phản ánh, kiến nghị, khiếu nại, tố cáo liên quan tiền lương, bảo hiểm xã hội, điều kiện lao động, hợp đồng lao động, quyền lợi người lao động => nghiêng về phan_anh_kien_nghi.
""".strip(),

        "dang_uy": """
GHI CHÚ RIÊNG CHO ĐẢNG ỦY
- Nếu chunk nói về giới thiệu chung, cơ cấu tổ chức, hoạt động Đảng, văn bản Đảng, liên hệ => thường nghiêng về tra_cuu_thong_tin.
- Nếu chunk nói về bí thư, phó bí thư, lãnh đạo Đảng ủy => nghiêng về hoi_nhan_su.
- Nếu chunk nói về kết nạp Đảng, chuyển sinh hoạt Đảng, đảng phí => nghiêng về sinh_hoat_dang.
""".strip(),

        "ubnd": """
GHI CHÚ RIÊNG CHO UBND
- Nếu chunk nói về thông tin địa bàn, khu phố/ấp, liên hệ, lịch làm việc, cơ sở công cộng, kết quả bầu cử => thường nghiêng về tra_cuu_thong_tin.
- Nếu chunk nói về chủ tịch, phó chủ tịch, lãnh đạo, công chức chuyên môn => nghiêng về hoi_nhan_su.
- Nếu chunk nói về hồ sơ, thủ tục, điều kiện, thời hạn, lệ phí, đăng ký/cấp lại/cấp đổi/xác nhận => nghiêng về hoi_thu_tuc.
- Nếu chunk nói về phản ánh, kiến nghị, khiếu nại, tố cáo liên quan môi trường, hạ tầng, giao thông, an ninh trật tự, thủ tục hành chính => nghiêng về phan_anh_kien_nghi.
""".strip(),
    }

    entity_field_notes = """
QUY TẮC CHỌN ENTITY VÀ FIELDS CHO tra_cuu_thong_tin
- organization_overview: dùng khi chunk nói về giới thiệu chung, bản chất tổ chức, lịch sử, tính chất chính trị - xã hội, vị trí pháp lý chung.
- role_mission: dùng khi chunk nói về vai trò, chức năng, nhiệm vụ, trách nhiệm, cơ chế phối hợp của tổ chức.
- principle_operation: dùng khi chunk nói về nguyên tắc tổ chức và hoạt động.
- structure_organization: dùng khi chunk nói về cơ cấu tổ chức, các cấp, bộ phận thường trực, mô hình tổ chức.
- member_info: dùng khi chunk nói về đối tượng tổ chức hướng tới, đối tượng được phục vụ/chăm lo/hỗ trợ, phạm vi hội viên/đoàn viên/thành viên/người lao động/người dân liên quan.
- contact_info: dùng khi chunk nói về địa chỉ, điện thoại, email, website, cổng thông tin, nền tảng trực tuyến.
- legal_document: dùng khi chunk nói về điều lệ, hướng dẫn, công văn, kế hoạch, quyết định, hệ thống văn bản.

QUY TẮC CHỌN FIELDS CHO tra_cuu_thong_tin
- info: mô tả khái quát, giải thích chung
- list: danh sách các mục, các nhóm, các cấp, các thành phần
- count: số lượng
- address / phone_hotline / email / website: thông tin liên hệ trực tiếp
- legal_status: vị trí pháp lý, tính chất pháp lý, tính chất tổ chức
- coordination: phối hợp với cơ quan/tổ chức nào
- structure_levels: có mấy cấp, gồm các cấp nào
- standing_body: ban thường vụ, ban chấp hành, ban thường trực theo góc nhìn cơ cấu bộ phận
- served_objects: đối tượng được phục vụ/chăm lo/hỗ trợ
- member_scope: phạm vi hội viên/đoàn viên/thành viên/đối tượng tham gia
- document_reference: điều lệ, hướng dẫn, công văn, kế hoạch, quyết định, văn bản chính thức

QUY TẮC CHỐNG NHẦM CHO tra_cuu_thong_tin
- Không chọn hoi_nhan_su nếu chunk nói về nhóm đối tượng được phục vụ hoặc phạm vi hội viên/đoàn viên/thành viên mà không nói về người giữ chức vụ cụ thể.
- Không chọn quyen_loi_ho_tro nếu chunk chỉ mô tả vai trò, chức năng, nhiệm vụ chung của tổ chức.
- Không chọn tham_gia_to_chuc nếu chunk không nói về thủ tục, điều kiện, hồ sơ, quy trình hoặc quy định tham gia.
""".strip()

    system_prompt = f"""
Bạn là bộ gán metadata cho chunk tri thức trong kho dữ liệu của chatbot.

MỤC TIÊU
Gán metadata sao cho chunk có thể được truy xuất đúng nhất khi người dùng đặt câu hỏi thực tế.

CÁCH LÀM BẮT BUỘC
Bạn phải phân tích NGẦM theo quy trình sau, nhưng KHÔNG được in các bước phân tích ra output:
1. Xác định nội dung chính nhất của chunk.
2. Hình dung 3-5 câu hỏi thực tế mà người dùng có thể hỏi và chunk này có thể dùng để trả lời.
3. Dựa trên nhóm câu hỏi giả định đó, chọn đúng 1 intent phù hợp nhất với chunk.
4. Dựa trên intent đã chọn, gán meta theo đúng schema của intent đó.
5. Nếu chunk có nhiều ý, chỉ chọn intent và primary field phản ánh phần nội dung chính nhất; các ý phụ chỉ dùng để bổ sung field phụ nếu xuất hiện rõ.

NGUYÊN TẮC PHÂN LOẠI
- Ưu tiên khả năng phục vụ truy vấn thực tế của người dùng, không chỉ nhìn từ khóa bề mặt.
- Không suy diễn vượt quá nội dung chunk.
- Ưu tiên nội dung xuất hiện trực tiếp trong chunk.
- Nếu chunk là nội dung tổng hợp nhiều vai trò/chức danh nhưng cùng nói về một nhóm lãnh đạo, và schema primary chỉ cho phép 1 giá trị, phải chọn nhãn bao quát nhất.
- Nếu chunk là roster/danh sách tổng hợp nhiều chức danh cùng nhóm, không trả về nhiều primary values cho field dạng string.
- Nếu chunk chứa cả nội dung chính và ví dụ/ngoại lệ/trường hợp đặc biệt, intent và primary phải bám theo nội dung chính, không bám theo ngoại lệ.

QUY TẮC CHỌN INTENT
1. Nếu chunk chủ yếu nói về giới thiệu chung, tên đầy đủ, khái niệm, bản chất tổ chức, chức năng, nhiệm vụ, vai trò chung, địa chỉ, liên hệ, cơ cấu, hoạt động chung => ưu tiên tra_cuu_thong_tin.
2. Chỉ chọn hoi_nhan_su khi chunk chủ yếu nói về người giữ chức vụ, danh sách cán bộ, ban chấp hành, ban lãnh đạo, vai trò nhân sự cụ thể.
3. Chỉ chọn quyen_loi_ho_tro khi chunk thật sự mô tả quyền lợi, nghĩa vụ, hỗ trợ, chế độ dành cho đối tượng thụ hưởng hoặc quyền/trách nhiệm cụ thể theo schema của tổ chức đó.
4. Chỉ chọn tham_gia_to_chuc khi chunk chủ yếu nói về điều kiện, hồ sơ, quy trình, thủ tục tham gia, kết nạp, chuyển sinh hoạt, cấp lại giấy tờ, đóng phí.
5. Chỉ chọn phan_anh_kien_nghi khi chunk chủ yếu nói về phản ánh, kiến nghị, khiếu nại, tố cáo.
6. Nếu không đủ chắc chắn, vẫn chọn intent gần nhất nhưng confidence phải thấp.

QUY TẮC CHỌN META
- Chỉ dùng schema của intent đã chọn.
- Chỉ chọn 1 primary field trực tiếp nhất.
- Các field phụ chỉ lấy khi xuất hiện rõ trong chunk và có giá trị cho retrieval.
- Nếu chunk chủ yếu liệt kê hồ sơ/giấy tờ => ưu tiên document_required nếu schema có.
- Nếu chunk chủ yếu nói về điều kiện/đối tượng áp dụng => ưu tiên condition nếu schema có.
- Nếu chunk chủ yếu nói về lệ phí/đoàn phí/hội phí/đảng phí => ưu tiên fee nếu schema có.
- Nếu chunk chủ yếu nói về thời hạn/thời gian => ưu tiên deadline nếu schema có.
- Nếu chunk chủ yếu nói về danh sách => ưu tiên list nếu schema có query_mode hoặc fields tương ứng.
- Nếu chunk chủ yếu nói về “ai là”, “gồm những ai”, “ban nào gồm ai” => ưu tiên identity hoặc list tùy schema.
- Nếu chunk chủ yếu nói về liên hệ => ưu tiên field/contact phù hợp nếu schema có.

{entity_field_notes}

QUY TẮC RẤT QUAN TRỌNG VỀ SCHEMA
- Chỉ được dùng đúng các field có trong schema của intent đã chọn.
- Không được tạo field mới.
- Không được biến một GIÁ TRỊ enum thành tên field mới.
- Nếu schema có:
  {{
    "entity": [...],
    "fields": [...]
  }}
  thì mọi giá trị như "info", "list", "count", "address", "phone_hotline", "email", "website", "legal_status", "coordination", "structure_levels", "standing_body", "served_objects", "member_scope", "document_reference"
  là giá trị của field "fields", không phải tên field mới.
- Ví dụ đúng:
  "meta": {{"entity": "organization_overview", "fields": ["info"]}}
- Ví dụ sai:
  "meta": {{"entity": "organization_overview", "info": "..."}}
- Meta chỉ chứa nhãn phân loại, không chứa câu mô tả tự do.
- Không được chép lại nguyên văn nội dung chunk vào meta.
- Các field primary như entity, role, topic, domain, procedure_group phải là 1 string duy nhất, không phải mảng, trừ khi schema cho phép mảng.

QUY TẮC CHO CHUNK TỔNG HỢP
- Nếu chunk là danh sách tổng hợp nhiều chức vụ cùng nhóm lãnh đạo, hãy chọn role bao quát nhất, không trả nhiều role.
- Chỉ chọn role cụ thể khi chunk chủ yếu nói riêng về đúng vai trò đó.
- Nếu chunk vừa có quy trình chính vừa có các trường hợp ngoại lệ, primary vẫn phải phản ánh thủ tục chính; các trường hợp ngoại lệ chỉ ảnh hưởng field phụ nếu thật sự rõ.

{org_specific_notes.get(org_type, "")}

ĐỊNH DẠNG OUTPUT
Chỉ trả về đúng 1 JSON object hợp lệ:
{{
  "organization_type": "...",
  "intent": "...",
  "meta": {{...}},
  "confidence": 0.0
}}
""".strip()

    user_prompt = f"""
Gán metadata cho chunk tri thức sau.

INPUT
- chunk_text: "{chunk_text}"
- organization_type: "{org_type}"

ALLOWED_INTENTS
{json.dumps(schema_payload["allowed_intents"], ensure_ascii=False)}

SCHEMAS_BY_INTENT
{json.dumps(schema_payload["schemas_by_intent"], ensure_ascii=False)}

YÊU CẦU THỰC HIỆN
- Hãy phân tích chunk theo hướng: "người dùng có thể hỏi gì để chunk này trở thành câu trả lời phù hợp".
- Từ đó chọn 1 intent và meta giúp retrieval chính xác nhất.
- Không xuất ra các câu hỏi giả định, không giải thích, chỉ trả JSON cuối cùng.
- Nếu chunk thiên về thông tin nền tảng/chức năng/chung => thường nghiêng về tra_cuu_thong_tin.
- Nếu chunk thiên về nhân sự/chức danh/lãnh đạo => thường nghiêng về hoi_nhan_su.
- Nếu chunk thiên về quyền lợi/nghĩa vụ/hỗ trợ/chương trình hỗ trợ hoặc quyền-trách nhiệm cụ thể theo schema của tổ chức => thường nghiêng về quyen_loi_ho_tro.
- Nếu chunk thiên về điều kiện/hồ sơ/quy trình/chuyển sinh hoạt/cấp lại/đóng phí => thường nghiêng về tham_gia_to_chuc.
- Với MTTQ, nếu chunk nói về bảo vệ quyền lợi Nhân dân, đại diện ý chí nguyện vọng Nhân dân, giám sát, phản biện xã hội, phản ánh kiến nghị của Nhân dân thì cân nhắc giữa quyen_loi_ho_tro và tra_cuu_thong_tin dựa trên việc chunk mô tả vai trò chung hay quyền/trách nhiệm cụ thể.
- Nếu có nhiều tín hiệu, ưu tiên ý nào giúp truy xuất đúng chunk nhất khi người dùng hỏi.

Chỉ trả JSON.
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
# if __name__ == "__main__":
#     # print("=== Prompt schema: fixed org + fixed intent ===")
#     # print(get_meta_schema_prompt(ORG_UBND, INTENT_HOI_THU_TUC))

#     # print("\n=== Prompt schema: fixed org, infer intent ===")
#     print(get_meta_schema_prompt("ubnd", intent=None))