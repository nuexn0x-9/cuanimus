/**
 * CUANIMUS Web Control Center — API Client Layer.
 * Provides resilient, typed HTTP communication with ControlPlaneAPI.
 */

const API = {
  baseUrl: window.location.origin,

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const defaultHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...defaultHeaders,
          ...(options.headers || {})
        }
      });

      if (!response.ok) {
        let errMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errBody = await response.json();
          if (errBody.error) errMessage = errBody.error;
        } catch (_) {}
        throw new Error(errMessage);
      }

      return await response.json();
    } catch (err) {
      console.warn(`[API ERROR] ${endpoint}:`, err.message);
      throw err;
    }
  },

  // 1. System & Safety
  getSystemStatus() {
    return this.request('/api/system/status');
  },
  triggerEmergencyStop(reason = "Operator Triggered Web Kill Switch") {
    return this.request('/api/system/emergency-stop', {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  },
  resetEmergencyStop() {
    return this.request('/api/system/reset-emergency-stop', {
      method: 'POST',
      body: JSON.stringify({})
    });
  },
  runDoctor() {
    return this.request('/api/doctor');
  },

  // 2. Trading: Positions, Orders, Trades, Traces
  getPositions() {
    return this.request('/api/trading/positions');
  },
  getOrders() {
    return this.request('/api/trading/orders');
  },
  getTrades(limit = 50) {
    return this.request(`/api/trading/trades?limit=${limit}`);
  },
  getDecisionTraces(tradeId = null) {
    const q = tradeId ? `?trade_id=${encodeURIComponent(tradeId)}` : '';
    return this.request(`/api/trading/decision-traces${q}`);
  },

  // 3. Markets & Charting
  getWatchlist() {
    return this.request('/api/markets/watchlist');
  },
  getRegimes() {
    return this.request('/api/markets/regimes');
  },
  getCandles(symbol = 'ETH/USDT:USDT', timeframe = '15m', limit = 80) {
    return this.request(`/api/markets/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`);
  },

  // 4. Risk Center
  getRiskStatus() {
    return this.request('/api/risk/status');
  },
  getRiskProfiles() {
    return this.request('/api/risk/profiles');
  },

  // 5. Strategies
  getStrategies() {
    return this.request('/api/strategies');
  },
  inspectStrategy(id) {
    return this.request(`/api/strategies/${encodeURIComponent(id)}`);
  },
  inspectSignal(id, symbol = 'ETH/USDT:USDT') {
    return this.request(`/api/strategies/signal/${encodeURIComponent(id)}?symbol=${encodeURIComponent(symbol)}`);
  },

  // 6. Research & Backtest
  getExperiments() {
    return this.request('/api/research/experiments');
  },
  getExperimentDetail(id) {
    return this.request(`/api/research/experiments/${encodeURIComponent(id)}`);
  },
  runBacktest(params) {
    return this.request('/api/research/backtest/run', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  },

  // 7. Agents & Sessions
  getAgents() {
    return this.request('/api/agents');
  },
  getSessions() {
    return this.request('/api/agents/sessions');
  },
  manageSession(sessionId, action) {
    return this.request(`/api/agents/sessions/${encodeURIComponent(sessionId)}/action`, {
      method: 'POST',
      body: JSON.stringify({ action })
    });
  },
  createPaperSession(agentId = 'antigravity-copilot', maxDuration = 7200, maxTrades = 20) {
    return this.request('/api/agents/sessions/create-paper', {
      method: 'POST',
      body: JSON.stringify({
        agent_id: agentId,
        max_duration_seconds: maxDuration,
        max_trades: maxTrades
      })
    });
  },
  getAgentAudit() {
    return this.request('/api/agents/audit');
  },
  proposeConfig(prompt) {
    return this.request('/api/agents/propose-config', {
      method: 'POST',
      body: JSON.stringify({ prompt })
    });
  },

  // 8. Configuration
  getConfigSchema() {
    return this.request('/api/config/schema');
  },
  getCurrentConfig() {
    return this.request('/api/config/current');
  },
  validateConfig(rawConfig) {
    return this.request('/api/config/validate', {
      method: 'POST',
      body: JSON.stringify(rawConfig)
    });
  },
  saveConfig(rawConfig, filename = 'cuanimus.user.yaml') {
    return this.request('/api/config/save', {
      method: 'POST',
      body: JSON.stringify({ config: rawConfig, filename })
    });
  },

  // 9. Data, Events, Telegram, Settings
  getDatasets() {
    return this.request('/api/data/datasets');
  },
  getEvents() {
    return this.request('/api/logs/events');
  },
  getTelegramStatus() {
    return this.request('/api/telegram/status');
  },
  sendTelegramTest() {
    return this.request('/api/telegram/test', {
      method: 'POST',
      body: JSON.stringify({})
    });
  },
  getSettings() {
    return this.request('/api/settings');
  },
  updateSettings(settings) {
    return this.request('/api/settings', {
      method: 'POST',
      body: JSON.stringify(settings)
    });
  }
};

window.API = API;
