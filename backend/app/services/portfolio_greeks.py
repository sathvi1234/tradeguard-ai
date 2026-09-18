"""Portfolio Greeks. Never invent live Greek values."""

from typing import Iterable, List, Optional
import re

from app.models.market_data import OptionSnapshot
from app.models.schemas import DATA_UNAVAILABLE, DataAvailability, PortfolioGreeksSnapshot

OCC_PATTERN = re.compile(r"^[A-Z]{1,6}\d{6}[CP]\d{8}$")


def _looks_like_occ(symbol: str) -> bool:
    return bool(OCC_PATTERN.match((symbol or "").upper()))


def _field(item: object, name: str) -> object:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


class PortfolioGreeksService:
    """Aggregate Greeks only from explicitly provided real Alpaca snapshots."""

    def snapshot(
        self,
        positions: Optional[Iterable] = None,
        real_greeks: Optional[dict] = None,
        option_snapshots: Optional[List[OptionSnapshot]] = None,
    ) -> PortfolioGreeksSnapshot:
        if real_greeks:
            return PortfolioGreeksSnapshot(
                availability=DataAvailability.AVAILABLE,
                delta=real_greeks.get("delta"),
                gamma=real_greeks.get("gamma"),
                theta=real_greeks.get("theta"),
                vega=real_greeks.get("vega"),
                iv=real_greeks.get("iv"),
                portfolio_delta=real_greeks.get("portfolio_delta", real_greeks.get("delta")),
                portfolio_gamma=real_greeks.get("portfolio_gamma", real_greeks.get("gamma")),
                portfolio_theta=real_greeks.get("portfolio_theta", real_greeks.get("theta")),
                portfolio_vega=real_greeks.get("portfolio_vega", real_greeks.get("vega")),
                source="provided_real_greeks",
                quality="REAL",
                notes="Greeks supplied by an explicit real data source.",
            )

        real_snaps = [
            s for s in (option_snapshots or [])
            if s.greeks_quality == "REAL"
        ]
        if real_snaps:
            qty = 1.0
            p_delta = sum((s.delta or 0) * qty for s in real_snaps if s.delta is not None)
            p_gamma = sum((s.gamma or 0) * qty for s in real_snaps if s.gamma is not None)
            p_theta = sum((s.theta or 0) * qty for s in real_snaps if s.theta is not None)
            p_vega = sum((s.vega or 0) * qty for s in real_snaps if s.vega is not None)
            return PortfolioGreeksSnapshot(
                availability=DataAvailability.AVAILABLE,
                delta=p_delta,
                gamma=p_gamma,
                theta=p_theta,
                vega=p_vega,
                iv=real_snaps[0].implied_volatility,
                portfolio_delta=p_delta,
                portfolio_gamma=p_gamma,
                portfolio_theta=p_theta,
                portfolio_vega=p_vega,
                source="alpaca_option_snapshots",
                quality="REAL",
                notes="Aggregated from Alpaca option snapshot Greeks only.",
            )

        positions = list(positions or [])
        option_positions = []
        for item in positions:
            symbol = str(_field(item, "symbol") or "")
            kind = str(_field(item, "type") or "").upper()
            occ = str(_field(item, "occ_symbol") or "")
            if kind in {"OPTION", "CALL", "PUT"} or occ or _looks_like_occ(symbol):
                option_positions.append(item)
        if not option_positions:
            return PortfolioGreeksSnapshot(
                availability=DataAvailability.EMPTY,
                source="none",
                quality="NONE",
                notes="Greeks are calculated only for currently held option positions.",
                reason_code="NO_OPTION_POSITIONS",
            )
        missing = []
        if not real_snaps:
            missing.append("Alpaca option snapshot Greeks")
        return PortfolioGreeksSnapshot(
            availability=DataAvailability.DATA_UNAVAILABLE,
            source=DATA_UNAVAILABLE,
            quality=DATA_UNAVAILABLE,
            notes="Option positions exist but Greeks cannot be calculated. Missing: " + ", ".join(missing) + ".",
            reason_code="NO_OPTION_GREEKS",
        )
