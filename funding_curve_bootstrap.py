"""
Funding Spread Adjusted Forward Curve Bootstrap Module

This module implements a "Dirty Curve" approach where:
1. OIS Curve is bootstrapped from OIS quotes
2. Funding spread is applied to derive funding-adjusted forward rates
3. The resulting curve reflects the bank's actual cost of funding

Key concept:
    r_funding(t) = r_ois(t) + spread(t)
    
This means forward rates projected from the funding curve will be higher
than those from the OIS curve by the funding spread amount.
"""

import QuantLib as ql
from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum
import numpy as np


class CurveInterpolation(Enum):
    """Interpolation methods for curve construction."""
    LINEAR = "linear"
    LOG_LINEAR = "log_linear"
    CUBIC = "cubic"


@dataclass
class OISQuote:
    """Represents an OIS swap quote."""
    tenor: str
    rate: float  # quoted rate in decimal (e.g., 0.05 for 5%)


@dataclass
class FundingSpreadPoint:
    """Represents a single funding spread data point."""
    tenor: str  # e.g., "1Y", "5Y", "10Y"
    spread_bps: float  # spread in basis points


class FundingAdjustedCurveBootstrap:
    """
    Bootstraps OIS curve and creates funding-adjusted forward curve.
    
    The "Dirty Curve" approach:
    1. Build standard OIS curve from SOFR OIS quotes
    2. Apply funding spread to create funding-adjusted curve
    
    The funding curve's forward rates = OIS forward rates + funding spread
    """
    
    def __init__(
        self,
        valuation_date: ql.Date,
        calendar: ql.Calendar = None,
        day_count: ql.DayCounter = None,
        settlement_days: int = 2
    ):
        """
        Initialize the FundingAdjustedCurveBootstrap.
        
        Args:
            valuation_date: The valuation/pricing date
            calendar: Calendar for business day adjustments
            day_count: Day count convention
            settlement_days: Number of settlement days
        """
        self.valuation_date = valuation_date
        self.calendar = calendar if calendar else ql.UnitedStates(ql.UnitedStates.FederalReserve)
        self.day_count = day_count if day_count else ql.Actual360()
        self.settlement_days = settlement_days
        
        # Set the global evaluation date
        ql.Settings.instance().evaluationDate = valuation_date
        
        # Initialize curve handles
        self._ois_curve: Optional[ql.YieldTermStructureHandle] = None
        self._funding_curve: Optional[ql.YieldTermStructureHandle] = None
        self._forward_curve: Optional[ql.YieldTermStructureHandle] = None
        
    def _parse_tenor(self, tenor: str) -> ql.Period:
        """Convert tenor string to QuantLib Period."""
        tenor = tenor.upper().strip()
        
        # Handle special cases
        if tenor == "ON" or tenor == "O/N":
            return ql.Period(1, ql.Days)
        elif tenor == "TN" or tenor == "T/N":
            return ql.Period(1, ql.Days)
        elif tenor == "SN" or tenor == "S/N":
            return ql.Period(1, ql.Days)
        
        # Parse standard tenors (1D, 1W, 1M, 1Y, etc.)
        unit_map = {
            'D': ql.Days,
            'W': ql.Weeks,
            'M': ql.Months,
            'Y': ql.Years
        }
        
        # Extract number and unit
        number = int(tenor[:-1])
        unit = tenor[-1]
        
        if unit not in unit_map:
            raise ValueError(f"Unknown tenor unit: {unit} in tenor {tenor}")
            
        return ql.Period(number, unit_map[unit])
    
    def build_ois_curve(
        self,
        ois_quotes: List[OISQuote],
        interpolation: CurveInterpolation = CurveInterpolation.LOG_LINEAR
    ) -> ql.YieldTermStructureHandle:
        """
        Build standard SOFR OIS curve from OIS swap quotes.
        
        Args:
            ois_quotes: List of OIS quotes with tenors and rates
            interpolation: Interpolation method for the curve
            
        Returns:
            YieldTermStructureHandle for the OIS curve
        """
        # Create rate helpers for OIS curve bootstrapping
        rate_helpers = []
        
        for quote in ois_quotes:
            period = self._parse_tenor(quote.tenor)
            rate = ql.QuoteHandle(ql.SimpleQuote(quote.rate))
            
            helper = ql.OISRateHelper(
                self.settlement_days,
                period,
                rate,
                ql.Sofr()  # SOFR overnight index
            )
            rate_helpers.append(helper)
        
        # Build the curve based on interpolation method
        if interpolation == CurveInterpolation.LOG_LINEAR:
            ois_curve = ql.PiecewiseLogLinearDiscount(
                self.valuation_date,
                rate_helpers,
                self.day_count
            )
        elif interpolation == CurveInterpolation.LINEAR:
            ois_curve = ql.PiecewiseLinearZero(
                self.valuation_date,
                rate_helpers,
                self.day_count
            )
        else:  # CUBIC
            ois_curve = ql.PiecewiseCubicZero(
                self.valuation_date,
                rate_helpers,
                self.day_count
            )
        
        # Enable extrapolation
        ois_curve.enableExtrapolation()
        
        self._ois_curve = ql.YieldTermStructureHandle(ois_curve)
        return self._ois_curve
    
    def build_funding_curve_from_ois(
        self,
        ois_curve_handle: ql.YieldTermStructureHandle,
        funding_spreads: List[FundingSpreadPoint]
    ) -> ql.YieldTermStructureHandle:
        """
        Build funding curve by applying funding spreads to OIS curve.
        
        This creates a new curve where:
            zero_rate_funding(t) = zero_rate_ois(t) + spread(t)
        
        Args:
            ois_curve_handle: Handle to the base OIS curve
            funding_spreads: List of funding spread data points
            
        Returns:
            YieldTermStructureHandle for the funding curve
        """
        # Build spread term structure dates and values
        spread_dates = [self.valuation_date]
        spread_values = [0.0]  # Start with zero spread at valuation date
        
        for spread_point in funding_spreads:
            period = self._parse_tenor(spread_point.tenor)
            date = self.calendar.advance(self.valuation_date, period)
            spread = spread_point.spread_bps / 10000.0  # Convert bps to decimal
            
            spread_dates.append(date)
            spread_values.append(spread)
        
        # Create spread curve for interpolation
        spread_curve = ql.ZeroCurve(
            spread_dates,
            spread_values,
            self.day_count,
            self.calendar
        )
        spread_curve.enableExtrapolation()
        
        # Generate funding curve by adding spreads to OIS zero rates
        # Create dense grid of dates for smooth interpolation
        max_date = max(spread_dates)
        
        funding_dates = [self.valuation_date]
        funding_rates = []
        
        # Get initial rate (use 1 day forward to avoid valuation date issues)
        one_day = self.calendar.advance(self.valuation_date, ql.Period(1, ql.Days))
        initial_ois_rate = ois_curve_handle.zeroRate(
            one_day, self.day_count, ql.Continuous
        ).rate()
        initial_spread = spread_curve.zeroRate(
            one_day, self.day_count, ql.Continuous
        ).rate()
        funding_rates.append(initial_ois_rate + initial_spread)
        
        # Generate monthly points for smooth curve
        current_date = self.calendar.advance(self.valuation_date, ql.Period(1, ql.Months))
        
        while current_date <= max_date:
            ois_rate = ois_curve_handle.zeroRate(
                current_date, self.day_count, ql.Continuous
            ).rate()
            spread = spread_curve.zeroRate(
                current_date, self.day_count, ql.Continuous
            ).rate()
            
            funding_dates.append(current_date)
            funding_rates.append(ois_rate + spread)
            
            current_date = self.calendar.advance(current_date, ql.Period(1, ql.Months))
        
        # Add final date if not already included
        if funding_dates[-1] < max_date:
            ois_rate = ois_curve_handle.zeroRate(
                max_date, self.day_count, ql.Continuous
            ).rate()
            spread = spread_curve.zeroRate(
                max_date, self.day_count, ql.Continuous
            ).rate()
            funding_dates.append(max_date)
            funding_rates.append(ois_rate + spread)
        
        # Build the funding curve
        funding_curve = ql.ZeroCurve(
            funding_dates,
            funding_rates,
            self.day_count,
            self.calendar
        )
        funding_curve.enableExtrapolation()
        
        self._funding_curve = ql.YieldTermStructureHandle(funding_curve)
        return self._funding_curve
    
    def build_funding_curve_flat_spread(
        self,
        ois_curve_handle: ql.YieldTermStructureHandle,
        flat_spread_bps: float
    ) -> ql.YieldTermStructureHandle:
        """
        Build funding curve with a flat (constant) spread over OIS curve.
        
        Args:
            ois_curve_handle: Handle to the base OIS curve
            flat_spread_bps: Constant funding spread in basis points
            
        Returns:
            YieldTermStructureHandle for the funding curve
        """
        spread = flat_spread_bps / 10000.0  # Convert to decimal
        spread_quote = ql.QuoteHandle(ql.SimpleQuote(spread))
        
        # ZeroSpreadedTermStructure adds a constant spread to the base curve
        funding_curve = ql.ZeroSpreadedTermStructure(
            ois_curve_handle,
            spread_quote,
            ql.Continuous,
            ql.Annual,
            self.day_count
        )
        funding_curve.enableExtrapolation()
        
        self._funding_curve = ql.YieldTermStructureHandle(funding_curve)
        return self._funding_curve
    
    def bootstrap_forward_curve_with_funding_discount(
        self,
        ois_quotes: List[OISQuote],
        discount_curve: ql.YieldTermStructureHandle,
        interpolation: CurveInterpolation = CurveInterpolation.LOG_LINEAR
    ) -> ql.YieldTermStructureHandle:
        """
        Bootstrap OIS forward curve using funding curve for discounting.
        
        This is the core "Dirty Curve" approach:
        - Use OIS swap quotes as instruments
        - Use Funding Curve for discounting cash flows
        - Solve for forward rates such that PV = 0
        
        The resulting forward rates will be different from standard OIS forward rates
        because the discounting is done with funding rates (OIS + spread).
        
        Args:
            ois_quotes: List of OIS quotes (tenor, rate)
            discount_curve: Funding curve to use for discounting
            interpolation: Interpolation method for the forward curve
            
        Returns:
            YieldTermStructureHandle for the funding-adjusted forward curve
        """
        # Create rate helpers with explicit discount curve
        rate_helpers = []
        
        for quote in ois_quotes:
            period = self._parse_tenor(quote.tenor)
            rate = ql.QuoteHandle(ql.SimpleQuote(quote.rate))
            
            # OISRateHelper with explicit discount curve
            # This will bootstrap forward rates such that swap PV = 0
            # when discounted with the funding curve
            helper = ql.OISRateHelper(
                self.settlement_days,
                period,
                rate,
                ql.Sofr(),  # SOFR overnight index
                discount_curve  # Use funding curve for discounting!
            )
            rate_helpers.append(helper)
        
        # Build the forward curve
        if interpolation == CurveInterpolation.LOG_LINEAR:
            forward_curve = ql.PiecewiseLogLinearDiscount(
                self.valuation_date,
                rate_helpers,
                self.day_count
            )
        elif interpolation == CurveInterpolation.LINEAR:
            forward_curve = ql.PiecewiseLinearZero(
                self.valuation_date,
                rate_helpers,
                self.day_count
            )
        else:  # CUBIC
            forward_curve = ql.PiecewiseCubicZero(
                self.valuation_date,
                rate_helpers,
                self.day_count
            )
        
        forward_curve.enableExtrapolation()
        
        self._forward_curve = ql.YieldTermStructureHandle(forward_curve)
        return self._forward_curve
    
    @property
    def forward_curve(self) -> ql.YieldTermStructureHandle:
        """Get the funding-adjusted forward curve."""
        return self._forward_curve
    
    def get_zero_rates(
        self,
        curve: ql.YieldTermStructureHandle,
        tenors: List[str]
    ) -> Dict[str, float]:
        """Extract zero rates from a curve at specified tenors."""
        zero_rates = {}
        
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = self.calendar.advance(self.valuation_date, period)
            
            rate = curve.zeroRate(
                date, self.day_count, ql.Continuous
            ).rate()
            
            zero_rates[tenor] = rate
            
        return zero_rates
    
    def get_forward_rates(
        self,
        curve: ql.YieldTermStructureHandle,
        tenors: List[str],
        forward_tenor: str = "3M"
    ) -> Dict[str, float]:
        """Extract forward rates from a curve at specified tenors."""
        forward_period = self._parse_tenor(forward_tenor)
        forward_rates = {}
        
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = self.calendar.advance(self.valuation_date, period)
            end_date = self.calendar.advance(date, forward_period)
            
            rate = curve.forwardRate(
                date, end_date, self.day_count, ql.Simple
            ).rate()
            
            forward_rates[tenor] = rate
            
        return forward_rates
    
    def get_discount_factors(
        self,
        curve: ql.YieldTermStructureHandle,
        tenors: List[str]
    ) -> Dict[str, float]:
        """Extract discount factors from a curve at specified tenors."""
        discount_factors = {}
        
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = self.calendar.advance(self.valuation_date, period)
            
            df = curve.discount(date)
            discount_factors[tenor] = df
            
        return discount_factors
    
    def price_swap(
        self,
        notional: float,
        tenor: str,
        fixed_rate: float,
        is_payer: bool,
        projection_curve: ql.YieldTermStructureHandle,
        discount_curve: ql.YieldTermStructureHandle = None,
        fixed_leg_frequency: int = None,
        float_leg_frequency: int = None,
        fixed_leg_day_count: ql.DayCounter = None,
        float_leg_day_count: ql.DayCounter = None
    ) -> Dict[str, float]:
        """
        Price an interest rate swap.
        
        Args:
            notional: Swap notional amount
            tenor: Swap tenor (e.g., "5Y")
            fixed_rate: Fixed leg rate (decimal)
            is_payer: True if paying fixed, False if receiving fixed
            projection_curve: Curve for projecting floating rates (funding curve)
            discount_curve: Curve for discounting (if None, uses projection_curve)
            
        Returns:
            Dictionary containing NPV and leg values
        """
        # Set defaults
        if discount_curve is None:
            discount_curve = projection_curve
        if fixed_leg_frequency is None:
            fixed_leg_frequency = ql.Annual
        if float_leg_frequency is None:
            float_leg_frequency = ql.Quarterly
        if fixed_leg_day_count is None:
            fixed_leg_day_count = ql.Thirty360(ql.Thirty360.BondBasis)
        if float_leg_day_count is None:
            float_leg_day_count = ql.Actual360()
        
        # Calculate dates
        start_date = self.calendar.advance(
            self.valuation_date, 
            ql.Period(self.settlement_days, ql.Days)
        )
        period = self._parse_tenor(tenor)
        maturity_date = self.calendar.advance(start_date, period)
        
        # Create schedules
        fixed_schedule = ql.Schedule(
            start_date,
            maturity_date,
            ql.Period(fixed_leg_frequency),
            self.calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )
        
        float_schedule = ql.Schedule(
            start_date,
            maturity_date,
            ql.Period(float_leg_frequency),
            self.calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )
        
        # Create SOFR index with projection curve
        sofr_index = ql.Sofr(projection_curve)
        
        # Determine swap type
        swap_type = ql.VanillaSwap.Payer if is_payer else ql.VanillaSwap.Receiver
        
        # Create the swap
        swap = ql.VanillaSwap(
            swap_type,
            notional,
            fixed_schedule,
            fixed_rate,
            fixed_leg_day_count,
            float_schedule,
            sofr_index,
            0.0,  # spread
            float_leg_day_count
        )
        
        # Create pricing engine with discount curve
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)
        
        return {
            'npv': swap.NPV(),
            'fixed_leg_npv': swap.fixedLegNPV(),
            'floating_leg_npv': swap.floatingLegNPV(),
            'fair_rate': swap.fairRate(),
            'fair_spread': swap.fairSpread()
        }
    
    def compare_curves(
        self,
        tenors: List[str],
        forward_tenor: str = "3M",
        include_forward_curve: bool = True
    ) -> Dict:
        """
        Compare OIS curve, funding curve, and forward curve.
        
        Args:
            tenors: List of tenors for comparison
            forward_tenor: Period for forward rates
            include_forward_curve: Whether to include forward curve in comparison
            
        Returns:
            Dictionary with comparison data
        """
        if self._ois_curve is None or self._funding_curve is None:
            raise ValueError("Both OIS and funding curves must be built first")
        
        comparison = {
            'tenors': tenors,
            'ois_curve': {
                'zero_rates': self.get_zero_rates(self._ois_curve, tenors),
                'forward_rates': self.get_forward_rates(self._ois_curve, tenors, forward_tenor),
                'discount_factors': self.get_discount_factors(self._ois_curve, tenors)
            },
            'funding_curve': {
                'zero_rates': self.get_zero_rates(self._funding_curve, tenors),
                'forward_rates': self.get_forward_rates(self._funding_curve, tenors, forward_tenor),
                'discount_factors': self.get_discount_factors(self._funding_curve, tenors)
            },
            'differences': {}
        }
        
        # Add forward curve if available and requested
        if include_forward_curve and self._forward_curve is not None:
            comparison['forward_curve'] = {
                'zero_rates': self.get_zero_rates(self._forward_curve, tenors),
                'forward_rates': self.get_forward_rates(self._forward_curve, tenors, forward_tenor),
                'discount_factors': self.get_discount_factors(self._forward_curve, tenors)
            }
        
        # Calculate differences
        for tenor in tenors:
            ois_zr = comparison['ois_curve']['zero_rates'][tenor]
            fund_zr = comparison['funding_curve']['zero_rates'][tenor]
            ois_fwd = comparison['ois_curve']['forward_rates'][tenor]
            fund_fwd = comparison['funding_curve']['forward_rates'][tenor]
            
            comparison['differences'][tenor] = {
                'zero_rate_diff_bps': (fund_zr - ois_zr) * 10000,
                'forward_rate_diff_bps': (fund_fwd - ois_fwd) * 10000,
                'discount_factor_ratio': (
                    comparison['funding_curve']['discount_factors'][tenor] /
                    comparison['ois_curve']['discount_factors'][tenor]
                )
            }
            
            # Add forward curve differences if available
            if include_forward_curve and self._forward_curve is not None:
                fwd_curve_zr = comparison['forward_curve']['zero_rates'][tenor]
                fwd_curve_fwd = comparison['forward_curve']['forward_rates'][tenor]
                comparison['differences'][tenor]['fwd_curve_zero_diff_bps'] = (fwd_curve_zr - ois_zr) * 10000
                comparison['differences'][tenor]['fwd_curve_forward_diff_bps'] = (fwd_curve_fwd - ois_fwd) * 10000
        
        return comparison
    
    @property
    def ois_curve(self) -> ql.YieldTermStructureHandle:
        """Get the OIS curve."""
        return self._ois_curve
    
    @property
    def funding_curve(self) -> ql.YieldTermStructureHandle:
        """Get the funding curve."""
        return self._funding_curve


class FundingCurveBuilder:
    """
    High-level builder class for constructing funding-adjusted curves.
    Provides a fluent interface for building curves with funding spread adjustments.
    """
    
    def __init__(self, valuation_date: Union[ql.Date, str]):
        """
        Initialize the builder.
        
        Args:
            valuation_date: Valuation date as QuantLib Date or string "YYYY-MM-DD"
        """
        if isinstance(valuation_date, str):
            parts = valuation_date.split('-')
            valuation_date = ql.Date(int(parts[2]), int(parts[1]), int(parts[0]))
        
        self.bootstrap = FundingAdjustedCurveBootstrap(valuation_date)
        self._ois_quotes = None
        
    def with_ois_curve(
        self,
        quotes: List[Tuple[str, float]],
        interpolation: CurveInterpolation = CurveInterpolation.LOG_LINEAR
    ) -> 'FundingCurveBuilder':
        """
        Build OIS curve from quotes.
        
        Args:
            quotes: List of (tenor, rate) tuples
            interpolation: Curve interpolation method
            
        Returns:
            Self for method chaining
        """
        self._ois_quotes = quotes  # Store for later use in forward curve bootstrap
        ois_quotes = [OISQuote(tenor, rate) for tenor, rate in quotes]
        self.bootstrap.build_ois_curve(ois_quotes, interpolation)
        return self
    
    def with_funding_spread(
        self,
        spreads: List[Tuple[str, float]]
    ) -> 'FundingCurveBuilder':
        """
        Apply term structure of funding spreads to OIS curve.
        
        Args:
            spreads: List of (tenor, spread_bps) tuples
            
        Returns:
            Self for method chaining
        """
        if self.bootstrap.ois_curve is None:
            raise ValueError("OIS curve must be built before applying funding spread")
        
        spread_points = [FundingSpreadPoint(tenor, bps) for tenor, bps in spreads]
        self.bootstrap.build_funding_curve_from_ois(self.bootstrap.ois_curve, spread_points)
        return self
    
    def with_flat_spread(self, spread_bps: float) -> 'FundingCurveBuilder':
        """
        Apply flat funding spread to OIS curve.
        
        Args:
            spread_bps: Spread in basis points
            
        Returns:
            Self for method chaining
        """
        if self.bootstrap.ois_curve is None:
            raise ValueError("OIS curve must be built before applying funding spread")
        
        self.bootstrap.build_funding_curve_flat_spread(self.bootstrap.ois_curve, spread_bps)
        return self
    
    def with_forward_curve_bootstrap(
        self,
        ois_quotes: List[Tuple[str, float]] = None
    ) -> 'FundingCurveBuilder':
        """
        Bootstrap forward curve using funding curve for discounting.
        
        This creates a forward curve where PV=0 is solved using the funding curve
        for discounting, resulting in funding-adjusted forward rates.
        
        Args:
            ois_quotes: Optional OIS quotes. If None, uses the quotes from OIS curve build.
            
        Returns:
            Self for method chaining
        """
        if self.bootstrap.funding_curve is None:
            raise ValueError("Funding curve must be built before forward curve bootstrap")
        
        if ois_quotes is None:
            ois_quotes = self._ois_quotes
        
        quotes = [OISQuote(tenor, rate) for tenor, rate in ois_quotes]
        self.bootstrap.bootstrap_forward_curve_with_funding_discount(
            quotes, self.bootstrap.funding_curve
        )
        return self
    
    def get_ois_curve(self) -> ql.YieldTermStructureHandle:
        """Get the OIS curve."""
        return self.bootstrap.ois_curve
    
    def get_funding_curve(self) -> ql.YieldTermStructureHandle:
        """Get the funding curve."""
        return self.bootstrap.funding_curve
    
    def get_forward_curve(self) -> ql.YieldTermStructureHandle:
        """Get the funding-adjusted forward curve."""
        return self.bootstrap.forward_curve
    
    def build(self) -> Dict[str, ql.YieldTermStructureHandle]:
        """
        Build and return all curves.
        
        Returns:
            Dictionary with 'ois', 'funding', and 'forward' curves
        """
        return {
            'ois': self.bootstrap.ois_curve,
            'funding': self.bootstrap.funding_curve,
            'forward': self.bootstrap.forward_curve
        }


def create_sample_market_data() -> Dict:
    """
    Create sample market data for testing.
    
    Returns:
        Dictionary containing sample OIS quotes and funding spreads
    """
    # Sample SOFR OIS quotes
    ois_quotes = [
        ("1M", 0.0535),
        ("3M", 0.0530),
        ("6M", 0.0520),
        ("1Y", 0.0500),
        ("2Y", 0.0465),
        ("3Y", 0.0445),
        ("5Y", 0.0430),
        ("7Y", 0.0425),
        ("10Y", 0.0420),
        ("15Y", 0.0418),
        ("20Y", 0.0415),
        ("30Y", 0.0410),
    ]
    
    # Sample term structure of funding spreads (bank-specific)
    funding_spreads = [
        ("1Y", 5.0),    # 5 bps for 1-year funding
        ("2Y", 8.0),    # 8 bps for 2-year funding
        ("3Y", 10.0),   # 10 bps for 3-year funding
        ("5Y", 15.0),   # 15 bps for 5-year funding
        ("7Y", 18.0),   # 18 bps for 7-year funding
        ("10Y", 20.0),  # 20 bps for 10-year funding
        ("15Y", 22.0),  # 22 bps for 15-year funding
        ("20Y", 25.0),  # 25 bps for 20-year funding
        ("30Y", 30.0),  # 30 bps for 30-year funding
    ]
    
    return {
        'ois_quotes': ois_quotes,
        'funding_spreads': funding_spreads
    }
