"""
Funding Spread Adjusted Forward Curve Bootstrap Module

This module implements a "Dirty Curve" approach for bootstrapping interest rate curves
with funding spread adjustments using Python QuantLib.

Key Features:
1. OIS Curve Bootstrap: Standard SOFR OIS curve construction
2. Funding Spread Term Structure: Time-varying funding spreads
3. Funding Curve Construction: OIS curve + funding spread
4. IRS Bootstrap with Funding Curve: Forward rates implied by funding-adjusted discounting
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
class FundingSpreadPoint:
    """Represents a single funding spread data point."""
    tenor: str  # e.g., "1Y", "5Y", "10Y"
    spread_bps: float  # spread in basis points


@dataclass
class OISQuote:
    """Represents an OIS swap quote."""
    tenor: str
    rate: float  # quoted rate in decimal (e.g., 0.05 for 5%)


@dataclass
class IRSQuote:
    """Represents an IRS quote."""
    tenor: str
    rate: float  # quoted rate in decimal


class FundingCurveBootstrap:
    """
    Bootstraps interest rate curves with funding spread adjustments.
    
    This class implements the "Dirty Curve" approach:
    1. Build standard OIS curve from SOFR OIS quotes
    2. Apply term structure of funding spreads
    3. Create funding curve = OIS curve + funding spread
    4. Bootstrap IRS using funding curve for discounting
    """
    
    def __init__(
        self,
        valuation_date: ql.Date,
        calendar: ql.Calendar = ql.UnitedStates(ql.UnitedStates.FederalReserve),
        day_count: ql.DayCounter = ql.Actual360(),
        settlement_days: int = 2
    ):
        """
        Initialize the FundingCurveBootstrap.
        
        Args:
            valuation_date: The valuation/pricing date
            calendar: Calendar for business day adjustments
            day_count: Day count convention
            settlement_days: Number of settlement days
        """
        self.valuation_date = valuation_date
        self.calendar = calendar
        self.day_count = day_count
        self.settlement_days = settlement_days
        
        # Set the global evaluation date
        ql.Settings.instance().evaluationDate = valuation_date
        
        # Initialize curve handles
        self._ois_curve: Optional[ql.YieldTermStructureHandle] = None
        self._funding_curve: Optional[ql.YieldTermStructureHandle] = None
        self._forward_curve: Optional[ql.YieldTermStructureHandle] = None
        
        # Store quotes and spreads
        self._ois_quotes: List[OISQuote] = []
        self._funding_spreads: List[FundingSpreadPoint] = []
        self._irs_quotes: List[IRSQuote] = []
        
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
    
    def _create_sofr_index(self, curve_handle: ql.YieldTermStructureHandle) -> ql.OvernightIndex:
        """Create SOFR overnight index."""
        return ql.Sofr(curve_handle)
    
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
        self._ois_quotes = ois_quotes
        
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
    
    def build_funding_curve(
        self,
        ois_curve_handle: ql.YieldTermStructureHandle,
        funding_spreads: List[FundingSpreadPoint],
        spread_interpolation: CurveInterpolation = CurveInterpolation.LINEAR
    ) -> ql.YieldTermStructureHandle:
        """
        Build funding curve by adding funding spreads to OIS curve.
        
        The funding curve represents the bank's actual cost of funding,
        which is higher than the risk-free OIS rate by the funding spread.
        
        Discount Factor (Funding) = Discount Factor (OIS) * exp(-spread * t)
        
        This is equivalent to: r_funding = r_ois + spread
        
        Args:
            ois_curve_handle: Handle to the base OIS curve
            funding_spreads: List of funding spread data points
            spread_interpolation: Interpolation method for spread term structure
            
        Returns:
            YieldTermStructureHandle for the funding curve
        """
        self._funding_spreads = funding_spreads
        
        # Convert spreads from basis points to decimal
        dates = [self.valuation_date]
        spreads = [0.0]  # Zero spread at valuation date
        
        for spread_point in funding_spreads:
            period = self._parse_tenor(spread_point.tenor)
            date = self.calendar.advance(self.valuation_date, period)
            spread = spread_point.spread_bps / 10000.0  # Convert bps to decimal
            
            dates.append(date)
            spreads.append(spread)
        
        # Create spread curve as a zero spread quote
        # Using ZeroSpreadedTermStructure to add constant or interpolated spread
        
        # For term structure of spreads, we create a spread curve first
        spread_curve = ql.ZeroCurve(
            dates,
            spreads,
            self.day_count,
            self.calendar
        )
        spread_curve.enableExtrapolation()
        spread_handle = ql.YieldTermStructureHandle(spread_curve)
        
        # Create funding curve by adding spread to OIS curve
        # We use a custom approach: extract OIS zero rates and add spreads
        funding_dates = []
        funding_rates = []
        
        for i, (date, spread) in enumerate(zip(dates, spreads)):
            if i == 0:
                # For valuation date, use a small offset
                funding_dates.append(date)
                # Get OIS zero rate at valuation date (use 1 day forward)
                one_day = self.calendar.advance(date, ql.Period(1, ql.Days))
                ois_rate = ois_curve_handle.zeroRate(
                    one_day, self.day_count, ql.Continuous
                ).rate()
                funding_rates.append(ois_rate + spread)
            else:
                funding_dates.append(date)
                ois_rate = ois_curve_handle.zeroRate(
                    date, self.day_count, ql.Continuous
                ).rate()
                funding_rates.append(ois_rate + spread)
        
        # Add more points for smoother interpolation
        max_date = max(dates)
        current_date = self.valuation_date
        
        while current_date < max_date:
            current_date = self.calendar.advance(current_date, ql.Period(1, ql.Months))
            if current_date not in funding_dates and current_date < max_date:
                ois_rate = ois_curve_handle.zeroRate(
                    current_date, self.day_count, ql.Continuous
                ).rate()
                # Interpolate spread for this date
                spread = spread_handle.zeroRate(
                    current_date, self.day_count, ql.Continuous
                ).rate()
                
                # Insert in sorted order
                insert_idx = 0
                for idx, d in enumerate(funding_dates):
                    if d > current_date:
                        insert_idx = idx
                        break
                    insert_idx = idx + 1
                
                funding_dates.insert(insert_idx, current_date)
                funding_rates.insert(insert_idx, ois_rate + spread)
        
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
    
    def build_funding_curve_simple(
        self,
        ois_curve_handle: ql.YieldTermStructureHandle,
        flat_spread_bps: float
    ) -> ql.YieldTermStructureHandle:
        """
        Build funding curve with a flat (constant) spread over OIS curve.
        
        This is a simplified version that applies a constant funding spread
        across all maturities.
        
        Args:
            ois_curve_handle: Handle to the base OIS curve
            flat_spread_bps: Constant funding spread in basis points
            
        Returns:
            YieldTermStructureHandle for the funding curve
        """
        spread = flat_spread_bps / 10000.0  # Convert to decimal
        spread_quote = ql.QuoteHandle(ql.SimpleQuote(spread))
        
        # ZeroSpreadedTermStructure adds a constant spread to the base curve
        # Signature: (handle, quote, compounding, frequency, day_counter)
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
    
    def bootstrap_irs_with_funding_curve(
        self,
        irs_quotes: List[IRSQuote],
        discount_curve: ql.YieldTermStructureHandle,
        fixed_leg_frequency: int = None,
        float_leg_frequency: int = None,
        fixed_leg_day_count: ql.DayCounter = None,
        float_leg_day_count: ql.DayCounter = None,
        interpolation: CurveInterpolation = CurveInterpolation.LOG_LINEAR
    ) -> ql.YieldTermStructureHandle:
        """
        Bootstrap IRS forward curve using funding curve for discounting.
        
        This method builds a forward curve where the swap PV=0 condition
        is solved using the funding curve for discounting. The resulting
        forward rates reflect the funding cost adjustment.
        
        Args:
            irs_quotes: List of IRS quotes
            discount_curve: Funding curve to use for discounting
            fixed_leg_frequency: Payment frequency of the fixed leg
            float_leg_frequency: Payment frequency of the floating leg
            fixed_leg_day_count: Day count for fixed leg
            float_leg_day_count: Day count for floating leg
            interpolation: Interpolation method for the forward curve
            
        Returns:
            YieldTermStructureHandle for the forward curve
        """
        # Set default values
        if fixed_leg_frequency is None:
            fixed_leg_frequency = ql.Annual
        if float_leg_frequency is None:
            float_leg_frequency = ql.Quarterly
        if fixed_leg_day_count is None:
            fixed_leg_day_count = ql.Thirty360(ql.Thirty360.BondBasis)
        if float_leg_day_count is None:
            float_leg_day_count = ql.Actual360()
        
        self._irs_quotes = irs_quotes
        
        # Create rate helpers for IRS bootstrapping
        # Use the funding curve as the discount curve
        rate_helpers = []
        
        # Create a SOFR index for the floating leg
        # The forward curve will be built and linked to this index
        sofr_index = ql.Sofr()
        
        for quote in irs_quotes:
            period = self._parse_tenor(quote.tenor)
            rate = ql.QuoteHandle(ql.SimpleQuote(quote.rate))
            
            # Create IRS rate helper with explicit discount curve
            helper = ql.SwapRateHelper(
                rate,
                period,
                self.calendar,
                fixed_leg_frequency,
                ql.ModifiedFollowing,  # Business day convention
                fixed_leg_day_count,
                sofr_index,
                ql.QuoteHandle(),  # No spread on float leg
                ql.Period(0, ql.Days),  # No payment lag
                discount_curve  # Use funding curve for discounting
            )
            rate_helpers.append(helper)
        
        # Build the forward curve
        if interpolation == CurveInterpolation.LOG_LINEAR:
            forward_curve = ql.PiecewiseLogLinearDiscount(
                self.valuation_date,
                rate_helpers,
                float_leg_day_count
            )
        elif interpolation == CurveInterpolation.LINEAR:
            forward_curve = ql.PiecewiseLinearZero(
                self.valuation_date,
                rate_helpers,
                float_leg_day_count
            )
        else:  # CUBIC
            forward_curve = ql.PiecewiseCubicZero(
                self.valuation_date,
                rate_helpers,
                float_leg_day_count
            )
        
        forward_curve.enableExtrapolation()
        
        self._forward_curve = ql.YieldTermStructureHandle(forward_curve)
        return self._forward_curve
    
    def price_swap(
        self,
        notional: float,
        tenor: str,
        fixed_rate: float,
        is_payer: bool,
        forward_curve: ql.YieldTermStructureHandle,
        discount_curve: ql.YieldTermStructureHandle,
        fixed_leg_frequency: int = None,
        float_leg_frequency: int = None,
        fixed_leg_day_count: ql.DayCounter = None,
        float_leg_day_count: ql.DayCounter = None
    ) -> Dict[str, float]:
        """
        Price an interest rate swap using specified forward and discount curves.
        
        Args:
            notional: Swap notional amount
            tenor: Swap tenor (e.g., "5Y")
            fixed_rate: Fixed leg rate (decimal)
            is_payer: True if paying fixed, False if receiving fixed
            forward_curve: Curve for projecting floating rates
            discount_curve: Curve for discounting cash flows
            fixed_leg_frequency: Payment frequency of fixed leg
            float_leg_frequency: Payment frequency of floating leg
            fixed_leg_day_count: Day count for fixed leg
            float_leg_day_count: Day count for floating leg
            
        Returns:
            Dictionary containing NPV and leg values
        """
        # Set default values
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
        
        # Create SOFR index with forward curve
        sofr_index = ql.Sofr(forward_curve)
        
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
        
        # Create pricing engine with funding curve for discounting
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)
        
        return {
            'npv': swap.NPV(),
            'fixed_leg_npv': swap.fixedLegNPV(),
            'floating_leg_npv': swap.floatingLegNPV(),
            'fair_rate': swap.fairRate(),
            'fair_spread': swap.fairSpread()
        }
    
    def get_forward_rates(
        self,
        forward_curve: ql.YieldTermStructureHandle,
        tenors: List[str],
        forward_tenor: str = "3M"
    ) -> Dict[str, float]:
        """
        Extract forward rates from a curve at specified tenors.
        
        Args:
            forward_curve: The forward curve
            tenors: List of tenors to extract rates for
            forward_tenor: The forward period (e.g., "3M" for 3-month forward rates)
            
        Returns:
            Dictionary mapping tenor strings to forward rates
        """
        forward_period = self._parse_tenor(forward_tenor)
        forward_rates = {}
        
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = self.calendar.advance(self.valuation_date, period)
            end_date = self.calendar.advance(date, forward_period)
            
            rate = forward_curve.forwardRate(
                date,
                end_date,
                self.day_count,
                ql.Simple
            ).rate()
            
            forward_rates[tenor] = rate
            
        return forward_rates
    
    def get_zero_rates(
        self,
        curve: ql.YieldTermStructureHandle,
        tenors: List[str]
    ) -> Dict[str, float]:
        """
        Extract zero rates from a curve at specified tenors.
        
        Args:
            curve: The yield curve
            tenors: List of tenors to extract rates for
            
        Returns:
            Dictionary mapping tenor strings to zero rates
        """
        zero_rates = {}
        
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = self.calendar.advance(self.valuation_date, period)
            
            rate = curve.zeroRate(
                date,
                self.day_count,
                ql.Continuous
            ).rate()
            
            zero_rates[tenor] = rate
            
        return zero_rates
    
    def get_discount_factors(
        self,
        curve: ql.YieldTermStructureHandle,
        tenors: List[str]
    ) -> Dict[str, float]:
        """
        Extract discount factors from a curve at specified tenors.
        
        Args:
            curve: The yield curve
            tenors: List of tenors to extract discount factors for
            
        Returns:
            Dictionary mapping tenor strings to discount factors
        """
        discount_factors = {}
        
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = self.calendar.advance(self.valuation_date, period)
            
            df = curve.discount(date)
            discount_factors[tenor] = df
            
        return discount_factors
    
    def compare_curves(
        self,
        curve1: ql.YieldTermStructureHandle,
        curve2: ql.YieldTermStructureHandle,
        tenors: List[str],
        curve1_name: str = "Curve 1",
        curve2_name: str = "Curve 2"
    ) -> Dict:
        """
        Compare two curves at specified tenors.
        
        Args:
            curve1: First curve
            curve2: Second curve
            tenors: List of tenors for comparison
            curve1_name: Label for first curve
            curve2_name: Label for second curve
            
        Returns:
            Dictionary with comparison data
        """
        comparison = {
            'tenors': tenors,
            curve1_name: {
                'zero_rates': self.get_zero_rates(curve1, tenors),
                'discount_factors': self.get_discount_factors(curve1, tenors)
            },
            curve2_name: {
                'zero_rates': self.get_zero_rates(curve2, tenors),
                'discount_factors': self.get_discount_factors(curve2, tenors)
            },
            'differences': {}
        }
        
        # Calculate differences
        for tenor in tenors:
            zr1 = comparison[curve1_name]['zero_rates'][tenor]
            zr2 = comparison[curve2_name]['zero_rates'][tenor]
            comparison['differences'][tenor] = {
                'zero_rate_diff_bps': (zr2 - zr1) * 10000,  # in basis points
                'discount_factor_ratio': (
                    comparison[curve2_name]['discount_factors'][tenor] /
                    comparison[curve1_name]['discount_factors'][tenor]
                )
            }
        
        return comparison


class FundingCurveBuilder:
    """
    High-level builder class for constructing funding-adjusted curves.
    
    This class provides a convenient fluent interface for building
    curves with funding spread adjustments.
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
        
        self.bootstrap = FundingCurveBootstrap(valuation_date)
        self._ois_curve = None
        self._funding_curve = None
        self._forward_curve = None
        
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
        ois_quotes = [OISQuote(tenor, rate) for tenor, rate in quotes]
        self._ois_curve = self.bootstrap.build_ois_curve(ois_quotes, interpolation)
        return self
    
    def with_flat_funding_spread(self, spread_bps: float) -> 'FundingCurveBuilder':
        """
        Apply flat funding spread to OIS curve.
        
        Args:
            spread_bps: Spread in basis points
            
        Returns:
            Self for method chaining
        """
        if self._ois_curve is None:
            raise ValueError("OIS curve must be built before applying funding spread")
        
        self._funding_curve = self.bootstrap.build_funding_curve_simple(
            self._ois_curve, spread_bps
        )
        return self
    
    def with_term_funding_spreads(
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
        if self._ois_curve is None:
            raise ValueError("OIS curve must be built before applying funding spread")
        
        spread_points = [FundingSpreadPoint(tenor, bps) for tenor, bps in spreads]
        self._funding_curve = self.bootstrap.build_funding_curve(
            self._ois_curve, spread_points
        )
        return self
    
    def with_irs_bootstrap(
        self,
        quotes: List[Tuple[str, float]],
        interpolation: CurveInterpolation = CurveInterpolation.LOG_LINEAR
    ) -> 'FundingCurveBuilder':
        """
        Bootstrap IRS forward curve using funding curve for discounting.
        
        Args:
            quotes: List of (tenor, rate) tuples
            interpolation: Curve interpolation method
            
        Returns:
            Self for method chaining
        """
        if self._funding_curve is None:
            raise ValueError("Funding curve must be built before IRS bootstrap")
        
        irs_quotes = [IRSQuote(tenor, rate) for tenor, rate in quotes]
        self._forward_curve = self.bootstrap.bootstrap_irs_with_funding_curve(
            irs_quotes, self._funding_curve, interpolation=interpolation
        )
        return self
    
    def get_ois_curve(self) -> ql.YieldTermStructureHandle:
        """Get the OIS curve."""
        return self._ois_curve
    
    def get_funding_curve(self) -> ql.YieldTermStructureHandle:
        """Get the funding curve."""
        return self._funding_curve
    
    def get_forward_curve(self) -> ql.YieldTermStructureHandle:
        """Get the forward curve."""
        return self._forward_curve
    
    def build(self) -> Dict[str, ql.YieldTermStructureHandle]:
        """
        Build and return all curves.
        
        Returns:
            Dictionary with 'ois', 'funding', and 'forward' curves
        """
        return {
            'ois': self._ois_curve,
            'funding': self._funding_curve,
            'forward': self._forward_curve
        }


def create_sample_market_data() -> Dict:
    """
    Create sample market data for testing.
    
    Returns:
        Dictionary containing sample OIS quotes, IRS quotes, and funding spreads
    """
    # Sample SOFR OIS quotes (as of a hypothetical date)
    ois_quotes = [
        ("1W", 0.0530),
        ("2W", 0.0532),
        ("1M", 0.0535),
        ("2M", 0.0533),
        ("3M", 0.0530),
        ("6M", 0.0520),
        ("9M", 0.0510),
        ("1Y", 0.0500),
        ("18M", 0.0480),
        ("2Y", 0.0465),
        ("3Y", 0.0445),
        ("4Y", 0.0435),
        ("5Y", 0.0430),
        ("7Y", 0.0425),
        ("10Y", 0.0420),
        ("15Y", 0.0418),
        ("20Y", 0.0415),
        ("30Y", 0.0410),
    ]
    
    # Sample IRS quotes (SOFR swaps)
    irs_quotes = [
        ("2Y", 0.0468),
        ("3Y", 0.0448),
        ("4Y", 0.0438),
        ("5Y", 0.0433),
        ("7Y", 0.0428),
        ("10Y", 0.0423),
        ("15Y", 0.0420),
        ("20Y", 0.0418),
        ("30Y", 0.0413),
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
        'irs_quotes': irs_quotes,
        'funding_spreads': funding_spreads
    }

