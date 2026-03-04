
import re
from collections import defaultdict
from normalize import AbbreviationResolver, normalize_text

normalize_system = AbbreviationResolver()

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
    "le phi",
    "giay phep",
    "quy hoach dat"
]

TONG_QUAN_INFO_KEYWORDS = [
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
    "phu trach",
    "nhan vien",
    "lanh dao",
    "dam nhiem",
    "vai tro"
]

CHUC_VU_INFO_KEYWORDS = [
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
    "giam doc",
    "cong chuc",
    "vien chuc",
    "pho truong phong",
    "pho giam doc",
    "can bo",
    "chuyen vien",
    "truong phong"
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
    "nam o dau",
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

SUBJECT_KEYWORDS = {

    "tu_phap_ho_tich": [
        "khai sinh",
        "khai tử",
        "kết hôn",
        "thay đổi hộ tịch",
        "cải chính hộ tịch",
        "xác nhận tình trạng hôn nhân",
        "nuôi con nuôi",
        "chứng thực bản sao",
        "chứng thực chữ ký",
        "chứng thực hợp đồng",
        "quốc tịch",
        "nhan cha me con",
        "giam ho",
        "cham dut giam ho",
        "ghi vao so ho tich",
        "xac nhan ho tich",
        "trich luc ho tich",
    ],

    "dat_dai": [
        "đăng ký đất đai lần đầu",
        "đăng ký đất đai",
        "giay chung nhan quyen su dung dat",
        "quyen su dung dat",
        "sổ đỏ",
        "sổ hồng",
        "chuyển nhượng quyền sử dụng đất",
        "tặng cho quyền sử dụng đất",
        "thừa kế quyền sử dụng đất",
        "chuyển mục đích sử dụng đất",
        "gia hạn thời hạn sử dụng đất",
        "thu hồi đất",
        "bồi thường tái định cư",
        "hỗ trợ tái định cư",
        "cung cấp thông tin đất đai",
    ],

    "xay_dung_nha_o": [
        "cấp phép xây dựng",
        "giấy phép xây dựng",
        "điều chỉnh giấy phép xây dựng",
        "hoàn công",
        "cấp chứng nhận nhà ở",
        "cải tạo công trình",
        "sửa chữa công trình",
        "nhà ở xã hội",
        "quản lý chung cư",
        "quy hoach xay dung"
    ],

    "dau_tu": [
        "chủ trương đầu tư",
        "quyết định chủ trương đầu tư",
        "giấy chứng nhận đăng ký đầu tư",
        "điều chỉnh dự án đầu tư",
        "chấm dứt hoạt động dự án",
        "ưu đãi đầu tư",
        "hỗ trợ đầu tư",
        "giám sát đầu tư",
        "đánh giá đầu tư"
    ],

    "doanh_nghiep": [
        "đăng ký thành lập doanh nghiệp",
        "đăng ký kinh doanh",
        "thay đổi nội dung đăng ký kinh doanh",
        "tạm ngừng kinh doanh",
        "giải thể doanh nghiệp",
        "chuyển đổi loại hình doanh nghiệp",
        "cấp lại giấy chứng nhận đăng ký doanh nghiệp",
        "thu hồi giấy chứng nhận đăng ký doanh nghiệp",
        "công bố thông tin doanh nghiệp",
        "ho kinh doanh",
        "hop tac xa",
        "to hop tac",
        "chi nhanh",
        "van phong dai dien",
        "dia diem kinh doanh",
        "giấy phép kinh doanh"
    ],

    "lao_dong_viec_lam": [
        "hợp đồng lao động",
        "tranh chấp lao động",
        "thang bảng lương",
        "an toàn lao động",
        "vệ sinh lao động",
        "giấy phép lao động",
        "lao động nước ngoài",
        "việc làm",
        "đào tạo nghề"
    ],

    "bao_hiem_an_sinh": [
        "bảo hiểm xã hội",
        "bảo hiểm y tế",
        "bảo hiểm thất nghiệp",
        "trợ cấp xã hội",
        "người có công",
        "giảm nghèo",
        "tro cap",
        "bao tro xa hoi",
        "mai tang",
        "tien tuat",
        "bảo vệ trẻ em",
        "tre em bi xam hai",
        "cham soc thay the",
        "nhan cham soc thay the",
        "can thiep tre em",
    ],

    "giao_duc_dao_tao": [
        "thành lập cơ sở giáo dục",
        "cấp phép hoạt động giáo dục",
        "công nhận văn bằng",
        "công nhận chứng chỉ",
        "liên kết đào tạo",
        "tuyển sinh",
        "kiểm định chất lượng giáo dục",
        "chuyen truong",
        "hoc bong",
        "ho tro hoc tap",
        "tuyen sinh trung hoc",
    ],

    "y_te": [
        "cấp phép hành nghề y",
        "cấp phép hành nghề dược",
        "cấp phép cơ sở khám chữa bệnh",
        "quản lý thuốc",
        "quản lý mỹ phẩm",
        "trang thiết bị y tế",
        "an toàn thực phẩm",
        "phòng chống dịch bệnh",
        "giám định y khoa"
    ],

    "giao_thong_van_tai": [
        "đăng ký phương tiện",
        "đăng kiểm",
        "giấy phép lái xe",
        "kinh doanh vận tải",
        "kết cấu hạ tầng giao thông",
        "vận tải quốc tế",
        "duong bo",
        "ben thuy",
        "cang",
        "dau noi",
        "an toan giao thong",
    ],

    "tai_nguyen_moi_truong": [
        "đánh giá tác động môi trường",
        "cam kết môi trường",
        "tài nguyên nước",
        "khoáng sản",
        "khí tượng thủy văn",
        "biển và hải đảo",
        "biến đổi khí hậu",
        "khai thác nước",
        "thiên tai",
        "ứng phó thiên tai"
    ],

    "van_hoa_the_thao_du_lich": [
        "nghệ thuật biểu diễn",
        "quảng cáo",
        "xuất bản",
        "in ấn",
        "thể dục thể thao",
        "lữ hành",
        "lưu trú du lịch",
        "di sản văn hóa",
        "cau lac bo the thao",
        "hoat dong van hoa",
        "lễ hội"
    ],

    "khoa_hoc_cong_nghe": [
        "nhiệm vụ khoa học công nghệ",
        "sở hữu trí tuệ",
        "tiêu chuẩn đo lường chất lượng",
        "công nghệ cao",
        "chuyển giao công nghệ",
        "an toàn bức xạ",
        "an toàn hạt nhân"
    ],

    "thong_tin_truyen_thong": [
        "báo chí",
        "phát thanh",
        "truyền hình",
        "xuất bản điện tử",
        "viễn thông",
        "internet",
        "mạng xã hội",
        "an toàn thông tin"
    ],

    "nong_nghiep": [
        "trồng trọt",
        "chăn nuôi",
        "thủy sản",
        "thú y",
        "bảo vệ thực vật",
        "lâm nghiệp",
        "xây dựng nông thôn mới",
        "cây trồng",
        "vật nuôi",
        "đất trồng lúa"
    ],

    "cong_thuong": [
        "xuất nhập khẩu",
        "quản lý thị trường",
        "điện lực",
        "hóa chất",
        "an toàn công nghiệp",
        "xúc tiến thương mại",
        "ruou",
        "thuoc la",
        "ban le ruou",
        "ban ruou",
        "san xuat ruou",
        "quan ruou",
    ],

    "tai_chinh_thue_phi": [
        "thuế",
        "hải quan",
        "ngân sách",
        "tài sản công"
    ]
}

def prepare_subject_keywords(subject_keywords):
    prepared = {}

    for subject, keywords in subject_keywords.items():
        normalized_keywords = []

        for kw in keywords:
            kw_norm = normalize_text(kw)

            # Trọng số cơ bản = số từ
            weight = len(kw_norm.split())

            # Boost nếu cụm dài >= 3 từ
            if weight >= 3:
                weight += 1

            normalized_keywords.append((kw_norm, weight))

        # Sắp xếp cụm dài trước
        normalized_keywords.sort(key=lambda x: len(x[0]), reverse=True)

        prepared[subject] = normalized_keywords

    return prepared

def detect_subject(text_norm, prepared_keywords, min_score=2):

    subject_scores = defaultdict(int)

    for subject, keywords in prepared_keywords.items():
        for kw, weight in keywords:

            # Match theo word boundary để tránh match nhầm
            pattern = r'\b' + re.escape(kw) + r'\b'

            if re.search(pattern, text_norm):
                subject_scores[subject] += weight

    if not subject_scores:
        return None, 0

    # Lấy subject có điểm cao nhất
    best_subject = max(subject_scores, key=subject_scores.get)
    best_score = subject_scores[best_subject]

    # Threshold chống match yếu
    if best_score < min_score:
        return None, 0

    # Confidence
    total_score = sum(subject_scores.values())
    confidence = round(best_score / total_score, 3)

    return best_subject, confidence

def classify(q: str, PREPARED):

    # --- Scores ---
    thu_tuc_score = sum(1 for kw in THU_TUC_KEYWORDS if kw in q)
    chuc_vu_score = sum(1 for kw in CHUC_VU_INFO_KEYWORDS if kw in q)
    nhan_su_score = sum(1 for kw in NHAN_SU_INFO_KEYWORDS if kw in q)
    khu_pho_score = sum(1 for kw in KHU_PHO_KEYWORDS if kw in q)
    contact_score = sum(1 for kw in CONTACT_INFO_KEYWORDS if kw in q)
    lich_score = sum(1 for kw in LICH_LAM_VIEC_KEYWORDS if kw in q)
    tong_quan_info_score = sum(1 for kw in TONG_QUAN_INFO_KEYWORDS if kw in q)

    # --- 1️⃣ Ưu tiên thủ tục ---
    if thu_tuc_score >= 1:
        subject, confidence  = detect_subject(q, PREPARED)
        return "thu_tuc_hanh_chinh", subject

    if lich_score >= 1:
        return "thong_tin_tong_quan", "lich_lam_viec"
    
    if contact_score >= 1:
        return "thong_tin_tong_quan", "thong_tin_lien_he"

    # --- 2️⃣ Subject level ---
    if chuc_vu_score >= 1:
        return "to_chuc_bo_may", "chuc_vu"

    if khu_pho_score >= 1:
        item = "thong_tin_khu_pho"
        if "bao nhieu" in q:
            item = "tong_quan" if any(kw in q for kw in DS_KHU_PHO_KEYWORDS) else item
        return "thong_tin_tong_quan", item
    
    if nhan_su_score >= 1:
        return "to_chuc_bo_may", "nhan_su"

    # --- 3️⃣ Fallback ---
    if tong_quan_info_score >= 1:
        return "thong_tin_tong_quan", "tong_quan"

    return None, None