"""
Example Usage: Funding Spread Adjusted Forward Curve Bootstrap

This example demonstrates how to:
1. Build a standard SOFR OIS curve
2. Apply funding spread to create a funding curve
3. Bootstrap forward curve using funding curve as discount curve
4. Compare OIS forward rates vs Funding-adjusted forward rates
"""

import QuantLib as ql
from funding_curve_bootstrap import (
    FundingAdjustedCurveBootstrap,
    FundingCurveBuilder,
    OISQuote,
    FundingSpreadPoint,
    CurveInterpolation,
    create_sample_market_data
)


def example_full_bootstrap():
    """
    Full example: OIS -> Funding Curve -> Forward Curve Bootstrap
    
    This is the "Dirty Curve" approach:
    1. Bootstrap OIS curve from OIS quotes
    2. Add funding spread to create funding curve
    3. Re-bootstrap forward curve using funding curve for discounting
    """
    print("=" * 80)
    print("EXAMPLE 1: Forward Curve Bootstrap with Funding Curve Discounting")
    print("=" * 80)
    
    # Set valuation date
    valuation_date = ql.Date(11, 12, 2024)
    
    # Initialize the bootstrap engine
    bootstrap = FundingAdjustedCurveBootstrap(
        valuation_date=valuation_date,
        calendar=ql.UnitedStates(ql.UnitedStates.FederalReserve),
        day_count=ql.Actual360()
    )
    
    # Step 1: Define OIS quotes
    ois_quotes = [
        OISQuote("1Y", 0.04),
        OISQuote("5Y", 0.04),
        OISQuote("10Y", 0.04),
    ]
    
    # Step 2: Build the OIS curve
    print("\n[Step 1] Building SOFR OIS Curve...")
    ois_curve = bootstrap.build_ois_curve(ois_quotes)
    
    # Step 3: Define funding spreads
    funding_spreads = [
        FundingSpreadPoint("1Y", 50.0),   # 50 bps
        FundingSpreadPoint("5Y", 50.0),   # 50 bps
        FundingSpreadPoint("10Y", 50.0),  # 50 bps
    ]
    
    # Step 4: Build the Funding Curve (OIS + Spread)
    print("[Step 2] Building Funding Curve (OIS + Spread)...")
    funding_curve = bootstrap.build_funding_curve_from_ois(ois_curve, funding_spreads)
    
    # Step 5: Bootstrap Forward Curve using Funding Curve for discounting
    print("[Step 3] Bootstrapping Forward Curve with Funding Curve Discounting...")
    forward_curve = bootstrap.bootstrap_forward_curve_with_funding_discount(
        ois_quotes, funding_curve
    )
    
    # Compare curves
    tenors = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y"]
    
    print("\n" + "=" * 80)
    print("CURVE COMPARISON")
    print("=" * 80)
    
    print("\n[1] Zero Rates Comparison:")
    print("-" * 80)
    print(f"{'Tenor':<8} {'OIS':>14} {'Funding':>14} {'Fwd Curve':>14} {'Fwd-OIS (bps)':>14}")
    print("-" * 80)
    
    comparison = bootstrap.compare_curves(tenors)
    
    for tenor in tenors:
        ois_zr = comparison['ois_curve']['zero_rates'][tenor]
        fund_zr = comparison['funding_curve']['zero_rates'][tenor]
        fwd_zr = comparison['forward_curve']['zero_rates'][tenor]
        diff = comparison['differences'][tenor]['fwd_curve_zero_diff_bps']
        print(f"{tenor:<8} {ois_zr*100:>13.4f}% {fund_zr*100:>13.4f}% {fwd_zr*100:>13.4f}% {diff:>13.2f}")
    
    print("\n[2] Forward Rates (3M) Comparison:")
    print("-" * 80)
    print(f"{'Tenor':<8} {'OIS Fwd':>14} {'Funding Fwd':>14} {'FwdCurve Fwd':>14} {'Fwd-OIS (bps)':>14}")
    print("-" * 80)
    
    for tenor in tenors:
        ois_fwd = comparison['ois_curve']['forward_rates'][tenor]
        fund_fwd = comparison['funding_curve']['forward_rates'][tenor]
        fwd_curve_fwd = comparison['forward_curve']['forward_rates'][tenor]
        diff = comparison['differences'][tenor]['fwd_curve_forward_diff_bps']
        print(f"{tenor:<8} {ois_fwd*100:>13.4f}% {fund_fwd*100:>13.4f}% {fwd_curve_fwd*100:>13.4f}% {diff:>13.2f}")
    
    print("\n[3] Discount Factors Comparison:")
    print("-" * 80)
    print(f"{'Tenor':<8} {'OIS DF':>16} {'Funding DF':>16} {'FwdCurve DF':>16}")
    print("-" * 80)
    
    for tenor in tenors:
        ois_df = comparison['ois_curve']['discount_factors'][tenor]
        fund_df = comparison['funding_curve']['discount_factors'][tenor]
        fwd_df = comparison['forward_curve']['discount_factors'][tenor]
        print(f"{tenor:<8} {ois_df:>16.10f} {fund_df:>16.10f} {fwd_df:>16.10f}")
    
    return bootstrap


def example_builder_pattern():
    """
    Example using the fluent builder pattern with forward curve bootstrap.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Fluent Builder Pattern with Forward Curve Bootstrap")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    
    # OIS quotes
    ois_quotes = [
        ("1Y", 0.03),
        ("5Y", 0.04),
        ("10Y", 0.05),
    ]
    
    # Funding spreads
    funding_spreads = [
        ("1Y", 50.0),
        ("5Y", 50.0),
        ("10Y", 50.0),
    ]
    
    # Build all curves using fluent interface
    builder = (
        FundingCurveBuilder(valuation_date)
        .with_ois_curve(ois_quotes)
        .with_funding_spread(funding_spreads)
        .with_forward_curve_bootstrap()  # Bootstrap forward curve with funding discount
    )
    
    curves = builder.build()
    
    print("\nCurves built successfully!")
    print(f"  - OIS Curve:     {'OK' if curves['ois'] else 'FAIL'}")
    print(f"  - Funding Curve: {'OK' if curves['funding'] else 'FAIL'}")
    print(f"  - Forward Curve: {'OK' if curves['forward'] else 'FAIL'}")
    
    # Display forward rates comparison
    tenors = ["1Y", "3Y", "5Y", "7Y", "10Y"]
    
    print("\nForward Rates (3M) - OIS vs Forward Curve (bootstrapped with funding discount):")
    print("-" * 60)
    print(f"{'Tenor':<8} {'OIS Fwd':>16} {'Fwd Curve':>16} {'Diff (bps)':>14}")
    print("-" * 60)
    
    ois_fwds = builder.bootstrap.get_forward_rates(curves['ois'], tenors)
    fwd_curve_fwds = builder.bootstrap.get_forward_rates(curves['forward'], tenors)
    
    for tenor in tenors:
        diff = (fwd_curve_fwds[tenor] - ois_fwds[tenor]) * 10000
        print(f"{tenor:<8} {ois_fwds[tenor]*100:>15.4f}% {fwd_curve_fwds[tenor]*100:>15.4f}% {diff:>13.2f}")
    
    return builder


def example_swap_pricing_comparison():
    """
    Compare swap pricing with different curve combinations.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Swap Pricing with Different Curve Combinations")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    
    bootstrap = FundingAdjustedCurveBootstrap(valuation_date=valuation_date)
    
    # Build curves
    ois_quotes = [
        OISQuote("1Y", 0.03),
        OISQuote("5Y", 0.04),
        OISQuote("10Y", 0.05),
    ]
    ois_curve = bootstrap.build_ois_curve(ois_quotes)
    
    funding_spreads = [
        FundingSpreadPoint("1Y", 50.0),
        FundingSpreadPoint("5Y", 50.0),
        FundingSpreadPoint("10Y", 50.0),
    ]
    funding_curve = bootstrap.build_funding_curve_from_ois(ois_curve, funding_spreads)
    
    # Bootstrap forward curve with funding discount
    forward_curve = bootstrap.bootstrap_forward_curve_with_funding_discount(
        ois_quotes, funding_curve
    )
    
    print("\n5Y Payer Swap Comparison (Notional: $100,000,000, Fixed: 4%)")
    print("-" * 80)
    
    notional = 100_000_000
    fixed_rate = 0.04
    
    # Scenario 1: OIS for both projection and discounting (market standard)
    result_ois = bootstrap.price_swap(
        notional=notional, tenor="5Y", fixed_rate=fixed_rate, is_payer=True,
        projection_curve=ois_curve, discount_curve=ois_curve
    )
    
    # Scenario 2: Forward curve for projection, Funding curve for discounting
    result_fwd_fund = bootstrap.price_swap(
        notional=notional, tenor="5Y", fixed_rate=fixed_rate, is_payer=True,
        projection_curve=forward_curve, discount_curve=funding_curve
    )
    
    # Scenario 3: OIS for projection, Funding curve for discounting
    result_ois_fund = bootstrap.price_swap(
        notional=notional, tenor="5Y", fixed_rate=fixed_rate, is_payer=True,
        projection_curve=ois_curve, discount_curve=funding_curve
    )
    
    print(f"{'Scenario':<45} {'NPV ($)':>18} {'Fair Rate':>14}")
    print("-" * 80)
    print(f"{'1. OIS Proj + OIS Disc (Market Standard)':<45} {result_ois['npv']:>18,.0f} {result_ois['fair_rate']*100:>13.4f}%")
    print(f"{'2. FwdCurve Proj + Funding Disc (Dirty Curve)':<45} {result_fwd_fund['npv']:>18,.0f} {result_fwd_fund['fair_rate']*100:>13.4f}%")
    print(f"{'3. OIS Proj + Funding Disc':<45} {result_ois_fund['npv']:>18,.0f} {result_ois_fund['fair_rate']*100:>13.4f}%")
    
    print("\n[Analysis]")
    print(f"  Market Fair Rate (OIS/OIS):        {result_ois['fair_rate']*100:.4f}%")
    print(f"  Dirty Curve Fair Rate:             {result_fwd_fund['fair_rate']*100:.4f}%")
    print(f"  Difference:                        {(result_fwd_fund['fair_rate'] - result_ois['fair_rate'])*10000:.2f} bps")
    
    return bootstrap


def example_term_varying_spread():
    """
    Example with term-varying funding spreads.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Term-Varying Funding Spread")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    
    # OIS quotes with more points
    ois_quotes = [
        ("1Y", 0.03),
        ("2Y", 0.035),
        ("5Y", 0.04),
        ("10Y", 0.05),
    ]
    
    # Term-varying funding spreads (increasing with tenor)
    funding_spreads = [
        ("1Y", 20.0),    # 20 bps
        ("2Y", 30.0),    # 30 bps
        ("5Y", 50.0),    # 50 bps
        ("10Y", 70.0),   # 70 bps
    ]
    
    # Build all curves
    builder = (
        FundingCurveBuilder(valuation_date)
        .with_ois_curve(ois_quotes)
        .with_funding_spread(funding_spreads)
        .with_forward_curve_bootstrap()
    )
    
    curves = builder.build()
    
    tenors = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y"]
    
    print("\nForward Rates (3M) with Term-Varying Spread:")
    print("-" * 80)
    print(f"{'Tenor':<8} {'OIS Fwd':>14} {'Fwd Curve':>14} {'Spread':>14} {'Diff (bps)':>14}")
    print("-" * 80)
    
    # Expected spreads (interpolated)
    expected_spreads = {
        "1Y": 20, "2Y": 30, "3Y": 40, "5Y": 50, "7Y": 60, "10Y": 70
    }
    
    ois_fwds = builder.bootstrap.get_forward_rates(curves['ois'], tenors)
    fwd_fwds = builder.bootstrap.get_forward_rates(curves['forward'], tenors)
    
    for tenor in tenors:
        diff = (fwd_fwds[tenor] - ois_fwds[tenor]) * 10000
        spread = expected_spreads.get(tenor, "~")
        print(f"{tenor:<8} {ois_fwds[tenor]*100:>13.4f}% {fwd_fwds[tenor]*100:>13.4f}% {spread:>12}bp {diff:>13.2f}")
    
    return builder


def example_impact_on_fair_rate():
    """
    Analyze impact of funding spread on fair rates across tenors.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Impact of Funding Spread on Fair Rates")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    
    # Build curves
    ois_quotes = [
        ("1Y", 0.03),
        ("5Y", 0.04),
        ("10Y", 0.05),
    ]
    
    funding_spreads = [
        ("1Y", 50.0),
        ("5Y", 50.0),
        ("10Y", 50.0),
    ]
    
    builder = (
        FundingCurveBuilder(valuation_date)
        .with_ois_curve(ois_quotes)
        .with_funding_spread(funding_spreads)
        .with_forward_curve_bootstrap()
    )
    
    curves = builder.build()
    notional = 100_000_000
    
    print("\nFair Rate Impact Across Tenors:")
    print("-" * 70)
    print(f"{'Tenor':<8} {'OIS Fair Rate':>16} {'Dirty Fair Rate':>18} {'Diff (bps)':>14}")
    print("-" * 70)
    
    for tenor in ["2Y", "3Y", "5Y", "7Y", "10Y"]:
        # OIS pricing
        result_ois = builder.bootstrap.price_swap(
            notional=notional, tenor=tenor, fixed_rate=0.04, is_payer=True,
            projection_curve=curves['ois'], discount_curve=curves['ois']
        )
        
        # Dirty curve pricing
        result_dirty = builder.bootstrap.price_swap(
            notional=notional, tenor=tenor, fixed_rate=0.04, is_payer=True,
            projection_curve=curves['forward'], discount_curve=curves['funding']
        )
        
        diff = (result_dirty['fair_rate'] - result_ois['fair_rate']) * 10000
        print(f"{tenor:<8} {result_ois['fair_rate']*100:>15.4f}% {result_dirty['fair_rate']*100:>17.4f}% {diff:>13.2f}")
    
    return builder


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("FUNDING SPREAD ADJUSTED FORWARD CURVE BOOTSTRAP")
    print("Dirty Curve Approach: Forward Curve Bootstrap with Funding Discount")
    print("=" * 80)
    
    try:
        example_full_bootstrap()
        example_builder_pattern()
        example_swap_pricing_comparison()
        example_term_varying_spread()
        example_impact_on_fair_rate()
        
        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
