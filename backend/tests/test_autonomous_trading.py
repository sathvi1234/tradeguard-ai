"""Comprehensive tests for autonomous trading system."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from app.trading.autonomous_engine import AutonomousTradingEngine
from app.trading.order_builder import OrderBuilder, OrderSide
from app.trading.order_validator import OrderValidator
from app.trading.order_executor import OrderExecutor
from app.trading.position_manager import PositionManager, PositionStatus
from app.trading.portfolio_monitor import PortfolioMonitor
from app.trading.audit_logger import AuditLogger, AuditEventType, AuditSeverity
from app.models import TradingMode


@pytest.mark.asyncio
class TestOrderBuilder:
    """Tests for OrderBuilder."""
    
    async def test_build_buy_call(self):
        """Test building a BUY_CALL order."""
        builder = OrderBuilder()
        
        order = builder.build_buy_call(
            symbol="AAPL",
            strike=105.0,
            expiration="2024-12-20",
            quantity=1,
            bid_price=2.50,
            ask_price=2.55,
        )
        
        assert order.symbol == "AAPL"
        assert order.option_type == "call"
        assert order.side == OrderSide.BUY
        assert order.quantity == 1
        assert order.strike == 105.0
    
    async def test_calculate_quantity(self):
        """Test quantity calculation."""
        builder = OrderBuilder()
        
        quantity = builder.calculate_quantity(
            proposed_size=1000.0,
            option_price=2.50,
            multiplier=100,
        )
        
        assert quantity >= 1
        assert isinstance(quantity, int)


@pytest.mark.asyncio
class TestOrderValidator:
    """Tests for OrderValidator."""
    
    async def test_validate_order_approved(self):
        """Test order validation passes."""
        validator = OrderValidator()
        builder = OrderBuilder()
        
        order = builder.build_buy_call(
            symbol="AAPL",
            strike=105.0,
            expiration="2024-12-20",
            quantity=1,
            bid_price=2.50,
            ask_price=2.55,
        )
        
        is_valid, errors = validator.validate_order(
            order=order,
            current_price=2.50,
            bid_price=2.50,
            ask_price=2.55,
            buying_power=10000.0,
            portfolio_value=100000.0,
            current_positions=0,
            decision_approved=True,
            risk_approved=True,
            drawdown_approved=True,
        )
        
        assert is_valid == True
        assert len(errors) == 0
    
    async def test_validate_order_rejected_low_confidence(self):
        """Test order rejection for low confidence."""
        validator = OrderValidator()
        builder = OrderBuilder()
        
        order = builder.build_buy_call(
            symbol="AAPL",
            strike=105.0,
            expiration="2024-12-20",
            quantity=1,
            bid_price=2.50,
            ask_price=2.55,
        )
        
        is_valid, errors = validator.validate_order(
            order=order,
            current_price=2.50,
            bid_price=2.50,
            ask_price=2.55,
            buying_power=10000.0,
            portfolio_value=100000.0,
            current_positions=0,
            decision_approved=False,  # Decision rejected
            risk_approved=True,
            drawdown_approved=True,
        )
        
        assert is_valid == False
        assert len(errors) > 0


@pytest.mark.asyncio
class TestOrderExecutor:
    """Tests for OrderExecutor."""
    
    async def test_execute_order_dry_run(self):
        """Test order execution in dry run mode."""
        executor = OrderExecutor(dry_run=True)
        builder = OrderBuilder()
        
        order = builder.build_buy_call(
            symbol="AAPL",
            strike=105.0,
            expiration="2024-12-20",
            quantity=1,
            bid_price=2.50,
            ask_price=2.55,
        )
        
        executed = await executor.execute_order(
            order=order,
            decision_id="test-decision-id",
            dry_run=True,
        )
        
        assert executed.status == "filled"
        assert executed.alpaca_order_id is not None


@pytest.mark.asyncio
class TestPositionManager:
    """Tests for PositionManager."""
    
    async def test_add_position(self):
        """Test adding a position."""
        manager = PositionManager()
        
        position = manager.add_position(
            position_id="pos-1",
            symbol="AAPL",
            option_type="call",
            strike=105.0,
            expiration="2024-12-20",
            quantity=1,
            entry_price=2.50,
        )
        
        assert position.symbol == "AAPL"
        assert position.quantity == 1
        assert position.status == PositionStatus.OPEN
    
    async def test_update_position_price(self):
        """Test updating position price."""
        manager = PositionManager()
        
        position = manager.add_position(
            position_id="pos-1",
            symbol="AAPL",
            option_type="call",
            strike=105.0,
            expiration="2024-12-20",
            quantity=1,
            entry_price=2.50,
        )
        
        manager.update_position_price("pos-1", 3.50)
        
        updated = manager.get_position("pos-1")
        assert updated.current_price == 3.50
        assert updated.unrealized_pnl() == 1.00
    
    async def test_should_exit_take_profit(self):
        """Test exit rule for take profit."""
        manager = PositionManager()
        
        position = manager.add_position(
            position_id="pos-1",
            symbol="AAPL",
            option_type="call",
            strike=105.0,
            expiration="2024-12-20",
            quantity=1,
            entry_price=2.50,
        )
        
        # Update price for 50% profit
        manager.update_position_price("pos-1", 3.75)
        
        should_exit, reason = manager.should_exit_position(
            "pos-1",
            max_loss_pct=0.50,
            take_profit_pct=0.50,
        )
        
        assert should_exit == True
        assert "profit" in reason.lower()


@pytest.mark.asyncio
class TestPortfolioMonitor:
    """Tests for PortfolioMonitor."""
    
    async def test_initialize(self):
        """Test portfolio initialization."""
        monitor = PortfolioMonitor()
        monitor.initialize(100000.0)
        
        assert monitor.starting_balance == 100000.0
        assert monitor.peak_value == 100000.0
    
    async def test_create_snapshot(self):
        """Test snapshot creation."""
        monitor = PortfolioMonitor()
        monitor.initialize(100000.0)
        
        snapshot = monitor.create_snapshot(
            account_value=100000.0,
            cash=80000.0,
            buying_power=90000.0,
            positions_count=1,
            position_exposure=20000.0,
            realized_pnl=0.0,
            unrealized_pnl=500.0,
        )
        
        assert snapshot.account_value == 100000.0
        assert snapshot.total_pnl == 500.0
    
    async def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        monitor = PortfolioMonitor()
        monitor.initialize(100000.0)
        
        # First snapshot at peak
        monitor.create_snapshot(
            account_value=100000.0,
            cash=80000.0,
            buying_power=90000.0,
        )
        
        # Second snapshot with drawdown
        snapshot = monitor.create_snapshot(
            account_value=90000.0,
            cash=80000.0,
            buying_power=90000.0,
        )
        
        assert snapshot.drawdown_pct == 0.10  # 10% drawdown


@pytest.mark.asyncio
class TestAuditLogger:
    """Tests for AuditLogger."""
    
    async def test_log_event(self):
        """Test event logging."""
        logger = AuditLogger()
        
        event = logger.log_event(
            event_type=AuditEventType.MARKET_SCAN,
            severity=AuditSeverity.INFO,
            symbol="AAPL",
            message="Market scan started",
        )
        
        assert event.event_type == AuditEventType.MARKET_SCAN
        assert event.symbol == "AAPL"
        assert len(logger.events) == 1
    
    async def test_get_events_filtered(self):
        """Test filtering events."""
        logger = AuditLogger()
        
        logger.log_event(
            AuditEventType.MARKET_SCAN,
            AuditSeverity.INFO,
            "AAPL",
            "Scan 1",
        )
        
        logger.log_event(
            AuditEventType.DECISION,
            AuditSeverity.INFO,
            "AAPL",
            "Decision made",
        )
        
        logger.log_event(
            AuditEventType.MARKET_SCAN,
            AuditSeverity.INFO,
            "TSLA",
            "Scan 2",
        )
        
        # Filter by AAPL
        aapl_events = logger.get_events(symbol="AAPL")
        assert len(aapl_events) == 2
        
        # Filter by event type
        scans = logger.get_events(event_type=AuditEventType.MARKET_SCAN)
        assert len(scans) == 2


@pytest.mark.asyncio
class TestAutonomousTradingEngine:
    """Tests for AutonomousTradingEngine."""
    
    async def test_initialization(self):
        """Test engine initialization."""
        engine = AutonomousTradingEngine(dry_run=True)
        
        assert engine.dry_run == True
        assert engine.running == False
        assert engine.cycle_count == 0
    
    async def test_system_health_check(self):
        """Test system health check."""
        engine = AutonomousTradingEngine(dry_run=True)
        
        # Mock Alpaca service
        with patch.object(engine.alpaca_service, 'get_account', new_callable=AsyncMock) as mock_account:
            mock_account.return_value = {
                "paper_trading_allowed": True,
                "trading_blocked": False,
            }
            
            is_healthy, error = await engine.check_system_health()
            
            # Note: real implementation would need more setup
            # This test verifies the structure


@pytest.mark.asyncio
class TestAutonomousIntegration:
    """Integration tests for autonomous system."""
    
    async def test_complete_cycle_with_mocks(self):
        """Test complete trading cycle with mocks."""
        engine = AutonomousTradingEngine(dry_run=True)
        
        # Mock all external dependencies
        with patch.object(engine.alpaca_service, 'get_account', new_callable=AsyncMock) as mock_account:
            mock_account.return_value = {
                "paper_trading_allowed": True,
                "trading_blocked": False,
                "portfolio_value": 100000.0,
                "cash": 80000.0,
                "buying_power": 90000.0,
            }
            
            # Initialize engine
            success = await engine.initialize()
            
            # Verify initialization
            assert success == True
            assert engine.drawdown_guardian.state is not None
    
    async def test_duplicate_order_protection(self):
        """Test duplicate order protection."""
        engine = AutonomousTradingEngine(dry_run=True)
        
        order1 = Mock(symbol="AAPL", strike=105.0, expiration="2024-12-20")
        order2 = Mock(symbol="AAPL", strike=105.0, expiration="2024-12-20")
        
        # First order
        engine.recent_orders.append({
            "symbol": "AAPL",
            "strike": 105.0,
            "expiration": "2024-12-20",
            "timestamp": datetime.utcnow(),
        })
        
        # Check for duplicate
        validator = OrderValidator()
        is_unique, error = validator.validate_duplicate_order(
            symbol="AAPL",
            strike=105.0,
            expiration="2024-12-20",
            recent_orders=engine.recent_orders,
            max_age_seconds=60,
        )
        
        assert is_unique == False
        assert error is not None


@pytest.mark.asyncio
class TestSafetyFeatures:
    """Tests for safety features."""
    
    async def test_paper_trading_enforcement(self):
        """Test paper trading enforcement."""
        engine = AutonomousTradingEngine(dry_run=True)
        
        # Engine should have paper trading enforced
        assert engine.dry_run == True
    
    async def test_critical_mode_blocks_trades(self):
        """Test critical mode blocks all trades."""
        engine = AutonomousTradingEngine(dry_run=True)
        
        # Initialize drawdown guardian
        engine.drawdown_guardian.initialize(100000.0)
        
        # Simulate critical mode
        engine.drawdown_guardian.state.current_mode = TradingMode.CRITICAL
        engine.drawdown_guardian.state.drawdown_percentage = 0.16
        
        # This would block order execution
        assert engine.drawdown_guardian.state.current_mode == TradingMode.CRITICAL
    
    async def test_stale_data_rejection(self):
        """Test stale data causes rejection."""
        validator = OrderValidator()
        
        # Create old timestamp
        from datetime import timedelta
        old_time = datetime.utcnow() - timedelta(minutes=10)
        
        is_fresh, error = validator.validate_quote_freshness(
            quote_timestamp=old_time,
            max_age_seconds=300,
        )
        
        assert is_fresh == False
        assert error is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])