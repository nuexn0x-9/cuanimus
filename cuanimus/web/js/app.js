/**
 * CUANIMUS Web Control Center — Main Application Logic & Single-Page Router.
 * Orchestrates views, state management, auto-refresh loops, and real-time syncing.
 */

class CuanimusApp {
  constructor() {
    this.currentView = 'overview';
    this.chartInstance = null;
    this.refreshTimer = null;
    this.systemStatus = {};
    this.selectedSymbol = 'ETH/USDT:USDT';
    this.selectedTimeframe = '15m';

    this.init();
  }

  async init() {
    Toast.init();
    CommandPalette.init();
    this._bindNavigation();
    this._bindGlobalHeader();

    await this.checkAuthStatus();

    // Route from hash or default
    const hash = window.location.hash.replace('#', '') || 'overview';
    this.navigate(hash);

    // Initial load
    await this.refreshAll();

    // Start auto-refresh polling loop (every 3 seconds)
    this.startAutoRefresh();
  }

  async checkAuthStatus() {
    try {
      const auth = await API.getAuthMe();
      this.currentUser = auth;
      const userBtn = document.getElementById('btn-header-auth');
      if (userBtn) {
        if (auth && auth.authenticated) {
          userBtn.innerHTML = `👤 ${auth.username} [${auth.role}]`;
          userBtn.title = "Click to Sign Out";
          userBtn.onclick = async () => {
            if (confirm(`Sign out from ${auth.username}?`)) {
              await API.logout();
              Toast.info("Signed out");
              this.checkAuthStatus();
            }
          };
        } else {
          userBtn.innerHTML = `🔑 Sign In`;
          userBtn.title = "Click to Sign In";
          userBtn.onclick = () => Modals.showLoginModal();
        }
      }
    } catch (_) {}
  }

  startAutoRefresh() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    this.refreshTimer = setInterval(() => {
      this.refreshLightweight();
    }, 3000);
  }

  _bindNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', () => {
        const view = item.getAttribute('data-view');
        if (view) this.navigate(view);
      });
    });

    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '') || 'overview';
      this.navigate(hash, false);
    });
  }

  _bindGlobalHeader() {
    const btnEmergency = document.getElementById('btn-header-emergency');
    if (btnEmergency) {
      btnEmergency.addEventListener('click', () => Modals.showEmergencyStopModal());
    }

    const btnDoctor = document.getElementById('btn-header-doctor');
    if (btnDoctor) {
      btnDoctor.addEventListener('click', () => this.runDoctorDiagnostics());
    }

    const btnCopilot = document.getElementById('btn-header-copilot');
    if (btnCopilot) {
      btnCopilot.addEventListener('click', () => Modals.showAiCopilotModal());
    }
  }

  navigate(viewName, updateHash = true) {
    this.currentView = viewName;
    if (updateHash) {
      window.location.hash = viewName;
    }

    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.getAttribute('data-view') === viewName);
    });

    document.querySelectorAll('.view-container').forEach(el => {
      el.classList.remove('active');
    });

    const targetView = document.getElementById(`view-${viewName}`);
    if (targetView) {
      targetView.classList.add('active');
      this.renderCurrentView();
    }
  }

  async refreshAll() {
    try {
      this.systemStatus = await API.getSystemStatus();
      this.updateHeaderBadges(this.systemStatus);
      this.renderCurrentView();
    } catch (err) {
      console.warn("Global refresh failed:", err);
    }
  }

  async refreshLightweight() {
    try {
      this.systemStatus = await API.getSystemStatus();
      this.updateHeaderBadges(this.systemStatus);
      if (this.currentView === 'overview' || this.currentView === 'trading' || this.currentView === 'risk') {
        this.renderCurrentView(true);
      }
    } catch (_) {}
  }

  updateHeaderBadges(status) {
    const envBadge = document.getElementById('header-env-badge');
    if (envBadge) {
      envBadge.textContent = status.environment || 'PAPER';
      envBadge.className = `env-indicator env-${(status.environment || 'paper').toLowerCase()}`;
    }

    const healthDot = document.getElementById('header-health-dot');
    if (healthDot) {
      const isOk = status.safety_status === 'SAFE' && !status.emergency_stop_active;
      healthDot.className = `health-dot ${isOk ? 'ok' : 'bad'}`;
    }

    const stratEl = document.getElementById('header-active-strategy');
    if (stratEl) stratEl.textContent = status.strategy_id || 'v2_pullback';

    const riskEl = document.getElementById('header-risk-profile');
    if (riskEl) riskEl.textContent = status.risk_profile || 'conservative';
  }

  renderCurrentView(isLightweight = false) {
    switch (this.currentView) {
      case 'overview':
        this.renderOverview();
        break;
      case 'trading':
        this.renderTrading(isLightweight);
        break;
      case 'markets':
        if (!isLightweight) this.renderMarkets();
        break;
      case 'strategies':
        if (!isLightweight) this.renderStrategies();
        break;
      case 'research':
        if (!isLightweight) this.renderResearch();
        break;
      case 'risk':
        this.renderRisk();
        break;
      case 'autonomous':
        this.renderAutonomous(isLightweight);
        break;
      case 'agents':
        this.renderAgents();
        break;
      case 'config':
        if (!isLightweight) this.renderConfig();
        break;
      case 'data':
        if (!isLightweight) this.renderData();
        break;
      case 'logs':
        if (!isLightweight) this.renderLogs();
        break;
      case 'settings':
        if (!isLightweight) this.renderSettings();
        break;
    }
  }

  // -------------------------------------------------------------------------
  // 1. OVERVIEW DASHBOARD
  // -------------------------------------------------------------------------
  async renderOverview() {
    const container = document.getElementById('view-overview');
    if (!container) return;

    const [positionsRes, riskRes] = await Promise.all([
      API.getPositions().catch(() => ({ positions: [] })),
      API.getRiskStatus().catch(() => ({ equity: 1000.0, daily_loss: {}, portfolio_drawdown: {} }))
    ]);

    const positions = positionsRes.positions || [];
    const risk = riskRes;
    const totalPnl = positions.reduce((acc, p) => acc + (p.unrealized_pnl_usd || 0), 0);

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title">
            <span>📊</span> Operational Dashboard
            <span class="badge ${this.systemStatus.safety_status === 'SAFE' ? 'badge-bull' : 'badge-bear'}">${this.systemStatus.safety_status || 'SAFE'}</span>
          </div>
          <div class="view-subtitle">Real-time portfolio surveillance, risk bounds & autonomous agent state</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-primary btn-sm" onclick="Modals.showAiCopilotModal()">🤖 Ask AI Copilot</button>
          <button class="btn btn-sm" onclick="window.app.refreshAll()">🔄 Refresh</button>
        </div>
      </div>

      <div class="grid-cards">
        <div class="stat-card">
          <div class="stat-card-label">Portfolio Equity</div>
          <div class="stat-card-value">$${(risk.equity || 1000).toFixed(2)}</div>
          <div class="stat-card-sub">Free Margin: $${(risk.free_margin || 800).toFixed(2)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Open Positions PnL</div>
          <div class="stat-card-value ${totalPnl >= 0 ? 'bull' : 'bear'}">
            ${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}
          </div>
          <div class="stat-card-sub">${positions.length} active paper position(s)</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Daily Loss vs Limit</div>
          <div class="stat-card-value">${(risk.daily_loss.current_pct || 0).toFixed(2)}% <span style="font-size: 13px; color: var(--text-muted);">/ ${(risk.daily_loss.limit_pct || 3.0)}%</span></div>
          <div class="stat-card-sub">Daily loss: $${(risk.daily_loss.current_usd || 0).toFixed(2)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Portfolio Drawdown</div>
          <div class="stat-card-value">${(risk.portfolio_drawdown.current_pct || 0).toFixed(2)}% <span style="font-size: 13px; color: var(--text-muted);">/ ${(risk.portfolio_drawdown.limit_pct || 15.0)}%</span></div>
          <div class="stat-card-sub">Circuit Breaker: <b class="bull">Armed</b></div>
        </div>
      </div>

      <!-- Subsystems Health Grid -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>🛡️</span> Subsystem Operational Status</div>
          <span style="font-size: 11px; color: var(--text-muted);">Strict Deterministic Architecture</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; padding: 14px;">
    `;

    const subs = this.systemStatus.subsystems || {};
    for (const [key, item] of Object.entries(subs)) {
      const isHealthy = item.status === 'HEALTHY' || item.status === 'SAFE' || item.status === 'ARMED' || item.status === 'CONNECTED' || item.status === 'ACTIVE' || item.status === 'READY';
      html += `
        <div style="background: var(--bg-surface-2); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 10px 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <span style="font-weight: 600; font-size: 11px;">${item.name}</span>
            <span class="health-dot ${isHealthy ? 'ok' : 'bad'}"></span>
          </div>
          <div style="font-size: 11px; font-family: monospace; color: ${isHealthy ? 'var(--color-bull)' : 'var(--color-bear)'};">${item.status}</div>
        </div>
      `;
    }

    html += `
        </div>
      </div>

      <!-- Open Positions Preview -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>📈</span> Open Positions (Paper / Testnet)</div>
          <button class="btn btn-sm" onclick="window.app.navigate('trading')">Go to Terminal →</button>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Size</th>
                <th>Entry Price</th>
                <th>Mark Price</th>
                <th>uPnL (USD)</th>
                <th>ROE %</th>
                <th>ATR Stop Loss</th>
                <th>Take Profit</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
    `;

    if (positions.length === 0) {
      html += `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 20px;">No open positions currently. System is safely monitoring market regimes.</td></tr>`;
    } else {
      positions.forEach(p => {
        html += `
          <tr>
            <td><b>${p.symbol}</b></td>
            <td><span class="badge ${p.side === 'LONG' ? 'badge-bull' : 'badge-bear'}">${p.side}</span></td>
            <td class="mono">${p.size}</td>
            <td class="mono">$${p.entry_price.toFixed(2)}</td>
            <td class="mono">$${p.mark_price.toFixed(2)}</td>
            <td class="mono ${p.unrealized_pnl_usd >= 0 ? 'bull' : 'bear'}">${p.unrealized_pnl_usd >= 0 ? '+' : ''}$${p.unrealized_pnl_usd.toFixed(2)}</td>
            <td class="mono ${p.roe_pct >= 0 ? 'bull' : 'bear'}">${p.roe_pct >= 0 ? '+' : ''}${p.roe_pct.toFixed(2)}%</td>
            <td class="mono" style="color: var(--color-bear);">$${p.stop_loss.toFixed(2)}</td>
            <td class="mono" style="color: var(--color-bull);">$${p.take_profit.toFixed(2)}</td>
            <td><span class="badge badge-bull">${p.risk_status}</span></td>
          </tr>
        `;
      });
    }

    html += `
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }

  // -------------------------------------------------------------------------
  // 2. TRADING TERMINAL
  // -------------------------------------------------------------------------
  async renderTrading(isLightweight = false) {
    const container = document.getElementById('view-trading');
    if (!container) return;

    if (!isLightweight) {
      container.innerHTML = `
        <div class="view-header">
          <div>
            <div class="view-title"><span>⚡</span> Trading Terminal</div>
            <div class="view-subtitle">Interactive market analysis, causal execution & order lifecycle FSM</div>
          </div>
          <div class="view-actions">
            <select id="select-trading-pair" class="btn btn-sm" style="background: var(--bg-surface-2); color: #fff;">
              <option value="ETH/USDT:USDT" ${this.selectedSymbol === 'ETH/USDT:USDT' ? 'selected' : ''}>ETH/USDT:USDT</option>
              <option value="BTC/USDT:USDT" ${this.selectedSymbol === 'BTC/USDT:USDT' ? 'selected' : ''}>BTC/USDT:USDT</option>
              <option value="SOL/USDT:USDT" ${this.selectedSymbol === 'SOL/USDT:USDT' ? 'selected' : ''}>SOL/USDT:USDT</option>
              <option value="XRP/USDT:USDT" ${this.selectedSymbol === 'XRP/USDT:USDT' ? 'selected' : ''}>XRP/USDT:USDT</option>
            </select>
            <div class="chart-timeframes">
              <button class="tf-btn ${this.selectedTimeframe === '5m' ? 'active' : ''}" data-tf="5m">5m</button>
              <button class="tf-btn ${this.selectedTimeframe === '15m' ? 'active' : ''}" data-tf="15m">15m</button>
              <button class="tf-btn ${this.selectedTimeframe === '1h' ? 'active' : ''}" data-tf="1h">1h</button>
              <button class="tf-btn ${this.selectedTimeframe === '4h' ? 'active' : ''}" data-tf="4h">4h</button>
            </div>
          </div>
        </div>

        <div class="terminal-layout">
          <!-- Main Chart -->
          <div class="chart-container">
            <div class="chart-toolbar">
              <div style="font-weight: 700; font-size: 13px;" id="chart-symbol-header">
                ${this.selectedSymbol} • ${this.selectedTimeframe}
              </div>
              <div style="display: flex; gap: 8px; font-size: 11px;">
                <label><input type="checkbox" id="chk-ema" checked> EMA20/50</label>
                <label><input type="checkbox" id="chk-sltp" checked> SL/TP Levels</label>
                <label><input type="checkbox" id="chk-ob" checked> Order Block</label>
              </div>
            </div>
            <div class="canvas-wrapper">
              <canvas id="main-chart"></canvas>
            </div>
          </div>

          <!-- Position & Action Card -->
          <div class="table-panel" style="margin-bottom: 0;">
            <div class="panel-header">
              <div class="panel-title">Active Market Overview</div>
              <span class="badge badge-bull">PAPER_SAFE</span>
            </div>
            <div style="padding: 14px;" id="terminal-side-summary">
              Loading market metrics...
            </div>
          </div>
        </div>

        <!-- Orders & Positions Tabs -->
        <div class="table-panel">
          <div class="panel-header">
            <div class="panel-title"><span>📋</span> Order Lifecycle FSM & Active Positions</div>
            <button class="btn btn-sm" onclick="window.app.renderTrading()">Refresh Table</button>
          </div>
          <div id="terminal-tables-container" style="padding: 10px;">
            Loading positions and orders...
          </div>
        </div>
      `;

      // Init chart
      this.chartInstance = new CuanimusChart('main-chart');

      // Bind events
      document.getElementById('select-trading-pair').addEventListener('change', (e) => {
        this.selectedSymbol = e.target.value;
        this.loadChartData();
      });

      // Dynamically load active USDT perpetual pairs from Binance
      API.getPairs().then(res => {
        const pairs = res.pairs || [];
        const sel = document.getElementById('select-trading-pair');
        if (sel && pairs.length > 0) {
          const cur = this.selectedSymbol;
          const options = pairs.map(p => {
            const sym = p.internal || (p.symbol.endsWith('USDT') ? p.symbol.slice(0, -4) + '/USDT:USDT' : p.symbol);
            return `<option value="${sym}" ${sym === cur ? 'selected' : ''}>${p.symbol} (${p.base})</option>`;
          }).join('');
          sel.innerHTML = options;
          if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
        }
      }).catch(() => {});

      document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this.selectedTimeframe = btn.getAttribute('data-tf');
          this.loadChartData();
        });
      });

      document.getElementById('chk-ema').addEventListener('change', (e) => {
        if (this.chartInstance) { this.chartInstance.options.showEma = e.target.checked; this.chartInstance.render(); }
      });
      document.getElementById('chk-sltp').addEventListener('change', (e) => {
        if (this.chartInstance) { this.chartInstance.options.showLevels = e.target.checked; this.chartInstance.render(); }
      });
      document.getElementById('chk-ob').addEventListener('change', (e) => {
        if (this.chartInstance) { this.chartInstance.options.showOrderBlock = e.target.checked; this.chartInstance.render(); }
      });

      await this.loadChartData();
    }

    // Refresh tables
    const [posRes, ordRes, tradesRes] = await Promise.all([
      API.getPositions().catch(() => ({ positions: [] })),
      API.getOrders().catch(() => ({ orders: [] })),
      API.getTrades(5).catch(() => ({ trades: [] }))
    ]);

    const pos = posRes.positions || [];
    const ord = ordRes.orders || [];
    const trd = tradesRes.trades || [];

    const sideEl = document.getElementById('terminal-side-summary');
    if (sideEl) {
      sideEl.innerHTML = `
        <div style="font-size: 12px; line-height: 1.8;">
          <div style="display:flex; justify-content:space-between;"><span>Active Pair:</span> <b>${this.selectedSymbol}</b></div>
          <div style="display:flex; justify-content:space-between;"><span>Environment:</span> <span class="badge badge-paper">${this.systemStatus.environment}</span></div>
          <div style="display:flex; justify-content:space-between;"><span>Execution Mode:</span> <b>Simulated Limit FSM</b></div>
          <div style="display:flex; justify-content:space-between;"><span>Active Positions:</span> <b>${pos.length}</b></div>
          <div style="display:flex; justify-content:space-between;"><span>Pending Orders:</span> <b>${ord.filter(o => o.status === 'SUBMITTED').length}</b></div>
        </div>
        <div style="margin-top: 14px; display: flex; flex-direction: column; gap: 8px;">
          <button class="btn btn-primary btn-sm" onclick="Modals.showAiCopilotModal()">🤖 Ask AI To Trade Intent</button>
          <button class="btn btn-danger btn-sm" onclick="Modals.showEmergencyStopModal()">🚨 Emergency Stop</button>
        </div>
      `;
    }

    const tblEl = document.getElementById('terminal-tables-container');
    if (tblEl) {
      let tblHtml = `
        <h4 style="margin: 6px 0 10px 0; font-size: 12px; color: var(--text-muted);">ACTIVE POSITIONS</h4>
        <div class="table-responsive" style="margin-bottom: 16px;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Size</th>
                <th>Entry</th>
                <th>Mark</th>
                <th>uPnL</th>
                <th>ROE</th>
                <th>Stop Loss</th>
                <th>Take Profit</th>
                <th>Trace</th>
              </tr>
            </thead>
            <tbody>
      `;

      if (pos.length === 0) {
        tblHtml += `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 18px;">No active open positions. Portfolio is currently flat and waiting for qualified setups.</td></tr>`;
      } else {
        pos.forEach(p => {
          tblHtml += `
            <tr>
              <td><b>${p.symbol}</b></td>
              <td><span class="badge ${p.side === 'LONG' ? 'badge-bull' : 'badge-bear'}">${p.side}</span></td>
              <td class="mono">${p.size}</td>
              <td class="mono">$${p.entry_price.toFixed(2)}</td>
              <td class="mono">$${p.mark_price.toFixed(2)}</td>
              <td class="mono ${p.unrealized_pnl_usd >= 0 ? 'bull' : 'bear'}">${p.unrealized_pnl_usd >= 0 ? '+' : ''}$${p.unrealized_pnl_usd.toFixed(2)}</td>
              <td class="mono ${p.roe_pct >= 0 ? 'bull' : 'bear'}">${p.roe_pct.toFixed(2)}%</td>
              <td class="mono" style="color: var(--color-bear);">$${p.stop_loss.toFixed(2)}</td>
              <td class="mono" style="color: var(--color-bull);">$${p.take_profit.toFixed(2)}</td>
              <td><button class="btn btn-sm" onclick="window.app.inspectTrace('${p.decision_trace_id || ('TRACE_' + p.id)}')">Trace</button></td>
            </tr>
          `;
        });
      }

      tblHtml += `
            </tbody>
          </table>
        </div>

        <h4 style="margin: 12px 0 10px 0; font-size: 12px; color: var(--text-muted);">LIVE ORDERS (ORDER LIFECYCLE FSM)</h4>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Client Order ID</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Type</th>
                <th>Price</th>
                <th>Filled / Amount</th>
                <th>FSM Status</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
      `;

      if (ord.length === 0) {
        tblHtml += `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 18px;">No active or recent orders in order lifecycle buffer.</td></tr>`;
      } else {
        ord.forEach(o => {
          let stBadge = 'badge-neutral';
          if (o.status === 'FILLED') stBadge = 'badge-bull';
          if (o.status === 'SUBMITTED') stBadge = 'badge-info';
          if (o.status === 'CANCELLED' || o.status === 'REJECTED') stBadge = 'badge-bear';

          tblHtml += `
            <tr>
              <td class="mono"><b>${o.order_id}</b></td>
              <td class="mono" style="font-size: 10px; color: var(--text-muted);">${o.client_order_id}</td>
              <td>${o.symbol}</td>
              <td><span class="badge ${o.side === 'BUY' ? 'badge-bull' : 'badge-bear'}">${o.side}</span></td>
              <td>${o.type}</td>
              <td class="mono">$${o.price.toFixed(2)}</td>
              <td class="mono">${o.filled} / ${o.amount}</td>
              <td><span class="badge ${stBadge}">${o.status}</span></td>
              <td style="font-size: 11px;">${o.created_at}</td>
            </tr>
          `;
        });
      }

      tblHtml += `
            </tbody>
          </table>
        </div>

        <h4 style="margin: 16px 0 10px 0; font-size: 12px; color: var(--text-muted);">RECENT EXECUTIONS & CLOSED TRADES (AUDIT TRAIL)</h4>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Trade ID</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Amount</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>PnL ($ / %)</th>
                <th>Exit Reason</th>
                <th>Close Time</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
      `;

      if (trd.length === 0) {
        tblHtml += `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 18px;">No closed trades recorded.</td></tr>`;
      } else {
        trd.forEach(t => {
          const entryStr = t.entry_price < 1.0 ? t.entry_price.toFixed(4) : t.entry_price.toFixed(2);
          const exitStr = t.exit_price < 1.0 ? t.exit_price.toFixed(4) : t.exit_price.toFixed(2);
          tblHtml += `
            <tr>
              <td class="mono"><b>${t.trade_id}</b></td>
              <td>${t.symbol}</td>
              <td><span class="badge ${t.side === 'LONG' ? 'badge-bull' : 'badge-bear'}">${t.side}</span></td>
              <td class="mono">${t.amount}</td>
              <td class="mono">$${entryStr}</td>
              <td class="mono">$${exitStr}</td>
              <td class="mono ${t.pnl_usd >= 0 ? 'bull' : 'bear'}">${t.pnl_usd >= 0 ? '+' : ''}$${t.pnl_usd.toFixed(2)} (${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%)</td>
              <td><span class="badge badge-neutral">${t.exit_reason}</span></td>
              <td style="font-size: 11px;">${t.close_time}</td>
              <td><button class="btn btn-sm" onclick="window.app.inspectTrace('${t.decision_trace_id || t.trade_id}')">Trace</button></td>
            </tr>
          `;
        });
      }

      tblHtml += `
            </tbody>
          </table>
        </div>
      `;
      tblEl.innerHTML = tblHtml;
    }
  }

  async loadChartData() {
    try {
      const data = await API.getCandles(this.selectedSymbol, this.selectedTimeframe, 80);
      if (this.chartInstance) {
        this.chartInstance.setData(data);
      }
      const hdr = document.getElementById('chart-symbol-header');
      if (hdr) hdr.textContent = `${this.selectedSymbol} • ${this.selectedTimeframe}`;
    } catch (err) {
      Toast.warn("Failed to load candle data: " + err.message);
    }
  }

  async inspectTrace(traceId) {
    try {
      const tracesRes = await API.getDecisionTraces(traceId);
      const trace = (tracesRes.traces || [])[0];
      if (trace) {
        Modals.showDecisionTraceModal(trace);
      } else {
        Toast.warn("No trace details found for ID: " + traceId);
      }
    } catch (err) {
      Toast.error("Failed to fetch decision trace: " + err.message);
    }
  }

  // -------------------------------------------------------------------------
  // 3. MARKETS & REGIME MATRIX
  // -------------------------------------------------------------------------
  async renderMarkets() {
    const container = document.getElementById('view-markets');
    if (!container) return;

    const [watchRes, regimeRes] = await Promise.all([
      API.getWatchlist().catch(() => ({ watchlist: [] })),
      API.getRegimes().catch(() => ({ matrix: [] }))
    ]);

    const watchlist = watchRes.watchlist || [];
    const matrix = regimeRes.matrix || [];

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>🌐</span> Market Surveillance & Regime Matrix</div>
          <div class="view-subtitle">Cross-asset trend evaluation, volatility compression & signal generation</div>
        </div>
      </div>

      <!-- Regime Matrix -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>🧭</span> Multi-Asset Market Regime Matrix</div>
          <span style="font-size: 11px; color: var(--text-muted);">Updated Candle-by-Candle</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Market Regime</th>
                <th>BTC/USDT</th>
                <th>ETH/USDT</th>
                <th>SOL/USDT</th>
                <th>XRP/USDT</th>
                <th>ADA/USDT</th>
              </tr>
            </thead>
            <tbody>
    `;

    matrix.forEach(row => {
      html += `
        <tr>
          <td><b>${row.regime}</b></td>
          <td>${row.BTC ? '<span class="badge badge-bull">● ACTIVE</span>' : '<span style="color: var(--text-muted)">○</span>'}</td>
          <td>${row.ETH ? '<span class="badge badge-bull">● ACTIVE</span>' : '<span style="color: var(--text-muted)">○</span>'}</td>
          <td>${row.SOL ? '<span class="badge badge-warn">● ACTIVE</span>' : '<span style="color: var(--text-muted)">○</span>'}</td>
          <td>${row.XRP ? '<span class="badge badge-warn">● ACTIVE</span>' : '<span style="color: var(--text-muted)">○</span>'}</td>
          <td>${row.ADA ? '<span class="badge badge-bear">● ACTIVE</span>' : '<span style="color: var(--text-muted)">○</span>'}</td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>

      <!-- Watchlist -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>👀</span> Asset Watchlist</div>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Asset</th>
                <th>Mark Price</th>
                <th>24h Change</th>
                <th>24h Volume (USD)</th>
                <th>ATR Volatility</th>
                <th>Regime</th>
                <th>Strategy Signal</th>
                <th>Signal Reason</th>
              </tr>
            </thead>
            <tbody>
    `;

    watchlist.forEach(w => {
      html += `
        <tr>
          <td><b>${w.symbol}</b></td>
          <td>${w.name}</td>
          <td class="mono">$${w.price.toFixed(2)}</td>
          <td class="mono ${w.change_24h_pct >= 0 ? 'bull' : 'bear'}">${w.change_24h_pct >= 0 ? '+' : ''}${w.change_24h_pct.toFixed(2)}%</td>
          <td class="mono">$${(w.volume_24h_usd / 1e6).toFixed(2)}M</td>
          <td class="mono">${w.atr_volatility_pct.toFixed(2)}%</td>
          <td><span class="badge ${w.regime.includes('BULL') ? 'badge-bull' : (w.regime.includes('BEAR') ? 'badge-bear' : 'badge-neutral')}">${w.regime}</span></td>
          <td><span class="badge ${w.current_signal === 'LONG' ? 'badge-bull' : 'badge-neutral'}">${w.current_signal}</span></td>
          <td style="font-size: 11px; color: var(--text-secondary);">${w.signal_reason}</td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }

  // -------------------------------------------------------------------------
  // 4. STRATEGIES & SIGNAL INSPECTOR
  // -------------------------------------------------------------------------
  async renderStrategies() {
    const container = document.getElementById('view-strategies');
    if (!container) return;

    const [stratRes, inspectRes] = await Promise.all([
      API.getStrategies().catch(() => ({ strategies: [] })),
      API.inspectSignal('structure_v2b', 'ETH/USDT:USDT').catch(() => ({}))
    ]);

    const strategies = stratRes.strategies || [];
    const inspect = inspectRes;

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>🧠</span> Strategy Center & Signal Inspector</div>
          <div class="view-subtitle">Inspect registered strategy plugins, parameters, and causal signal evaluations</div>
        </div>
      </div>

      <!-- Strategy Signal Inspector -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>🔬</span> Causal Signal Inspector: ${inspect.strategy_id || 'structure_v2b'} (${inspect.symbol || 'ETH/USDT:USDT'})</div>
          <span class="badge badge-bull">CONFIDENCE: ${inspect.confidence || 82}%</span>
        </div>
        <div style="padding: 14px;">
          <div style="margin-bottom: 12px; font-size: 12px;">
            <b>Generated Signal:</b> <span class="badge badge-bull">${inspect.signal || 'LONG'}</span>
            <span style="margin-left: 12px; color: var(--text-muted);">Conclusion: ${inspect.conclusion || ''}</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Factor</th>
                <th>Requirement</th>
                <th>Observed Condition</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
    `;

    (inspect.evaluations || []).forEach(ev => {
      html += `
        <tr>
          <td><b>${ev.factor}</b></td>
          <td class="mono">${ev.requirement}</td>
          <td class="mono">${ev.observed}</td>
          <td><span class="badge ${ev.pass ? 'badge-bull' : 'badge-bear'}">${ev.pass ? 'PASS' : 'FAIL'}</span></td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>

      <!-- Strategy Catalog -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>📚</span> Registered Strategy Plugins</div>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Strategy ID</th>
                <th>Name</th>
                <th>Version</th>
                <th>Timeframe</th>
                <th>Long / Short</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
    `;

    strategies.forEach(s => {
      html += `
        <tr>
          <td><b>${s.strategy_id}</b></td>
          <td>${s.name}</td>
          <td class="mono">${s.version}</td>
          <td class="mono">${s.supported_timeframes.join(', ')}</td>
          <td>${s.supports_long ? 'LONG' : ''} ${s.supports_short ? '/ SHORT' : ''}</td>
          <td><span class="badge badge-bull">VERIFIED</span></td>
          <td>
            <button class="btn btn-sm" onclick="window.app.inspectStrategyDetails('${s.strategy_id}')">Inspect</button>
          </td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }

  async inspectStrategyDetails(stratId) {
    try {
      const details = await API.inspectStrategy(stratId);
      alert(`Strategy ${details.name} (v${details.version})\n\nDescription: ${details.description}\n\nParameters: ${JSON.stringify(details.parameters, null, 2)}`);
    } catch (err) {
      Toast.error("Failed to inspect strategy: " + err.message);
    }
  }

  // -------------------------------------------------------------------------
  // 5. RESEARCH & BACKTEST LAB
  // -------------------------------------------------------------------------
  async renderResearch() {
    const container = document.getElementById('view-research');
    if (!container) return;

    const expRes = await API.getExperiments().catch(() => ({ experiments: [] }));
    const experiments = expRes.experiments || [];

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>🧪</span> Research & Backtesting Lab</div>
          <div class="view-subtitle">Deterministic causal replay, cost model validation & multi-model comparison</div>
        </div>
      </div>

      <!-- Interactive Backtest Execution Form -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>⚙️</span> Launch New Quantitative Backtest</div>
        </div>
        <div style="padding: 16px;">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 14px;">
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Strategy</label>
              <select id="bt-strategy" class="cmd-input" style="padding: 6px; border: 1px solid var(--border-subtle); border-radius: 4px;">
                <option value="structure_v2b">structure_v2b (Structure & Order Blocks)</option>
                <option value="pullback_v2a">pullback_v2a (Trend Pullback)</option>
                <option value="hybrid_v2c">hybrid_v2c (Hybrid Multi-Timeframe)</option>
                <option value="atr_v1">atr_v1 (ATR Adaptive Stop)</option>
                <option value="baseline_v0">baseline_v0 (Baseline)</option>
              </select>
            </div>
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Initial Capital ($)</label>
              <input type="number" id="bt-capital" class="cmd-input" style="padding: 6px; border: 1px solid var(--border-subtle); border-radius: 4px;" value="1000">
            </div>
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Fee Model</label>
              <input type="text" id="bt-fee" class="cmd-input" style="padding: 6px; border: 1px solid var(--border-subtle); border-radius: 4px;" value="0.05% Taker / 0.02% Maker" disabled>
            </div>
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Slippage Model</label>
              <input type="text" id="bt-slippage" class="cmd-input" style="padding: 6px; border: 1px solid var(--border-subtle); border-radius: 4px;" value="0.05% Adverse" disabled>
            </div>
          </div>
          <button class="btn btn-primary" id="btn-run-backtest">▶ RUN DETERMINISTIC BACKTEST</button>
        </div>
      </div>

      <!-- Backtest Result Card (populated after run) -->
      <div id="bt-result-box" style="display: none; margin-bottom: 16px;"></div>

      <!-- Multi-Model Revalidation Comparison Matrix -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>📊</span> Multi-Model Revalidation Comparison Matrix</div>
          <span style="font-size: 11px; color: var(--text-muted);">Strict Out-Of-Sample Data Partitioning</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Experiment ID</th>
                <th>Model Type</th>
                <th>Total Trades</th>
                <th>Win Rate</th>
                <th>Profit Factor</th>
                <th>Expectancy</th>
                <th>Net PnL</th>
                <th>Max DD</th>
                <th>Partition</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
    `;

    experiments.forEach(e => {
      const m = e.metrics || {};
      html += `
        <tr>
          <td><b>${e.experiment_id}</b></td>
          <td>${(e.metadata || {}).strategy_id || 'quantitative'}</td>
          <td class="mono">${m.total_trades || 'N/A'}</td>
          <td class="mono">${m.win_rate ? m.win_rate.toFixed(1) + '%' : 'N/A'}</td>
          <td class="mono">${m.profit_factor ? m.profit_factor.toFixed(2) : 'N/A'}</td>
          <td class="mono">${m.expectancy_usd ? '$' + m.expectancy_usd.toFixed(2) : 'N/A'}</td>
          <td class="mono ${(m.net_pnl_usd || 0) >= 0 ? 'bull' : 'bear'}">${m.net_pnl_usd ? (m.net_pnl_usd >= 0 ? '+' : '') + '$' + m.net_pnl_usd.toFixed(2) : 'N/A'}</td>
          <td class="mono" style="color: var(--color-bear);">${m.max_drawdown_pct ? m.max_drawdown_pct.toFixed(2) + '%' : 'N/A'}</td>
          <td><span class="badge badge-info">OUT-OF-SAMPLE</span></td>
          <td><button class="btn btn-sm" onclick="window.app.inspectExperiment('${e.experiment_id}')">Details</button></td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;

    document.getElementById('btn-run-backtest').addEventListener('click', async () => {
      const strat = document.getElementById('bt-strategy').value;
      const capital = document.getElementById('bt-capital').value;
      Toast.info(`Simulating deterministic replay for ${strat}...`);

      try {
        const res = await API.runBacktest({ strategy_id: strat, initial_capital: capital });
        Toast.success("Backtest replay completed!");
        const resBox = document.getElementById('bt-result-box');
        resBox.style.display = 'block';
        resBox.innerHTML = `
          <div class="stat-card" style="border: 1px solid var(--color-brand);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
              <div style="font-weight: 700; font-size: 13px;">Backtest Run: ${res.run_id} (${res.strategy_id})</div>
              <span class="badge badge-bull">OUT-OF-SAMPLE VERIFIED</span>
            </div>
            <div class="grid-cards" style="margin-bottom: 0;">
              <div><span class="stat-card-label">Total Trades</span><div class="stat-card-value">${res.total_trades}</div></div>
              <div><span class="stat-card-label">Win Rate</span><div class="stat-card-value">${res.win_rate}%</div></div>
              <div><span class="stat-card-label">Profit Factor</span><div class="stat-card-value">${res.profit_factor}</div></div>
              <div><span class="stat-card-label">Expectancy</span><div class="stat-card-value">$${res.expectancy_usd}</div></div>
              <div><span class="stat-card-label">Net PnL</span><div class="stat-card-value bull">+$${res.net_pnl_usd} (+${res.net_pnl_pct}%)</div></div>
              <div><span class="stat-card-label">Max Drawdown</span><div class="stat-card-value bear">${res.max_drawdown_pct}%</div></div>
            </div>
          </div>
        `;
      } catch (err) {
        Toast.error("Backtest failed: " + err.message);
      }
    });
  }

  async inspectExperiment(expId) {
    try {
      const detail = await API.getExperimentDetail(expId);
      const metrics = detail.metrics || {};
      alert(`Experiment: ${expId}\n\nTrades: ${metrics.total_trades}\nWin Rate: ${metrics.win_rate}%\nProfit Factor: ${metrics.profit_factor}\nNet PnL: $${metrics.net_pnl_usd}\nMax Drawdown: ${metrics.max_drawdown_pct}%\n\nEquity Curve Points: ${detail.equity_curve.length}`);
    } catch (err) {
      Toast.error("Failed to inspect experiment: " + err.message);
    }
  }

  // -------------------------------------------------------------------------
  // 6. RISK CENTER
  // -------------------------------------------------------------------------
  async renderRisk() {
    const container = document.getElementById('view-risk');
    if (!container) return;

    const risk = await API.getRiskStatus().catch(() => ({}));
    const isStopActive = risk.emergency_stop_active;

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title">
            <span>🛡️</span> Risk Control Center
            <span class="badge ${isStopActive ? 'badge-bear' : 'badge-bull'}">${isStopActive ? 'STOPPED / LOCKED' : 'ARMED / PROTECTED'}</span>
          </div>
          <div class="view-subtitle">Independent capital protection, circuit breakers & hard risk invariants</div>
        </div>
        <div class="view-actions">
          ${isStopActive
            ? `<button class="btn btn-success btn-sm" id="btn-reset-risk-stop">🔓 Reset Emergency Lock</button>`
            : `<button class="btn btn-danger btn-sm" onclick="Modals.showEmergencyStopModal()">🚨 Trigger Emergency Kill Switch</button>`
          }
        </div>
      </div>

      <div class="grid-cards">
        <div class="stat-card">
          <div class="stat-card-label">Risk Per Trade</div>
          <div class="stat-card-value">${(risk.risk_per_trade_pct || {}).current || 1.5}%</div>
          <div class="stat-card-sub">Fixed Fractional ATR Sizing</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Daily Realized Loss</div>
          <div class="stat-card-value">${((risk.daily_loss || {}).current_pct || 0).toFixed(2)}%</div>
          <div class="stat-card-sub">Limit Cap: ${(risk.daily_loss || {}).limit_pct || 3.0}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Portfolio Drawdown</div>
          <div class="stat-card-value">${((risk.portfolio_drawdown || {}).current_pct || 0).toFixed(2)}%</div>
          <div class="stat-card-sub">Hard Breaker: ${(risk.portfolio_drawdown || {}).limit_pct || 15.0}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Total Capital Exposure</div>
          <div class="stat-card-value">${((risk.total_exposure || {}).current_pct || 0).toFixed(1)}%</div>
          <div class="stat-card-sub">Exposure Cap: ${(risk.total_exposure || {}).limit_pct || 80.0}%</div>
        </div>
      </div>

      <!-- Visual Risk Limits & Progress Gauges -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>📊</span> Live Exposure & Circuit Breaker Thresholds</div>
        </div>
        <div style="padding: 16px;">
    `;

    // Gauge 1: Daily Loss
    const dlPct = (risk.daily_loss || {}).current_pct || 0;
    const dlLim = (risk.daily_loss || {}).limit_pct || 3.0;
    const dlRatio = Math.min(100, (dlPct / dlLim) * 100);

    html += `
      <div class="risk-meter">
        <div class="risk-meter-header">
          <span><b>Daily Loss Meter:</b> ${dlPct.toFixed(2)}% of ${dlLim}% limit</span>
          <span class="mono">${dlRatio.toFixed(0)}% Utilized</span>
        </div>
        <div class="risk-meter-track">
          <div class="risk-meter-fill ${dlRatio > 80 ? 'fill-danger' : (dlRatio > 50 ? 'fill-warn' : 'fill-ok')}" style="width: ${dlRatio}%;"></div>
        </div>
      </div>
    `;

    // Gauge 2: Portfolio Drawdown
    const ddPct = (risk.portfolio_drawdown || {}).current_pct || 0;
    const ddLim = (risk.portfolio_drawdown || {}).limit_pct || 15.0;
    const ddRatio = Math.min(100, (ddPct / ddLim) * 100);

    html += `
      <div class="risk-meter">
        <div class="risk-meter-header">
          <span><b>Portfolio Drawdown Meter:</b> ${ddPct.toFixed(2)}% of ${ddLim}% breaker</span>
          <span class="mono">${ddRatio.toFixed(0)}% Utilized</span>
        </div>
        <div class="risk-meter-track">
          <div class="risk-meter-fill ${ddRatio > 80 ? 'fill-danger' : (ddRatio > 50 ? 'fill-warn' : 'fill-ok')}" style="width: ${ddRatio}%;"></div>
        </div>
      </div>
    `;

    // Gauge 3: Total Exposure
    const expPct = (risk.total_exposure || {}).current_pct || 0;
    const expLim = (risk.total_exposure || {}).limit_pct || 80.0;
    const expRatio = Math.min(100, (expPct / expLim) * 100);

    html += `
      <div class="risk-meter">
        <div class="risk-meter-header">
          <span><b>Total Capital Exposure:</b> ${expPct.toFixed(1)}% of ${expLim}% cap</span>
          <span class="mono">${expRatio.toFixed(0)}% Utilized</span>
        </div>
        <div class="risk-meter-track">
          <div class="risk-meter-fill fill-ok" style="width: ${expRatio}%;"></div>
        </div>
      </div>
    `;

    html += `
        </div>
      </div>
    `;

    container.innerHTML = html;

    const btnReset = document.getElementById('btn-reset-risk-stop');
    if (btnReset) {
      btnReset.addEventListener('click', async () => {
        try {
          await API.resetEmergencyStop();
          Toast.success("Emergency stop cleared. RiskEngine re-armed.");
          this.refreshAll();
        } catch (err) {
          Toast.error("Failed to reset lock: " + err.message);
        }
      });
    }
  }

  // -------------------------------------------------------------------------
  // 6.5. AUTONOMOUS TRADING CENTER & TRADING PROFILES
  // -------------------------------------------------------------------------
  async renderAutonomous(isLightweight = false) {
    const container = document.getElementById('view-autonomous');
    if (!container) return;

    const [profilesRes, engineRes, tracesRes, sessionsRes, positionsRes] = await Promise.all([
      API.getTradingProfiles().catch(() => ({ profiles: [] })),
      API.getEngineStatus().catch(() => ({ engine_running: false, running_profiles: [] })),
      API.getEngineTraces().catch(() => ({ traces: [] })),
      API.getEngineSessions().catch(() => ({ sessions: [] })),
      API.getPositions().catch(() => ({ positions: [] }))
    ]);

    const profiles = profilesRes.profiles || [];
    const engine = engineRes || {};
    const traces = tracesRes.traces || [];
    const sessions = sessionsRes.sessions || [];
    const positions = positionsRes.positions || [];

    const runningCount = profiles.filter(p => p.is_running).length;
    const isEngineActive = engine.engine_running;

    // Profiles HTML
    let profilesHtml = '';
    if (profiles.length === 0) {
      profilesHtml = `
        <div class="empty-state" style="grid-column: 1 / -1; padding: 40px; text-align: center; background: var(--color-surface); border: 1px dashed var(--color-border); border-radius: 8px;">
          <div style="font-size: 32px; margin-bottom: 8px;">🚀</div>
          <div style="font-weight: 700; color: var(--color-text-primary); margin-bottom: 4px;">No Trading Profiles Configured</div>
          <div style="font-size: 12px; color: var(--color-text-muted); margin-bottom: 16px;">Create your first Autonomous Trading Profile using Strategy, AI Agent, or Hybrid mode.</div>
          <button class="btn btn-primary" id="btn-create-profile-empty">Create Trading Profile</button>
        </div>
      `;
    } else {
      profilesHtml = profiles.map(p => {
        let modeBadge = '';
        let modeDetails = '';

        if (p.decision_mode === 'strategy') {
          modeBadge = `<span class="badge" style="background: rgba(69, 255, 202, 0.15); color: var(--color-primary); border: 1px solid var(--color-primary);">🧠 Strategy Template</span>`;
          modeDetails = `<div>Template: <b>${p.strategy_id || 'hybrid_v2c'}</b></div>`;
        } else if (p.decision_mode === 'ai_agent') {
          modeBadge = `<span class="badge" style="background: rgba(214, 123, 255, 0.15); color: var(--color-accent-purple); border: 1px solid var(--color-accent-purple);">🤖 AI Agent</span>`;
          modeDetails = `<div>Agent: <b>${p.agent_id || 'trader-paper'}</b></div>`;
        } else {
          modeBadge = `<span class="badge" style="background: rgba(255, 182, 217, 0.15); color: var(--color-accent-pink); border: 1px solid var(--color-accent-pink);">⚡ Hybrid (Filter + AI)</span>`;
          modeDetails = `<div>Filter: <b>${p.strategy_id}</b> | Agent: <b>${p.agent_id}</b></div>`;
        }

        const isRunning = !!p.is_running;
        const statusBadge = isRunning
          ? `<span class="badge badge-bull" style="display: flex; align-items: center; gap: 4px;"><span class="health-dot ok"></span> RUNNING</span>`
          : `<span class="badge" style="background: rgba(255, 255, 255, 0.05); color: var(--color-text-muted);">⏹ STOPPED</span>`;

        return `
          <div class="card" style="border: 1px solid ${isRunning ? 'var(--color-primary)' : 'var(--color-border)'};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
              <div>
                <div style="font-weight: 700; font-size: 14px; color: var(--color-text-primary); margin-bottom: 2px;">${p.name}</div>
                <div style="font-size: 11px; color: var(--color-text-muted);">${p.symbol} • <b>${p.timeframe}</b></div>
              </div>
              <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                ${statusBadge}
                ${modeBadge}
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 11px; background: rgba(0,0,0,0.25); padding: 8px; border-radius: 4px; margin-bottom: 12px;">
              ${modeDetails}
              <div>Risk Profile: <b style="text-transform: capitalize;">${p.risk_profile}</b></div>
              <div>Execution: <b style="color: var(--color-secondary);">${p.execution_mode.toUpperCase()}</b></div>
              <div>Max Pos: <b>${p.max_open_positions}</b> | Daily Max: <b>${p.max_trades_per_day}</b></div>
              <div>SL: <b>${p.stop_loss_pct}%</b> | TP: <b>${p.take_profit_pct}%</b></div>
              <div>Last Candle: <span style="font-family: monospace; font-size: 10px; color: var(--color-text-muted);">${p.last_processed_candle ? p.last_processed_candle.slice(-8) : 'Waiting'}</span></div>
            </div>

            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              ${isRunning
                ? `
                  <button class="btn btn-sm btn-warn btn-prof-pause" data-id="${p.profile_id}">⏸ Pause</button>
                  <button class="btn btn-sm btn-danger btn-prof-stop" data-id="${p.profile_id}">⏹ Stop</button>
                  <button class="btn btn-sm btn-prof-trigger" data-id="${p.profile_id}" title="Force immediate candle evaluation tick">⚡ Trigger Tick</button>
                `
                : `
                  <button class="btn btn-sm btn-primary btn-prof-start" data-id="${p.profile_id}">▶️ Start</button>
                  <button class="btn btn-sm btn-prof-trigger" data-id="${p.profile_id}" title="Run test evaluation tick">⚡ Test Tick</button>
                `
              }
              <button class="btn btn-sm btn-prof-edit" data-id="${p.profile_id}">✏️ Edit</button>
              <button class="btn btn-sm btn-prof-delete" data-id="${p.profile_id}" style="color: var(--color-danger);">🗑️</button>
            </div>
          </div>
        `;
      }).join('');
    }

    // Traces HTML
    let tracesRows = '';
    if (traces.length === 0) {
      tracesRows = `<tr><td colspan="7" style="text-align: center; color: var(--color-text-muted); padding: 20px;">No decision traces recorded yet. Active profiles will log traces on each candle close.</td></tr>`;
    } else {
      tracesRows = traces.slice(0, 15).map(t => {
        let statusBadge = '<span class="badge">ABSTAINED</span>';
        if (t.execution_status === 'EXECUTED') statusBadge = '<span class="badge badge-bull">EXECUTED</span>';
        else if (t.execution_status === 'REJECTED') statusBadge = '<span class="badge badge-bear">REJECTED</span>';

        return `
          <tr>
            <td style="font-size: 11px; color: var(--color-text-muted);">${t.decision_timestamp || 'N/A'}</td>
            <td><b>${t.symbol}</b> <span style="font-size: 10px; color: var(--color-text-muted);">${t.timeframe}</span></td>
            <td><span class="badge" style="text-transform: capitalize;">${t.decision_mode}</span></td>
            <td>${t.strategy_signal || 'N/A'}</td>
            <td>${t.ai_decision ? `${t.ai_decision} (${Math.round((t.ai_confidence || 0) * 100)}%)` : 'N/A'}</td>
            <td>${statusBadge}</td>
            <td>
              <button class="btn btn-sm btn-inspect-trace" data-id="${t.trace_id}">Inspect</button>
            </td>
          </tr>
        `;
      }).join('');
    }

    const html = `
      <div class="view-header">
        <div>
          <div class="view-title">
            <span>🚀</span> Autonomous Trading Center
            <span class="badge ${isEngineActive ? 'badge-bull' : 'badge-neutral'}">
              <span class="health-dot ${isEngineActive ? 'ok' : 'warn'}"></span>
              ${isEngineActive ? 'ENGINE ACTIVE' : 'ENGINE IDLE'}
            </span>
          </div>
          <div class="view-subtitle">Continuous multi-profile autonomous trading across Strategy Templates, AI Agents, and Hybrid Mode.</div>
        </div>
        <div class="view-actions">
          <button class="btn" id="btn-refresh-autonomous">🔄 Refresh</button>
          <button class="btn btn-primary" id="btn-create-profile">+ Create Trading Profile</button>
        </div>
      </div>

      <!-- Telemetry Metric Cards -->
      <div class="metrics-grid" style="margin-bottom: 20px;">
        <div class="stat-card">
          <div class="stat-label">Running Profiles</div>
          <div class="stat-value bull">${runningCount} <span style="font-size: 12px; color: var(--color-text-muted);">/ ${profiles.length} total</span></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Engine Worker State</div>
          <div class="stat-value ${isEngineActive ? 'bull' : 'warn'}">${isEngineActive ? 'ONLINE' : 'STANDBY'}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Protected Open Positions</div>
          <div class="stat-value">${positions.length}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Risk & Safety Gate</div>
          <div class="stat-value bull">${this.systemStatus.safety_status || 'PAPER_SAFE'}</div>
        </div>
      </div>

      <!-- Profiles Grid -->
      <div style="margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="font-size: 14px; font-weight: 700; color: var(--color-text-primary); margin: 0;">Configured Trading Profiles</h3>
          <span style="font-size: 11px; color: var(--color-text-muted);">Candle Boundary: Strictly Closed Bars (No Future Leakage)</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px;">
          ${profilesHtml}
        </div>
      </div>

      <!-- Causal Decision Traces -->
      <div class="card" style="margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <div style="font-weight: 700; font-size: 13px; color: var(--color-text-primary);">Autonomous Decision Traces & Telemetry</div>
            <div style="font-size: 11px; color: var(--color-text-muted);">Causal audit trail from Market Data → Strategy/AI → Policy → RiskEngine → Execution</div>
          </div>
        </div>
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Decision Timestamp</th>
                <th>Pair / TF</th>
                <th>Decision Mode</th>
                <th>Strategy Signal</th>
                <th>AI Decision</th>
                <th>Outcome</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${tracesRows}
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Attach Event Listeners
    const btnCreate = document.getElementById('btn-create-profile');
    if (btnCreate) btnCreate.addEventListener('click', () => Modals.showProfileModal(null, () => this.renderAutonomous()));

    const btnCreateEmpty = document.getElementById('btn-create-profile-empty');
    if (btnCreateEmpty) btnCreateEmpty.addEventListener('click', () => Modals.showProfileModal(null, () => this.renderAutonomous()));

    const btnRefresh = document.getElementById('btn-refresh-autonomous');
    if (btnRefresh) btnRefresh.addEventListener('click', () => this.renderAutonomous());

    // Profile Actions: Start / Pause / Stop / Trigger / Edit / Delete
    container.querySelectorAll('.btn-prof-start').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        try {
          await API.startTradingProfile(id);
          Toast.success("Trading profile activated and running in background!");
          this.renderAutonomous();
        } catch (err) {
          Toast.error("Failed to start profile: " + err.message);
        }
      });
    });

    container.querySelectorAll('.btn-prof-pause').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        try {
          await API.pauseTradingProfile(id);
          Toast.info("Profile execution paused.");
          this.renderAutonomous();
        } catch (err) {
          Toast.error("Failed to pause profile: " + err.message);
        }
      });
    });

    container.querySelectorAll('.btn-prof-stop').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        try {
          await API.stopTradingProfile(id);
          Toast.info("Profile stopped cleanly.");
          this.renderAutonomous();
        } catch (err) {
          Toast.error("Failed to stop profile: " + err.message);
        }
      });
    });

    container.querySelectorAll('.btn-prof-trigger').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        Toast.info("Running evaluation tick on profile...");
        try {
          const res = await API.triggerProfileTick(id);
          Toast.success(`Evaluation outcome: ${res.status || 'OK'}`);
          this.renderAutonomous();
        } catch (err) {
          Toast.error("Evaluation tick error: " + err.message);
        }
      });
    });

    container.querySelectorAll('.btn-prof-edit').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const p = profiles.find(item => item.profile_id === id);
        if (p) Modals.showProfileModal(p, () => this.renderAutonomous());
      });
    });

    container.querySelectorAll('.btn-prof-delete').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        if (confirm("Are you sure you want to delete this trading profile?")) {
          try {
            await API.deleteTradingProfile(id);
            Toast.success("Profile deleted.");
            this.renderAutonomous();
          } catch (err) {
            Toast.error("Failed to delete profile: " + err.message);
          }
        }
      });
    });

    // Trace Inspection Modal
    container.querySelectorAll('.btn-inspect-trace').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const trace = traces.find(t => t.trace_id === id);
        if (trace) Modals.showAutonomousTraceModal(trace);
      });
    });
  }

  // -------------------------------------------------------------------------
  // 7. AGENT CENTER & SESSIONS
  // -------------------------------------------------------------------------
  async renderAgents() {
    const container = document.getElementById('view-agents');
    if (!container) return;

    const [agentsRes, sessRes, aiRes, mcpRes] = await Promise.all([
      API.getAgents().catch(() => ({ agents: [] })),
      API.getSessions().catch(() => ({ sessions: [] })),
      API.getAiConfig().catch(() => ({})),
      API.getMcpTools().catch(() => ({ tools: [] }))
    ]);

    const agents = agentsRes.agents || [];
    const sessions = sessRes.sessions || [];
    const aiConfig = aiRes || {};
    const mcpTools = mcpRes.tools || [];

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>🤖</span> AI Agent Center, MCP Protocol & LLM Configuration</div>
          <div class="view-subtitle">Autonomous trading sessions, model providers, dynamic MCP tools & watchdog health</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-primary btn-sm" id="btn-create-session">▶ Start New Paper Session</button>
        </div>
      </div>

      <!-- Active Sessions -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>⚡</span> Active Trading Sessions</div>
          <span style="font-size: 11px; color: var(--text-muted);">Watchdog & Error Budget Enforced</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Session ID</th>
                <th>Agent ID</th>
                <th>Mode</th>
                <th>Lifecycle State</th>
                <th>Trades / Max</th>
                <th>Error Budget</th>
                <th>Heartbeat</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
    `;

    if (sessions.length === 0) {
      html += `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 16px;">No trading sessions active.</td></tr>`;
    } else {
      sessions.forEach(s => {
        let stBadge = 'badge-neutral';
        if (s.state === 'RUNNING') stBadge = 'badge-bull';
        if (s.state === 'PAUSED') stBadge = 'badge-warn';
        if (s.state === 'STOPPED' || s.state === 'FAILED') stBadge = 'badge-bear';

        html += `
          <tr>
            <td class="mono"><b>${s.session_id}</b></td>
            <td>${s.agent_id}</td>
            <td><span class="badge badge-paper">${s.mode}</span></td>
            <td><span class="badge ${stBadge}">${s.state}</span></td>
            <td class="mono">${s.trade_count} / ${s.max_trades}</td>
            <td class="mono">${s.error_count} / ${s.error_budget}</td>
            <td style="font-size: 11px;">${s.last_heartbeat ? s.last_heartbeat.substr(11, 8) + ' UTC' : 'Active'}</td>
            <td>
              ${s.state === 'RUNNING'
                ? `<button class="btn btn-sm" onclick="window.app.controlSession('${s.session_id}', 'pause')">Pause</button>
                   <button class="btn btn-danger btn-sm" onclick="window.app.controlSession('${s.session_id}', 'stop')">Stop</button>`
                : (s.state === 'PAUSED'
                  ? `<button class="btn btn-sm btn-primary" onclick="window.app.controlSession('${s.session_id}', 'resume')">Resume</button>
                     <button class="btn btn-danger btn-sm" onclick="window.app.controlSession('${s.session_id}', 'stop')">Stop</button>`
                  : `<span style="color: var(--text-muted);">Ended</span>`)
              }
            </td>
          </tr>
        `;
      });
    }

    html += `
            </tbody>
          </table>
        </div>
      </div>

      <!-- AI Provider & API Key Configuration -->
      <div class="table-panel" style="margin-top: 16px;">
        <div class="panel-header">
          <div class="panel-title"><span style="color: var(--color-accent-purple);">🧠</span> AI Model Provider & Inference Endpoint</div>
          <span class="badge badge-purple">${aiConfig.enabled ? 'AI LAYER ACTIVE' : 'DETERMINISTIC MODE'}</span>
        </div>
        <div style="padding: 16px;">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 16px;">
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Provider</label>
              <select id="ai-provider-select" class="btn btn-sm" style="width: 100%; background: var(--bg-surface-3); color: var(--text-primary); text-align: left;">
                <option value="gemini" ${aiConfig.provider === 'gemini' ? 'selected' : ''}>Google Gemini (Official REST)</option>
                <option value="antigravity" ${aiConfig.provider === 'antigravity' ? 'selected' : ''}>Antigravity Agent Copilot</option>
                <option value="openai" ${aiConfig.provider === 'openai' ? 'selected' : ''}>OpenAI Compatible</option>
                <option value="anthropic" ${aiConfig.provider === 'anthropic' ? 'selected' : ''}>Anthropic Claude</option>
                <option value="mock" ${aiConfig.provider === 'mock' ? 'selected' : ''}>Mock / Offline Deterministic</option>
              </select>
            </div>
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Model Identifier</label>
              <input id="ai-model-input" type="text" class="btn btn-sm mono" style="width: 100%; background: var(--bg-surface-3); color: var(--text-primary); text-align: left;" value="${aiConfig.model_name || 'gemini-2.5-flash'}" placeholder="e.g. gemini-2.5-flash">
            </div>
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">API Key / Agent Token</label>
              <input id="ai-key-input" type="password" class="btn btn-sm mono" style="width: 100%; background: var(--bg-surface-3); color: var(--text-primary); text-align: left;" placeholder="${aiConfig.api_key_masked ? 'Configured: ' + aiConfig.api_key_masked : 'Enter API Key (cnms_agent_... or AIza...)'}">
            </div>
            <div>
              <label style="display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Inference Mode</label>
              <select id="ai-mode-select" class="btn btn-sm" style="width: 100%; background: var(--bg-surface-3); color: var(--text-primary); text-align: left;">
                <option value="regime_context" ${aiConfig.mode === 'regime_context' ? 'selected' : ''}>Regime & Macro Bias Context</option>
                <option value="advisory" ${aiConfig.mode === 'advisory' ? 'selected' : ''}>Advisory Signal Validation</option>
                <option value="autonomous_paper" ${aiConfig.mode === 'autonomous_paper' ? 'selected' : ''}>Autonomous Paper Trading</option>
              </select>
            </div>
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; border-top: 1px solid var(--border-subtle); padding-top: 12px;">
            <div style="display: flex; align-items: center; gap: 12px;">
              <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 12px;">
                <input id="ai-enabled-chk" type="checkbox" ${aiConfig.enabled ? 'checked' : ''}>
                <b>Enable AI Intelligence Layer</b>
              </label>
              <span id="ai-test-result" style="font-size: 11px; color: var(--text-muted);"></span>
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-sm" id="btn-test-ai">⚡ Test Connection</button>
              <button class="btn btn-primary btn-sm" id="btn-save-ai">💾 Save AI Configuration</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Dynamic MCP Tools Discovery -->
      <div class="table-panel" style="margin-top: 16px;">
        <div class="panel-header">
          <div class="panel-title"><span style="color: var(--color-accent-purple);">🔌</span> Model Context Protocol (MCP) Registered Tools (${mcpTools.length})</div>
          <span style="font-size: 11px; color: var(--text-muted);">Port :8889 / /mcp JSON-RPC 2.0</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Tool Name</th>
                <th>Description</th>
                <th>Required Permission</th>
                <th>Input Schema Properties</th>
              </tr>
            </thead>
            <tbody>
    `;

    if (mcpTools.length === 0) {
      html += `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 16px;">No MCP tools registered.</td></tr>`;
    } else {
      mcpTools.forEach(t => {
        const props = Object.keys(t.inputSchema?.properties || {}).join(', ') || 'None';
        html += `
          <tr>
            <td class="mono" style="color: var(--color-accent-purple);"><b>${t.name}</b></td>
            <td>${t.description}</td>
            <td><span class="badge badge-paper">${t.name.startsWith('place_') || t.name.startsWith('cancel_') ? 'TRADE_EXECUTE' : 'MARKET_READ'}</span></td>
            <td class="mono" style="font-size: 11px; color: var(--text-secondary);">${props}</td>
          </tr>
        `;
      });
    }

    html += `
            </tbody>
          </table>
        </div>
      </div>

      <!-- Registered Agents -->
      <div class="table-panel" style="margin-top: 16px;">
        <div class="panel-header">
          <div class="panel-title"><span>👥</span> Registered AI Identities (${agents.length})</div>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Agent ID</th>
                <th>Role</th>
                <th>Environment</th>
                <th>Status</th>
                <th>Permissions</th>
                <th>Heartbeat</th>
              </tr>
            </thead>
            <tbody>
    `;

    agents.forEach(a => {
      html += `
        <tr>
          <td><b>${a.agent_id}</b></td>
          <td>${a.role}</td>
          <td><span class="badge badge-paper">${a.environment}</span></td>
          <td><span class="badge badge-bull">${a.status}</span></td>
          <td class="mono" style="font-size: 11px;">${(a.permissions || []).join(', ')}</td>
          <td style="font-size: 11px;">${a.heartbeat}</td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Bind Session Button
    const btnCreate = document.getElementById('btn-create-session');
    if (btnCreate) {
      btnCreate.addEventListener('click', async () => {
        try {
          await API.createPaperSession('antigravity-agent', 7200, 20);
          Toast.success("New PAPER session started cleanly!");
          this.refreshAll();
        } catch (err) {
          Toast.error("Failed to start session: " + err.message);
        }
      });
    }

    // Bind Test Connection Button
    const btnTestAi = document.getElementById('btn-test-ai');
    if (btnTestAi) {
      btnTestAi.addEventListener('click', async () => {
        const prov = document.getElementById('ai-provider-select').value;
        const model = document.getElementById('ai-model-input').value;
        const key = document.getElementById('ai-key-input').value;
        const statusEl = document.getElementById('ai-test-result');
        if (statusEl) statusEl.textContent = 'Testing connection...';
        btnTestAi.disabled = true;

        try {
          const res = await API.testAiConnection({ provider: prov, model_name: model, api_key: key });
          if (res.status === 'CONNECTED') {
            Toast.success(`AI Connected: ${res.model} (${res.latency_ms}ms)`);
            if (statusEl) statusEl.innerHTML = `<span style="color: var(--color-primary);">✔ Connected (${res.latency_ms}ms)</span>`;
          } else {
            Toast.warn(res.message);
            if (statusEl) statusEl.innerHTML = `<span style="color: var(--color-warning);">⚠ ${res.message}</span>`;
          }
        } catch (err) {
          Toast.error("Test failed: " + err.message);
          if (statusEl) statusEl.innerHTML = `<span style="color: var(--color-danger);">✖ ${err.message}</span>`;
        } finally {
          btnTestAi.disabled = false;
        }
      });
    }

    // Bind Save AI Config Button
    const btnSaveAi = document.getElementById('btn-save-ai');
    if (btnSaveAi) {
      btnSaveAi.addEventListener('click', async () => {
        const prov = document.getElementById('ai-provider-select').value;
        const model = document.getElementById('ai-model-input').value;
        const key = document.getElementById('ai-key-input').value;
        const mode = document.getElementById('ai-mode-select').value;
        const enabled = document.getElementById('ai-enabled-chk').checked;

        try {
          const payload = {
            provider: prov,
            model_name: model,
            mode: mode,
            enabled: enabled,
          };
          if (key) payload.api_key = key;

          await API.saveAiConfig(payload);
          Toast.success("AI Intelligence configuration saved & applied!");
          this.renderAgents();
        } catch (err) {
          Toast.error("Failed to save AI config: " + err.message);
        }
      });
    }
  }

  async controlSession(sessionId, action) {
    try {
      await API.manageSession(sessionId, action);
      Toast.info(`Session ${sessionId} -> ${action.toUpperCase()}`);
      this.refreshAll();
    } catch (err) {
      Toast.error("Action failed: " + err.message);
    }
  }

  // -------------------------------------------------------------------------
  // 8. CONFIGURATION CENTER
  // -------------------------------------------------------------------------
  async renderConfig() {
    const container = document.getElementById('view-config');
    if (!container) return;

    const [schemaRes, curRes] = await Promise.all([
      API.getConfigSchema().catch(() => ({})),
      API.getCurrentConfig().catch(() => ({}))
    ]);

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>⚙️</span> Configuration Center</div>
          <div class="view-subtitle">Dynamic typed configuration powered by JSON Schema & AI Copilot</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-primary btn-sm" onclick="Modals.showAiCopilotModal()">🤖 AI Assisted Config</button>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>📝</span> Active Configuration YAML Inspector</div>
          <button class="btn btn-sm btn-success" id="btn-save-config">Validate & Save</button>
        </div>
        <div style="padding: 16px;">
          <textarea id="config-raw-yaml" class="cmd-input mono" style="width: 100%; height: 320px; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 12px; font-size: 12px;">${JSON.stringify(curRes, null, 2)}</textarea>
        </div>
      </div>
    `;

    container.innerHTML = html;

    document.getElementById('btn-save-config').addEventListener('click', async () => {
      try {
        const parsed = JSON.parse(document.getElementById('config-raw-yaml').value);
        const valRes = await API.validateConfig(parsed);
        if (valRes.is_valid) {
          await API.saveConfig(parsed);
          Toast.success("Configuration validated and saved!");
        } else {
          Toast.error("Validation failed: " + (valRes.errors || []).join('; '));
        }
      } catch (err) {
        Toast.error("Invalid JSON/YAML: " + err.message);
      }
    });
  }

  // -------------------------------------------------------------------------
  // 9. DATA HEALTH & DATASETS
  // -------------------------------------------------------------------------
  async renderData() {
    const container = document.getElementById('view-data');
    if (!container) return;

    const res = await API.getDatasets().catch(() => ({ datasets: [] }));
    const datasets = res.datasets || [];

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>💾</span> Data Health & Provenance</div>
          <div class="view-subtitle">Market datasets, candle counts & cryptographic SHA256 integrity checks</div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>🗄️</span> Verified Historical Datasets</div>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Dataset Name</th>
                <th>Exchange</th>
                <th>Market Type</th>
                <th>Candles</th>
                <th>Timeframes</th>
                <th>SHA256 Fingerprint</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
    `;

    datasets.forEach(d => {
      html += `
        <tr>
          <td><b>${d.name}</b></td>
          <td>${d.exchange}</td>
          <td>${d.market_type}</td>
          <td class="mono">${d.candle_count}</td>
          <td class="mono">${(d.timeframes || []).join(', ')}</td>
          <td class="mono" style="font-size: 10px; color: var(--text-muted);">${d.sha256}</td>
          <td><span class="badge badge-bull">${d.status}</span></td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }

  // -------------------------------------------------------------------------
  // 10. SYSTEM EVENTS & AUDIT LOGS
  // -------------------------------------------------------------------------
  async renderLogs() {
    const container = document.getElementById('view-logs');
    if (!container) return;

    const res = await API.getEvents().catch(() => ({ events: [] }));
    const events = res.events || [];

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>📜</span> System Events & Decision Logs</div>
          <div class="view-subtitle">Filterable event timeline with correlation IDs and domain tags</div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>🔍</span> Chronological Event Feed</div>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Time</th>
                <th>Severity</th>
                <th>Domain</th>
                <th>Message</th>
                <th>Correlation ID</th>
              </tr>
            </thead>
            <tbody>
    `;

    events.forEach(ev => {
      let sevBadge = 'badge-info';
      if (ev.severity === 'WARNING') sevBadge = 'badge-warn';
      if (ev.severity === 'ERROR' || ev.severity === 'CRITICAL') sevBadge = 'badge-bear';

      html += `
        <tr>
          <td class="mono"><b>${ev.id}</b></td>
          <td style="font-size: 11px;">${ev.timestamp}</td>
          <td><span class="badge ${sevBadge}">${ev.severity}</span></td>
          <td><span class="badge badge-neutral">${ev.domain}</span></td>
          <td>${ev.message}</td>
          <td class="mono" style="font-size: 10px; color: var(--text-muted);">${ev.correlation_id}</td>
        </tr>
      `;
    });

    html += `
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }

  // -------------------------------------------------------------------------
  // 11. SETTINGS & TELEGRAM INTEGRATION
  // -------------------------------------------------------------------------
  async renderSettings() {
    const container = document.getElementById('view-settings');
    if (!container) return;

    const [settings, tgStatus] = await Promise.all([
      API.getSettings().catch(() => ({})),
      API.getTelegramStatus().catch(() => ({}))
    ]);

    let html = `
      <div class="view-header">
        <div>
          <div class="view-title"><span>⚙️</span> Settings & Integrations</div>
          <div class="view-subtitle">UI preferences, theme controls & Telegram notification center</div>
        </div>
      </div>

      <!-- Telegram Integration Section -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>📱</span> Telegram Bot Integration Center</div>
          <span class="badge ${tgStatus.is_configured ? 'badge-bull' : 'badge-warn'}">
            ${tgStatus.is_configured ? 'CONFIGURED' : 'NOT CONFIGURED'}
          </span>
        </div>
        <div style="padding: 16px;">
          <p style="color: var(--text-secondary); margin-bottom: 12px; font-size: 12px;">
            Dispatches instant alerts for Order Fills, Stop Loss / Take Profit hits, Risk Vetoes, and Emergency Stops.
          </p>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 14px;">
            <div>
              <span class="stat-card-label">Bot Token:</span>
              <div class="mono" style="font-size: 12px; color: var(--text-primary);">${tgStatus.bot_token_masked || 'None'}</div>
            </div>
            <div>
              <span class="stat-card-label">Chat ID:</span>
              <div class="mono" style="font-size: 12px; color: var(--text-primary);">${tgStatus.chat_id || 'None'}</div>
            </div>
            <div>
              <span class="stat-card-label">Alert Status:</span>
              <div>${tgStatus.enabled ? '<b class="bull">ENABLED</b>' : '<b class="warn">DISABLED</b>'}</div>
            </div>
          </div>
          <button class="btn btn-primary btn-sm" id="btn-test-telegram">🔔 Send Test Alert to Telegram</button>
        </div>
      </div>

      <!-- Application Preferences -->
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title"><span>🎨</span> Application Appearance & Refresh</div>
        </div>
        <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>Theme:</span>
            <select id="pref-theme" class="btn btn-sm" style="background: var(--bg-surface-2); color: #fff;">
              <option value="dark" ${settings.theme === 'dark' ? 'selected' : ''}>Dark (Trading Pro)</option>
              <option value="light" ${settings.theme === 'light' ? 'selected' : ''}>Light</option>
            </select>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>Timezone:</span>
            <span class="mono">UTC</span>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>Auto Refresh Rate:</span>
            <span class="mono">3000 ms</span>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    document.getElementById('btn-test-telegram').addEventListener('click', async () => {
      Toast.info("Sending test notification to Telegram...");
      try {
        const res = await API.sendTelegramTest();
        if (res.success) {
          Toast.success("Test notification delivered successfully!");
        } else {
          Toast.warn("Telegram response: " + (res.reason || res.error || "Check credentials"));
        }
      } catch (err) {
        Toast.error("Failed to send alert: " + err.message);
      }
    });

    document.getElementById('pref-theme').addEventListener('change', (e) => {
      document.body.className = e.target.value === 'light' ? 'theme-light' : '';
      Toast.info(`Theme switched to ${e.target.value}`);
    });
  }

  async runDoctorDiagnostics() {
    Toast.info("Running CUANIMUS system doctor diagnostics...");
    try {
      const res = await API.runDoctor();
      const checks = res.checks || [];
      const fails = checks.filter(c => c.status === 'FAIL');
      if (fails.length === 0) {
        Toast.success(`Doctor diagnostics: All ${checks.length} health checks PASSED!`);
      } else {
        Toast.error(`Doctor diagnostics: ${fails.length} checks failed!`);
      }
    } catch (err) {
      Toast.error("Doctor failed: " + err.message);
    }
  }

  async sendTelegramTest() {
    Toast.info("Dispatching Telegram test alert...");
    try {
      const res = await API.sendTelegramTest();
      if (res.success) {
        Toast.success("Telegram alert sent!");
      } else {
        Toast.warn("Telegram: " + (res.reason || res.error));
      }
    } catch (err) {
      Toast.error("Telegram error: " + err.message);
    }
  }
}

// Instantiate on load
window.addEventListener('DOMContentLoaded', () => {
  window.app = new CuanimusApp();
});
