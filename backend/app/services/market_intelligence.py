"""Advanced market intelligence. Unconnected sources return DATA_UNAVAILABLE."""

from typing import Any, Dict, Optional

from app.models.schemas import DATA_UNAVAILABLE, DataAvailability, MarketIntelligenceSnapshot


class MarketIntelligenceService:
    """Interface for flow, IV, VWAP, events. Does not fabricate feeds."""

    def snapshot(self, symbol: str, real_data: Optional[Dict[str, Any]] = None) -> MarketIntelligenceSnapshot:
        if not real_data:
            return MarketIntelligenceSnapshot(
                availability=DataAvailability.DATA_UNAVAILABLE,
                notes=f"No real market-intelligence source connected for {symbol}.",
            )

        def _field(key: str) -> str:
            value = real_data.get(key)
            if value is None:
                return DATA_UNAVAILABLE
            return str(value)

        available_keys = [k for k, v in real_data.items() if v is not None]
        availability = (
            DataAvailability.AVAILABLE if available_keys else DataAvailability.DATA_UNAVAILABLE
        )
        return MarketIntelligenceSnapshot(
            availability=availability,
            options_flow=_field("options_flow"),
            volume=_field("volume"),
            open_interest=_field("open_interest"),
            volume_profile_poc=_field("volume_profile_poc"),
            iv=_field("iv"),
            iv_skew=_field("iv_skew"),
            vwap=_field("vwap"),
            anchored_vwap=_field("anchored_vwap"),
            vix_intelligence=_field("vix_intelligence"),
            market_regime=_field("market_regime"),
            earnings_events=_field("earnings_events"),
            news_sentiment=_field("news_sentiment"),
            bid_ask_spread=_field("bid_ask_spread"),
            option_chain_structure=_field("option_chain_structure"),
            market_session=_field("market_session"),
            price=_field("price"),
            bid=_field("bid"),
            ask=_field("ask"),
            spread=_field("spread") if real_data.get("spread") is not None else _field("bid_ask_spread"),
            previous_close=_field("previous_close"),
            day_change=_field("day_change"),
            day_change_pct=_field("day_change_pct"),
            quote_timestamp=_field("quote_timestamp"),
            volatility=_field("volatility"),
            market_status=_field("market_status"),
            freshness=_field("freshness") if real_data.get("freshness") is not None else DATA_UNAVAILABLE,
            quote_available=str(real_data.get("quote_available")) if real_data.get("quote_available") is not None else DATA_UNAVAILABLE,
            notes=(
                f"Populated from real Alpaca keys: {', '.join(available_keys)}. "
                "Optional unconnected feeds remain unavailable and are not invented."
            ),
        )
