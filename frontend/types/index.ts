// Portfolio Types
export interface Portfolio {
  account_value: number;
  cash: number;
  buying_power: number;
  total_pnl: number;
  realized_pnl: number;
  unrealized_pnl: number;
  drawdown_pct: number;
  daily_pnl?: number;
}

export interface PortfolioStats {
  peak_equity: number;
  current_equity: number;
  max_drawdown: number;
  win_rate: number;
  trades_count: number;
}

export interface PortfolioHealth {
  status: string;
  current_mode: string;
  current_drawdown: number;
  risk_limits: Record<string, number>;
  risk_guardian_decisions: RiskDecision[];
  drawdown_guardian_events: DrawdownEvent[];
}

// Position Types
export interface Position {
  symbol: string;
  contract: string;
  type: 'CALL' | 'PUT';
  quantity: number;
  avg_fill_price: number;
  current_price: number;
  pnl: number;
  pnl_pct: number;
  expiration: string;
  days_to_expiry: number;
  delta: number;
  theta: number;
  gamma: number;
  vega: number;
  risk: number;
}

// Order Types
export interface Order {
  timestamp: string;
  symbol: string;
  contract: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  status: 'filled' | 'pending' | 'canceled' | 'partial';
  alpaca_id: string;
  executed_qty: number;
}

// Activity Types
export interface Activity {
  timestamp: string;
  event_type: string;
  severity: 'critical' | 'warning' | 'info';
  symbol?: string;
  message: string;
}

// Autonomous Status Types
export interface AutonomousStatus {
  running: boolean;
  current_mode: string;
  current_drawdown: number;
  positions_open: number;
  cycle_count: number;
  last_cycle_time?: string;
}

// Debate Types
export interface AgentOutput {
  data: Record<string, any>;
  reasoning: string;
  confidence: number;
}

export interface Debate {
  debate_id: string;
  symbol: string;
  completed: boolean;
  agent_outputs: Record<string, AgentOutput>;
  risk_guardian_result: RiskGuardianResult;
  final_decision: {
    decision: string;
    confidence: number;
  };
}

export interface RiskGuardianResult {
  decision: 'approved' | 'rejected';
  risk_score: number;
  limits_checked?: string[];
  rejection_reasons?: string[];
}

export interface RiskDecision {
  timestamp: string;
  decision: string;
  reason: string;
  proposed_position: {
    symbol: string;
    size: number;
  };
}

export interface DrawdownEvent {
  timestamp: string;
  event: string;
  from_mode?: string;
  to_mode?: string;
  drawdown: number;
  reason: string;
}

// Opportunity Types
export interface Opportunity {
  symbol: string;
  direction: 'bullish' | 'bearish';
  confidence: number;
  option_contract: string;
  strategy: string;
  reward: number;
  risk: number;
  ratio: number;
  market_score: number;
  timestamp: string;
}

// API Response Types
export interface ApiResponse<T> {
  data: T;
  status: string;
  message?: string;
}

export interface ApiError {
  detail: string;
  status: number;
}