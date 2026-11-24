# -*- coding: utf-8 -*-
"""외화 금액 표기를 한국 '원' 표기로 정규화한다.

쿠폰 데이터에는 해외 플랫폼의 프로모션을 그대로 옮긴 문장이 섞여 있어
`$400`, `200€`, `350 달러`, `1만엔` 처럼 외화가 그대로 남는다.
사이트 표기는 한국 '원' 하나로 통일하므로, 수집 단계에서 이 모듈을 거쳐
모든 금액을 원화로 환산한다.

환율은 고정 기준값(2026년 11월 무렵의 대략적인 원화 환율)을 쓴다.
환산한 값에는 '약'을 붙여 정확한 고지가 아니라 어림값임을 드러낸다.
"""

from __future__ import annotations

import re

# 1 외화 = RATES[통화] 원 (고정 기준 환율)
RATES = {
    "USD": 1400.0,
    "EUR": 1520.0,
    "GBP": 1780.0,
    "JPY": 9.4,
    "CNY": 195.0,
    "HKD": 180.0,
    "TWD": 44.0,
    "SGD": 1050.0,
    "THB": 41.0,
    "VND": 0.055,
    "AUD": 920.0,
    "CAD": 1020.0,
    "CHF": 1580.0,
    "NZD": 850.0,
    "MYR": 320.0,
    "PHP": 25.0,
    "IDR": 0.09,
}

# 기호 -> 통화 코드
SYMBOLS = {
    "US$": "USD",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "JPY": "JPY",
    "CNY": "CNY",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "￥": "JPY",
}

# 한글/한자 통화 단위 -> 통화 코드
WORDS = {
    "달러": "USD",
    "불": "USD",
    "유로": "EUR",
    "파운드": "GBP",
    "엔화": "JPY",
    "엔": "JPY",
    "위안화": "CNY",
    "위안": "CNY",
    "元": "CNY",
    "円": "JPY",
}

WON_SYMBOLS = ("₩", "￦")
CURRENCY_CODES = ("USD", "EUR", "GBP", "JPY", "CNY", "HKD", "TWD", "SGD",
                  "THB", "VND", "AUD", "CAD", "CHF", "NZD", "MYR", "PHP", "IDR")

_NUM = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"


def _to_won(amount: float, code: str) -> int:
    """환산 후 읽기 좋은 단위로 반올림한다."""
    value = amount * RATES.get(code, 1.0)
    if value >= 100000:
        step = 1000
    elif value >= 1000:
        step = 100
    else:
        step = 10
    return int(round(value / step) * step)


def _won_text(amount: float, code: str) -> str:
    return f"약 {_to_won(amount, code):,}원"


def _num(text: str) -> float:
    return float(text.replace(",", ""))


# 외화 금액 바로 뒤 괄호에 원화 금액이 함께 적힌 경우: 괄호 안 원화 표기를 남긴다.
_KRW_IN_PARENS = re.compile(
    r"(?:US)?[$€£]\s*" + _NUM + r"\s*(?:할인|상당|이상|부터)?\s*"
    r"(\(\s*[\d,]+\s*원[^)]*\))"
)


def _collapse_krw_parens(text: str) -> str:
    def repl(m: re.Match) -> str:
        inner = m.group(1).strip().strip("()").strip()
        return inner
    return _KRW_IN_PARENS.sub(repl, text)


def normalize_money(text: str) -> str:
    """문장 안의 외화 금액을 '약 N원' 표기로 바꾼다. '%' 할인율은 건드리지 않는다."""
    if not text:
        return text
    out = str(text)

    # 1) 외화 + 괄호 안 원화: 원화 표기만 남긴다. (예: "$13 할인 (17,316원 할인)")
    out = _collapse_krw_parens(out)

    # 2) 원 기호는 기호만 지우고 숫자는 그대로 둔다. (예: ₩14,000 -> 14,000원)
    def won_sym(m: re.Match) -> str:
        return f"{m.group(1)}원"
    out = re.sub(r"[₩￦]\s*(" + _NUM + r")", won_sym, out)

    # 3) 숫자 + 통화 코드 (예: USD 100, 100 USD)
    def code_after(m: re.Match) -> str:
        return _won_text(_num(m.group(1)), m.group(2))
    out = re.sub(r"(" + _NUM + r")\s*(" + "|".join(CURRENCY_CODES) + r")\b", code_after, out)

    def code_before(m: re.Match) -> str:
        return _won_text(_num(m.group(2)), m.group(1))
    out = re.sub(r"\b(" + "|".join(CURRENCY_CODES) + r")\s*(" + _NUM + r")", code_before, out)

    # 4) '만' 단위 (예: 1만엔, 3만 엔, 1만 달러)
    def man_unit(m: re.Match) -> str:
        code = WORDS.get(m.group(2))
        if not code:
            return m.group(0)
        return _won_text(_num(m.group(1)) * 10000, code)
    out = re.sub(r"(" + _NUM + r")\s*만\s*(엔화|엔|달러|유로|파운드|위안|원)?", man_unit, out)

    # 5) 숫자 + 기호 (예: 200€, 20€)
    def sym_after(m: re.Match) -> str:
        return _won_text(_num(m.group(1)), SYMBOLS[m.group(2)])
    out = re.sub(r"(" + _NUM + r")\s*([$€£¥￥])", sym_after, out)

    # 5-1) 기호 + 숫자 (예: $400, €200, £50)
    def sym_before(m: re.Match) -> str:
        return _won_text(_num(m.group(2)), SYMBOLS[m.group(1)])
    out = re.sub(r"(US\$|[$€£¥￥])\s*(" + _NUM + r")", sym_before, out)

    # 6) 숫자 + 한글 통화 단위 (예: 350 달러, 500유로, 200€)
    def word_after(m: re.Match) -> str:
        code = WORDS.get(m.group(2))
        if not code:
            return m.group(0)
        return _won_text(_num(m.group(1)), code)
    out = re.sub(r"(" + _NUM + r")\s*(달러|유로|파운드|엔화|엔|위안화|위안|元|円)(?![가-힣])", word_after, out)

    # 7) 숫자 없이 남은 통화 단위는 '원'으로 바꾼다.
    out = re.sub(r"(?<![가-힣])(달러|유로|파운드|위안|엔화)(?![가-힣])", "원", out)

    # 8) 남은 기호 정리
    out = out.replace("US$", "원").replace("$", "원")
    out = re.sub(r"약\s+약\s*", "약 ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


# 검증용: 외화 표기가 남아 있는지
FOREIGN_PATTERN = re.compile(
    r"[$€£¥￥₩￦]|USD|EUR|GBP|JPY|CNY|HKD|TWD|SGD|THB|VND|AUD|CAD|CHF|"
    r"달러|유로|파운드|위안|엔화|만엔|[0-9]엔"
)


def has_foreign(text: str) -> bool:
    return bool(text and FOREIGN_PATTERN.search(str(text)))


if __name__ == "__main__":  # 간단한 자체 점검
    samples = [
        "$400 또는 €200 이상 결제시 일부 브랜드 10% 할인",
        "350 달러 이상 결제시 남성 마지막 찬스 아이템 30% 할인",
        "레스토랑 10달러 지출마다 100 포인트 적립",
        "신규 가입 후 21일 내 $30 이상 숙박 예약시 3,000포인트 적립",
        "1만엔 이상 구매시",
        "500유로 이상 구매시 10% 할인",
        "$9.9 이상 구매 시 30% 할인",
        "모든 제품 20% 할인 ($129 이상 주문시 25% 할인)",
        "신규 브랜드 및 신제품 $0.99부터~",
        "$13 할인 (17,316원 할인)",
        "오메가 시계 $1,000 이상 구매 시 $50 할인 (선착순 마감)",
        "첫구매 전용 200€ 이상 주문 시 20€ 할인",
        "₩14,000 할인",
        "USD 100 이상 구매 시 무료배송",
    ]
    for s in samples:
        out = normalize_money(s)
        print(f"{s}\n  -> {out}   [남은 외화: {has_foreign(out)}]")
