"""Audit logger - append-only event logging."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from app.utils.logging import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Audit event types."""
    MARKET_SCAN = "market_scan"
    OPPORTUNITY_FOUND = "opportunity_found"
    OPTIONS_ANALYSIS = "options_analysis"
    BULL_ANALYSIS = "bull_analysis"
    BEAR_ANALYSIS = "bear_analysis"
    STRATEGY_ANALYSIS = "strategy_analysis"
    RISK_ANALYSIS = "risk_analysis"
    DECISION = "decision"
    RISK_APPROVAL = "risk_approval"
    RISK_REJECTION = "risk_rejection"
    TRADE_PROPOSAL = "trade_proposal"
    LLM_REVIEW = "llm_review"
    FINAL_RISK_GUARDIAN = "final_risk_guardian"
    DRAWDOWN_CHANGE = "drawdown_change"
    ORDER_VALIDATION = "order_validation"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    POSITION_UPDATE = "position_update"
    EXIT = "exit"
    VOICE_ALERT = "voice_alert"
    SYSTEM_ERROR = "system_error"


class AuditSeverity(str, Enum):
    """Event severity levels."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event record."""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    symbol: Optional[str]
    message: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "symbol": self.symbol,
            "message": self.message,
            "metadata": self.metadata,
            "cycle_id": (self.metadata or {}).get("cycle_id"),
            "dry_run": (self.metadata or {}).get("dry_run"),
        }


class AuditLogger:
    """Append-only audit event logger."""
    
    def __init__(self):
        """Initialize audit logger."""
        self.logger = logger
        self.events: List[AuditEvent] = []
    
    def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        symbol: Optional[str],
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Log an audit event (append-only).
        
        Args:
            event_type: Type of event
            severity: Severity level
            symbol: Trading symbol (if applicable)
            message: Event message
            metadata: Additional event data
            
        Returns:
            AuditEvent
        """
        event = AuditEvent(
            event_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            event_type=event_type,
            severity=severity,
            symbol=symbol,
            message=message,
            metadata=metadata or {},
        )
        
        # Append (never delete)
        self.events.append(event)
        
        self.logger.info(
            f"Audit: {event_type.value}",
            event_id=event.event_id,
            severity=severity.value,
            symbol=symbol,
            message=message,
        )
        
        return event
    
    def log_market_scan(self, symbol: str, metadata: Dict = None) -> AuditEvent:
        """Log market scan event."""
        return self.log_event(
            AuditEventType.MARKET_SCAN,
            AuditSeverity.INFO,
            symbol,
            f"Market scan initiated for {symbol}",
            metadata,
        )
    
    def log_opportunity_found(
        self,
        symbol: str,
        strategy: str,
        confidence: float,
        metadata: Dict = None,
    ) -> AuditEvent:
        """Log opportunity found event."""
        return self.log_event(
            AuditEventType.OPPORTUNITY_FOUND,
            AuditSeverity.INFO,
            symbol,
            f"Opportunity found: {strategy} (confidence: {confidence:.1%})",
            metadata or {},
        )
    
    def log_decision(
        self,
        symbol: str,
        decision: str,
        confidence: float,
        metadata: Dict = None,
    ) -> AuditEvent:
        """Log decision event."""
        return self.log_event(
            AuditEventType.DECISION,
            AuditSeverity.INFO,
            symbol,
            f"Decision: {decision} (confidence: {confidence:.1%})",
            metadata or {},
        )
    
    def log_risk_approval(
        self,
        symbol: str,
        risk_score: float,
        metadata: Dict = None,
    ) -> AuditEvent:
        """Log risk approval event."""
        return self.log_event(
            AuditEventType.RISK_APPROVAL,
            AuditSeverity.INFO,
            symbol,
            f"Risk approved (risk score: {risk_score:.2f})",
            metadata or {},
        )
    
    def log_risk_rejection(
        self,
        symbol: str,
        reasons: List[str],
        metadata: Dict = None,
    ) -> AuditEvent:
        """Log risk rejection event."""
        return self.log_event(
            AuditEventType.RISK_REJECTION,
            AuditSeverity.WARNING,
            symbol,
            f"Risk rejected: {'; '.join(reasons[:2])}",
            {"reasons": reasons, **(metadata or {})},
        )
    
    def log_order_submitted(
        self,
        symbol: str,
        quantity: int,
        side: str,
        metadata: Dict = None,
    ) -> AuditEvent:
        """Log order submitted event."""
        return self.log_event(
            AuditEventType.ORDER_SUBMITTED,
            AuditSeverity.INFO,
            symbol,
            f"Order submitted: {side} {quantity} contracts",
            metadata or {},
        )
    
    def log_order_filled(
        self,
        symbol: str,
        quantity: int,
        filled_price: float,
        metadata: Dict = None,
    ) -> AuditEvent:
        """Log order filled event."""
        return self.log_event(
            AuditEventType.ORDER_FILLED,
            AuditSeverity.INFO,
            symbol,
            f"Order filled: {quantity} contracts at ${filled_price:.2f}",
            metadata or {},
        )
    
    def log_system_error(
        self,
        error: str,
        metadata: Dict = None,
    ) -> AuditEvent:
        """Log system error event."""
        return self.log_event(
            AuditEventType.SYSTEM_ERROR,
            AuditSeverity.CRITICAL,
            None,
            f"System error: {error}",
            metadata or {},
        )
    
    def get_events(
        self,
        symbol: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        limit: Optional[int] = None,
    ) -> List[AuditEvent]:
        """
        Get audit events with optional filtering.
        
        Args:
            symbol: Filter by symbol
            event_type: Filter by event type
            limit: Limit number of results
            
        Returns:
            List of events
        """
        filtered = self.events
        
        if symbol:
            filtered = [e for e in filtered if e.symbol == symbol]
        
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        
        # Return most recent first, optionally limited
        result = list(reversed(filtered))
        if limit:
            result = result[:limit]
        
        return result
    
    def get_event_count(self) -> int:
        """Get total event count."""
        return len(self.events)