/**
 * CUANIMUS Web Control Center — API Client Layer.
 * Provides resilient, typed HTTP communication with ControlPlaneAPI.
 */

const API = {
  baseUrl: window.location.origin,

  getToken() {
    return localStorage.getItem('cnms_session_token') || '';
  },
  setToken(token) {
    if (token) localStorage.setItem('cnms_session_token', token);
    else localStorage.removeItem('cnms_session_token');
  },
  getCsrfToken() {
    return localStorage.getItem('cnms_csrf_token') || '';
  },
  setCsrfToken(token) {
    if (token) localStorage.setItem('cnms_csrf_token', token);
    else localStorage.removeItem('cnms_csrf_token');
  },

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const token = this.getToken();
    const csrf = this.getCsrfToken();
    const defaultHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...(csrf ? { 'X-CSRF-Token': csrf } : {})
    };

    try {
      const response = await fetch(url, {
        credentials: 'include',
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

  // 0. Authentication & User Management
  async login(username, password) {
    const res = await this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    if (res?.session_token) {
      this.setToken(res.session_token);
      if (res.csrf_token) this.setCsrfToken(res.csrf_token);
    }
    return res;
  },
  async logout() {
    try {
      await this.request('/api/auth/logout', {
        method: 'POST',
        body: JSON.stringify({})
      });
    } finally {
      this.setToken('');
      this.setCsrfToken('');
    }
  },
  getAuthMe() {
    return this.request('/api/auth/me');
  },
  changePassword(oldPassword, newPassword) {
    return this.request('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
    });
  },
  getUsers() {
    return this.request('/api/auth/users');
  },
  createUser(username, password, role = 'OPERATOR') {
    return this.request('/api/auth/users', {
      method: 'POST',
      body: JSON.stringify({ username, password, role })
    });
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
  closePosition(tradeId, reason = 'manual_operator') {
    return this.request('/api/trading/positions/close', {
      method: 'POST',
      body: JSON.stringify({ trade_id: tradeId, reason })
    });
  },
  createManualOrder(params) {
    return this.request('/api/trading/orders/create', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  },
  cancelOrder(orderId) {
    return this.request('/api/trading/orders/cancel', {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId })
    });
  },
  getTradesCsvUrl() {
    return `${this.baseUrl}/api/trading/trades/export-csv`;
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
  getPairs() {
    return this.request('/api/markets/pairs');
  },
  getTicker(symbol = 'ETH/USDT:USDT') {
    return this.request(`/api/markets/ticker?symbol=${encodeURIComponent(symbol)}`);
  },
  getMarkPrice(symbol = 'ETH/USDT:USDT') {
    return this.request(`/api/markets/mark-price?symbol=${encodeURIComponent(symbol)}`);
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
  getMcpTools() {
    return this.request('/api/agents/mcp-tools');
  },
  getAiConfig() {
    return this.request('/api/ai/config');
  },
  saveAiConfig(aiConfig) {
    return this.request('/api/ai/config', {
      method: 'POST',
      body: JSON.stringify(aiConfig)
    });
  },
  testAiConnection(payload) {
    return this.request('/api/ai/test-connection', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
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
  },

  // 10. Autonomous Trading Profiles & Engine
  getTradingProfiles() {
    return this.request('/api/trading/profiles');
  },
  getTradingProfile(id) {
    return this.request(`/api/trading/profiles/${encodeURIComponent(id)}`);
  },
  createTradingProfile(data) {
    return this.request('/api/trading/profiles', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  updateTradingProfile(id, data) {
    return this.request(`/api/trading/profiles/${encodeURIComponent(id)}/update`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  deleteTradingProfile(id) {
    return this.request(`/api/trading/profiles/${encodeURIComponent(id)}/delete`, {
      method: 'POST',
      body: JSON.stringify({})
    });
  },
  startTradingProfile(id) {
    return this.request(`/api/trading/profiles/${encodeURIComponent(id)}/start`, {
      method: 'POST',
      body: JSON.stringify({})
    });
  },
  pauseTradingProfile(id) {
    return this.request(`/api/trading/profiles/${encodeURIComponent(id)}/pause`, {
      method: 'POST',
      body: JSON.stringify({})
    });
  },
  stopTradingProfile(id) {
    return this.request(`/api/trading/profiles/${encodeURIComponent(id)}/stop`, {
      method: 'POST',
      body: JSON.stringify({})
    });
  },
  triggerProfileTick(id) {
    return this.request(`/api/trading/profiles/${encodeURIComponent(id)}/trigger`, {
      method: 'POST',
      body: JSON.stringify({})
    });
  },
  getEngineStatus() {
    return this.request('/api/trading/engine/status');
  },
  getEngineSessions() {
    return this.request('/api/trading/engine/sessions');
  },
  getEngineTraces(profileId = null) {
    const q = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : '';
    return this.request(`/api/trading/engine/traces${q}`);
  }
};

window.API = API;
