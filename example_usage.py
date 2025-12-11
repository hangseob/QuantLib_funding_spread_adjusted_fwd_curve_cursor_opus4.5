"""
Example Usage: Funding Spread Adjusted Forward Curve Bootstrap

This example demonstrates how to:
1. Build a standard SOFR OIS curve
2. Apply term structure of funding spreads to create a "Dirty Curve"
3. Bootstrap IRS using the funding curve for discounting
4. Compare the resulting forward curves with and without funding adjustments
"""

import QuantLib as ql
from funding_curve_bootstrap import (
    FundingCurveBootstrap,
    FundingCurveBuilder,
    OISQuote,
    IRSQuote,
    FundingSpreadPoint,
    CurveInterpolation,
    create_sample_market_data
)


def example_basic_usage():
    """
    Basic example using the FundingCurveBootstrap class directly.
    """
    print("=" * 80)
    print("EXAMPLE 1: Basic Usage with FundingCurveBootstrap")
    print("=" * 80)
    
    # Set valuation date
    valuation_date = ql.Date(11, 12, 2024)  # December 11, 2024
    
    # Initialize the bootstrap engine
    bootstrap = FundingCurveBootstrap(
        valuation_date=valuation_date,
        calendar=ql.UnitedStates(ql.UnitedStates.FederalReserve),
        day_count=ql.Actual360(),
        settlement_days=2
    )
    
    # Step 1: Define OIS quotes
    ois_quotes = [
        OISQuote("1M", 0.0535),
        OISQuote("3M", 0.0530),
        OISQuote("6M", 0.0520),
        OISQuote("1Y", 0.0500),
        OISQuote("2Y", 0.0465),
        OISQuote("3Y", 0.0445),
        OISQuote("5Y", 0.0430),
        OISQuote("7Y", 0.0425),
        OISQuote("10Y", 0.0420),
        OISQuote("15Y", 0.0418),
        OISQuote("20Y", 0.0415),
        OISQuote("30Y", 0.0410),
    ]
    
    # Step 2: Build the OIS curve
    print("\n[Step 1] Building SOFR OIS Curve...")
    ois_curve = bootstrap.build_ois_curve(ois_quotes, CurveInterpolation.LOG_LINEAR)
    
    # Step 3: Define funding spreads (term structure)
    funding_spreads = [
        FundingSpreadPoint("1Y", 5.0),    # 5 bps
        FundingSpreadPoint("2Y", 8.0),    # 8 bps
        FundingSpreadPoint("3Y", 10.0),   # 10 bps
        FundingSpreadPoint("5Y", 15.0),   # 15 bps
        FundingSpreadPoint("7Y", 18.0),   # 18 bps
        FundingSpreadPoint("10Y", 20.0),  # 20 bps
        FundingSpreadPoint("20Y", 25.0),  # 25 bps
        FundingSpreadPoint("30Y", 30.0),  # 30 bps
    ]
    
    # Step 4: Build the Funding Curve (OIS + Spread)
    print("[Step 2] Building Funding Curve (OIS + Funding Spread)...")
    funding_curve = bootstrap.build_funding_curve(ois_curve, funding_spreads)
    
    # Step 5: Compare OIS and Funding curves
    print("\n[Comparison] OIS Curve vs Funding Curve:")
    print("-" * 60)
    tenors = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]
    
    comparison = bootstrap.compare_curves(
        ois_curve, funding_curve, tenors,
        "OIS Curve", "Funding Curve"
    )
    
    print(f"{'Tenor':<8} {'OIS Rate':>12} {'Funding Rate':>14} {'Spread (bps)':>14}")
    print("-" * 60)
    for tenor in tenors:
        ois_rate = comparison["OIS Curve"]["zero_rates"][tenor]
        funding_rate = comparison["Funding Curve"]["zero_rates"][tenor]
        spread_bps = comparison["differences"][tenor]["zero_rate_diff_bps"]
        print(f"{tenor:<8} {ois_rate*100:>11.4f}% {funding_rate*100:>13.4f}% {spread_bps:>13.2f}")
    
    # Step 6: Define IRS quotes
    irs_quotes = [
        IRSQuote("2Y", 0.0468),
        IRSQuote("3Y", 0.0448),
        IRSQuote("5Y", 0.0433),
        IRSQuote("7Y", 0.0428),
        IRSQuote("10Y", 0.0423),
        IRSQuote("15Y", 0.0420),
        IRSQuote("20Y", 0.0418),
        IRSQuote("30Y", 0.0413),
    ]
    
    # Step 7: Bootstrap IRS with Funding Curve as discount curve
    print("\n[Step 3] Bootstrapping IRS Forward Curve with Funding Curve Discounting...")
    forward_curve_with_funding = bootstrap.bootstrap_irs_with_funding_curve(
        irs_quotes, funding_curve
    )
    
    # Also bootstrap without funding adjustment for comparison
    forward_curve_without_funding = bootstrap.bootstrap_irs_with_funding_curve(
        irs_quotes, ois_curve  # Use OIS curve for discounting instead
    )
    
    # Step 8: Compare forward curves
    print("\n[Comparison] Forward Curves (3M Forward Rates):")
    print("-" * 70)
    forward_tenors = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y"]
    
    print(f"{'Tenor':<8} {'OIS Discount':>14} {'Funding Discount':>16} {'Diff (bps)':>12}")
    print("-" * 70)
    
    for tenor in forward_tenors:
        fwd_ois = bootstrap.get_forward_rates(forward_curve_without_funding, [tenor], "3M")[tenor]
        fwd_funding = bootstrap.get_forward_rates(forward_curve_with_funding, [tenor], "3M")[tenor]
        diff_bps = (fwd_funding - fwd_ois) * 10000
        print(f"{tenor:<8} {fwd_ois*100:>13.4f}% {fwd_funding*100:>15.4f}% {diff_bps:>11.2f}")
    
    # Step 9: Price a sample swap
    print("\n[Step 4] Pricing a 5Y Payer Swap...")
    print("-" * 50)
    
    swap_result = bootstrap.price_swap(
        notional=100_000_000,  # 100 million
        tenor="5Y",
        fixed_rate=0.0433,  # At-the-money rate
        is_payer=True,
        forward_curve=forward_curve_with_funding,
        discount_curve=funding_curve
    )
    
    print(f"Notional:           $100,000,000")
    print(f"Fixed Rate:         4.33%")
    print(f"NPV:                ${swap_result['npv']:,.2f}")
    print(f"Fixed Leg NPV:      ${swap_result['fixed_leg_npv']:,.2f}")
    print(f"Floating Leg NPV:   ${swap_result['floating_leg_npv']:,.2f}")
    print(f"Fair Rate:          {swap_result['fair_rate']*100:.4f}%")
    
    return bootstrap, ois_curve, funding_curve, forward_curve_with_funding


def example_builder_pattern():
    """
    Example using the fluent builder pattern for cleaner code.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Fluent Builder Pattern")
    print("=" * 80)
    
    # Get sample market data
    market_data = create_sample_market_data()
    
    # Build all curves using the fluent interface
    valuation_date = ql.Date(11, 12, 2024)
    
    builder = (
        FundingCurveBuilder(valuation_date)
        .with_ois_curve(market_data['ois_quotes'])
        .with_term_funding_spreads(market_data['funding_spreads'])
        .with_irs_bootstrap(market_data['irs_quotes'])
    )
    
    curves = builder.build()
    
    print("\nCurves built successfully!")
    print(f"- OIS Curve:     {'OK' if curves['ois'] else 'FAIL'}")
    print(f"- Funding Curve: {'OK' if curves['funding'] else 'FAIL'}")
    print(f"- Forward Curve: {'OK' if curves['forward'] else 'FAIL'}")
    
    # Display zero rates
    tenors = ["1Y", "2Y", "5Y", "10Y", "30Y"]
    print("\nZero Rates Comparison:")
    print("-" * 50)
    print(f"{'Tenor':<8} {'OIS':>12} {'Funding':>12}")
    print("-" * 50)
    
    for tenor in tenors:
        ois_rate = builder.bootstrap.get_zero_rates(curves['ois'], [tenor])[tenor]
        funding_rate = builder.bootstrap.get_zero_rates(curves['funding'], [tenor])[tenor]
        print(f"{tenor:<8} {ois_rate*100:>11.4f}% {funding_rate*100:>11.4f}%")
    
    return builder


def example_flat_spread():
    """
    Example using a flat (constant) funding spread.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Flat Funding Spread")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    
    # Get sample market data
    market_data = create_sample_market_data()
    
    # Build with flat spread of 15 bps
    builder = (
        FundingCurveBuilder(valuation_date)
        .with_ois_curve(market_data['ois_quotes'])
        .with_flat_funding_spread(15.0)  # 15 bps flat spread
        .with_irs_bootstrap(market_data['irs_quotes'])
    )
    
    curves = builder.build()
    
    # Compare discount factors
    tenors = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]
    
    print("\nDiscount Factor Comparison (Flat 15 bps spread):")
    print("-" * 60)
    print(f"{'Tenor':<8} {'OIS DF':>14} {'Funding DF':>14} {'Ratio':>12}")
    print("-" * 60)
    
    for tenor in tenors:
        ois_df = builder.bootstrap.get_discount_factors(curves['ois'], [tenor])[tenor]
        funding_df = builder.bootstrap.get_discount_factors(curves['funding'], [tenor])[tenor]
        ratio = funding_df / ois_df
        print(f"{tenor:<8} {ois_df:>14.8f} {funding_df:>14.8f} {ratio:>12.6f}")
    
    return builder


def example_impact_analysis():
    """
    Analyze the impact of funding spreads on swap valuation.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Funding Spread Impact Analysis")
    print("=" * 80)
    
    valuation_date = ql.Date(11, 12, 2024)
    market_data = create_sample_market_data()
    
    # Build curves with funding spread
    builder_with_spread = (
        FundingCurveBuilder(valuation_date)
        .with_ois_curve(market_data['ois_quotes'])
        .with_term_funding_spreads(market_data['funding_spreads'])
        .with_irs_bootstrap(market_data['irs_quotes'])
    )
    curves_with_spread = builder_with_spread.build()
    
    # Build curves without funding spread (OIS curve for both)
    builder_no_spread = (
        FundingCurveBuilder(valuation_date)
        .with_ois_curve(market_data['ois_quotes'])
        .with_flat_funding_spread(0.0)  # No spread
        .with_irs_bootstrap(market_data['irs_quotes'])
    )
    curves_no_spread = builder_no_spread.build()
    
    # Price swaps with and without funding spread
    print("\n5Y Payer Swap Valuation Impact:")
    print("-" * 70)
    
    notional = 100_000_000
    fixed_rate = 0.0430  # Slightly off-market
    
    # Price with funding spread
    result_with_spread = builder_with_spread.bootstrap.price_swap(
        notional=notional,
        tenor="5Y",
        fixed_rate=fixed_rate,
        is_payer=True,
        forward_curve=curves_with_spread['forward'],
        discount_curve=curves_with_spread['funding']
    )
    
    # Price without funding spread
    result_no_spread = builder_no_spread.bootstrap.price_swap(
        notional=notional,
        tenor="5Y",
        fixed_rate=fixed_rate,
        is_payer=True,
        forward_curve=curves_no_spread['forward'],
        discount_curve=curves_no_spread['funding']  # This is effectively OIS curve
    )
    
    print(f"Fixed Rate:             {fixed_rate*100:.2f}%")
    print(f"Notional:               ${notional:,.0f}")
    print()
    print(f"{'Metric':<25} {'No Spread':>15} {'With Spread':>15} {'Difference':>15}")
    print("-" * 70)
    print(f"{'NPV ($)':<25} {result_no_spread['npv']:>15,.0f} {result_with_spread['npv']:>15,.0f} {result_with_spread['npv'] - result_no_spread['npv']:>15,.0f}")
    print(f"{'Fair Rate (%)':<25} {result_no_spread['fair_rate']*100:>15.4f} {result_with_spread['fair_rate']*100:>15.4f} {(result_with_spread['fair_rate'] - result_no_spread['fair_rate'])*10000:>14.2f}bp")
    
    # Impact across different tenors
    print("\n\nFair Rate Impact Across Tenors:")
    print("-" * 50)
    print(f"{'Tenor':<8} {'No Spread':>12} {'With Spread':>14} {'Diff (bps)':>12}")
    print("-" * 50)
    
    for tenor in ["2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"]:
        result_ns = builder_no_spread.bootstrap.price_swap(
            notional=notional,
            tenor=tenor,
            fixed_rate=0.04,
            is_payer=True,
            forward_curve=curves_no_spread['forward'],
            discount_curve=curves_no_spread['funding']
        )
        
        result_ws = builder_with_spread.bootstrap.price_swap(
            notional=notional,
            tenor=tenor,
            fixed_rate=0.04,
            is_payer=True,
            forward_curve=curves_with_spread['forward'],
            discount_curve=curves_with_spread['funding']
        )
        
        diff_bps = (result_ws['fair_rate'] - result_ns['fair_rate']) * 10000
        print(f"{tenor:<8} {result_ns['fair_rate']*100:>11.4f}% {result_ws['fair_rate']*100:>13.4f}% {diff_bps:>11.2f}")
    
    return builder_with_spread, builder_no_spread


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("FUNDING SPREAD ADJUSTED FORWARD CURVE BOOTSTRAP")
    print("Python QuantLib Implementation")
    print("=" * 80)
    
    # Run examples
    try:
        example_basic_usage()
        example_builder_pattern()
        example_flat_spread()
        example_impact_analysis()
        
        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

