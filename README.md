# Funding Spread Adjusted Forward Curve Bootstrap

Python QuantLib 기반의 Funding Spread가 반영된 할인 커브("Dirty Curve") 부트스트랩 모듈입니다.

Cursor with Opus 4.5 가 만들었음.

## 개요

은행의 실제 자금조달 비용(Funding Cost)을 반영한 할인 커브를 구축하고, 이를 IRS 부트스트랩에 적용하여 Funding Cost가 반영된 선도금리를 도출합니다.

### 주요 기능

1. **OIS 커브 부트스트랩**: 표준 SOFR OIS 커브 구축
2. **Funding Spread 시간구조**: 만기별 차등화된 자금조달 스프레드 정의
3. **Funding Curve 구축**: OIS 커브 + Funding Spread = Dirty Curve
4. **IRS 부트스트랩**: Funding Curve를 할인 커브로 사용한 선도금리 도출

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 1. 기본 사용법 (FundingCurveBootstrap 클래스)

```python
import QuantLib as ql
from funding_curve_bootstrap import (
    FundingCurveBootstrap,
    OISQuote,
    IRSQuote,
    FundingSpreadPoint,
    CurveInterpolation
)

# 평가일 설정
valuation_date = ql.Date(11, 12, 2024)

# 부트스트랩 엔진 초기화
bootstrap = FundingCurveBootstrap(
    valuation_date=valuation_date,
    calendar=ql.UnitedStates(ql.UnitedStates.FederalReserve),
    day_count=ql.Actual360()
)

# Step 1: OIS 커브 부트스트랩
ois_quotes = [
    OISQuote("1M", 0.0535),
    OISQuote("3M", 0.0530),
    OISQuote("6M", 0.0520),
    OISQuote("1Y", 0.0500),
    OISQuote("2Y", 0.0465),
    OISQuote("5Y", 0.0430),
    OISQuote("10Y", 0.0420),
    OISQuote("30Y", 0.0410),
]
ois_curve = bootstrap.build_ois_curve(ois_quotes)

# Step 2: Funding Spread 정의 (시간구조)
funding_spreads = [
    FundingSpreadPoint("1Y", 5.0),    # 5 bps
    FundingSpreadPoint("2Y", 8.0),    # 8 bps
    FundingSpreadPoint("5Y", 15.0),   # 15 bps
    FundingSpreadPoint("10Y", 20.0),  # 20 bps
    FundingSpreadPoint("30Y", 30.0),  # 30 bps
]

# Step 3: Funding Curve 구축 (OIS + Spread)
funding_curve = bootstrap.build_funding_curve(ois_curve, funding_spreads)

# Step 4: IRS 부트스트랩 (Funding Curve로 할인)
irs_quotes = [
    IRSQuote("2Y", 0.0468),
    IRSQuote("5Y", 0.0433),
    IRSQuote("10Y", 0.0423),
    IRSQuote("30Y", 0.0413),
]
forward_curve = bootstrap.bootstrap_irs_with_funding_curve(irs_quotes, funding_curve)
```

### 2. Fluent Builder 패턴

```python
from funding_curve_bootstrap import FundingCurveBuilder

# OIS 시세
ois_quotes = [
    ("1M", 0.0535), ("3M", 0.0530), ("1Y", 0.0500),
    ("5Y", 0.0430), ("10Y", 0.0420), ("30Y", 0.0410),
]

# Funding Spread
funding_spreads = [
    ("1Y", 5.0), ("5Y", 15.0), ("10Y", 20.0), ("30Y", 30.0),
]

# IRS 시세
irs_quotes = [
    ("2Y", 0.0468), ("5Y", 0.0433), ("10Y", 0.0423), ("30Y", 0.0413),
]

# 한 번에 모든 커브 구축
valuation_date = ql.Date(11, 12, 2024)
builder = (
    FundingCurveBuilder(valuation_date)
    .with_ois_curve(ois_quotes)
    .with_term_funding_spreads(funding_spreads)
    .with_irs_bootstrap(irs_quotes)
)

curves = builder.build()
# curves['ois'] - OIS 커브
# curves['funding'] - Funding 커브
# curves['forward'] - 선도 커브
```

### 3. Flat Spread 적용

```python
# 모든 만기에 동일한 15 bps 스프레드 적용
builder = (
    FundingCurveBuilder(valuation_date)
    .with_ois_curve(ois_quotes)
    .with_flat_funding_spread(15.0)  # 15 bps 균등 스프레드
    .with_irs_bootstrap(irs_quotes)
)
```

### 4. 스왑 가격 산출

```python
# Funding 커브로 할인한 스왑 가격 산출
result = bootstrap.price_swap(
    notional=100_000_000,  # 1억
    tenor="5Y",
    fixed_rate=0.0433,
    is_payer=True,
    forward_curve=forward_curve,
    discount_curve=funding_curve
)

print(f"NPV: ${result['npv']:,.2f}")
print(f"Fair Rate: {result['fair_rate']*100:.4f}%")
```

## 이론적 배경

### Dirty Curve Approach

일반적인 IRS 가격 산출에서는 OIS 커브를 할인 커브로 사용합니다. 그러나 은행의 실제 자금조달 비용은 무위험 금리보다 높으므로, 이를 반영한 "Dirty Curve"를 사용합니다.

**수학적 관계:**

```
r_funding(t) = r_ois(t) + s(t)
```

여기서:
- `r_funding(t)`: t 시점의 Funding Rate
- `r_ois(t)`: t 시점의 OIS Rate (무위험 금리)
- `s(t)`: t 시점의 Funding Spread

**할인율 변환:**

```
DF_funding(t) = DF_ois(t) × exp(-s(t) × t)
```

### IRS 부트스트랩에서의 적용

`DiscountingSwapEngine`에 Funding Curve를 주입하면:

```
PV_fixed + PV_float = 0
```

조건에서 Funding Cost가 반영된 선도금리가 도출됩니다.

## 주요 클래스

### FundingCurveBootstrap

메인 부트스트랩 엔진

| 메서드 | 설명 |
|--------|------|
| `build_ois_curve()` | SOFR OIS 커브 부트스트랩 |
| `build_funding_curve()` | 시간구조 Funding Spread 반영 커브 구축 |
| `build_funding_curve_simple()` | Flat Spread 반영 커브 구축 |
| `bootstrap_irs_with_funding_curve()` | Funding 커브로 할인한 IRS 부트스트랩 |
| `price_swap()` | 스왑 가격 산출 |
| `get_forward_rates()` | 선도금리 추출 |
| `get_zero_rates()` | 제로금리 추출 |
| `get_discount_factors()` | 할인율 추출 |
| `compare_curves()` | 커브 비교 |

### FundingCurveBuilder

Fluent Builder 패턴 인터페이스

```python
builder = (
    FundingCurveBuilder(valuation_date)
    .with_ois_curve(quotes)
    .with_term_funding_spreads(spreads)  # 또는 .with_flat_funding_spread(bps)
    .with_irs_bootstrap(irs_quotes)
)
```

### 데이터 클래스

- `OISQuote`: OIS 시세 (tenor, rate)
- `IRSQuote`: IRS 시세 (tenor, rate)
- `FundingSpreadPoint`: Funding Spread 데이터 포인트 (tenor, spread_bps)

## 예제 실행

```bash
python example_usage.py
```

## 출력 예시

```
================================================================================
EXAMPLE 1: Basic Usage with FundingCurveBootstrap
================================================================================

[Step 1] Building SOFR OIS Curve...
[Step 2] Building Funding Curve (OIS + Funding Spread)...

[Comparison] OIS Curve vs Funding Curve:
------------------------------------------------------------
Tenor      OIS Rate   Funding Rate   Spread (bps)
------------------------------------------------------------
1Y         5.0012%       5.0512%          5.00
2Y         4.6498%       4.7298%          8.00
5Y         4.2996%       4.4496%         15.00
10Y        4.1993%       4.3993%         20.00
30Y        4.0985%       4.3985%         30.00
```

## 라이선스

MIT License

