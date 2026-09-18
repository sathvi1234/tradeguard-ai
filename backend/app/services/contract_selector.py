"""Deterministic option-contract selection from real Alpaca data."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from app.alpaca.service import AlpacaService
from app.config import settings
from app.models.market_data import OptionContract, OptionSnapshot, SelectedContract, StockQuote
from app.models.market_data import FreshnessStatus
from app.services.strategy_library import get_strategy_by_key
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _today() -> datetime:
    return datetime.now(timezone.utc).date()


def _dte(expiration: Optional[str]) -> Optional[int]:
    if not expiration:
        return None
    try:
        exp = datetime.strptime(expiration[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (exp - _today()).days


def filter_contracts(contracts: List[OptionContract]) -> List[OptionContract]:
    kept: List[OptionContract] = []
    for contract in contracts:
        dte = _dte(contract.expiration)
        if dte is None or dte < 0:
            continue
        if contract.tradable is False:
            continue
        if contract.status and str(contract.status).lower() not in ("active", "tradable"):
            continue
        if not contract.strike or not contract.expiration or not contract.option_type:
            continue
        kept.append(contract)
    return kept


def filter_quoted(
    contracts: List[OptionContract],
    snapshots: dict,
    max_spread_pct: float,
) -> List[Tuple[OptionContract, OptionSnapshot]]:
    usable: List[Tuple[OptionContract, OptionSnapshot]] = []
    for contract in contracts:
        snap = snapshots.get(contract.occ_symbol)
        if not snap:
            continue
        if snap.bid is None or snap.ask is None or snap.bid <= 0 or snap.ask <= 0:
            continue
        if snap.freshness == FreshnessStatus.STALE:
            continue
        mid = (snap.bid + snap.ask) / 2
        if mid <= 0:
            continue
        spread_pct = (snap.ask - snap.bid) / mid
        if spread_pct > max_spread_pct:
            continue
        usable.append((contract, snap))
    return usable


class ContractSelector:
    """Pick a currently valid contract. No aggressive strategy engine."""

    def __init__(self, alpaca: Optional[AlpacaService] = None) -> None:
        self.alpaca = alpaca or AlpacaService()
        self.logger = logger

    async def select(
        self,
        watchlist: Optional[List[str]] = None,
        strategy_key: str = "directional_vertical_spread",
    ) -> Optional[SelectedContract]:
        strategy = get_strategy_by_key(strategy_key)
        symbols = watchlist or list(settings.watchlist)
        start = (_today() + timedelta(days=settings.preferred_dte_min)).isoformat()
        end = (_today() + timedelta(days=settings.preferred_dte_max)).isoformat()

        for symbol in symbols:
            asset = await self.alpaca.get_asset(symbol)
            if asset and asset.get("tradable") is False:
                continue
            quote = await self.alpaca.get_latest_quote(symbol)
            if not quote.usable:
                continue
            last = quote.bid and quote.ask and (quote.bid + quote.ask) / 2
            contracts = await self.alpaca.get_option_contracts(
                underlying_symbol=symbol,
                expiration_start=start,
                expiration_end=end,
                option_type="call",
                strike_min=(last * 0.95) if last else None,
                strike_max=(last * 1.10) if last else None,
            )
            filtered = filter_contracts(contracts)
            if not filtered:
                continue
            snapshots = await self.alpaca.get_option_snapshots(symbol)
            quoted = filter_quoted(filtered, snapshots, settings.max_option_spread_pct)
            if not quoted:
                continue
            picked = self._prefer_otm_call(quoted, last or 0)
            if not picked:
                continue
            contract, snap = picked
            reason = "Closest listed OTM call with usable Alpaca quotes in preferred DTE window"
            if strategy and strategy.required_market_fields:
                missing = []
                needs = set(strategy.required_market_fields)
                if "underlying_quote" in needs and not quote.usable:
                    missing.append("underlying_quote")
                if "option_chain" in needs and not filtered:
                    missing.append("option_chain")
                if "option_quotes" in needs and (snap.bid is None or snap.ask is None):
                    missing.append("option_quotes")
                if "iv" in needs and snap.implied_volatility is None:
                    missing.append("iv")
                if missing:
                    self.logger.info("Strategy %s missing %s for %s", strategy_key, missing, symbol)
                    continue
            return SelectedContract(
                underlying=symbol,
                occ_symbol=contract.occ_symbol,
                option_type=contract.option_type or "call",
                strike=float(contract.strike),
                expiration=contract.expiration,
                bid=snap.bid,
                ask=snap.ask,
                last_price=snap.last_price,
                implied_volatility=snap.implied_volatility,
                greeks={
                    "delta": snap.delta,
                    "gamma": snap.gamma,
                    "theta": snap.theta,
                    "vega": snap.vega,
                    "quality": snap.greeks_quality,
                },
                strategy_key=strategy_key,
                selection_reason=reason,
            )
        return None

    def _prefer_otm_call(
        self,
        quoted: List[Tuple[OptionContract, OptionSnapshot]],
        last: float,
    ) -> Optional[Tuple[OptionContract, OptionSnapshot]]:
        calls = [
            pair for pair in quoted
            if (pair[0].option_type or "").lower() == "call" and pair[0].strike
        ]
        if not calls:
            calls = quoted
        otm = [pair for pair in calls if last and pair[0].strike >= last]
        pool = otm or calls

        def _key(pair: Tuple[OptionContract, OptionSnapshot]):
            contract, _snap = pair
            dte = _dte(contract.expiration) or 0
            strike_gap = abs((contract.strike or 0) - last)
            return (strike_gap, abs(dte - ((settings.preferred_dte_min + settings.preferred_dte_max) / 2)))

        pool.sort(key=_key)
        return pool[0] if pool else None
