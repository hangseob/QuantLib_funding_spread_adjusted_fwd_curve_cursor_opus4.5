"""
Cross-Currency Swap Bootstrap for USD Discount Curve

Given:
- KRW Discount Curve (already built)
- USD Forward Curve (SOFR forward curve, already built)
- KRW Fixed Rate vs USD SOFR Floating swap quotes by tenor

Bootstrap:
- USD Discount Curve

Principle:
    PV(KRW Fixed Leg) = PV(USD Floating Leg)
    
    KRW Fixed Leg: discounted with KRW discount curve
    USD Floating Leg: projected with USD forward curve, discounted with USD discount curve
    
    At each tenor, solve for USD discount factor such that PV_KRW = PV_USD
"""

import QuantLib as ql
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class CCSQuote:
    """Cross-Currency Swap quote: KRW Fixed vs USD SOFR Float"""
    tenor: str
    krw_fixed_rate: float  # KRW fixed rate in decimal (e.g., 0.03 for 3%)
    notional_krw: float = 1_000_000_000  # KRW notional (1 billion KRW)
    notional_usd: float = None  # USD notional (calculated from spot rate)


class CCSUSDDiscountBootstrap:
    """
    Bootstrap USD Discount Curve from Cross-Currency Swap quotes.
    
    The approach:
    1. KRW Fixed Leg PV is calculated using KRW discount curve
    2. USD Floating Leg cash flows are projected using USD forward curve
    3. USD discount factors are solved such that PV(KRW) = PV(USD)
    """
    
    def __init__(
        self,
        valuation_date: ql.Date,
        spot_fx_rate: float,  # USD/KRW spot rate (e.g., 1300 means 1 USD = 1300 KRW)
        krw_calendar: ql.Calendar = None,
        usd_calendar: ql.Calendar = None,
        krw_day_count: ql.DayCounter = None,
        usd_day_count: ql.DayCounter = None,
        settlement_days: int = 2
    ):
        """
        Initialize the CCS USD Discount Bootstrap.
        
        Args:
            valuation_date: Valuation date
            spot_fx_rate: USD/KRW spot rate (1 USD = X KRW)
            krw_calendar: Korean calendar
            usd_calendar: US calendar
            krw_day_count: Day count for KRW leg
            usd_day_count: Day count for USD leg
            settlement_days: Settlement days
        """
        self.valuation_date = valuation_date
        self.spot_fx_rate = spot_fx_rate
        self.krw_calendar = krw_calendar if krw_calendar else ql.SouthKorea()
        self.usd_calendar = usd_calendar if usd_calendar else ql.UnitedStates(ql.UnitedStates.FederalReserve)
        self.krw_day_count = krw_day_count if krw_day_count else ql.Actual365Fixed()
        self.usd_day_count = usd_day_count if usd_day_count else ql.Actual360()
        self.settlement_days = settlement_days
        
        # Set global evaluation date
        ql.Settings.instance().evaluationDate = valuation_date
        
        # Curves
        self._krw_discount_curve: Optional[ql.YieldTermStructureHandle] = None
        self._usd_forward_curve: Optional[ql.YieldTermStructureHandle] = None
        self._usd_discount_curve: Optional[ql.YieldTermStructureHandle] = None
        
    def _parse_tenor(self, tenor: str) -> ql.Period:
        """Convert tenor string to QuantLib Period."""
        tenor = tenor.upper().strip()
        
        unit_map = {
            'D': ql.Days,
            'W': ql.Weeks,
            'M': ql.Months,
            'Y': ql.Years
        }
        
        number = int(tenor[:-1])
        unit = tenor[-1]
        
        if unit not in unit_map:
            raise ValueError(f"Unknown tenor unit: {unit}")
            
        return ql.Period(number, unit_map[unit])
    
    def set_krw_discount_curve(
        self,
        curve: ql.YieldTermStructureHandle
    ) -> 'CCSUSDDiscountBootstrap':
        """Set the KRW discount curve."""
        self._krw_discount_curve = curve
        return self
    
    def set_usd_forward_curve(
        self,
        curve: ql.YieldTermStructureHandle
    ) -> 'CCSUSDDiscountBootstrap':
        """Set the USD forward curve (SOFR forward curve)."""
        self._usd_forward_curve = curve
        return self
    
    def build_krw_discount_curve(
        self,
        zero_rates: List[Tuple[str, float]]
    ) -> ql.YieldTermStructureHandle:
        """
        Build KRW discount curve from zero rates.
        
        Args:
            zero_rates: List of (tenor, rate) tuples
            
        Returns:
            YieldTermStructureHandle for KRW discount curve
        """
        dates = [self.valuation_date]
        rates = [zero_rates[0][1]]  # Use first rate for valuation date
        
        for tenor, rate in zero_rates:
            period = self._parse_tenor(tenor)
            date = self.krw_calendar.advance(self.valuation_date, period)
            dates.append(date)
            rates.append(rate)
        
        curve = ql.ZeroCurve(dates, rates, self.krw_day_count, self.krw_calendar)
        curve.enableExtrapolation()
        
        self._krw_discount_curve = ql.YieldTermStructureHandle(curve)
        return self._krw_discount_curve
    
    def build_usd_forward_curve(
        self,
        zero_rates: List[Tuple[str, float]]
    ) -> ql.YieldTermStructureHandle:
        """
        Build USD forward curve from zero rates.
        
        Args:
            zero_rates: List of (tenor, rate) tuples
            
        Returns:
            YieldTermStructureHandle for USD forward curve
        """
        dates = [self.valuation_date]
        rates = [zero_rates[0][1]]
        
        for tenor, rate in zero_rates:
            period = self._parse_tenor(tenor)
            date = self.usd_calendar.advance(self.valuation_date, period)
            dates.append(date)
            rates.append(rate)
        
        curve = ql.ZeroCurve(dates, rates, self.usd_day_count, self.usd_calendar)
        curve.enableExtrapolation()
        
        self._usd_forward_curve = ql.YieldTermStructureHandle(curve)
        return self._usd_forward_curve
    
    def _calculate_krw_fixed_leg_pv(
        self,
        notional_krw: float,
        fixed_rate: float,
        start_date: ql.Date,
        end_date: ql.Date,
        payment_frequency: int = None
    ) -> float:
        """
        Calculate PV of KRW fixed leg.
        
        Args:
            notional_krw: KRW notional
            fixed_rate: KRW fixed rate
            start_date: Start date
            end_date: End date
            payment_frequency: Payment frequency
            
        Returns:
            PV of KRW fixed leg in KRW
        """
        if payment_frequency is None:
            payment_frequency = ql.Quarterly
        
        schedule = ql.Schedule(
            start_date,
            end_date,
            ql.Period(payment_frequency),
            self.krw_calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )
        
        pv = 0.0
        for i in range(1, len(schedule)):
            accrual_start = schedule[i-1]
            accrual_end = schedule[i]
            payment_date = accrual_end
            
            # Year fraction
            yf = self.krw_day_count.yearFraction(accrual_start, accrual_end)
            
            # Discount factor from KRW curve
            df = self._krw_discount_curve.discount(payment_date)
            
            # Cash flow
            cashflow = notional_krw * fixed_rate * yf
            pv += cashflow * df
        
        # Add notional exchange at maturity (for cross-currency swap)
        pv += notional_krw * self._krw_discount_curve.discount(end_date)
        
        return pv
    
    def _calculate_usd_floating_leg_pv_without_discount(
        self,
        notional_usd: float,
        start_date: ql.Date,
        end_date: ql.Date,
        payment_frequency: int = None
    ) -> List[Tuple[ql.Date, float]]:
        """
        Calculate USD floating leg cash flows (without discounting).
        
        Returns list of (payment_date, cash_flow) tuples.
        """
        if payment_frequency is None:
            payment_frequency = ql.Quarterly
        
        schedule = ql.Schedule(
            start_date,
            end_date,
            ql.Period(payment_frequency),
            self.usd_calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )
        
        cash_flows = []
        
        for i in range(1, len(schedule)):
            accrual_start = schedule[i-1]
            accrual_end = schedule[i]
            payment_date = accrual_end
            
            # Year fraction
            yf = self.usd_day_count.yearFraction(accrual_start, accrual_end)
            
            # Forward rate from USD forward curve
            forward_rate = self._usd_forward_curve.forwardRate(
                accrual_start, accrual_end, self.usd_day_count, ql.Simple
            ).rate()
            
            # Cash flow
            cashflow = notional_usd * forward_rate * yf
            cash_flows.append((payment_date, cashflow))
        
        # Add notional exchange at maturity
        cash_flows.append((end_date, notional_usd))
        
        return cash_flows
    
    def bootstrap_usd_discount_curve(
        self,
        ccs_quotes: List[CCSQuote],
        krw_payment_frequency: int = None,
        usd_payment_frequency: int = None
    ) -> ql.YieldTermStructureHandle:
        """
        Bootstrap USD discount curve from CCS quotes.
        
        The key equation at each tenor:
            PV(KRW Fixed Leg) / Spot_FX = PV(USD Floating Leg)
        
        We solve for USD discount factors iteratively.
        
        Args:
            ccs_quotes: List of CCS quotes (KRW Fixed vs USD Float)
            krw_payment_frequency: KRW leg payment frequency
            usd_payment_frequency: USD leg payment frequency
            
        Returns:
            YieldTermStructureHandle for USD discount curve
        """
        if self._krw_discount_curve is None:
            raise ValueError("KRW discount curve must be set first")
        if self._usd_forward_curve is None:
            raise ValueError("USD forward curve must be set first")
        
        if krw_payment_frequency is None:
            krw_payment_frequency = ql.Quarterly
        if usd_payment_frequency is None:
            usd_payment_frequency = ql.Quarterly
        
        # Sort quotes by tenor
        sorted_quotes = sorted(ccs_quotes, key=lambda q: self._parse_tenor(q.tenor).length())
        
        # Settlement date
        start_date = self.usd_calendar.advance(
            self.valuation_date, 
            ql.Period(self.settlement_days, ql.Days)
        )
        
        # Bootstrap USD discount factors
        usd_discount_dates = [self.valuation_date]
        usd_discount_factors = [1.0]
        
        for quote in sorted_quotes:
            period = self._parse_tenor(quote.tenor)
            end_date = self.usd_calendar.advance(start_date, period)
            
            # Calculate notional in USD
            notional_krw = quote.notional_krw
            notional_usd = quote.notional_usd if quote.notional_usd else notional_krw / self.spot_fx_rate
            
            # Calculate KRW fixed leg PV (in KRW)
            krw_pv = self._calculate_krw_fixed_leg_pv(
                notional_krw, quote.krw_fixed_rate, start_date, end_date, krw_payment_frequency
            )
            
            # Convert KRW PV to USD
            target_usd_pv = krw_pv / self.spot_fx_rate
            
            # Get USD floating leg cash flows
            usd_cash_flows = self._calculate_usd_floating_leg_pv_without_discount(
                notional_usd, start_date, end_date, usd_payment_frequency
            )
            
            # Build temporary discount curve for interpolation
            if len(usd_discount_dates) > 1:
                temp_curve = ql.DiscountCurve(
                    usd_discount_dates, 
                    usd_discount_factors, 
                    self.usd_day_count, 
                    self.usd_calendar
                )
                temp_curve.enableExtrapolation()
            else:
                temp_curve = None
            
            # Solve for the discount factor at end_date
            # PV = sum(cf_i * df_i) where df_i for intermediate dates are interpolated
            
            # Separate cash flows: those we can discount with known DFs vs the final one
            known_pv = 0.0
            final_cf = 0.0
            final_date = None
            
            for cf_date, cf_amount in usd_cash_flows:
                if cf_date <= usd_discount_dates[-1] if len(usd_discount_dates) > 1 else False:
                    # Use existing discount factor
                    df = temp_curve.discount(cf_date)
                    known_pv += cf_amount * df
                elif cf_date == end_date:
                    final_cf += cf_amount
                    final_date = cf_date
                else:
                    # Intermediate dates - we need to interpolate
                    # For simplicity, we'll solve iteratively
                    final_cf += cf_amount
                    final_date = cf_date
            
            # Solve: target_usd_pv = known_pv + final_cf * df_end
            # df_end = (target_usd_pv - known_pv) / final_cf
            
            # For more accurate bootstrapping, we iterate
            df_end = self._solve_discount_factor(
                target_usd_pv, 
                usd_cash_flows, 
                usd_discount_dates, 
                usd_discount_factors,
                end_date
            )
            
            usd_discount_dates.append(end_date)
            usd_discount_factors.append(df_end)
        
        # Build final USD discount curve
        usd_discount_curve = ql.DiscountCurve(
            usd_discount_dates,
            usd_discount_factors,
            self.usd_day_count,
            self.usd_calendar
        )
        usd_discount_curve.enableExtrapolation()
        
        self._usd_discount_curve = ql.YieldTermStructureHandle(usd_discount_curve)
        return self._usd_discount_curve
    
    def _solve_discount_factor(
        self,
        target_pv: float,
        cash_flows: List[Tuple[ql.Date, float]],
        known_dates: List[ql.Date],
        known_dfs: List[float],
        target_date: ql.Date,
        max_iterations: int = 100,
        tolerance: float = 1e-10
    ) -> float:
        """
        Solve for discount factor at target_date such that PV equals target_pv.
        
        Uses Newton-Raphson iteration.
        """
        # Initial guess based on log-linear interpolation
        if len(known_dates) > 1:
            last_date = known_dates[-1]
            last_df = known_dfs[-1]
            
            t_last = self.usd_day_count.yearFraction(self.valuation_date, last_date)
            t_target = self.usd_day_count.yearFraction(self.valuation_date, target_date)
            
            if t_last > 0:
                implied_rate = -np.log(last_df) / t_last
                df_guess = np.exp(-implied_rate * t_target)
            else:
                df_guess = 0.99
        else:
            t_target = self.usd_day_count.yearFraction(self.valuation_date, target_date)
            df_guess = np.exp(-0.04 * t_target)  # Assume 4% rate
        
        df = df_guess
        
        for _ in range(max_iterations):
            # Calculate PV with current df guess
            pv = 0.0
            dpv_ddf = 0.0  # Derivative of PV with respect to df
            
            for cf_date, cf_amount in cash_flows:
                if cf_date <= target_date:
                    # Get discount factor for this date
                    cf_df = self._interpolate_df(
                        cf_date, known_dates + [target_date], known_dfs + [df]
                    )
                    pv += cf_amount * cf_df
                    
                    # Derivative contribution
                    if cf_date == target_date:
                        dpv_ddf += cf_amount
                    else:
                        # Interpolation derivative (approximate)
                        t_cf = self.usd_day_count.yearFraction(self.valuation_date, cf_date)
                        t_target = self.usd_day_count.yearFraction(self.valuation_date, target_date)
                        if len(known_dates) > 1:
                            t_last = self.usd_day_count.yearFraction(self.valuation_date, known_dates[-1])
                            if t_target > t_last and t_cf > t_last:
                                weight = (t_cf - t_last) / (t_target - t_last)
                                dpv_ddf += cf_amount * weight * cf_df / df
            
            # Newton-Raphson update
            error = pv - target_pv
            
            if abs(error) < tolerance:
                break
            
            if abs(dpv_ddf) > 1e-15:
                df = df - error / dpv_ddf
            else:
                # Fallback: simple bisection-like adjustment
                df = df * (target_pv / pv) if pv > 0 else df * 0.99
            
            # Keep df in reasonable bounds
            df = max(0.01, min(1.5, df))
        
        return df
    
    def _interpolate_df(
        self,
        target_date: ql.Date,
        dates: List[ql.Date],
        dfs: List[float]
    ) -> float:
        """Log-linear interpolation of discount factors."""
        if target_date <= dates[0]:
            return dfs[0]
        if target_date >= dates[-1]:
            return dfs[-1]
        
        # Find surrounding dates
        for i in range(len(dates) - 1):
            if dates[i] <= target_date <= dates[i + 1]:
                t0 = self.usd_day_count.yearFraction(self.valuation_date, dates[i])
                t1 = self.usd_day_count.yearFraction(self.valuation_date, dates[i + 1])
                t = self.usd_day_count.yearFraction(self.valuation_date, target_date)
                
                if t1 - t0 > 0:
                    # Log-linear interpolation
                    log_df0 = np.log(dfs[i]) if dfs[i] > 0 else -10
                    log_df1 = np.log(dfs[i + 1]) if dfs[i + 1] > 0 else -10
                    
                    weight = (t - t0) / (t1 - t0)
                    log_df = log_df0 + weight * (log_df1 - log_df0)
                    return np.exp(log_df)
                else:
                    return dfs[i]
        
        return dfs[-1]
    
    def get_zero_rates(
        self,
        curve: ql.YieldTermStructureHandle,
        tenors: List[str],
        calendar: ql.Calendar = None,
        day_count: ql.DayCounter = None
    ) -> Dict[str, float]:
        """Extract zero rates from a curve."""
        if calendar is None:
            calendar = self.usd_calendar
        if day_count is None:
            day_count = self.usd_day_count
            
        zero_rates = {}
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = calendar.advance(self.valuation_date, period)
            rate = curve.zeroRate(date, day_count, ql.Continuous).rate()
            zero_rates[tenor] = rate
        return zero_rates
    
    def get_discount_factors(
        self,
        curve: ql.YieldTermStructureHandle,
        tenors: List[str],
        calendar: ql.Calendar = None
    ) -> Dict[str, float]:
        """Extract discount factors from a curve."""
        if calendar is None:
            calendar = self.usd_calendar
            
        discount_factors = {}
        for tenor in tenors:
            period = self._parse_tenor(tenor)
            date = calendar.advance(self.valuation_date, period)
            df = curve.discount(date)
            discount_factors[tenor] = df
        return discount_factors
    
    def compare_curves(self, tenors: List[str]) -> Dict:
        """Compare USD forward curve and USD discount curve."""
        comparison = {
            'tenors': tenors,
            'usd_forward_curve': {
                'zero_rates': self.get_zero_rates(self._usd_forward_curve, tenors),
                'discount_factors': self.get_discount_factors(self._usd_forward_curve, tenors)
            },
            'usd_discount_curve': {
                'zero_rates': self.get_zero_rates(self._usd_discount_curve, tenors),
                'discount_factors': self.get_discount_factors(self._usd_discount_curve, tenors)
            }
        }
        
        # Calculate cross-currency basis
        comparison['basis_bps'] = {}
        for tenor in tenors:
            fwd_rate = comparison['usd_forward_curve']['zero_rates'][tenor]
            disc_rate = comparison['usd_discount_curve']['zero_rates'][tenor]
            comparison['basis_bps'][tenor] = (disc_rate - fwd_rate) * 10000
        
        return comparison
    
    @property
    def krw_discount_curve(self) -> ql.YieldTermStructureHandle:
        return self._krw_discount_curve
    
    @property
    def usd_forward_curve(self) -> ql.YieldTermStructureHandle:
        return self._usd_forward_curve
    
    @property
    def usd_discount_curve(self) -> ql.YieldTermStructureHandle:
        return self._usd_discount_curve


class CCSBootstrapBuilder:
    """Fluent builder for CCS-based USD discount curve bootstrap."""
    
    def __init__(
        self,
        valuation_date: ql.Date,
        spot_fx_rate: float
    ):
        """
        Initialize builder.
        
        Args:
            valuation_date: Valuation date
            spot_fx_rate: USD/KRW spot rate
        """
        self.bootstrap = CCSUSDDiscountBootstrap(valuation_date, spot_fx_rate)
        self._ccs_quotes = []
    
    def with_krw_discount_curve(
        self,
        zero_rates: List[Tuple[str, float]]
    ) -> 'CCSBootstrapBuilder':
        """Build and set KRW discount curve."""
        self.bootstrap.build_krw_discount_curve(zero_rates)
        return self
    
    def with_usd_forward_curve(
        self,
        zero_rates: List[Tuple[str, float]]
    ) -> 'CCSBootstrapBuilder':
        """Build and set USD forward curve."""
        self.bootstrap.build_usd_forward_curve(zero_rates)
        return self
    
    def with_ccs_quotes(
        self,
        quotes: List[Tuple[str, float]]
    ) -> 'CCSBootstrapBuilder':
        """
        Add CCS quotes.
        
        Args:
            quotes: List of (tenor, krw_fixed_rate) tuples
        """
        self._ccs_quotes = [CCSQuote(tenor, rate) for tenor, rate in quotes]
        return self
    
    def bootstrap_usd_discount(self) -> 'CCSBootstrapBuilder':
        """Bootstrap USD discount curve from CCS quotes."""
        self.bootstrap.bootstrap_usd_discount_curve(self._ccs_quotes)
        return self
    
    def build(self) -> Dict[str, ql.YieldTermStructureHandle]:
        """Return all curves."""
        return {
            'krw_discount': self.bootstrap.krw_discount_curve,
            'usd_forward': self.bootstrap.usd_forward_curve,
            'usd_discount': self.bootstrap.usd_discount_curve
        }

