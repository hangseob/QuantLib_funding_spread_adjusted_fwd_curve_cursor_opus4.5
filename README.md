# Funding Spread Adjusted Forward Curve Bootstrap

Python QuantLib 기반의 Funding Spread가 반영된 선도금리 커브 부트스트랩 모듈입니다.

## 개요

"Dirty Curve" 접근법을 구현합니다:
1. OIS 커브 부트스트랩
2. Funding Spread 적용하여 Funding Curve 생성
3. **Funding Curve를 Discount Curve로 사용하여 Forward Curve 부트스트랩**

### 핵심 개념

```
Forward Curve Bootstrap:
- OIS quotes를 사용
- Funding Curve로 할인
- PV = 0 조건에서 implied forward rates 도출
```

이렇게 하면 은행의 실제 자금조달 비용이 반영된 선도금리를 얻을 수 있습니다.

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 1. 기본 사용법 (전체 흐름)

```python
import QuantLib as ql
from funding_curve_bootstrap import (
    FundingAdjustedCurveBootstrap,
    OISQuote,
    FundingSpreadPoint
)

# 평가일 설정
valuation_date = ql.Date(11, 12, 2024)

# 부트스트랩 엔진 초기화
bootstrap = FundingAdjustedCurveBootstrap(valuation_date=valuation_date)

# Step 1: OIS 커브 부트스트랩
ois_quotes = [
    OISQuote("1Y", 0.03),
    OISQuote("5Y", 0.04),
    OISQuote("10Y", 0.05),
]
ois_curve = bootstrap.build_ois_curve(ois_quotes)

# Step 2: Funding Curve 생성 (OIS + Spread)
funding_spreads = [
    FundingSpreadPoint("1Y", 50.0),   # 50 bps
    FundingSpreadPoint("5Y", 50.0),
    FundingSpreadPoint("10Y", 50.0),
]
funding_curve = bootstrap.build_funding_curve_from_ois(ois_curve, funding_spreads)

# Step 3: Forward Curve 부트스트랩 (Funding Curve로 할인)
forward_curve = bootstrap.bootstrap_forward_curve_with_funding_discount(
    ois_quotes, funding_curve
)
```

### 2. Fluent Builder 패턴

```python
from funding_curve_bootstrap import FundingCurveBuilder

valuation_date = ql.Date(11, 12, 2024)

builder = (
    FundingCurveBuilder(valuation_date)
    .with_ois_curve([
        ("1Y", 0.03),
        ("5Y", 0.04),
        ("10Y", 0.05),
    ])
    .with_funding_spread([
        ("1Y", 50.0),
        ("5Y", 50.0),
        ("10Y", 50.0),
    ])
    .with_forward_curve_bootstrap()  # Funding Curve로 할인하여 Forward Curve 부트스트랩
)

curves = builder.build()
# curves['ois']     - OIS 커브
# curves['funding'] - Funding 커브 (OIS + Spread)
# curves['forward'] - Forward 커브 (Funding Curve로 할인하여 부트스트랩)
```

### 3. 스왑 가격 산출

```python
# Dirty Curve 방식: Forward Curve로 projection, Funding Curve로 discounting
result = bootstrap.price_swap(
    notional=100_000_000,
    tenor="5Y",
    fixed_rate=0.04,
    is_payer=True,
    projection_curve=forward_curve,
    discount_curve=funding_curve
)

print(f"NPV: ${result['npv']:,.2f}")
print(f"Fair Rate: {result['fair_rate']*100:.4f}%")
```

## 실행 결과 예시

```
================================================================================
CURVE COMPARISON
================================================================================

[1] Zero Rates Comparison:
--------------------------------------------------------------------------------
Tenor               OIS        Funding      Fwd Curve  Fwd-OIS (bps)
--------------------------------------------------------------------------------
1Y              2.9550%        3.4602%        2.9550%          0.00
5Y              3.9398%        4.4466%        3.9425%          0.27
10Y             5.0264%        5.5264%        5.0433%          1.69

[2] Forward Rates (3M) Comparison:
--------------------------------------------------------------------------------
Tenor           OIS Fwd    Funding Fwd   FwdCurve Fwd  Fwd-OIS (bps)
--------------------------------------------------------------------------------
1Y              4.1558%        4.6352%        4.1590%          0.32
5Y              6.1186%        6.4844%        6.1497%          3.11
10Y             6.1626%        6.6792%        6.1943%          3.17

5Y Payer Swap Comparison:
--------------------------------------------------------------------------------
Scenario                                           Fair Rate
--------------------------------------------------------------------------------
1. OIS Proj + OIS Disc (Market Standard)           4.0577%
2. FwdCurve Proj + Funding Disc (Dirty Curve)      4.0662%
Difference:                                        0.86 bps
```

## 이론적 배경

### Dirty Curve Approach

**문제**: 은행의 실제 자금조달 비용은 무위험 금리(OIS)보다 높습니다.

**해결책**: Funding Spread를 반영한 할인 커브로 선도금리를 부트스트랩합니다.

**수학적 원리**:

1. Funding Curve 생성:
   ```
   r_funding(t) = r_ois(t) + spread(t)
   ```

2. Forward Curve 부트스트랩:
   - OIS swap quotes 사용
   - **Funding Curve로 cash flows 할인**
   - PV = 0 조건에서 forward rates 역산
   
3. 결과:
   - Forward rates는 OIS forward rates와 다름
   - Funding cost가 반영된 implied forward rates

### 커브 용도

| 커브 | 용도 |
|------|------|
| OIS Curve | 시장 무위험 금리 |
| Funding Curve | 할인 (은행의 자금조달 비용 반영) |
| Forward Curve | Floating rate projection |

### 스왑 가격 산출 시나리오

| Projection | Discounting | 용도 |
|------------|-------------|------|
| OIS | OIS | 시장 공정가치 |
| Forward | Funding | Dirty Curve (내부 전가 가격) |
| OIS | Funding | 할인만 funding 반영 |

## 주요 메서드

### FundingAdjustedCurveBootstrap

| 메서드 | 설명 |
|--------|------|
| `build_ois_curve()` | SOFR OIS 커브 부트스트랩 |
| `build_funding_curve_from_ois()` | 시간구조 Funding Spread 반영 커브 |
| `build_funding_curve_flat_spread()` | Flat Spread 반영 커브 |
| `bootstrap_forward_curve_with_funding_discount()` | **Funding Curve로 할인하여 Forward Curve 부트스트랩** |
| `price_swap()` | 스왑 가격 산출 |
| `compare_curves()` | 커브 비교 |

### FundingCurveBuilder (Fluent API)

```python
builder = (
    FundingCurveBuilder(valuation_date)
    .with_ois_curve(quotes)
    .with_funding_spread(spreads)
    .with_forward_curve_bootstrap()  # 핵심 기능
)
```

## 예제 실행

```bash
python example_usage.py
```

## 라이선스

MIT License
