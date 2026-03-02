
import re
import unicodedata


THU_TUC_KEYWORDS = [
    "thu tuc",
    "dang ky",
    "ho so",
    "nop o dau",
    "bao lau",
    "cap giay",
    "khai sinh",
    "khai tu",
    "ket hon",
    "chung thuc",
    "lam the nao",
    "can gi",
    "nop truc tuyen",
    "truc tuyen",
    "giay to",
    "le phi"
]

PHUONG_INFO_KEYWORDS = [
    "vi tri",
    "dia ly",
    "dia chi",
    "dien tich",
    "dan so",
    "dan cu",
    "dong dan",
    "ho dan",
    "bao nhieu nguoi",
    "lanh dao",
    "so dien thoai",
    "khu pho",
    "gio lam viec",
    "lich lam viec",
    "website",
    "email",
    "duong day nong",
    "nam o dau",
    "lien he",
    "thanh lap",
    "nam nao",
    "xa ba diem"
]

NHAN_SU_INFO_KEYWORDS = [
    "giam doc",
    "phu trach",
    "cong chuc",
    "nhan vien",
    "lanh dao"
]

LANH_DAO_INFO_KEYWORDS = [
    "bi thu phuong",
    "bi thu",
    "pho bi thu",
    "bi thu dang uy",
    "chu tich phuong",
    "chu tich",
    "pho chu tich",
    "pho chu tich phuong",
    "bi thu doan phuong",
    "bi thu doan",
    "pho bi thu phuong",
    "chu tich ubnd phuong",
    "chu tich ubnd",
    "pho chu tich ubnd phuong",
    "pho chu tich ubnd",
    "chu tich hdnd phuong",
    "chu tich hdnd",
    "pho chu tich hdnd phuong",
    "pho chu tich hdnd",
]

KHU_PHO_KEYWORDS = [
    "khu pho",
    "kp",
]

DS_KHU_PHO_KEYWORDS = [
    "danh sach",
    "so luong",
    "bao nhieu",
]

CONTACT_INFO_KEYWORDS = [
    "duong day nong",
    "thong tin lien he",
    "lien he",
    "website",
    "email",
    "fanpage",
    "so dien thoai",
    "dia chi",
    "goi dien",
    "zalo",
]

LICH_LAM_VIEC_KEYWORDS = [
    "lam viec tu",
    "lich lam viec",
    "gio lam viec",
    "buoi sang",
    "chu nhat",
    "thu 2",
    "thu hai",
    "thu 3",
    "thu ba",
    "thu 4",
    "thu nam",
    "thu 5",
    "thu sau",
    "thu 6",
    "thu 7",
    "t2",
    "t3",
    "t4",
    "t5",
    "t6",
    "t7",
    "cn",
    "thu bay",
    "ngay le",
    "nghi le",
    "lam viec may gio",
    "may gio",
]

def normalize_text(text: str) -> str:
    # Bỏ dấu tiếng Việt
    text = unicodedata.normalize("NFD", text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')

    text = re.sub(r"[^\w\s]", "", text)

    text = text.replace("  ", " ")
    
    # Thay _ thành khoảng trắng
    text = text.replace('_', ' ')

    # Thay . thành khoảng trắng
    text = text.replace('.', ' ')

    text = text.replace('Đ', 'D')
    text = text.replace('đ', 'd')

    text = text.replace(',', '')
    
    # Chuẩn hóa lowercase + trim
    return text.lower().strip()

def classify(q: str):

    # --- Scores ---
    thu_tuc_score = sum(1 for kw in THU_TUC_KEYWORDS if kw in q)
    lanh_dao_score = sum(1 for kw in LANH_DAO_INFO_KEYWORDS if kw in q)
    nhan_su_score = sum(1 for kw in NHAN_SU_INFO_KEYWORDS if kw in q)
    khu_pho_score = sum(1 for kw in KHU_PHO_KEYWORDS if kw in q)
    contact_score = sum(1 for kw in CONTACT_INFO_KEYWORDS if kw in q)
    lich_score = sum(1 for kw in LICH_LAM_VIEC_KEYWORDS if kw in q)
    phuong_info_score = sum(1 for kw in PHUONG_INFO_KEYWORDS if kw in q)

    # --- 1️⃣ Ưu tiên thủ tục ---
    if thu_tuc_score >= 1:
        return "thu_tuc_hanh_chinh", "tu_phap_ho_tich"

    if lich_score >= 1:
        return "thong_tin_phuong", "lich_lam_viec"

    # --- 2️⃣ Subject level ---
    if lanh_dao_score >= 1:
        return "thong_tin_phuong", "lanh_dao"

    if khu_pho_score >= 1:
        item = "thong_tin_khu_pho"
        if "bao nhieu" in q:
            item = "tong_quan" if any(kw in q for kw in DS_KHU_PHO_KEYWORDS) else item
        return "thong_tin_phuong", item
    
    if nhan_su_score >= 1:
        return "thong_tin_phuong", "nhan_su"

    if contact_score >= 1:
        return "thong_tin_phuong", "thong_tin_lien_he"

    # --- 3️⃣ Fallback ---
    if phuong_info_score >= 1:
        return "thong_tin_phuong", "tong_quan"

    return None, None