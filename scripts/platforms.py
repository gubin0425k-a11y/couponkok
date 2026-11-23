# -*- coding: utf-8 -*-
"""수집 대상 플랫폼 목록과 분류 규칙.

각 항목: slug -> (표시 이름, 카테고리)
카테고리: shopping / travel / fashion
"""

BASE = "https://benefitshub.co.kr"

CATEGORY_LABELS = {
    "shopping": "쇼핑",
    "travel": "여행",
    "fashion": "패션",
}

# 카테고리 인덱스 페이지: 새 플랫폼 페이지를 자동 발견하는 데 사용한다.
CATEGORY_INDEXES = {
    "shopping": "promo-code",
    "travel": "travel-promo-code",
    "fashion": "fashion-coupon",
}

# 자동 발견에서 제외할 슬러그(플랫폼 페이지가 아니거나 표가 없는 페이지)
EXCLUDE_SLUGS = {
    "card_promo_code",
    "pay_code",
    "laptop-coupang",
    "apple-discount",
    "oliveyoung-sale",
    "skyscanner-coupon",
    "hotelscombined-promo-code",
}

PLATFORMS = {
    # 쇼핑
    "coup-code": ("쿠팡", "shopping"),
    "coupangeats-coupon": ("쿠팡이츠", "shopping"),
    "a-promo-code": ("알리익스프레스", "shopping"),
    "temu-coupon-promo-code": ("테무", "shopping"),
    "amazon-promo-code": ("아마존", "shopping"),
    "iherb-promo-code": ("아이허브", "shopping"),
    "myprotein-promo-code": ("마이프로틴", "shopping"),
    "cjmarket-coupon": ("CJ더마켓", "shopping"),
    "kurly-promo-code": ("마켓컬리", "shopping"),
    "pulmuone-coupon": ("풀무원", "shopping"),
    "ohou-promo-code": ("오늘의집", "shopping"),
    "metree-promo-code": ("미트리", "shopping"),
    "pet-friends-code": ("펫프렌즈", "shopping"),
    "club-clio-coupon": ("클럽클리오", "shopping"),
    "jomalone-coupon": ("조말론", "shopping"),
    "jomashop-promo-code": ("조마샵", "shopping"),
    "lenovo-promo-code": ("레노버", "shopping"),
    "lego-promo-code": ("레고", "shopping"),
    "casetify-promo-code": ("케이스티파이", "shopping"),
    "donquijote-coupon": ("돈키호테", "shopping"),
    # 여행
    "trip-promo-code": ("트립닷컴", "travel"),
    "agoda-promo-code": ("아고다", "travel"),
    "hotels-promo-code": ("호텔스닷컴", "travel"),
    "booking-promo-code": ("부킹닷컴", "travel"),
    "expedia-promo-code": ("익스피디아", "travel"),
    "rakuten-travel-promo-code": ("라쿠텐 트래블", "travel"),
    "klook-promo-code": ("클룩", "travel"),
    "kkday-promo-code": ("KKday", "travel"),
    "myrealtrip-coupon": ("마이리얼트립", "travel"),
    "traveloka-promo-code": ("트래블로카", "travel"),
    "yanolja-promo-code": ("NOL(야놀자)", "travel"),
    "triple-promo-code": ("트리플", "travel"),
    "tripbtoz-promo-code": ("트립비토즈", "travel"),
    "waug-coupon": ("와그", "travel"),
    "interparktour-coupon": ("인터파크투어", "travel"),
    "hanatour-coupon": ("하나투어", "travel"),
    "ybtour-coupon": ("노랑풍선", "travel"),
    "ttang-coupon": ("땡처리닷컴", "travel"),
    "jejupass-promo-code": ("제주패스", "travel"),
    "socar-coupon": ("쏘카", "travel"),
    "getyourguide-promo-code": ("겟유어가이드", "travel"),
    "minda-coupon": ("민다", "travel"),
    "airalo-esim-code": ("에어알로", "travel"),
    "saily-promo-code": ("세일리", "travel"),
    "usimsa-coupon": ("유심사", "travel"),
    "ihg-promotion": ("IHG", "travel"),
    # 패션
    "musinsa-promo-code": ("무신사", "fashion"),
    "ably-coupon": ("에이블리", "fashion"),
    "kream-promo-code": ("크림", "fashion"),
    "zigzag-coupon": ("지그재그", "fashion"),
    "wconcept-coupon": ("W컨셉", "fashion"),
    "24s-promo-code": ("24S", "fashion"),
    "arket-promo-code": ("아르켓", "fashion"),
    "cettire-promo-code": ("세타이어", "fashion"),
    "cider-promo-code": ("샵사이다", "fashion"),
    "cos-promo-code": ("COS", "fashion"),
    "crocs-coupon-code": ("크록스", "fashion"),
    "diesel-promo-code": ("디젤", "fashion"),
    "endclothing-promo-code": ("엔드클로딩", "fashion"),
    "farfetch-promo-code": ("파페치", "fashion"),
    "fwrd-promo-code": ("FWRD", "fashion"),
    "giglio-promo-code": ("질리오", "fashion"),
    "hbx-promo-code": ("HBX", "fashion"),
    "hm-promo-code": ("H&M", "fashion"),
    "lululemon-promo-code": ("룰루레몬", "fashion"),
    "mrporter-promo-code": ("미스터포터", "fashion"),
    "mytheresa-promo-code": ("마이테레사", "fashion"),
    "netaporter-promo-code": ("네타포르테", "fashion"),
    "shopbop-promo-code": ("샵밥", "fashion"),
    "ssense-promo-code": ("SSENSE", "fashion"),
    "swarovski-promo-code": ("스와로브스키", "fashion"),
    "theory-promo-code": ("띠어리", "fashion"),
    "theoutnet-promo-code": ("더아웃넷", "fashion"),
    "yoox-promo-code": ("YOOX", "fashion"),
    "aloyoga-promo-code": ("알로요가", "fashion"),
}

# 표의 첫 번째 열 머리글에 이 단어가 있으면 쿠폰 표로 본다.
COUPON_COLUMN_HINTS = ("코드", "쿠폰", "프로모션", "할인 세일", "할인행사")

# 두 번째 열 머리글이 이런 값이면 쿠폰 표가 아니다(상품 카테고리 색인 등).
BENEFIT_COLUMN_BLOCKLIST = ("쿠폰 최대 할인율",)

# 표 전체 머리글에 이 단어가 있으면 쿠폰 표가 아니다.
TABLE_BLOCKLIST = (
    "수수료",
    "배송비",
    "관세",
    "결제 수단",
    "결제수단",
    "통화",
    "카드 모음",
    "구분",
    "가격",
    "환율",
)

TYPE_LABELS = {
    "signup": "신규·첫구매",
    "card": "카드·간편결제",
    "member": "멤버십·대상자 전용",
    "code": "코드 입력형",
    "link": "전용 링크형",
}

# 유형 판별 키워드(앞에 있는 유형이 우선)
TYPE_KEYWORDS = {
    "card": (
        "카드", "VISA", "비자카드", "마스터", "MASTER", "AMEX", "아멕스",
        "카카오페이", "네이버페이", "페이코", "토스페이", "삼성페이", "애플페이",
        "간편결제", "간편 결제", "무이자", "할부",
    ),
    "member": (
        "멤버십", "와우", "프라임", "등급", "전용", "대상", "인플루언서",
        "기자단", "학생", "교사", "생일", "VIP", "골드", "실버", "채널추가",
        "채널 추가", "앱 전용", "구독", "사장님", "크리에이터", "파트너",
    ),
    "signup": (
        "신규", "첫구매", "첫 구매", "첫주문", "첫 주문", "회원가입", "가입",
        "웰컴", "추천인", "초대", "신규회원", "첫결제", "첫 결제", "첫예약",
    ),
}

# 유형별 기본 적용 방법(플랫폼 페이지에서 사용법을 찾지 못했을 때)
DEFAULT_APPLY = {
    "code": "결제 화면의 프로모션 코드 입력란에 코드를 입력하고 적용",
    "link": "전용 링크로 접속해 쿠폰을 받은 뒤 결제",
    "card": "해당 카드·간편결제로 결제하면 자동 적용",
    "signup": "신규 가입 후 쿠폰함에서 확인하고 결제 시 적용",
    "member": "해당 멤버십·조건을 충족한 뒤 쿠폰함에서 확인하고 결제 시 적용",
}
