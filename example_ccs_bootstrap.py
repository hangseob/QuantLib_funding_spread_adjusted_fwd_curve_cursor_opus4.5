"""
Example: Cross-Currency Swap Bootstrap for USD Discount Curve

Given:
- KRW Discount Curve
- USD Forward Curve (SOFR)
- KRW Fixed vs USD SOFR Float swap quotes

Bootstrap:
- USD Discount Curve
"""

import QuantLib as ql
from ccs_usd_discount_bootstrap import (
    CCSUSDDiscountBootstrap,
    CCSBootstrapBuilder,
    CCSQuote
)


def example_basic_ccs_bootstrap():
    """
    Basic example of CCS-based USD discount curve bootstrap.
    """
    print("=" * 80)
    print("EXAMPLE 1: CCS-Based USD Discount Curve Bootstrap")
    print("=" * 80)
    
    # Valuation date
    valuation_date = ql.Date(11, 12, 2024)
    
    # USD/KRW spot rate
    spot_fx_rate = 1400.0  # 1 USD = 1400 KRW
    
    # Initialize bootstrap engine
    bootstrap = CCSUSDDiscountBootstrap(
        valuation_date=valuation_date,
        spot_fx_rate=spot_fx_rate
    )
    
    # Step 1: Build KRW Discount Curve
    print("\n[Step 1] Building KRW Discount Curve...")
    krw_zero_rates = [
        ("1Y", 0.035),   # 3.5%
        ("2Y", 0.036),   # 3.6%
        ("3Y", 0.037),   # 3.7%
        ("5Y", 0.038),   # 3.8%
        ("7Y", 0.039),   # 3.9%
        ("10Y", 0.040),  # 4.0%
    ]
    krw_curve = bootstrap.build_krw_discount_curve(krw_zero_rates)
    
    # Step 2: Build USD Forward Curve (SOFR)
    print("[Step 2] Building USD Forward Curve (SOFR)...")
    usd_forward_rates = [
        ("1Y", 0.045),   # 4.5%
        ("2Y", 0.043),   # 4.3%
        ("3Y", 0.042),   # 4.2%
        ("5Y", 0.041),   # 4.1%
        ("7Y", 0.040),   # 4.0%
        ("10Y", 0.039),  # 3.9%
    ]
    usd_fwd_curve = bootstrap.build_usd_forward_curve(usd_forward_rates)
    
    # Step 3: Define CCS Quotes (KRW Fixed vs USD SOFR Float)
    # These represent the KRW fixed rate that makes the CCS fair
    print("[Step 3] Defining CCS Quotes (KRW Fixed vs USD SOFR Float)...")
    ccs_quotes = [
        CCSQuote("1Y", 0.032),   # 1Y: KRW fixed 3.2% vs USD SOFR float
        CCSQuote("2Y", 0.033),   # 2Y: KRW fixed 3.3%
        CCSQuote("3Y", 0.034),   # 3Y: KRW fixed 3.4%
        CCSQuote("5Y", 0.035),   # 5Y: KRW fixed 3.5%
        CCSQuote("7Y", 0.036),   # 7Y: KRW fixed 3.6%
        CCSQuote("10Y", 0.037),  # 10Y: KRW fixed 3.7%
    ]
    
    # Step 4: Bootstrap USD Discount Curve from CCS
    print("[Step 4] Bootstrapping USD Discount Curve from CCS...")
    usd_disc_curve = bootstrap.bootstrap_usd_discount_curve(ccs_quotes)
    
    # Compare curves
    tenors = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y"]
    
    print("\n" + "=" * 80)
    print("RESULTS: USD Forward Curve vs USD Discount Curve")
    print("=" * 80)
    
    comparison = bootstrap.compare_curves(tenors)
    
    print("\n[Zero Rates]")
    print("-" * 70)
    print(f"{'Tenor':<8} {'USD Forward':>14} {'USD Discount':>14} {'Basis (bps)':>14}")
    print("-" * 70)
    
    for tenor in tenors:
        fwd_rate = comparison['usd_forward_curve']['zero_rates'][tenor]
        disc_rate = comparison['usd_discount_curve']['zero_rates'][tenor]
        basis = comparison['basis_bps'][tenor]
        print(f"{tenor:<8} {fwd_rate*100:>13.4f}% {disc_rate*100:>13.4f}% {basis:>13.2f}")
    
    print("\n[Discount Factors]")
    print("-" * 70)
    print(f"{'Tenor':<8} {'USD Forward':>18} {'USD Discount':>18}")
    print("-" * 70)
    
    for tenor in tenors:
        fwd_df = comparison['usd_forward_curve']['discount_factors'][tenor]
        disc_df = comparison['usd_discount_curve']['discount_factors'][tenor]
        print(f"{tenor:<8} {fwd_df:>18.10f} {disc_df:>18.10f}")
    
    # Also show KRW curve
    print("\n[KRW Discount Curve - Reference]")
    print("-" * 50)
    print(f"{'Tenor':<8} {'Zero Rate':>14} {'Discount Factor':>18}")
    print("-" * 50)
    
    krw_rates = bootstrap.get_zero_rates(
        krw_curve, tenors, 
        bootstrap.krw_calendar, bootstrap.krw_day_count
    )
    krw_dfs = bootstrap.get_discount_factors(
        krw_curve, tenors, bootstrap.krw_calendar
    )
    
    for tenor in tenors:
        print(f"{tenor:<8} {krw_rates[tenor]*100:>13.4f}% {krw_dfs[tenor]:>18.10f}")
    
    return bootstrap


def example_builder_pattern():
    """
    Example using the fluent builder pattern.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Fluent Builder Pattern")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    spot_fx_rate = 1400.0
    
    # KRW zero rates
    krw_rates = [
        ("1Y", 0.035),
        ("2Y", 0.036),
        ("5Y", 0.038),
        ("10Y", 0.040),
    ]
    
    # USD forward rates (SOFR)
    usd_fwd_rates = [
        ("1Y", 0.045),
        ("2Y", 0.043),
        ("5Y", 0.041),
        ("10Y", 0.039),
    ]
    
    # CCS quotes (KRW fixed rate)
    ccs_quotes = [
        ("1Y", 0.032),
        ("2Y", 0.033),
        ("5Y", 0.035),
        ("10Y", 0.037),
    ]
    
    # Build all curves using fluent interface
    builder = (
        CCSBootstrapBuilder(valuation_date, spot_fx_rate)
        .with_krw_discount_curve(krw_rates)
        .with_usd_forward_curve(usd_fwd_rates)
        .with_ccs_quotes(ccs_quotes)
        .bootstrap_usd_discount()
    )
    
    curves = builder.build()
    
    print("\nCurves built successfully!")
    print(f"  - KRW Discount Curve: {'OK' if curves['krw_discount'] else 'FAIL'}")
    print(f"  - USD Forward Curve:  {'OK' if curves['usd_forward'] else 'FAIL'}")
    print(f"  - USD Discount Curve: {'OK' if curves['usd_discount'] else 'FAIL'}")
    
    # Display cross-currency basis
    tenors = ["1Y", "2Y", "5Y", "10Y"]
    
    print("\nCross-Currency Basis (USD Discount - USD Forward):")
    print("-" * 50)
    print(f"{'Tenor':<8} {'Basis (bps)':>14}")
    print("-" * 50)
    
    comparison = builder.bootstrap.compare_curves(tenors)
    for tenor in tenors:
        basis = comparison['basis_bps'][tenor]
        print(f"{tenor:<8} {basis:>13.2f}")
    
    return builder


def example_negative_basis():
    """
    Example with negative cross-currency basis.
    
    In practice, USD/KRW cross-currency basis is often negative,
    meaning USD discount rates are lower than USD forward rates.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Negative Cross-Currency Basis Scenario")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    spot_fx_rate = 1400.0
    
    # KRW discount curve
    krw_rates = [
        ("1Y", 0.035),
        ("2Y", 0.036),
        ("5Y", 0.038),
        ("10Y", 0.040),
    ]
    
    # USD forward rates (SOFR)
    usd_fwd_rates = [
        ("1Y", 0.045),
        ("2Y", 0.043),
        ("5Y", 0.041),
        ("10Y", 0.039),
    ]
    
    # CCS quotes - lower KRW fixed rates imply negative USD basis
    # (USD investor receives less in KRW, implying USD funding advantage)
    ccs_quotes = [
        ("1Y", 0.028),   # Lower than before -> negative basis
        ("2Y", 0.029),
        ("5Y", 0.030),
        ("10Y", 0.031),
    ]
    
    builder = (
        CCSBootstrapBuilder(valuation_date, spot_fx_rate)
        .with_krw_discount_curve(krw_rates)
        .with_usd_forward_curve(usd_fwd_rates)
        .with_ccs_quotes(ccs_quotes)
        .bootstrap_usd_discount()
    )
    
    curves = builder.build()
    tenors = ["1Y", "2Y", "5Y", "10Y"]
    
    print("\nCross-Currency Basis with Lower KRW Fixed Rates:")
    print("-" * 70)
    print(f"{'Tenor':<8} {'USD Forward':>14} {'USD Discount':>14} {'Basis (bps)':>14}")
    print("-" * 70)
    
    comparison = builder.bootstrap.compare_curves(tenors)
    for tenor in tenors:
        fwd_rate = comparison['usd_forward_curve']['zero_rates'][tenor]
        disc_rate = comparison['usd_discount_curve']['zero_rates'][tenor]
        basis = comparison['basis_bps'][tenor]
        print(f"{tenor:<8} {fwd_rate*100:>13.4f}% {disc_rate*100:>13.4f}% {basis:>13.2f}")
    
    print("\n[Interpretation]")
    print("  Negative basis means USD discount rates < USD forward rates")
    print("  This implies USD funding advantage in cross-currency markets")
    
    return builder


def example_with_existing_curves():
    """
    Example using pre-built QuantLib curves.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Using Pre-Built QuantLib Curves")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    ql.Settings.instance().evaluationDate = valuation_date
    
    spot_fx_rate = 1400.0
    
    # Build KRW curve externally
    krw_calendar = ql.SouthKorea()
    krw_day_count = ql.Actual365Fixed()
    
    krw_dates = [
        valuation_date,
        krw_calendar.advance(valuation_date, ql.Period(1, ql.Years)),
        krw_calendar.advance(valuation_date, ql.Period(5, ql.Years)),
        krw_calendar.advance(valuation_date, ql.Period(10, ql.Years)),
    ]
    krw_rates = [0.03, 0.03, 0.03, 0.03]

    krw_curve_obj = ql.ZeroCurve(krw_dates, krw_rates, krw_day_count, krw_calendar)
    krw_curve_obj.enableExtrapolation()
    krw_curve = ql.YieldTermStructureHandle(krw_curve_obj)
    
    # Build USD forward curve externally
    usd_calendar = ql.UnitedStates(ql.UnitedStates.FederalReserve)
    usd_day_count = ql.Actual360()
    
    usd_dates = [
        valuation_date,
        usd_calendar.advance(valuation_date, ql.Period(1, ql.Years)),
        usd_calendar.advance(valuation_date, ql.Period(5, ql.Years)),
        usd_calendar.advance(valuation_date, ql.Period(10, ql.Years)),
    ]
    usd_rates = [0.04, 0.04, 0.04, 0.04]
    
    usd_fwd_curve_obj = ql.ZeroCurve(usd_dates, usd_rates, usd_day_count, usd_calendar)
    usd_fwd_curve_obj.enableExtrapolation()
    usd_fwd_curve = ql.YieldTermStructureHandle(usd_fwd_curve_obj)
    
    # Initialize bootstrap with existing curves
    bootstrap = CCSUSDDiscountBootstrap(valuation_date, spot_fx_rate)
    bootstrap.set_krw_discount_curve(krw_curve)
    bootstrap.set_usd_forward_curve(usd_fwd_curve)
    
    # CCS quotes
    ccs_quotes = [
        CCSQuote("1Y", 0.02),
        CCSQuote("5Y", 0.02),
        CCSQuote("10Y", 0.02),
    ]
    
    # Bootstrap USD discount curve
    usd_disc_curve = bootstrap.bootstrap_usd_discount_curve(ccs_quotes)
    
    print("\nUsing externally built curves:")
    print("-" * 50)
    
    tenors = ["1Y", "5Y", "10Y"]
    comparison = bootstrap.compare_curves(tenors)
    
    print(f"{'Tenor':<8} {'USD Fwd Rate':>14} {'USD Disc Rate':>14} {'Basis':>12}")
    print("-" * 50)
    
    for tenor in tenors:
        fwd_rate = comparison['usd_forward_curve']['zero_rates'][tenor]
        disc_rate = comparison['usd_discount_curve']['zero_rates'][tenor]
        basis = comparison['basis_bps'][tenor]
        print(f"{tenor:<8} {fwd_rate*100:>13.4f}% {disc_rate*100:>13.4f}% {basis:>10.2f}bp")
    
    return bootstrap


def example_usd_forward_curve_with_ccs_discount():
    """
    Example: Bootstrap USD Forward Curve using CCS-derived USD Discount Curve.
    
    Flow:
    1. Build KRW discount curve
    2. Build initial USD forward curve (SOFR)
    3. Bootstrap USD discount curve from CCS quotes
    4. Re-bootstrap USD forward curve using CCS-derived discount curve
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 5: USD Forward Curve Bootstrap with CCS-Derived Discount Curve")
    print("=" * 80)
    
    from funding_curve_bootstrap import FundingAdjustedCurveBootstrap, OISQuote
    
    valuation_date = ql.Date(11, 12, 2024)
    spot_fx_rate = 1400.0
    
    # ========================================
    # Part 1: CCS Bootstrap for USD Discount Curve
    # ========================================
    print("\n[Part 1] CCS Bootstrap for USD Discount Curve")
    print("-" * 50)
    
    ccs_bootstrap = CCSUSDDiscountBootstrap(valuation_date, spot_fx_rate)
    
    # KRW discount curve
    krw_rates = [
        ("1Y", 0.035),
        ("2Y", 0.036),
        ("5Y", 0.038),
        ("10Y", 0.040),
    ]
    ccs_bootstrap.build_krw_discount_curve(krw_rates)
    print("  - KRW Discount Curve: Built")
    
    # Initial USD forward curve (for CCS pricing)
    usd_fwd_rates = [
        ("1Y", 0.045),
        ("2Y", 0.043),
        ("5Y", 0.041),
        ("10Y", 0.039),
    ]
    ccs_bootstrap.build_usd_forward_curve(usd_fwd_rates)
    print("  - Initial USD Forward Curve: Built")
    
    # CCS quotes
    ccs_quotes = [
        CCSQuote("1Y", 0.032),
        CCSQuote("2Y", 0.033),
        CCSQuote("5Y", 0.035),
        CCSQuote("10Y", 0.037),
    ]
    
    # Bootstrap USD discount curve from CCS
    usd_discount_curve = ccs_bootstrap.bootstrap_usd_discount_curve(ccs_quotes)
    print("  - USD Discount Curve (from CCS): Bootstrapped")
    
    # ========================================
    # Part 2: USD Forward Curve Bootstrap with CCS Discount
    # ========================================
    print("\n[Part 2] USD Forward Curve Bootstrap with CCS-Derived Discount")
    print("-" * 50)
    
    # Initialize USD forward curve bootstrap engine
    usd_bootstrap = FundingAdjustedCurveBootstrap(
        valuation_date=valuation_date,
        calendar=ql.UnitedStates(ql.UnitedStates.FederalReserve),
        day_count=ql.Actual360()
    )
    
    # USD OIS quotes (same rates as before, but will bootstrap differently due to discount curve)
    usd_ois_quotes = [
        OISQuote("1Y", 0.045),
        OISQuote("2Y", 0.043),
        OISQuote("5Y", 0.041),
        OISQuote("10Y", 0.039),
    ]
    
    # Build standard USD OIS curve (OIS discount)
    usd_ois_curve = usd_bootstrap.build_ois_curve(usd_ois_quotes)
    print("  - Standard USD OIS Curve: Built (OIS discounting)")
    
    # Bootstrap USD forward curve using CCS-derived discount curve
    usd_forward_curve_ccs = usd_bootstrap.bootstrap_forward_curve_with_funding_discount(
        usd_ois_quotes,
        usd_discount_curve  # CCS-derived discount curve!
    )
    print("  - USD Forward Curve (CCS Discount): Bootstrapped")
    
    # ========================================
    # Part 3: Compare Results
    # ========================================
    print("\n[Part 3] Comparison Results")
    print("=" * 80)
    
    tenors = ["1Y", "2Y", "5Y", "10Y"]
    
    print("\n[3.1] USD Discount Curves Comparison")
    print("-" * 70)
    print(f"{'Tenor':<8} {'OIS Discount':>16} {'CCS Discount':>16} {'Diff (bps)':>14}")
    print("-" * 70)
    
    for tenor in tenors:
        ois_disc_rate = usd_bootstrap.get_zero_rates(usd_ois_curve, [tenor])[tenor]
        ccs_disc_rate = ccs_bootstrap.get_zero_rates(usd_discount_curve, tenors)[tenor]
        diff = (ccs_disc_rate - ois_disc_rate) * 10000
        print(f"{tenor:<8} {ois_disc_rate*100:>15.4f}% {ccs_disc_rate*100:>15.4f}% {diff:>13.2f}")
    
    print("\n[3.2] USD Forward Curves Comparison (Zero Rates)")
    print("-" * 80)
    print(f"{'Tenor':<8} {'OIS Fwd Curve':>16} {'CCS-Disc Fwd':>16} {'Diff (bps)':>14}")
    print("-" * 80)
    
    for tenor in tenors:
        ois_fwd_rate = usd_bootstrap.get_zero_rates(usd_ois_curve, [tenor])[tenor]
        ccs_fwd_rate = usd_bootstrap.get_zero_rates(usd_forward_curve_ccs, [tenor])[tenor]
        diff = (ccs_fwd_rate - ois_fwd_rate) * 10000
        print(f"{tenor:<8} {ois_fwd_rate*100:>15.4f}% {ccs_fwd_rate*100:>15.4f}% {diff:>13.2f}")
    
    print("\n[3.3] USD Forward Rates (3M) Comparison")
    print("-" * 80)
    print(f"{'Tenor':<8} {'OIS Fwd Rate':>16} {'CCS-Disc Fwd':>16} {'Diff (bps)':>14}")
    print("-" * 80)
    
    ois_fwd_rates = usd_bootstrap.get_forward_rates(usd_ois_curve, tenors, "3M")
    ccs_fwd_rates = usd_bootstrap.get_forward_rates(usd_forward_curve_ccs, tenors, "3M")
    
    for tenor in tenors:
        diff = (ccs_fwd_rates[tenor] - ois_fwd_rates[tenor]) * 10000
        print(f"{tenor:<8} {ois_fwd_rates[tenor]*100:>15.4f}% {ccs_fwd_rates[tenor]*100:>15.4f}% {diff:>13.2f}")
    
    print("\n[3.4] Summary of All Curves")
    print("-" * 90)
    print(f"{'Curve':<30} {'1Y':>14} {'2Y':>14} {'5Y':>14} {'10Y':>14}")
    print("-" * 90)
    
    # KRW Discount
    krw_rates_dict = ccs_bootstrap.get_zero_rates(
        ccs_bootstrap.krw_discount_curve, tenors,
        ccs_bootstrap.krw_calendar, ccs_bootstrap.krw_day_count
    )
    print(f"{'KRW Discount':<30}", end="")
    for t in tenors:
        print(f" {krw_rates_dict[t]*100:>13.4f}%", end="")
    print()
    
    # USD OIS (Standard)
    print(f"{'USD OIS (Standard)':<30}", end="")
    for t in tenors:
        print(f" {usd_bootstrap.get_zero_rates(usd_ois_curve, [t])[t]*100:>13.4f}%", end="")
    print()
    
    # USD Discount (CCS)
    print(f"{'USD Discount (CCS)':<30}", end="")
    for t in tenors:
        print(f" {ccs_bootstrap.get_zero_rates(usd_discount_curve, [t])[t]*100:>13.4f}%", end="")
    print()
    
    # USD Forward (CCS Discount)
    print(f"{'USD Forward (CCS Discount)':<30}", end="")
    for t in tenors:
        print(f" {usd_bootstrap.get_zero_rates(usd_forward_curve_ccs, [t])[t]*100:>13.4f}%", end="")
    print()
    
    print("\n[Interpretation]")
    print("  - USD OIS (Standard): OIS 커브를 projection과 discounting 모두에 사용")
    print("  - USD Discount (CCS): CCS quotes로부터 부트스트랩된 할인 커브")
    print("  - USD Forward (CCS Discount): CCS Discount 커브로 할인하여 부트스트랩된 선도 커브")
    print("  - Cross-Currency Basis가 반영되어 Forward Curve가 달라짐")
    
    return ccs_bootstrap, usd_bootstrap, usd_forward_curve_ccs


def example_iterative_ccs_bootstrap():
    """
    Example: Iterative CCS Bootstrap for USD Curves.
    
    The USD forward curve and USD discount curve are interdependent:
    - USD discount curve depends on USD forward curve (for CCS floating leg projection)
    - USD forward curve depends on USD discount curve (for OIS bootstrapping)
    
    Solution: Iterate until convergence.
    
    Flow:
    1. Initial: Use given USD forward curve to bootstrap USD discount curve from CCS
    2. Iteration:
       a. Use USD discount curve to re-bootstrap USD forward curve
       b. Use new USD forward curve to re-bootstrap USD discount curve from CCS
       c. Repeat until convergence
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Iterative CCS Bootstrap (USD Forward <-> USD Discount)")
    print("=" * 80)
    
    from funding_curve_bootstrap import FundingAdjustedCurveBootstrap, OISQuote
    
    valuation_date = ql.Date(11, 12, 2024)
    spot_fx_rate = 1400.0
    
    # ========================================
    # Setup: Input Data
    # ========================================
    print("\n[Setup] Input Data")
    print("-" * 50)
    
    # KRW discount curve rates
    krw_rates = [
        ("1Y", 0.03),
        ("5Y", 0.03),
        ("10Y", 0.03),
    ]
    
    # USD OIS quotes
    usd_ois_quotes_data = [
        ("1Y", 0.03),
        ("5Y", 0.04),
        ("10Y", 0.05),
    ]
    
    # CCS quotes (KRW fixed rate)
    ccs_quotes_data = [
        ("1Y", 0.025),
        ("5Y", 0.025),
        ("10Y", 0.025),
    ]
    
    print(f"  KRW Discount Rates: {krw_rates}")
    print(f"  USD OIS Quotes: {usd_ois_quotes_data}")
    print(f"  CCS Quotes (KRW Fixed): {ccs_quotes_data}")
    
    tenors = ["1Y", "2Y", "5Y", "10Y"]
    max_iterations = 10
    tolerance = 1e-10  # Convergence tolerance (in rate terms)
    
    # ========================================
    # Initial Bootstrap
    # ========================================
    print("\n[Iteration 0] Initial Bootstrap")
    print("-" * 50)
    
    # Build KRW discount curve (fixed throughout)
    ccs_bootstrap = CCSUSDDiscountBootstrap(valuation_date, spot_fx_rate)
    ccs_bootstrap.build_krw_discount_curve(krw_rates)
    
    # Build initial USD forward curve (standard OIS bootstrap)
    usd_bootstrap = FundingAdjustedCurveBootstrap(
        valuation_date=valuation_date,
        calendar=ql.UnitedStates(ql.UnitedStates.FederalReserve),
        day_count=ql.Actual360()
    )
    usd_ois_quotes = [OISQuote(t, r) for t, r in usd_ois_quotes_data]
    usd_forward_curve = usd_bootstrap.build_ois_curve(usd_ois_quotes)
    
    # Set initial USD forward curve for CCS bootstrap
    ccs_bootstrap.set_usd_forward_curve(usd_forward_curve)
    
    # Bootstrap initial USD discount curve from CCS
    ccs_quotes = [CCSQuote(t, r) for t, r in ccs_quotes_data]
    usd_discount_curve = ccs_bootstrap.bootstrap_usd_discount_curve(ccs_quotes)
    
    print("  - KRW Discount Curve: Built")
    print("  - Initial USD Forward Curve (OIS): Built")
    print("  - Initial USD Discount Curve (CCS): Bootstrapped")
    
    # Store iteration history
    iteration_history = []
    
    # Record initial values
    initial_fwd_rates = usd_bootstrap.get_zero_rates(usd_forward_curve, tenors)
    initial_disc_rates = ccs_bootstrap.get_zero_rates(usd_discount_curve, tenors)
    
    iteration_history.append({
        'iteration': 0,
        'forward_rates': initial_fwd_rates.copy(),
        'discount_rates': initial_disc_rates.copy()
    })
    
    prev_fwd_rates = initial_fwd_rates
    prev_disc_rates = initial_disc_rates
    
    # ========================================
    # Iterative Bootstrap
    # ========================================
    print("\n[Iterative Bootstrap]")
    print("-" * 80)
    
    for iteration in range(1, max_iterations + 1):
        print(f"\n  Iteration {iteration}:")
        
        # Step A: Re-bootstrap USD forward curve using current USD discount curve
        usd_forward_curve = usd_bootstrap.bootstrap_forward_curve_with_funding_discount(
            usd_ois_quotes,
            usd_discount_curve  # Use CCS-derived discount curve
        )
        
        # Step B: Update CCS bootstrap with new USD forward curve
        ccs_bootstrap_new = CCSUSDDiscountBootstrap(valuation_date, spot_fx_rate)
        ccs_bootstrap_new.build_krw_discount_curve(krw_rates)
        ccs_bootstrap_new.set_usd_forward_curve(usd_forward_curve)  # New forward curve!
        
        # Step C: Re-bootstrap USD discount curve from CCS with new forward curve
        usd_discount_curve = ccs_bootstrap_new.bootstrap_usd_discount_curve(ccs_quotes)
        
        # Update ccs_bootstrap reference
        ccs_bootstrap = ccs_bootstrap_new
        
        # Get current rates
        curr_fwd_rates = usd_bootstrap.get_zero_rates(usd_forward_curve, tenors)
        curr_disc_rates = ccs_bootstrap.get_zero_rates(usd_discount_curve, tenors)
        
        # Calculate changes
        max_fwd_change = max(abs(curr_fwd_rates[t] - prev_fwd_rates[t]) for t in tenors)
        max_disc_change = max(abs(curr_disc_rates[t] - prev_disc_rates[t]) for t in tenors)
        
        print(f"    - USD Forward Curve: re-bootstrapped (max change: {max_fwd_change*10000:.4f} bps)")
        print(f"    - USD Discount Curve: re-bootstrapped (max change: {max_disc_change*10000:.4f} bps)")
        
        # Store history
        iteration_history.append({
            'iteration': iteration,
            'forward_rates': curr_fwd_rates.copy(),
            'discount_rates': curr_disc_rates.copy()
        })
        
        # Check convergence
        if max_fwd_change < tolerance and max_disc_change < tolerance:
            print(f"\n  *** Converged at iteration {iteration}! ***")
            break
        
        prev_fwd_rates = curr_fwd_rates
        prev_disc_rates = curr_disc_rates
    else:
        print(f"\n  Warning: Did not converge within {max_iterations} iterations")
    
    # ========================================
    # Results
    # ========================================
    print("\n" + "=" * 80)
    print("CONVERGENCE RESULTS")
    print("=" * 80)
    
    print("\n[Iteration History - USD Forward Curve Zero Rates]")
    print("-" * 80)
    header = f"{'Iter':<6}"
    for t in tenors:
        header += f" {t:>14}"
    print(header)
    print("-" * 80)
    
    for hist in iteration_history:
        row = f"{hist['iteration']:<6}"
        for t in tenors:
            row += f" {hist['forward_rates'][t]*100:>13.6f}%"
        print(row)
    
    print("\n[Iteration History - USD Discount Curve Zero Rates]")
    print("-" * 80)
    print(header)
    print("-" * 80)
    
    for hist in iteration_history:
        row = f"{hist['iteration']:<6}"
        for t in tenors:
            row += f" {hist['discount_rates'][t]*100:>13.6f}%"
        print(row)
    
    print("\n[Final Curves Comparison]")
    print("-" * 90)
    print(f"{'Curve':<35} {'1Y':>12} {'2Y':>12} {'5Y':>12} {'10Y':>12}")
    print("-" * 90)
    
    # Initial USD Forward (Iteration 0)
    print(f"{'USD Forward (Initial, Iter 0)':<35}", end="")
    for t in tenors:
        print(f" {iteration_history[0]['forward_rates'][t]*100:>11.4f}%", end="")
    print()
    
    # Final USD Forward
    print(f"{'USD Forward (Final)':<35}", end="")
    for t in tenors:
        print(f" {iteration_history[-1]['forward_rates'][t]*100:>11.4f}%", end="")
    print()
    
    # Forward Change
    print(f"{'  Change (bps)':<35}", end="")
    for t in tenors:
        change = (iteration_history[-1]['forward_rates'][t] - iteration_history[0]['forward_rates'][t]) * 10000
        print(f" {change:>11.2f}", end="")
    print()
    
    print()
    
    # Initial USD Discount (Iteration 0)
    print(f"{'USD Discount (Initial, Iter 0)':<35}", end="")
    for t in tenors:
        print(f" {iteration_history[0]['discount_rates'][t]*100:>11.4f}%", end="")
    print()
    
    # Final USD Discount
    print(f"{'USD Discount (Final)':<35}", end="")
    for t in tenors:
        print(f" {iteration_history[-1]['discount_rates'][t]*100:>11.4f}%", end="")
    print()
    
    # Discount Change
    print(f"{'  Change (bps)':<35}", end="")
    for t in tenors:
        change = (iteration_history[-1]['discount_rates'][t] - iteration_history[0]['discount_rates'][t]) * 10000
        print(f" {change:>11.2f}", end="")
    print()
    
    print("\n[Cross-Currency Basis (Final)]")
    print("-" * 60)
    print(f"{'Tenor':<8} {'USD Forward':>14} {'USD Discount':>14} {'Basis (bps)':>14}")
    print("-" * 60)
    
    final_fwd = iteration_history[-1]['forward_rates']
    final_disc = iteration_history[-1]['discount_rates']
    
    for t in tenors:
        basis = (final_disc[t] - final_fwd[t]) * 10000
        print(f"{t:<8} {final_fwd[t]*100:>13.4f}% {final_disc[t]*100:>13.4f}% {basis:>13.2f}")
    
    print("\n[Interpretation]")
    print("  - Iterative bootstrap ensures consistency between USD forward and discount curves")
    print("  - USD forward curve is bootstrapped using CCS-derived discount curve for discounting")
    print("  - USD discount curve is bootstrapped from CCS using the adjusted forward curve")
    print("  - Convergence typically occurs within a few iterations")
    
    return ccs_bootstrap, usd_bootstrap, usd_forward_curve, usd_discount_curve, iteration_history


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("CROSS-CURRENCY SWAP BOOTSTRAP FOR USD DISCOUNT CURVE")
    print("Given: KRW Discount, USD Forward, CCS Quotes")
    print("Output: USD Discount Curve")
    print("=" * 80)
    
    try:
        example_basic_ccs_bootstrap()
        example_builder_pattern()
        example_negative_basis()
        example_with_existing_curves()
        example_usd_forward_curve_with_ccs_discount()
        example_iterative_ccs_bootstrap()
        
        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

