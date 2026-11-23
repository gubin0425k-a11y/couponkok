# -*- coding: utf-8 -*-
"""쿠폰라이브러리 데이터 수집 스크립트.

공개 소스(benefitshub.co.kr 의 카테고리/플랫폼 페이지)를 직접 읽어
표 형태의 쿠폰 데이터를 뽑아 data/coupons.json 을 만든다.
GitHub Actions 에서 하루 3회(정해진 날짜) 실행되며, 실행에 필요한 패키지는
파이썬 표준 라이브러리뿐이다.

사용법:
    python scripts/update_coupons.py            # 수집 후 data/ 갱신
    python scripts/update_coupons.py --check    # 검증만 (CI 게이트용)
    python scripts/update_coupons.py --offline  # 저장된 HTML 로 테스트
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from official_urls import OFFICIAL_URLS  # noqa: E402
from platforms import (  # noqa: E402
    BASE,
    BENEFIT_COLUMN_BLOCKLIST,
    CATEGORY_INDEXES,
    CATEGORY_LABELS,
    COUPON_COLUMN_HINTS,
    DEFAULT_APPLY,
    EXCLUDE_SLUGS,
    PLATFORMS,
    TABLE_BLOCKLIST,
    TYPE_KEYWORDS,
    TYPE_LABELS,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CACHE_DIR = os.path.join(ROOT, ".cache")
UA = "Mozilla/5.0 (compatible; CouponLibraryBot/1.0; +https://github.com/gubin0425k-a11y/coupon-library)"
KST = dt.timezone(dt.timedelta(hours=9))
NO_EXPIRY = "사용 기한 표기 없음"


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
def http_get(url: str, timeout: int = 35, retries: int = 3) -> str | None:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                raw = res.read()
            for enc in ("utf-8", "cp949"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", "replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"  ! fetch failed {url}: {last}", file=sys.stderr)
    return None


LINK_CACHE_PATH = os.path.join(CACHE_DIR, "links.json")


def load_link_cache() -> dict:
    try:
        with open(LINK_CACHE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def resolve_redirect(url: str, cache: dict) -> str:
    """제휴 리다이렉트 주소를 최종 목적지 URL 로 바꾼다(실패하면 원래 주소)."""
    return cache.get(url, url)


def warm_link_cache(urls: list[str], cache: dict) -> None:
    """리다이렉트 주소를 병렬로 풀어 둔다(플랫폼별 1회)."""
    todo = [u for u in dict.fromkeys(urls) if u and u not in cache]
    if not todo:
        return

    def one(url: str) -> tuple[str, str]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=12) as res:
                return url, (res.geturl() or url)
        except Exception:
            return url, url

    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, final in pool.map(one, todo):
            cache[url] = final


# --------------------------------------------------------------------------
# HTML 유틸
# --------------------------------------------------------------------------
def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"</(p|li|div|td|th|h[1-6])>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    text = html.unescape(fragment).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def article_body(page: str) -> str:
    match = re.search(r'<div class="entry-content[^"]*"(.*?)</article>', page, re.S)
    if match:
        return match.group(1)
    match = re.search(r'<div class="entry-content[^"]*"(.*?)(?:<footer|</main>)', page, re.S)
    return match.group(1) if match else page


def table_cells(row_html: str) -> list[str]:
    cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.S)
    return [one_line(strip_tags(c)) for c in cells]


def split_sections(body: str):
    """(섹션 제목, 섹션 HTML, 제목 레벨) 목록. h2/h3 기준으로 나눈다."""
    marks = []
    for m in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", body, re.S):
        title = one_line(strip_tags(m.group(2)))
        if not title or "?" in title or len(title) > 50:
            continue
        marks.append((m.start(), m.end(), title, int(m.group(1))))
    sections = [("", body[: marks[0][0]] if marks else body, 2)]
    for i, (start, end, title, level) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        sections.append((title, body[end:stop], level))
    return sections


# --------------------------------------------------------------------------
# 쿠폰 표 파싱
# --------------------------------------------------------------------------
def is_coupon_table(header: list[str]) -> bool:
    if len(header) < 2:
        return False
    joined = " ".join(header)
    if any(word in joined for word in TABLE_BLOCKLIST):
        return False
    if any(word in header[1] for word in BENEFIT_COLUMN_BLOCKLIST):
        return False
    first = header[0]
    return any(hint in first for hint in COUPON_COLUMN_HINTS)


def column_roles(header: list[str]) -> dict:
    """머리글을 보고 열의 역할을 정한다."""
    roles: dict[str, int] = {}
    for idx, name in enumerate(header):
        if re.search(r"혜택|할인율|할인 ?금액|금액|설명|내용", name) and "benefit" not in roles:
            roles["benefit"] = idx
    for idx, name in enumerate(header):
        if idx == roles.get("benefit"):
            continue
        if re.search(r"조건|대상|등급 조건", name) and "condition" not in roles:
            roles["condition"] = idx
        elif re.search(r"기한|마감|유효|지급일|행사기간", name) and "expiry" not in roles:
            roles["expiry"] = idx
    if "benefit" not in roles and len(header) > 1:
        if re.search(r"기간|마감|기한", header[1]) and len(header) > 1:
            # "할인 행사 | 행사 기간" 처럼 첫 열이 행사 이름인 표
            roles["benefit"] = 0
            roles["expiry"] = 1
        else:
            roles["benefit"] = 1
    # 혜택 열 뒤에 머리글이 없는 값이 있으면 기한/조건으로 본다.
    if "expiry" not in roles and "condition" not in roles:
        for idx in range(len(header)):
            if idx > roles["benefit"]:
                roles["maybe_third"] = idx
                break
    return roles


def classify(section: str, condition: str, benefit: str, has_code: bool) -> str:
    haystack = " ".join([section, condition, benefit]).upper()
    for type_name in ("card", "member", "signup"):
        for word in TYPE_KEYWORDS[type_name]:
            if word.upper() in haystack:
                return type_name
    return "code" if has_code else "link"


def parse_expiry(text: str) -> tuple[str | None, bool]:
    """사용기한 문자열 -> (ISO 날짜, 종료 여부)."""
    if not text:
        return None, False
    cleaned = one_line(text)
    if "종료됨" in cleaned or cleaned.strip(" .") in ("종료", "마감"):
        return None, True

    full = re.findall(r"(\d{2,4})\s*[./년-]\s*(\d{1,2})\s*[./월-]\s*(\d{1,2})", cleaned)
    short = [] if full else re.findall(r"(\d{1,2})\s*[./월]\s*(\d{1,2})", cleaned)
    candidates = full or short
    if not candidates:
        return None, False

    # "시작 : 11/01 ~ 종료 : 12/03" 처럼 두 날짜가 있으면 끝나는 날짜를 쓴다.
    pick = candidates[-1] if len(candidates) > 1 and "종료" in cleaned else candidates[0]
    try:
        if len(pick) == 3:
            year, month, day = (int(v) for v in pick)
            if year < 100:
                year += 2000
            short_year = len(str(pick[0])) <= 2
        else:
            year = dt.date.today().year
            month, day = int(pick[0]), int(pick[1])
            short_year = True
        date = dt.date(year, month, day)
    except ValueError:
        return None, False

    # 연도가 생략된 날짜가 이미 오래전이면 다음 해로 본다.
    if short_year and date < dt.date.today() - dt.timedelta(days=200):
        try:
            date = date.replace(year=date.year + 1)
        except ValueError:
            pass
    return date.isoformat(), date < dt.date.today()


DATE_LIKE = re.compile(r"(\d|~|∼)")
NON_DATE_TERMS = ("소진", "상시", "선착순", "마감", "기간 중", "매일", "한정")


def looks_like_expiry(text: str) -> bool:
    if not text:
        return False
    if any(term in text for term in NON_DATE_TERMS):
        return True
    return bool(DATE_LIKE.search(text)) and len(text) <= 30


PROMO_WORDS = re.compile(
    r"할인|무료|증정|적립|캐시백|쿠폰|리워드|페이백|상품권|%|원|\$|달러|배송비"
)

LINK_PROMO_WORDS = re.compile(r"할인|무료|증정|적립|캐시백|쿠폰|리워드|페이백|상품권|%|\$|달러")

SECTION_NOISE = re.compile(
    r"총정리|모음집|모음|요약|정리|정보|및|프로모션 ?코드|할인 ?쿠폰 ?코드|할인 ?코드|할인 ?쿠폰|쿠폰 ?코드|할인|쿠폰|세일|[\[\]()·]"
)


def clean_section(title: str, platform: str) -> str:
    text = re.sub(r"^\[[^\]]*\]\s*", "", one_line(title))
    text = re.sub(re.escape(platform), " ", text, flags=re.I)
    text = SECTION_NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" -—,")
    return text if len(text) >= 2 else ""


def tidy_benefit(text: str) -> str:
    benefit = one_line(text).replace("합니다", "")
    benefit = re.sub(r"\s*·\s*", " · ", benefit)
    benefit = re.sub(r"\s+", " ", benefit).strip()
    if re.fullmatch(r"\d+(\.\d+)?%", benefit):
        benefit = f"{benefit} 할인"
    return benefit


def format_expiry(expires_at: str | None, raw: str) -> str:
    if not expires_at:
        return raw
    year, month, day = expires_at.split("-")
    text = f"{year}.{month}.{day}"
    time_match = re.search(r"(\d{1,2}:\d{2})", raw)
    if time_match:
        text += f" {time_match.group(1)}"
    return f"{text}까지"


def parse_tables(section_title: str, section_html: str, platform_link_cache: dict) -> list[dict]:
    results: list[dict] = []
    for table in re.findall(r"<table.*?</table>", section_html, re.S):
        rows = re.findall(r"<tr.*?</tr>", table, re.S)
        if len(rows) < 2:
            continue
        header = table_cells(rows[0])
        if not is_coupon_table(header):
            continue
        roles = column_roles(header)
        for row in rows[1:]:
            cells = table_cells(row)
            if not cells or not any(cells):
                continue
            first_html = re.search(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
            first_cell_html = first_html.group(1) if first_html else ""
            code_match = re.search(r'data-code="([^"]+)"', row)
            code = one_line(code_match.group(1)) if code_match else None
            code_in_first_cell = bool(re.search(r'data-code="', first_cell_html))

            def cell(index: str) -> str:
                pos = roles.get(index)
                if pos is None or pos >= len(cells):
                    return ""
                return cells[pos]

            benefit = cell("benefit")
            condition = cell("condition")
            expiry_text = cell("expiry")
            third = cell("maybe_third")
            if third:
                if looks_like_expiry(third):
                    expiry_text = third
                else:
                    condition = (condition + " " + third).strip()

            if not benefit:
                continue
            label = "" if (code and code_in_first_cell) else cells[0]

            data_url = re.search(r'data-url="([^"]+)"', row)
            anchor = re.search(r'<a[^>]+href="([^"]+)"', row)
            link = None
            if anchor and not anchor.group(1).startswith(BASE):
                link = anchor.group(1)
            elif data_url:
                link = resolve_redirect(data_url.group(1), platform_link_cache)
            elif anchor and anchor.group(1).startswith("http"):
                link = anchor.group(1)
            if link and not link.startswith("http"):
                link = None

            expires_at, expired = parse_expiry(expiry_text)
            results.append({
                "section": section_title,
                "label": label,
                "code": code,
                "benefit": benefit,
                "condition": condition,
                "expiry_text": expiry_text,
                "expires_at": expires_at,
                "expired": expired,
                "link": link,
            })
    return results


def tidy_apply(text: str) -> str:
    # 안내 문구에 들어 있는 예시 코드(예: (alx224644))는 실제 코드와 달라 혼동을 준다.
    text = re.sub(r"\s*\((?=[A-Za-z0-9]{5,}\))[A-Za-z0-9]*\d[A-Za-z0-9]*\)", "", text)
    text = re.sub(r"\[[^\]]*(?:Ctrl\+V|붙여넣기)[^\]]*\]", "붙여넣기", text)
    text = re.sub(r"\s*또는\s*붙여넣기", "", text)
    text = re.sub(r"\s*또는\s*", " ", text)
    text = text.replace("붙여넣기 를", "붙여넣기를").replace("붙여넣기를 클릭", "붙여넣기")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,→-")


def parse_usage(section_title: str, sections: list[tuple[str, str, int]]) -> str | None:
    """플랫폼 페이지의 '사용 방법' 설명에서 실제 플랫폼 쪽 단계만 뽑아 요약한다."""
    target = None
    for idx, (title, body, level) in enumerate(sections):
        if not re.search(r"사용 ?방법|사용법|입력 ?방법|등록 ?방법|적용 ?방법", title):
            continue
        # 소제목(h3)으로 나뉜 단계 설명까지 이어 붙인다.
        chunks = [body]
        for sub_title, sub_body, sub_level in sections[idx + 1:]:
            if sub_level <= level:
                break
            chunks.append("<p>" + sub_title + "</p>" + sub_body)
        target = "".join(chunks)
        break
    if target is None:
        return None

    lines = [ln for ln in strip_tags(target).split("\n") if ln.strip()]
    # 소제목(확인하기/사용하기 등) 단위로 나눈다.
    blocks, current = [], []
    for line in lines:
        if re.search(r"(확인하기|확인 방법|사용하기|사용 방법|입력하기|입력 방법|등록 방법|쿠폰받기|다운받기|적용하기)$", line) and current:
            blocks.append(current)
            current = []
        if re.search(r"(확인하기|확인 방법|사용하기|사용 방법|입력하기|입력 방법|등록 방법)$", line):
            continue
        current.append(line)
    if current:
        blocks.append(current)
    if not blocks:
        return None

    # 두 번째 블록(실제 사이트에서 코드를 쓰는 단계)을 우선 사용한다.
    chosen = blocks[1] if len(blocks) > 1 else blocks[0]
    noise = re.compile(r"혜택창고|benefitshub|클릭하면 .*복사|자동 ?복사|복사되|페이지로 이동|이동합니다")
    steps = [ln for ln in chosen if not noise.search(ln)]
    steps = [re.sub(r"^[·•\-\d.\s]+", "", ln).strip() for ln in steps]
    steps = [ln for ln in steps if len(ln) > 6]
    if not steps:
        return None
    # 결제/입력과 직접 관계있는 문장을 앞세운다.
    key = re.compile(r"입력|붙여넣기|적용|쿠폰받기|다운로드|쿠폰선택|등록")
    junk = re.compile(r"결제를 진행|표시됩니다|표시되는데요|확인합니다|이전에|클릭한|복사되|이미지|적용되지 않을 때|확인해보세요")

    sentences: list[str] = []
    for step in steps:
        for piece in re.split(r"\s*(?:→|\.\s)", step):
            piece = tidy_apply(piece).strip(" .")
            if len(piece) < 6 or junk.search(piece):
                continue
            if piece.count("(") != piece.count(")") or piece.count("[") != piece.count("]"):
                continue
            if piece.startswith("(") and piece.rstrip(" .").endswith(")"):
                continue
            if not re.search(r"합니다|하세요|클릭|입력|붙여넣기|선택|누르|적용|등록|받기|다운로드", piece):
                continue
            sentences.append(piece)

    if not sentences:
        return None
    sentences.sort(key=lambda t: 0 if key.search(t) else 1)
    picked = []
    for piece in sentences:
        if len(picked) >= 2:
            break
        if sum(len(p) for p in picked) + len(piece) > 90 and picked:
            break
        picked.append(piece)
    return " → ".join(picked) if picked else None


# --------------------------------------------------------------------------
# 한 플랫폼 처리
# --------------------------------------------------------------------------
def normalize(text: str) -> str:
    text = one_line(text)
    text = re.sub(r"\s*·\s*", " · ", text)
    return text


def platform_coupons(slug: str, name: str, category: str, page: str, link_cache: dict) -> tuple[list[dict], dict]:
    body = article_body(page)
    sections = split_sections(body)
    usage = parse_usage("", sections)
    coupons: list[dict] = []
    seen = set()
    title_match = re.search(r"<title>(.*?)</title>", page, re.S)
    page_title = one_line(html.unescape(title_match.group(1))) if title_match else name
    updated = ""
    upd = re.search(r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)\s*:", body)
    if upd:
        updated = one_line(upd.group(1))

    for section_title, section_html, _level in sections:
        for row in parse_tables(section_title, section_html, link_cache):
            benefit = tidy_benefit(row["benefit"])
            condition = normalize(row["condition"])
            code = row["code"]
            if row["expired"]:
                continue
            # 상시 할인가·카테고리 목록처럼 쿠폰 성격이 없는 행은 버린다.
            if not code and not LINK_PROMO_WORDS.search(benefit) and not row["expires_at"]:
                continue
            if len(benefit) > 120:
                continue
            key = (code or "", benefit)
            if key in seen:
                continue
            seen.add(key)
            coupon_type = classify(section_title + " " + row["label"], condition, benefit, bool(code))
            raw_expiry = normalize(row["expiry_text"])
            if raw_expiry and not looks_like_expiry(raw_expiry):
                # 기한 칸에 조건 문구가 들어간 표는 조건으로 옮긴다.
                condition = (condition + " " + raw_expiry).strip()
                raw_expiry = ""
            expiry_text = format_expiry(row["expires_at"], raw_expiry) or NO_EXPIRY
            tag = row["label"] or clean_section(section_title, name)
            if code and usage:
                apply_text = usage
            elif not code and usage and re.search(r"받기|다운로드|쿠폰선택|자동 ?적용|전용 링크", usage):
                apply_text = usage
            else:
                apply_text = DEFAULT_APPLY[coupon_type]
            generic = (f"{BASE}/{slug}/", f"{BASE}/{slug}", f"{BASE}/{slug}#")
            link = row["link"] or ""
            if not link or link in generic:
                link = OFFICIAL_URLS.get(slug) or f"{BASE}/{slug}/"
            coupons.append({
                "platform_id": slug,
                "platform": name,
                "category": category,
                "type": coupon_type,
                "section": tag,
                "benefit": benefit,
                "condition": condition,
                "expiry": expiry_text,
                "expires_at": row["expires_at"],
                "code": code,
                "apply": apply_text,
                "link": link,
                "source": f"{BASE}/{slug}/",
                "origin": "auto",
            })

    meta = {
        "id": slug,
        "name": name,
        "category": category,
        "page_title": page_title,
        "source": f"{BASE}/{slug}/",
        "updated": updated,
        "count": len(coupons),
    }
    return coupons, meta


def discover_platforms(pages: dict[str, str]) -> dict[str, tuple[str, str]]:
    """카테고리 인덱스에서 새 플랫폼 페이지 슬러그를 찾아 보탠다."""
    found: dict[str, tuple[str, str]] = {}
    for category, index_slug in CATEGORY_INDEXES.items():
        page = pages.get(f"__index__{index_slug}")
        if not page:
            page = http_get(f"{BASE}/{index_slug}/")
        if not page:
            continue
        body = article_body(page)
        for href in re.findall(r'href="https://benefitshub\.co\.kr/([a-z0-9_\-]+)/?"', body):
            if href in PLATFORMS or href in EXCLUDE_SLUGS or href in CATEGORY_INDEXES.values():
                continue
            if not re.fullmatch(r"[a-z0-9_\-]+", href):
                continue
            if not re.search(r"(promo-code|coupon|code|promotion|discount|sale)$", href):
                continue
            found.setdefault(href, (href, category))
    return found


# --------------------------------------------------------------------------
# 검증
# --------------------------------------------------------------------------
REQUIRED = ("platform", "benefit", "apply", "expiry", "type", "link")


def validate(coupons: list[dict]) -> list[str]:
    problems: list[str] = []
    valid_types = set(TYPE_LABELS)
    for idx, c in enumerate(coupons):
        for field in REQUIRED:
            if not str(c.get(field) or "").strip():
                problems.append(f"{idx}:{c.get('platform')}:{field} 비어 있음")
        if c.get("type") not in valid_types:
            problems.append(f"{idx}:{c.get('platform')}: 알 수 없는 유형 {c.get('type')}")
        expiry = c.get("expiry") or ""
        if expiry and "사용 기한 표기 없음" not in expiry:
            if not re.search(r"\d", expiry) and not any(t in expiry for t in ("소진", "상시", "선착순", "마감", "한정", "매일")):
                problems.append(f"{idx}:{c.get('platform')}: 기한에 날짜 없음 '{expiry}'")
        link = str(c.get("link") or "")
        if link and not link.startswith("http"):
            problems.append(f"{idx}:{c.get('platform')}: 링크 형식 오류")
        benefit = c.get("benefit") or ""
        if re.search(r"[<>]", benefit):
            problems.append(f"{idx}:{c.get('platform')}: 혜택에 태그 문자")
        if len(benefit) > 200:
            problems.append(f"{idx}:{c.get('platform')}: 혜택 문장 김")
    return problems


def load_curated(platform_names: dict[str, str]) -> list[dict]:
    """자동 수집으로 잡히지 않는 대표 조건부 쿠폰(직접 확인해 둔 항목)."""
    path = os.path.join(DATA_DIR, "curated.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            items = json.load(fh)
    except Exception as exc:
        print(f"  ! curated.json 읽기 실패: {exc}", file=sys.stderr)
        return []
    out = []
    today = dt.date.today().isoformat()
    for item in items:
        if item.get("expires_at") and item["expires_at"] < today:
            continue
        platform_id = item["platform_id"]
        out.append({
            "platform_id": platform_id,
            "platform": platform_names.get(platform_id, item.get("platform", platform_id)),
            "category": item.get("category", "shopping"),
            "type": item.get("type", "code"),
            "section": item.get("section", ""),
            "benefit": item["benefit"],
            "condition": item.get("condition", ""),
            "expiry": item.get("expiry", NO_EXPIRY),
            "expires_at": item.get("expires_at"),
            "code": item.get("code"),
            "apply": item["apply"],
            "link": item["link"],
            "source": item.get("source", f"{BASE}/{platform_id}/"),
            "origin": "curated",
        })
    return out


def dedupe(coupons: list[dict]) -> list[dict]:
    out, seen = [], set()
    for c in coupons:
        key = (c["platform_id"], c.get("code") or "", c["benefit"])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    for idx, c in enumerate(out):
        c["id"] = f"{c['platform_id']}-{idx}"
    return out


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build(offline: bool = False) -> dict:
    pages: dict[str, str] = {}
    if offline:
        for slug in PLATFORMS:
            path = os.path.join(CACHE_DIR, f"{slug}.html")
            if os.path.exists(path):
                pages[slug] = open(path, encoding="utf-8", errors="replace").read()
        print(f"offline: {len(pages)} cached pages")
    else:
        slugs = list(PLATFORMS)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = pool.map(lambda s: (s, http_get(f"{BASE}/{s}/")), slugs)
            for slug, page in results:
                if page:
                    pages[slug] = page
        if not os.path.isdir(CACHE_DIR):
            os.makedirs(CACHE_DIR, exist_ok=True)
        for slug, page in pages.items():
            with open(os.path.join(CACHE_DIR, f"{slug}.html"), "w", encoding="utf-8") as fh:
                fh.write(page)

    extra = discover_platforms(pages) if not offline else {}
    for slug, (_, category) in extra.items():
        page = http_get(f"{BASE}/{slug}/")
        if page:
            pages[slug] = page
            title = re.search(r"<title>(.*?)</title>", page, re.S)
            raw = one_line(html.unescape(title.group(1))) if title else slug
            raw = re.sub(r"\[?20\d{2}년[^\]]*\]?\s*", "", raw)
            raw = re.split(r"\s*(?:할인|프로모션|쿠폰|直|직구)", raw)[0].strip() or slug
            PLATFORMS.setdefault(slug, (raw, category))

    all_coupons: list[dict] = []
    platform_meta: list[dict] = []
    link_cache: dict[str, str] = {} if offline else load_link_cache()
    if not offline:
        pending = []
        for page in pages.values():
            pending.extend(re.findall(r'data-url="([^"]+)"', page))
        warm_link_cache(pending, link_cache)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(LINK_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(link_cache, fh)
    for slug, (name, category) in PLATFORMS.items():
        page = pages.get(slug)
        if not page:
            continue
        coupons, meta = platform_coupons(slug, name, category, page, link_cache)
        if coupons:
            all_coupons.extend(coupons)
            platform_meta.append(meta)
        else:
            print(f"  - {slug}: 쿠폰 없음")

    all_coupons.extend(load_curated({slug: name for slug, (name, _) in PLATFORMS.items()}))
    all_coupons = dedupe(all_coupons)
    # 직접 확인한 항목만 있는 플랫폼도 목록에 남긴다.
    known = {p["id"] for p in platform_meta}
    for coupon in all_coupons:
        if coupon["platform_id"] in known:
            continue
        known.add(coupon["platform_id"])
        platform_meta.append({
            "id": coupon["platform_id"],
            "name": coupon["platform"],
            "category": coupon["category"],
            "page_title": "",
            "source": coupon["source"],
            "updated": "",
            "count": sum(1 for c in all_coupons if c["platform_id"] == coupon["platform_id"]),
        })
    for meta in platform_meta:
        meta["count"] = sum(1 for c in all_coupons if c["platform_id"] == meta["id"])
    all_coupons.sort(key=lambda c: (c["platform"], TYPE_LABELS[c["type"]], c["expiry"] == NO_EXPIRY, c["benefit"]))
    platform_meta.sort(key=lambda p: (-p["count"], p["name"]))

    now = dt.datetime.now(KST)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_date": now.strftime("%Y-%m-%d"),
        "source": BASE,
        "count": len(all_coupons),
        "platforms": platform_meta,
        "coupons": all_coupons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="저장된 HTML 로만 실행")
    parser.add_argument("--check", action="store_true", help="기존 data/coupons.json 만 검증")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    if args.check:
        path = os.path.join(DATA_DIR, "coupons.json")
        data = json.load(open(path, encoding="utf-8"))
        problems = validate(data["coupons"])
        print(f"검증: 쿠폰 {len(data['coupons'])}개, 문제 {len(problems)}건")
        for p in problems[:20]:
            print(" -", p)
        return 1 if problems else 0

    data = build(offline=args.offline)
    problems = validate(data["coupons"])
    if not data["coupons"]:
        print("쿠폰을 하나도 수집하지 못했습니다.", file=sys.stderr)
        return 2
    data["validation"] = {"problems": len(problems)}
    with open(os.path.join(DATA_DIR, "coupons.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)

    by_type: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    for c in data["coupons"]:
        by_type[c["type"]] = by_type.get(c["type"], 0) + 1
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    print(f"수집 완료: 쿠폰 {data['count']}개 / 플랫폼 {len(data['platforms'])}개")
    print("  유형:", {TYPE_LABELS[k]: v for k, v in by_type.items()})
    print("  카테고리:", {CATEGORY_LABELS.get(k, k): v for k, v in by_cat.items()})
    if problems:
        print(f"검증 경고 {len(problems)}건 (앞 10건):")
        for p in problems[:10]:
            print(" -", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
