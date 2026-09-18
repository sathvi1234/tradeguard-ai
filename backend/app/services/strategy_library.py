"""Structured options strategy definitions. Educational / simulation only — never auto-traded."""

from typing import List, Optional

from app.models.schemas import StrategyCategory, StrategyDefinition


STRATEGY_DEFINITIONS: List[StrategyDefinition] = [
    StrategyDefinition(
        name="Theta Iron Condor",
        key="theta_iron_condor",
        category=StrategyCategory.INCOME,
        market_conditions=["range-bound", "elevated IV that is expected to contract"],
        required_data=["option chain", "IV", "strikes", "expirations", "liquidity"],
        max_risk_characteristics="Defined risk equal to wing width minus net credit",
        typical_objective="Collect premium as underlying stays between short strikes",
        candidate_selection_rules=[
            "Prefer liquid underlyings with tight spreads",
            "Short strikes outside expected range; wings define max loss",
        ],
        invalidation_conditions=["strong directional break", "IV expansion against shorts", "earnings inside DTE if not intended"],
        required_market_fields=["underlying_quote", "option_chain", "option_quotes", "expiration", "strikes", "iv"],
    ),
    StrategyDefinition(
        name="Earnings Straddle",
        key="earnings_straddle",
        category=StrategyCategory.EARNINGS,
        market_conditions=["known binary event", "implied move vs expected realized move"],
        required_data=["earnings date", "option chain", "IV", "expected move"],
        max_risk_characteristics="Debit paid for long straddle; theoretically unlimited upside on large move",
        typical_objective="Capture a larger realized move than implied, or fade IV crush if structured as a short (not default)",
        candidate_selection_rules=["Require confirmed event date", "Compare implied move to historical earnings moves"],
        invalidation_conditions=["event date unknown", "illiquid chain", "IV already extreme without edge"],
        required_market_fields=["underlying_quote", "option_chain", "expiration", "iv", "event_data"],
    ),
    StrategyDefinition(
        name="Directional Vertical Spread",
        key="directional_vertical_spread",
        category=StrategyCategory.DEFINED_RISK,
        market_conditions=["directional thesis with defined risk preference"],
        required_data=["direction thesis", "option chain", "delta", "liquidity"],
        max_risk_characteristics="Defined: width minus credit (credit) or debit paid (debit)",
        typical_objective="Express bullish or bearish view with capped loss",
        candidate_selection_rules=["Align spread with StrategyBrain scenario", "Prefer liquid strikes"],
        invalidation_conditions=["thesis invalidated", "missing chain data", "spread too wide vs account limits"],
        required_market_fields=["underlying_quote", "option_chain", "option_quotes"],
    ),
    StrategyDefinition(
        name="The Wheel",
        key="the_wheel",
        category=StrategyCategory.INCOME,
        market_conditions=["bullish-to-neutral on a stock you would own", "adequate cash"],
        required_data=["cash/buying power", "underlying price", "put chain", "assignment risk"],
        max_risk_characteristics="Cash-secured put then covered call; stock ownership risk if assigned",
        typical_objective="Generate premium while potentially acquiring stock at a net discount",
        candidate_selection_rules=["Only on names acceptable to own", "Cash-secured; no naked short puts"],
        invalidation_conditions=["insufficient cash", "thesis no longer wants stock", "CRITICAL drawdown mode"],
        required_market_fields=["underlying_quote", "option_chain", "option_quotes"],
    ),
    StrategyDefinition(
        name="Calendar Spread",
        key="calendar_spread",
        category=StrategyCategory.VOLATILITY,
        market_conditions=["term-structure opportunity", "range-bound near-term"],
        required_data=["multi-expiration chain", "IV by expiry", "liquidity"],
        max_risk_characteristics="Defined: net debit paid",
        typical_objective="Benefit from near-term theta vs longer-dated vega",
        candidate_selection_rules=["Require two expirations with quotes", "Avoid illiquid far month"],
        invalidation_conditions=["missing expirations", "large directional gap", "event in short leg unaccounted for"],
        required_market_fields=["underlying_quote", "option_chain", "option_quotes", "iv"],
    ),
    StrategyDefinition(
        name="Diagonal Spread",
        key="diagonal_spread",
        category=StrategyCategory.DIRECTIONAL,
        market_conditions=["mild directional view with calendar component"],
        required_data=["multi-expiration chain", "IV", "direction thesis"],
        max_risk_characteristics="Typically defined by debit; assignment/early exercise risk on short option",
        typical_objective="Directional + theta with different strikes and expirations",
        candidate_selection_rules=["Long further expiry, short nearer expiry at different strike"],
        invalidation_conditions=["chain incomplete", "early-exercise risk unmanaged", "thesis flip"],
        required_market_fields=["underlying_quote", "option_chain", "option_quotes", "iv"],
    ),
    StrategyDefinition(
        name="Broken-Wing Butterfly",
        key="broken_wing_butterfly",
        category=StrategyCategory.DEFINED_RISK,
        market_conditions=["skewed directional butterfly", "defined-risk income"],
        required_data=["three-strike chain", "liquidity", "skew"],
        max_risk_characteristics="Defined but asymmetric; one wing has greater risk",
        typical_objective="Reduce debit or create credit by skipping a symmetric wing",
        candidate_selection_rules=["Map the larger-risk wing explicitly", "Size to worst-case wing"],
        invalidation_conditions=["unmapped max loss", "illiquid wings", "CRITICAL mode"],
        required_market_fields=["underlying_quote", "option_chain", "option_quotes"],
    ),
    StrategyDefinition(
        name="0-DTE Mean Reversion",
        key="zero_dte_mean_reversion",
        category=StrategyCategory.VOLATILITY,
        market_conditions=["same-day expiration", "intraday mean reversion setup"],
        required_data=["0-DTE chain", "intraday quotes", "fresh timestamps", "liquidity"],
        max_risk_characteristics="Extremely path-dependent; gamma/theta dominate; defined only if using spreads",
        typical_objective="Fade an intraday extreme when data is fresh",
        candidate_selection_rules=["Require non-stale quotes", "Prefer defined-risk structures", "No trade if DTE data missing"],
        invalidation_conditions=["stale quotes", "no 0-DTE listing", "trend day without mean-reversion evidence"],
        required_market_fields=["underlying_quote", "option_chain", "option_quotes", "fresh_timestamps"],
    ),
]


def get_strategy_library() -> List[StrategyDefinition]:
    """Return catalog definitions. None are auto-executed."""
    return list(STRATEGY_DEFINITIONS)


def get_strategy_by_key(key: str) -> Optional[StrategyDefinition]:
    for item in STRATEGY_DEFINITIONS:
        if item.key == key:
            return item
    return None


def missing_required_market_fields(strategy_key: str, available: dict) -> List[str]:
    """Return required fields that are missing. Candidate is INVALID if any are missing."""
    strategy = get_strategy_by_key(strategy_key)
    if not strategy:
        return ["unknown_strategy"]
    missing: List[str] = []
    for field in strategy.required_market_fields:
        if not available.get(field):
            missing.append(field)
    return missing
