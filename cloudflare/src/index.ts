import { Container } from '@cloudflare/containers';
import { env } from 'cloudflare:workers';

/**
 * Runs the existing FastAPI image (backend/Dockerfile) on port 8001.
 * Worker secrets/vars are forwarded into the container via envVars.
 * Never commit secret values — use `wrangler secret put` or the dashboard.
 */
export class TradeAiApiContainer extends Container {
  defaultPort = 8001;
  sleepAfter = '30m';

  envVars = {
    PORT: '8001',
    ENVIRONMENT: env.ENVIRONMENT ?? 'production',
    DEBUG: env.DEBUG ?? 'false',
    ALPACA_PAPER_TRADE: env.ALPACA_PAPER_TRADE ?? 'true',
    DRY_RUN: env.DRY_RUN ?? 'true',
    ALPACA_BASE_URL: env.ALPACA_BASE_URL ?? 'https://paper-api.alpaca.markets',
    ALPACA_DATA_URL: env.ALPACA_DATA_URL ?? 'https://data.alpaca.markets',
    LLM_PROVIDER: env.LLM_PROVIDER ?? 'groq',
    LLM_MODEL: env.LLM_MODEL ?? 'llama-3.1-8b-instant',
    FRONTEND_URL: env.FRONTEND_URL ?? '',
    ALPACA_API_KEY: env.ALPACA_API_KEY,
    ALPACA_SECRET_KEY: env.ALPACA_SECRET_KEY,
    LLM_API_KEY: env.LLM_API_KEY,
    DATABASE_URL: env.DATABASE_URL,
  };

  override onStart(): void {
    console.log('Trade AI API container started');
  }

  override onStop(): void {
    console.log('Trade AI API container stopped');
  }

  override onError(error: unknown): void {
    console.error('Trade AI API container error', error);
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = env.TRADE_AI_API.getByName('primary');
    return container.fetch(request);
  },
};

interface Env {
  TRADE_AI_API: DurableObjectNamespace<TradeAiApiContainer>;
  ENVIRONMENT?: string;
  DEBUG?: string;
  ALPACA_PAPER_TRADE?: string;
  DRY_RUN?: string;
  ALPACA_BASE_URL?: string;
  ALPACA_DATA_URL?: string;
  LLM_PROVIDER?: string;
  LLM_MODEL?: string;
  FRONTEND_URL?: string;
  ALPACA_API_KEY: string;
  ALPACA_SECRET_KEY: string;
  LLM_API_KEY: string;
  DATABASE_URL: string;
}
