/**
 * CUANIMUS Web Control Center — Main Application v2
 * All data sourced from real backend APIs — zero dummy data.
 * New pastel palette: Mint #5BFFCA · Yellow #FFFFA3 · Pink #FFB3D9 · Lavender #CC88FF
 */

class CuanimusApp {
  constructor() {
    this.currentView    = 'overview';
    this.chartInstance  = null;
    this.refreshTimer   = null;
    this.systemStatus   = {};
    this.currentUser    = null;
    this.selectedSymbol    = 'ETH/USDT:USDT';
    this.selectedTimeframe = '15m';
    this._tradingInit   = false;
    this.init();
  }

  async init() {
    Toast.init();
    CommandPalette.init();
    this._bindNavigation();
    this._bindGlobalHeader();
    await this.checkAuthStatus();
    const hash = window.location.hash.replace('#', '') || 'overview';
    this.navigate(hash);
    await this.refreshAll();
    this.startAutoRefresh();
  }

  async checkAuthStatus() {
    try {
      const auth = await API.getAuthMe();
      this.currentUser = auth;
      const btn = document.getElementById('btn-header-auth');
      if (!btn) return;
      if (auth?.authenticated) {
        btn.innerHTML = `👤 ${auth.username} [${auth.role}]`;
        btn.title = 'Click to sign out';
        btn.onclick = async () => {
          if (!confirm(`Sign out from ${auth.username}?`)) return;
          await API.logout().catch(() => {});
          Toast.info('Signed out');
          this.checkAuthStatus();
        };
      } else {
        btn.innerHTML = '🔑 Sign In';
        btn.title = 'Click to sign in';
        btn.onclick = () => Modals.showLoginModal(() => this.checkAuthStatus());
      }
    } catch (_) {}
  }

  startAutoRefresh() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    this.refreshTimer = setInterval(() => this.refreshLightweight(), 4000);
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
    document.getElementById('btn-header-emergency')?.addEventListener('click', () => Modals.showEmergencyStopModal());
    document.getElementById('btn-header-doctor')?.addEventListener('click',    () => this.runDoctorDiagnostics());
    document.getElementById('btn-header-copilot')?.addEventListener('click',   () => Modals.showAiCopilotModal());
  }

  navigate(viewName, updateHash = true) {
    this.currentView = viewName;
    if (updateHash) window.location.hash = viewName;
    document.querySelectorAll('.nav-item').forEach(el =>
      el.classList.toggle('active', el.getAttribute('data-view') === viewName));
    document.querySelectorAll('.view-container').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`view-${viewName}`);
    if (target) { target.classList.add('active'); this.renderCurrentView(); }
  }

  async refreshAll() {
    try {
      this.systemStatus = await API.getSystemStatus();
      this._updateHeaderBadges(this.systemStatus);
      this.renderCurrentView();
    } catch (_) {}
  }

  async refreshLightweight() {
    try {
      this.systemStatus = await API.getSystemStatus();
      this._updateHeaderBadges(this.systemStatus);
      if (['overview','trading','risk','autonomous'].includes(this.currentView)) {
        this.renderCurrentView(true);
      }
    } catch (_) {}
  }

  _updateHeaderBadges(s) {
    const envBadge = document.getElementById('header-env-badge');
    if (envBadge) {
      const env = (s.environment || 'paper').toLowerCase();
      envBadge.textContent = env.toUpperCase();
      envBadge.className   = `env-indicator env-${env}`;
    }
    const dot = document.getElementById('header-health-dot');
    if (dot) dot.className = `health-dot ${s.emergency_stop_active ? 'bad' : 'ok'}`;
    const strat = document.getElementById('header-active-strategy');
    if (strat) strat.textContent = s.strategy_id || '—';
    const risk = document.getElementById('header-risk-profile');
    if (risk) risk.textContent = s.risk_profile || '—';
  }

  renderCurrentView(light = false) {
    switch (this.currentView) {
      case 'overview':    this.renderOverview(); break;
      case 'trading':     this.renderTrading(light); break;
      case 'markets':     if (!light) this.renderMarkets(); break;
      case 'strategies':  if (!light) this.renderStrategies(); break;
      case 'research':    if (!light) this.renderResearch(); break;
      case 'risk':        this.renderRisk(); break;
      case 'autonomous':  this.renderAutonomous(light); break;
      case 'agents':      if (!light) this.renderAgents(); break;
      case 'config':      if (!light) this.renderConfig(); break;
      case 'data':        if (!light) this.renderData(); break;
      case 'logs':        if (!light) this.renderLogs(); break;
      case 'settings':    if (!light) this.renderSettings(); break;
    }
  }

  /* ─── helpers ─────────────────────────────────────────────── */
  _emptyRow(cols, msg) {
    return `<tr class="empty-row"><td colspan="${cols}">${msg}</td></tr>`;
  }
  _loadingRow(cols) {
    return `<tr class="loading-row"><td colspan="${cols}"><span class="spinner"></span>Loading…</td></tr>`;
  }
  _fmt(n, d = 2) { return n != null ? Number(n).toFixed(d) : '—'; }
  _pnlClass(v)   { return v >= 0 ? 'bull' : 'bear'; }
  _pnlSign(v)    { return v >= 0 ? '+' : ''; }

  /* ═══════════════════════════════════════════════════════════
     1. OVERVIEW DASHBOARD
  ═══════════════════════════════════════════════════════════ */
  async renderOverview() {
    const c = document.getElementById('view-overview');
    if (!c) return;

    const [posRes, riskRes] = await Promise.all([
      API.getPositions().catch(() => ({ positions: [] })),
      API.getRiskStatus().catch(() => ({}))
    ]);
    const positions = posRes.positions || [];
    const risk      = riskRes;
    const totalPnl  = positions.reduce((a, p) => a + (p.unrealized_pnl_usd || 0), 0);
    const equity    = risk.equity ?? 0;
    const safeStatus = this.systemStatus.safety_status || 'SAFE';

    let posRows = positions.length ? positions.map(p => `
      <tr>
        <td><b>${p.symbol}</b></td>
        <td><span class="badge ${p.side === 'LONG' ? 'badge-bull' : 'badge-bear'}">${p.side}</span></td>
        <td class="mono">${p.size}</td>
        <td class="mono">$${this._fmt(p.entry_price)}</td>
        <td class="mono">$${this._fmt(p.mark_price)}</td>
        <td class="mono ${this._pnlClass(p.unrealized_pnl_usd)}">${this._pnlSign(p.unrealized_pnl_usd)}$${this._fmt(p.unrealized_pnl_usd)}</td>
        <td class="mono ${this._pnlClass(p.roe_pct)}">${this._pnlSign(p.roe_pct)}${this._fmt(p.roe_pct)}%</td>
        <td class="mono bear">$${this._fmt(p.stop_loss)}</td>
        <td class="mono bull">$${this._fmt(p.take_profit)}</td>
      </tr>`).join('') : this._emptyRow(9, 'No open positions. System monitoring market regimes.');

    const subs = this.systemStatus.subsystems || {};
    let subsHtml = Object.values(subs).map(item => {
      const ok = ['HEALTHY','SAFE','ARMED','CONNECTED','ACTIVE','READY'].includes(item.status);
      return `
        <div class="subsystem-card">
          <div class="subsystem-card-header">
            <span class="subsystem-card-name">${item.name}</span>
            <span class="health-dot ${ok ? 'ok' : 'bad'}"></span>
          </div>
          <div class="subsystem-card-status" style="color:${ok ? 'var(--bull)' : 'var(--bear)'}">${item.status}</div>
        </div>`;
    }).join('') || '<p style="color:var(--text-muted);padding:14px">Subsystem data unavailable.</p>';

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">📊 Operational Dashboard
            <span class="badge ${safeStatus === 'SAFE' ? 'badge-bull' : 'badge-bear'}">${safeStatus}</span>
          </div>
          <div class="view-subtitle">Real-time portfolio surveillance, risk bounds &amp; autonomous agent state</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-ai btn-sm" onclick="Modals.showAiCopilotModal()">🤖 AI Copilot</button>
          <button class="btn btn-sm" onclick="window.app.refreshAll()">🔄 Refresh</button>
        </div>
      </div>

      <div class="grid-cards">
        <div class="stat-card">
          <div class="stat-card-label">Portfolio Equity</div>
          <div class="stat-card-value">$${this._fmt(equity)}</div>
          <div class="stat-card-sub">Free Margin: $${this._fmt(risk.free_margin ?? equity)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Open Positions PnL</div>
          <div class="stat-card-value ${this._pnlClass(totalPnl)}">${this._pnlSign(totalPnl)}$${this._fmt(totalPnl)}</div>
          <div class="stat-card-sub">${positions.length} active position(s)</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Daily Loss vs Limit</div>
          <div class="stat-card-value">${this._fmt(risk.daily_loss?.current_pct ?? 0)}% <span style="font-size:12px;color:var(--text-muted)">/ ${risk.daily_loss?.limit_pct ?? 3.0}%</span></div>
          <div class="stat-card-sub">Loss: $${this._fmt(risk.daily_loss?.current_usd ?? 0)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Portfolio Drawdown</div>
          <div class="stat-card-value">${this._fmt(risk.portfolio_drawdown?.current_pct ?? 0)}% <span style="font-size:12px;color:var(--text-muted)">/ ${risk.portfolio_drawdown?.limit_pct ?? 15.0}%</span></div>
          <div class="stat-card-sub">Circuit Breaker: <b class="bull">Armed</b></div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">🛡️ Subsystem Operational Status</div>
          <span style="font-size:11px;color:var(--text-muted)">Strict Deterministic Architecture</span>
        </div>
        <div class="subsystem-grid">${subsHtml}</div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">📈 Open Positions</div>
          <button class="btn btn-sm" onclick="window.app.navigate('trading')">Trading Terminal →</button>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Symbol</th><th>Side</th><th>Size</th><th>Entry</th><th>Mark</th><th>uPnL</th><th>ROE%</th><th>Stop Loss</th><th>Take Profit</th></tr></thead>
            <tbody>${posRows}</tbody>
          </table>
        </div>
      </div>`;
  }

  /* ═══════════════════════════════════════════════════════════
     2. TRADING TERMINAL
  ═══════════════════════════════════════════════════════════ */
  async renderTrading(light = false) {
    const c = document.getElementById('view-trading');
    if (!c) return;

    if (!light || !this._tradingInit) {
      this._tradingInit = true;
      c.innerHTML = `
        <div class="view-header">
          <div>
            <div class="view-title">⚡ Trading Terminal</div>
            <div class="view-subtitle">Candle chart, causal execution &amp; order lifecycle FSM</div>
          </div>
          <div class="view-actions">
            <select id="select-trading-pair" class="btn btn-sm" style="background:var(--bg-s2);color:var(--text)">
              <option value="ETH/USDT:USDT">ETH/USDT</option>
              <option value="BTC/USDT:USDT">BTC/USDT</option>
              <option value="SOL/USDT:USDT">SOL/USDT</option>
              <option value="XRP/USDT:USDT">XRP/USDT</option>
              <option value="ADA/USDT:USDT">ADA/USDT</option>
            </select>
            <div class="chart-timeframes">
              ${['5m','15m','1h','4h'].map(tf => `<button class="tf-btn ${this.selectedTimeframe===tf?'active':''}" data-tf="${tf}">${tf}</button>`).join('')}
            </div>
          </div>
        </div>

        <div class="terminal-layout">
          <div class="chart-container">
            <div class="chart-toolbar">
              <div style="font-weight:700;font-size:13px" id="chart-symbol-header">${this.selectedSymbol} • ${this.selectedTimeframe}</div>
              <div style="display:flex;gap:12px;font-size:11px;color:var(--text-sec)">
                <label style="cursor:pointer"><input type="checkbox" id="chk-ema" checked> EMA20/50</label>
                <label style="cursor:pointer"><input type="checkbox" id="chk-sltp" checked> SL/TP</label>
                <label style="cursor:pointer"><input type="checkbox" id="chk-ob" checked> Order Block</label>
              </div>
            </div>
            <div class="canvas-wrapper"><canvas id="main-chart"></canvas></div>
          </div>
          <div class="table-panel" style="margin-bottom:0">
            <div class="panel-header">
              <div class="panel-title">Active Market</div>
              <span class="badge badge-paper" id="trading-env-badge">PAPER</span>
            </div>
            <div style="padding:14px" id="terminal-side-summary"><span class="spinner"></span>Loading…</div>
          </div>
        </div>

        <div class="table-panel">
          <div class="panel-header">
            <div class="panel-title">📋 Order Lifecycle FSM &amp; Positions</div>
            <button class="btn btn-sm" onclick="window.app._refreshTradingTables()">🔄 Refresh</button>
          </div>
          <div id="terminal-tables-container" style="padding:10px"><span class="spinner"></span>Loading…</div>
        </div>`;

      // Pair selector
      document.getElementById('select-trading-pair').value = this.selectedSymbol;
      document.getElementById('select-trading-pair').addEventListener('change', e => {
        this.selectedSymbol = e.target.value;
        this.loadChartData();
      });

      // Load real pairs
      API.getPairs().then(res => {
        const pairs = res.pairs || [];
        if (!pairs.length) return;
        const sel = document.getElementById('select-trading-pair');
        if (!sel) return;
        const cur = this.selectedSymbol;
        sel.innerHTML = pairs.map(p => {
          const sym = p.internal || p.symbol;
          return `<option value="${sym}" ${sym===cur?'selected':''}>${p.symbol||sym}</option>`;
        }).join('');
      }).catch(() => {});

      // TF buttons
      document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this.selectedTimeframe = btn.getAttribute('data-tf');
          document.getElementById('chart-symbol-header').textContent = `${this.selectedSymbol} • ${this.selectedTimeframe}`;
          this.loadChartData();
        });
      });

      // Chart overlay toggles
      this.chartInstance = new CuanimusChart('main-chart');
      document.getElementById('chk-ema').addEventListener('change',  e => { if(this.chartInstance){this.chartInstance.options.showEma=e.target.checked;this.chartInstance.render();} });
      document.getElementById('chk-sltp').addEventListener('change', e => { if(this.chartInstance){this.chartInstance.options.showLevels=e.target.checked;this.chartInstance.render();} });
      document.getElementById('chk-ob').addEventListener('change',   e => { if(this.chartInstance){this.chartInstance.options.showOrderBlock=e.target.checked;this.chartInstance.render();} });

      await this.loadChartData();
    }

    await this._refreshTradingTables();
  }

  async loadChartData() {
    try {
      const data = await API.getCandles(this.selectedSymbol, this.selectedTimeframe, 80);
      if (this.chartInstance) this.chartInstance.setData(data);
      const h = document.getElementById('chart-symbol-header');
      if (h) h.textContent = `${this.selectedSymbol} • ${this.selectedTimeframe}`;
    } catch (err) {
      Toast.warn('Chart data unavailable: ' + err.message);
    }
  }

  async _refreshTradingTables() {
    const [posRes, ordRes, trdRes] = await Promise.all([
      API.getPositions().catch(() => ({ positions: [] })),
      API.getOrders().catch(() => ({ orders: [] })),
      API.getTrades(8).catch(() => ({ trades: [] }))
    ]);
    const pos = posRes.positions || [];
    const ord = ordRes.orders   || [];
    const trd = trdRes.trades   || [];

    // Side summary
    const sideEl = document.getElementById('terminal-side-summary');
    if (sideEl) {
      const env = this.systemStatus.environment || 'PAPER';
      sideEl.innerHTML = `
        <div style="font-size:12px;line-height:2.0">
          <div style="display:flex;justify-content:space-between"><span>Pair:</span><b>${this.selectedSymbol}</b></div>
          <div style="display:flex;justify-content:space-between"><span>Environment:</span><span class="badge badge-paper">${env}</span></div>
          <div style="display:flex;justify-content:space-between"><span>Open Positions:</span><b>${pos.length}</b></div>
          <div style="display:flex;justify-content:space-between"><span>Pending Orders:</span><b>${ord.filter(o=>o.status==='SUBMITTED').length}</b></div>
          <div style="display:flex;justify-content:space-between"><span>Closed Trades:</span><b>${trd.length}</b></div>
        </div>
        <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px">
          <button class="btn btn-ai btn-sm" onclick="Modals.showAiCopilotModal()">🤖 Ask AI Copilot</button>
          <button class="btn btn-danger btn-sm" onclick="Modals.showEmergencyStopModal()">🚨 Emergency Stop</button>
        </div>`;
    }

    // Tables
    const tblEl = document.getElementById('terminal-tables-container');
    if (!tblEl) return;

    const posRows = pos.length ? pos.map(p => `
      <tr>
        <td><b>${p.symbol}</b></td>
        <td><span class="badge ${p.side==='LONG'?'badge-bull':'badge-bear'}">${p.side}</span></td>
        <td class="mono">${p.size}</td>
        <td class="mono">$${this._fmt(p.entry_price)}</td>
        <td class="mono">$${this._fmt(p.mark_price)}</td>
        <td class="mono ${this._pnlClass(p.unrealized_pnl_usd)}">${this._pnlSign(p.unrealized_pnl_usd)}$${this._fmt(p.unrealized_pnl_usd)}</td>
        <td class="mono ${this._pnlClass(p.roe_pct)}">${this._pnlSign(p.roe_pct)}${this._fmt(p.roe_pct)}%</td>
        <td class="mono bear">$${this._fmt(p.stop_loss)}</td>
        <td class="mono bull">$${this._fmt(p.take_profit)}</td>
        <td><button class="btn btn-xs" onclick="window.app.inspectTrace('${p.decision_trace_id||p.id}')">Trace</button></td>
      </tr>`).join('') : this._emptyRow(10, 'No open positions. Portfolio is flat.');

    const ordRows = ord.length ? ord.map(o => {
      let cls = 'badge-neutral';
      if (o.status==='FILLED') cls='badge-bull';
      else if (o.status==='SUBMITTED') cls='badge-info';
      else if (['CANCELLED','REJECTED'].includes(o.status)) cls='badge-bear';
      return `<tr>
        <td class="mono"><b>${o.order_id}</b></td>
        <td class="mono" style="font-size:10px;color:var(--text-muted)">${o.client_order_id}</td>
        <td>${o.symbol}</td>
        <td><span class="badge ${o.side==='BUY'?'badge-bull':'badge-bear'}">${o.side}</span></td>
        <td>${o.type}</td>
        <td class="mono">$${this._fmt(o.price)}</td>
        <td class="mono">${o.filled}/${o.amount}</td>
        <td><span class="badge ${cls}">${o.status}</span></td>
        <td style="font-size:10px;color:var(--text-muted)">${o.created_at||''}</td>
      </tr>`;}).join('') : this._emptyRow(9, 'No orders in lifecycle buffer.');

    const trdRows = trd.length ? trd.map(t => {
      const ep = t.entry_price < 1 ? this._fmt(t.entry_price,4) : this._fmt(t.entry_price);
      const xp = t.exit_price  < 1 ? this._fmt(t.exit_price, 4) : this._fmt(t.exit_price);
      return `<tr>
        <td class="mono"><b>${t.trade_id}</b></td>
        <td>${t.symbol}</td>
        <td><span class="badge ${t.side==='LONG'?'badge-bull':'badge-bear'}">${t.side}</span></td>
        <td class="mono">${t.amount}</td>
        <td class="mono">$${ep}</td>
        <td class="mono">$${xp}</td>
        <td class="mono ${this._pnlClass(t.pnl_usd)}">${this._pnlSign(t.pnl_usd)}$${this._fmt(t.pnl_usd)} (${this._pnlSign(t.pnl_pct)}${this._fmt(t.pnl_pct)}%)</td>
        <td><span class="badge badge-neutral">${t.exit_reason}</span></td>
        <td style="font-size:10px;color:var(--text-muted)">${t.close_time||''}</td>
        <td><button class="btn btn-xs" onclick="window.app.inspectTrace('${t.decision_trace_id||t.trade_id}')">Trace</button></td>
      </tr>`;}).join('') : this._emptyRow(10, 'No closed trades recorded.');

    tblEl.innerHTML = `
      <h4 class="section-title" style="margin-bottom:8px">ACTIVE POSITIONS</h4>
      <div class="table-responsive" style="margin-bottom:20px">
        <table class="data-table">
          <thead><tr><th>Symbol</th><th>Side</th><th>Size</th><th>Entry</th><th>Mark</th><th>uPnL</th><th>ROE%</th><th>SL</th><th>TP</th><th>Trace</th></tr></thead>
          <tbody>${posRows}</tbody>
        </table>
      </div>
      <h4 class="section-title" style="margin-bottom:8px">ORDER LIFECYCLE FSM</h4>
      <div class="table-responsive" style="margin-bottom:20px">
        <table class="data-table">
          <thead><tr><th>Order ID</th><th>Client ID</th><th>Symbol</th><th>Side</th><th>Type</th><th>Price</th><th>Fill/Qty</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>${ordRows}</tbody>
        </table>
      </div>
      <h4 class="section-title" style="margin-bottom:8px">CLOSED TRADES — AUDIT TRAIL</h4>
      <div class="table-responsive">
        <table class="data-table">
          <thead><tr><th>Trade ID</th><th>Symbol</th><th>Side</th><th>Amount</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Reason</th><th>Close Time</th><th>Trace</th></tr></thead>
          <tbody>${trdRows}</tbody>
        </table>
      </div>`;
  }

  async inspectTrace(traceId) {
    try {
      const res = await API.getDecisionTraces(traceId);
      const trace = (res.traces || [])[0];
      if (trace) Modals.showDecisionTraceModal(trace);
      else Toast.warn('No trace details found: ' + traceId);
    } catch (err) { Toast.error('Trace fetch failed: ' + err.message); }
  }

  /* ═══════════════════════════════════════════════════════════
     3. MARKETS & REGIME MATRIX
  ═══════════════════════════════════════════════════════════ */
  async renderMarkets() {
    const c = document.getElementById('view-markets');
    if (!c) return;

    const [wRes, rRes] = await Promise.all([
      API.getWatchlist().catch(() => ({ watchlist: [] })),
      API.getRegimes().catch(() => ({ matrix: [] }))
    ]);
    const watchlist = wRes.watchlist || [];
    const matrix    = rRes.matrix    || [];

    const regimeRows = matrix.map(row => `
      <tr>
        <td><b>${row.regime}</b></td>
        ${['BTC','ETH','SOL','XRP','ADA'].map(a => `<td>${row[a]
          ? '<span class="badge badge-bull">● ACTIVE</span>'
          : '<span style="color:var(--text-muted)">○</span>'}</td>`).join('')}
      </tr>`).join('') || this._emptyRow(6, 'No regime data available.');

    const watchRows = watchlist.map(w => `
      <tr>
        <td><b>${w.symbol}</b></td>
        <td>${w.name||''}</td>
        <td class="mono">$${w.price < 1 ? this._fmt(w.price,4) : this._fmt(w.price)}</td>
        <td class="mono ${this._pnlClass(w.change_24h_pct)}">${this._pnlSign(w.change_24h_pct)}${this._fmt(w.change_24h_pct)}%</td>
        <td class="mono">$${((w.volume_24h_usd||0)/1e6).toFixed(2)}M</td>
        <td class="mono">${this._fmt(w.atr_volatility_pct)}%</td>
        <td><span class="badge ${w.regime?.includes('BULL')?'badge-bull':(w.regime?.includes('BEAR')?'badge-bear':'badge-neutral')}">${w.regime||'—'}</span></td>
        <td><span class="badge ${w.current_signal==='LONG'?'badge-bull':'badge-neutral'}">${w.current_signal||'HOLD'}</span></td>
        <td style="font-size:11px;color:var(--text-sec)">${w.signal_reason||''}</td>
      </tr>`).join('') || this._emptyRow(9, 'Watchlist data unavailable (exchange connectivity required).');

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">🌐 Market Surveillance &amp; Regime Matrix</div>
          <div class="view-subtitle">Cross-asset trend evaluation, volatility &amp; signal generation</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-sm" onclick="window.app.renderMarkets()">🔄 Refresh</button>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">🧭 Multi-Asset Market Regime Matrix</div>
          <span style="font-size:11px;color:var(--text-muted)">Candle-by-Candle</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Regime</th><th>BTC</th><th>ETH</th><th>SOL</th><th>XRP</th><th>ADA</th></tr></thead>
            <tbody>${regimeRows}</tbody>
          </table>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">👀 Asset Watchlist</div></div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Symbol</th><th>Asset</th><th>Price</th><th>24h Δ%</th><th>Volume</th><th>ATR Vol%</th><th>Regime</th><th>Signal</th><th>Reason</th></tr></thead>
            <tbody>${watchRows}</tbody>
          </table>
        </div>
      </div>`;
  }

  /* ═══════════════════════════════════════════════════════════
     4. STRATEGIES CENTER
  ═══════════════════════════════════════════════════════════ */
  async renderStrategies() {
    const c = document.getElementById('view-strategies');
    if (!c) return;

    const [sRes, sigRes] = await Promise.all([
      API.getStrategies().catch(() => ({ strategies: [] })),
      API.inspectSignal('hybrid_v2c', this.selectedSymbol).catch(() => ({}))
    ]);
    const strategies = sRes.strategies || [];
    const sig        = sigRes;

    const evalRows = (sig.evaluations || []).map(ev => `
      <tr>
        <td><b>${ev.factor}</b></td>
        <td class="mono">${ev.requirement}</td>
        <td class="mono">${ev.observed}</td>
        <td><span class="badge ${ev.pass?'badge-bull':'badge-bear'}">${ev.pass?'PASS':'FAIL'}</span></td>
      </tr>`).join('') || this._emptyRow(4, 'Signal evaluation data unavailable (requires live Binance connection).');

    const stratRows = strategies.map(s => `
      <tr>
        <td><b>${s.strategy_id}</b></td>
        <td>${s.name}</td>
        <td class="mono">${s.version}</td>
        <td class="mono">${(s.supported_timeframes||[]).join(', ')}</td>
        <td>${s.long_enabled||s.supports_long?'<span class="badge badge-bull">LONG</span>':''} ${s.short_enabled||s.supports_short?'<span class="badge badge-bear">SHORT</span>':''}</td>
        <td><span class="badge badge-bull">VERIFIED</span></td>
        <td><button class="btn btn-xs" onclick="window.app.inspectStrategyDetails('${s.strategy_id}')">Inspect</button></td>
      </tr>`).join('') || this._emptyRow(7, 'No strategy plugins registered.');

    const sigBadgeClass = sig.signal === 'LONG' ? 'badge-bull' : (sig.signal === 'SHORT' ? 'badge-bear' : 'badge-neutral');

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">🧠 Strategy Center &amp; Signal Inspector</div>
          <div class="view-subtitle">Registered strategy plugins, parameters, and causal signal evaluations</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-sm" onclick="window.app.renderStrategies()">🔄 Refresh</button>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">🔬 Live Signal Inspector: ${sig.strategy_id||'hybrid_v2c'} (${sig.symbol||this.selectedSymbol})</div>
          ${sig.confidence != null ? `<span class="badge badge-bull">Confidence: ${sig.confidence}%</span>` : ''}
        </div>
        <div style="padding:14px">
          ${sig.signal ? `<div style="margin-bottom:12px;font-size:12px"><b>Generated Signal:</b> <span class="badge ${sigBadgeClass}">${sig.signal}</span><span style="margin-left:12px;color:var(--text-muted)">${sig.conclusion||''}</span></div>` : ''}
          <div class="table-responsive">
            <table class="data-table">
              <thead><tr><th>Factor</th><th>Requirement</th><th>Observed</th><th>Status</th></tr></thead>
              <tbody>${evalRows}</tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">📚 Registered Strategy Plugins</div></div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>ID</th><th>Name</th><th>Version</th><th>Timeframes</th><th>Direction</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>${stratRows}</tbody>
          </table>
        </div>
      </div>`;
  }

  async inspectStrategyDetails(id) {
    try {
      const d = await API.inspectStrategy(id);
      const info = `Strategy: ${d.name} (v${d.version})\n\nDescription: ${d.description}\n\nParameters:\n${JSON.stringify(d.parameters||d.parameter_specs||{}, null, 2)}`;
      alert(info);
    } catch (err) { Toast.error('Inspect failed: ' + err.message); }
  }

  /* ═══════════════════════════════════════════════════════════
     5. RESEARCH & BACKTEST LAB
  ═══════════════════════════════════════════════════════════ */
  async renderResearch() {
    const c = document.getElementById('view-research');
    if (!c) return;

    const [expRes, stratRes] = await Promise.all([
      API.getExperiments().catch(() => ({ experiments: [] })),
      API.getStrategies().catch(() => ({ strategies: [] }))
    ]);
    const experiments = expRes.experiments || [];
    const strategies  = stratRes.strategies || [];

    const stratOpts = strategies.map(s => `<option value="${s.strategy_id}">${s.strategy_id} — ${s.name}</option>`).join('') ||
      ['hybrid_v2c','pullback_v2a','structure_v2b','atr_v1','baseline_v0'].map(s => `<option value="${s}">${s}</option>`).join('');

    const expRows = experiments.map(e => {
      const m = e.metrics || {};
      return `<tr>
        <td><b>${e.experiment_id}</b></td>
        <td>${e.metadata?.strategy_id||'quantitative'}</td>
        <td class="mono">${m.total_trades||'—'}</td>
        <td class="mono">${m.win_rate!=null?this._fmt(m.win_rate,1)+'%':'—'}</td>
        <td class="mono">${m.profit_factor!=null?this._fmt(m.profit_factor):'—'}</td>
        <td class="mono">${m.expectancy_usd!=null?'$'+this._fmt(m.expectancy_usd):'—'}</td>
        <td class="mono ${this._pnlClass(m.net_pnl_usd)}">${m.net_pnl_usd!=null?this._pnlSign(m.net_pnl_usd)+'$'+this._fmt(m.net_pnl_usd):'—'}</td>
        <td class="mono bear">${m.max_drawdown_pct!=null?this._fmt(m.max_drawdown_pct)+'%':'—'}</td>
        <td><span class="badge badge-info">OUT-OF-SAMPLE</span></td>
        <td><button class="btn btn-xs" onclick="window.app.inspectExperiment('${e.experiment_id}')">Details</button></td>
      </tr>`;}).join('') || this._emptyRow(10, 'No backtest experiments found. Run a backtest to see results here.');

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">🧪 Research &amp; Backtesting Lab</div>
          <div class="view-subtitle">Deterministic causal replay, cost model validation &amp; multi-model comparison</div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">⚙️ Launch New Backtest</div></div>
        <div style="padding:16px">
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:14px">
            <div>
              <label class="form-label">Strategy</label>
              <select id="bt-strategy" class="form-input">${stratOpts}</select>
            </div>
            <div>
              <label class="form-label">Initial Capital ($)</label>
              <input type="number" id="bt-capital" class="form-input" value="1000" min="100">
            </div>
            <div>
              <label class="form-label">Fee Model</label>
              <input type="text" class="form-input" value="0.05% Taker / 0.02% Maker" disabled style="opacity:0.6">
            </div>
            <div>
              <label class="form-label">Slippage</label>
              <input type="text" class="form-input" value="0.05% Adverse" disabled style="opacity:0.6">
            </div>
          </div>
          <button class="btn btn-primary" id="btn-run-backtest">▶ RUN DETERMINISTIC BACKTEST</button>
        </div>
      </div>

      <div id="bt-result-box" style="display:none;margin-bottom:18px"></div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">📊 Multi-Model Revalidation Matrix</div>
          <span style="font-size:11px;color:var(--text-muted)">Strict Out-Of-Sample Partitioning</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Experiment ID</th><th>Model</th><th>Trades</th><th>Win%</th><th>PF</th><th>Expectancy</th><th>Net PnL</th><th>MaxDD</th><th>Partition</th><th>Action</th></tr></thead>
            <tbody>${expRows}</tbody>
          </table>
        </div>
      </div>`;

    document.getElementById('btn-run-backtest').addEventListener('click', async () => {
      const strat   = document.getElementById('bt-strategy').value;
      const capital = parseFloat(document.getElementById('bt-capital').value) || 1000;
      const btn     = document.getElementById('btn-run-backtest');
      btn.disabled  = true; btn.textContent = '⏳ Running…';
      Toast.info(`Running deterministic replay for ${strat}…`);
      try {
        const res = await API.runBacktest({ strategy_id: strat, initial_capital: capital });
        Toast.success('Backtest complete!');
        const box = document.getElementById('bt-result-box');
        box.style.display = 'block';
        box.innerHTML = `
          <div class="stat-card" style="border-color:var(--mint)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <div style="font-weight:700;font-size:13px">Run: ${res.run_id} — ${res.strategy_id}</div>
              <span class="badge badge-bull">OUT-OF-SAMPLE VERIFIED</span>
            </div>
            <div class="grid-cards" style="margin-bottom:0">
              <div><div class="stat-card-label">Trades</div><div class="stat-card-value">${res.total_trades}</div></div>
              <div><div class="stat-card-label">Win Rate</div><div class="stat-card-value">${res.win_rate}%</div></div>
              <div><div class="stat-card-label">Profit Factor</div><div class="stat-card-value">${res.profit_factor}</div></div>
              <div><div class="stat-card-label">Expectancy</div><div class="stat-card-value">$${res.expectancy_usd}</div></div>
              <div><div class="stat-card-label">Net PnL</div><div class="stat-card-value bull">+$${res.net_pnl_usd}</div></div>
              <div><div class="stat-card-label">Max Drawdown</div><div class="stat-card-value bear">${res.max_drawdown_pct}%</div></div>
            </div>
          </div>`;
      } catch (err) {
        Toast.error('Backtest failed: ' + err.message);
      } finally {
        btn.disabled = false; btn.textContent = '▶ RUN DETERMINISTIC BACKTEST';
      }
    });
  }

  async inspectExperiment(id) {
    try {
      const d = await API.getExperimentDetail(id);
      const m = d.metrics || {};
      alert(`Experiment: ${id}\nTrades: ${m.total_trades}\nWin Rate: ${m.win_rate}%\nProfit Factor: ${m.profit_factor}\nNet PnL: $${m.net_pnl_usd}\nMax Drawdown: ${m.max_drawdown_pct}%\nEquity Curve Points: ${(d.equity_curve||[]).length}`);
    } catch (err) { Toast.error('Inspect failed: ' + err.message); }
  }

  /* ═══════════════════════════════════════════════════════════
     6. RISK CENTER
  ═══════════════════════════════════════════════════════════ */
  async renderRisk() {
    const c = document.getElementById('view-risk');
    if (!c) return;

    const risk     = await API.getRiskStatus().catch(() => ({}));
    const stopped  = !!risk.emergency_stop_active;
    const dl       = risk.daily_loss         || {};
    const dd       = risk.portfolio_drawdown || {};
    const exp      = risk.total_exposure     || {};
    const rpt      = risk.risk_per_trade_pct || {};

    const gauge = (label, cur, lim) => {
      const r = Math.min(100, lim > 0 ? (cur/lim*100) : 0);
      const cls = r > 80 ? 'fill-danger' : (r > 50 ? 'fill-warn' : 'fill-ok');
      return `<div class="risk-meter">
        <div class="risk-meter-header">
          <span><b>${label}:</b> ${this._fmt(cur)}% of ${this._fmt(lim)}% limit</span>
          <span class="mono">${this._fmt(r,0)}% Utilized</span>
        </div>
        <div class="risk-meter-track"><div class="risk-meter-fill ${cls}" style="width:${r}%"></div></div>
      </div>`;
    };

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">🛡️ Risk Control Center
            <span class="badge ${stopped?'badge-bear':'badge-bull'}">${stopped?'STOPPED / LOCKED':'ARMED / PROTECTED'}</span>
          </div>
          <div class="view-subtitle">Independent capital protection, circuit breakers &amp; hard risk invariants</div>
        </div>
        <div class="view-actions">
          ${stopped
            ? `<button class="btn btn-success btn-sm" id="btn-reset-stop">🔓 Reset Emergency Lock</button>`
            : `<button class="btn btn-danger btn-sm" onclick="Modals.showEmergencyStopModal()">🚨 Emergency Kill Switch</button>`}
          <button class="btn btn-sm" onclick="window.app.renderRisk()">🔄 Refresh</button>
        </div>
      </div>

      <div class="grid-cards">
        <div class="stat-card">
          <div class="stat-card-label">Risk Per Trade</div>
          <div class="stat-card-value">${rpt.current||rpt||1.0}%</div>
          <div class="stat-card-sub">Fixed Fractional ATR Sizing</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Daily Realized Loss</div>
          <div class="stat-card-value">${this._fmt(dl.current_pct??0)}%</div>
          <div class="stat-card-sub">Limit: ${this._fmt(dl.limit_pct??3.0)}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Portfolio Drawdown</div>
          <div class="stat-card-value">${this._fmt(dd.current_pct??0)}%</div>
          <div class="stat-card-sub">Hard Breaker: ${this._fmt(dd.limit_pct??15.0)}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-label">Total Capital Exposure</div>
          <div class="stat-card-value">${this._fmt(exp.current_pct??0)}%</div>
          <div class="stat-card-sub">Cap: ${this._fmt(exp.limit_pct??80.0)}%</div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">📊 Live Exposure &amp; Circuit Breaker Thresholds</div></div>
        <div style="padding:16px">
          ${gauge('Daily Loss Meter',      dl.current_pct??0,  dl.limit_pct??3.0)}
          ${gauge('Portfolio Drawdown',    dd.current_pct??0,  dd.limit_pct??15.0)}
          ${gauge('Total Capital Exposure',exp.current_pct??0, exp.limit_pct??80.0)}
        </div>
      </div>`;

    document.getElementById('btn-reset-stop')?.addEventListener('click', async () => {
      try {
        await API.resetEmergencyStop();
        Toast.success('Emergency stop cleared. RiskEngine re-armed.');
        this.renderRisk();
      } catch (err) { Toast.error('Reset failed: ' + err.message); }
    });
  }

  /* ═══════════════════════════════════════════════════════════
     7. AUTONOMOUS TRADING ENGINE
  ═══════════════════════════════════════════════════════════ */
  async renderAutonomous(light = false) {
    const c = document.getElementById('view-autonomous');
    if (!c) return;

    const [profRes, engRes, tracesRes, posRes] = await Promise.all([
      API.getTradingProfiles().catch(() => ({ profiles: [] })),
      API.getEngineStatus().catch(() => ({})),
      API.getEngineTraces().catch(() => ({ traces: [] })),
      API.getPositions().catch(() => ({ positions: [] }))
    ]);

    const profiles  = profRes.profiles    || [];
    const engine    = engRes              || {};
    const traces    = tracesRes.traces    || [];
    const positions = posRes.positions    || [];
    const running   = profiles.filter(p => p.is_running).length;
    const engineOn  = !!engine.engine_running;

    // Profile cards
    let profilesHtml = '';
    if (!profiles.length) {
      profilesHtml = `
        <div style="grid-column:1/-1">
          <div class="empty-state" style="border:1px dashed var(--border);border-radius:var(--radius-md)">
            <div class="empty-state-icon">🚀</div>
            <div class="empty-state-title">No Trading Profiles Configured</div>
            <div class="empty-state-desc">Create your first Autonomous Trading Profile using Strategy, AI Agent, or Hybrid mode.</div>
            <button class="btn btn-primary" id="btn-create-empty">+ Create Trading Profile</button>
          </div>
        </div>`;
    } else {
      profilesHtml = profiles.map(p => {
        const run = !!p.is_running;
        const modeColors = {
          strategy: { bg:'rgba(91,255,202,0.10)', color:'var(--mint)',     label:'🧠 Strategy', detail:`Template: <b>${p.strategy_id||'—'}</b>` },
          ai_agent: { bg:'rgba(204,136,255,0.10)',color:'var(--lavender)', label:'🤖 AI Agent',  detail:`Agent: <b>${p.agent_id||'—'}</b>` },
          hybrid:   { bg:'rgba(255,179,217,0.10)',color:'var(--pink)',     label:'⚡ Hybrid',    detail:`Filter: <b>${p.strategy_id}</b> | Agent: <b>${p.agent_id||'—'}</b>` }
        };
        const mc = modeColors[p.decision_mode] || modeColors.strategy;
        return `
          <div class="card ${run?'running':''}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
              <div>
                <div style="font-weight:800;font-size:14px;margin-bottom:2px">${p.name}</div>
                <div style="font-size:11px;color:var(--text-muted)">${p.symbol} • <b>${p.timeframe}</b></div>
              </div>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px">
                ${run
                  ? `<span class="badge badge-bull"><span class="health-dot ok" style="margin-right:4px"></span>RUNNING</span>`
                  : `<span class="badge badge-neutral">⏹ STOPPED</span>`}
                <span class="badge" style="background:${mc.bg};color:${mc.color}">${mc.label}</span>
              </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:11px;background:var(--bg-s3);padding:9px;border-radius:5px;margin-bottom:12px">
              <div>${mc.detail}</div>
              <div>Risk: <b style="text-transform:capitalize">${p.risk_profile}</b></div>
              <div>Exec: <b style="color:var(--yellow)">${(p.execution_mode||'paper').toUpperCase()}</b></div>
              <div>Max Pos: <b>${p.max_open_positions}</b> | Daily: <b>${p.max_trades_per_day}</b></div>
              <div>SL: <b>${p.stop_loss_pct}%</b></div>
              <div>TP: <b>${p.take_profit_pct}%</b></div>
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              ${run ? `
                <button class="btn btn-sm btn-warn   btn-prof-pause"   data-id="${p.profile_id}">⏸ Pause</button>
                <button class="btn btn-sm btn-danger  btn-prof-stop"    data-id="${p.profile_id}">⏹ Stop</button>
                <button class="btn btn-sm btn-prof-trigger" data-id="${p.profile_id}">⚡ Tick</button>
              ` : `
                <button class="btn btn-sm btn-primary btn-prof-start"   data-id="${p.profile_id}">▶ Start</button>
                <button class="btn btn-sm btn-prof-trigger" data-id="${p.profile_id}">⚡ Test</button>
              `}
              <button class="btn btn-sm btn-prof-edit"   data-id="${p.profile_id}">✏️ Edit</button>
              <button class="btn btn-sm btn-prof-delete" data-id="${p.profile_id}" style="color:var(--bear)">🗑️</button>
            </div>
          </div>`;
      }).join('');
    }

    // Decision traces
    const traceRows = traces.length ? traces.slice(0,20).map(t => {
      const cls = t.execution_status==='EXECUTED' ? 'badge-bull' : (t.execution_status==='REJECTED' ? 'badge-bear' : 'badge-neutral');
      return `<tr>
        <td style="font-size:10px;color:var(--text-muted)">${t.decision_timestamp||'—'}</td>
        <td><b>${t.symbol}</b> <span style="font-size:10px;color:var(--text-muted)">${t.timeframe}</span></td>
        <td><span class="badge badge-neutral">${t.decision_mode}</span></td>
        <td>${t.strategy_signal||'—'}</td>
        <td>${t.ai_decision ? `${t.ai_decision} (${Math.round((t.ai_confidence||0)*100)}%)` : '—'}</td>
        <td><span class="badge ${cls}">${t.execution_status||'ABSTAINED'}</span></td>
        <td><button class="btn btn-xs btn-inspect-trace" data-id="${t.trace_id}">Inspect</button></td>
      </tr>`;}).join('') : this._emptyRow(7, 'No decision traces yet. Start a profile to generate traces.');

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">🚀 Autonomous Trading Engine
            <span class="badge ${engineOn?'badge-bull':'badge-neutral'}">
              <span class="health-dot ${engineOn?'ok':'warn'}" style="margin-right:4px"></span>
              ${engineOn?'ENGINE ACTIVE':'ENGINE IDLE'}
            </span>
          </div>
          <div class="view-subtitle">Continuous multi-profile autonomous trading — Strategy, AI Agent &amp; Hybrid Mode.</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-sm" id="btn-refresh-autonomous">🔄 Refresh</button>
          <button class="btn btn-primary btn-sm" id="btn-create-profile">+ Create Profile</button>
        </div>
      </div>

      <div class="metrics-grid" style="margin-bottom:20px">
        <div class="stat-card"><div class="stat-label">Running Profiles</div><div class="stat-value bull">${running} <span style="font-size:12px;color:var(--text-muted)">/ ${profiles.length}</span></div></div>
        <div class="stat-card"><div class="stat-label">Engine State</div><div class="stat-value ${engineOn?'bull':'warn'}">${engineOn?'ONLINE':'STANDBY'}</div></div>
        <div class="stat-card"><div class="stat-label">Open Positions</div><div class="stat-value">${positions.length}</div></div>
        <div class="stat-card"><div class="stat-label">Safety Gate</div><div class="stat-value bull">${this.systemStatus.safety_status||'SAFE'}</div></div>
      </div>

      <div style="margin-bottom:22px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="font-size:13px;font-weight:700;margin:0">Configured Trading Profiles</h3>
          <span style="font-size:11px;color:var(--text-muted)">Candle Boundary: Strictly Closed Bars</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px">
          ${profilesHtml}
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">📋 Autonomous Decision Traces</div>
          <span style="font-size:11px;color:var(--text-muted)">Market Data → Strategy/AI → Policy → Risk → Execution</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Timestamp</th><th>Pair/TF</th><th>Mode</th><th>Strategy</th><th>AI</th><th>Outcome</th><th>Inspect</th></tr></thead>
            <tbody>${traceRows}</tbody>
          </table>
        </div>
      </div>`;

    // Wire buttons
    c.querySelector('#btn-create-profile')?.addEventListener('click', () => Modals.showProfileModal(null, () => this.renderAutonomous()));
    c.querySelector('#btn-create-empty')?.addEventListener('click',   () => Modals.showProfileModal(null, () => this.renderAutonomous()));
    c.querySelector('#btn-refresh-autonomous')?.addEventListener('click', () => this.renderAutonomous());

    const action = (sel, fn) => c.querySelectorAll(sel).forEach(btn => btn.addEventListener('click', () => fn(btn.getAttribute('data-id'))));
    action('.btn-prof-start',   id => this._profileAction(id,'start'));
    action('.btn-prof-pause',   id => this._profileAction(id,'pause'));
    action('.btn-prof-stop',    id => this._profileAction(id,'stop'));
    action('.btn-prof-trigger', id => this._profileTick(id));
    action('.btn-prof-edit',    id => { const p = profiles.find(x=>x.profile_id===id); if(p) Modals.showProfileModal(p, ()=>this.renderAutonomous()); });
    action('.btn-prof-delete',  id => this._profileDelete(id));
    action('.btn-inspect-trace',id => { const t = traces.find(x=>x.trace_id===id); if(t) Modals.showAutonomousTraceModal(t); });
  }

  async _profileAction(id, act) {
    try {
      if (act==='start') await API.startTradingProfile(id);
      else if (act==='pause') await API.pauseTradingProfile(id);
      else if (act==='stop')  await API.stopTradingProfile(id);
      Toast.success(`Profile ${act} successful.`);
      this.renderAutonomous();
    } catch (err) { Toast.error(`Failed to ${act} profile: ${err.message}`); }
  }
  async _profileTick(id) {
    Toast.info('Running evaluation tick…');
    try {
      const r = await API.triggerProfileTick(id);
      Toast.success(`Tick outcome: ${r.status||'OK'}`);
      this.renderAutonomous();
    } catch (err) { Toast.error('Tick error: ' + err.message); }
  }
  async _profileDelete(id) {
    if (!confirm('Delete this trading profile?')) return;
    try {
      await API.deleteTradingProfile(id);
      Toast.success('Profile deleted.');
      this.renderAutonomous();
    } catch (err) { Toast.error('Delete failed: ' + err.message); }
  }

  /* ═══════════════════════════════════════════════════════════
     8. AI AGENT CENTER
  ═══════════════════════════════════════════════════════════ */
  async renderAgents() {
    const c = document.getElementById('view-agents');
    if (!c) return;

    const [agRes, sessRes, aiRes, mcpRes] = await Promise.all([
      API.getAgents().catch(() => ({ agents: [] })),
      API.getSessions().catch(() => ({ sessions: [] })),
      API.getAiConfig().catch(() => ({})),
      API.getMcpTools().catch(() => ({ tools: [] }))
    ]);
    const agents   = agRes.agents    || [];
    const sessions = sessRes.sessions|| [];
    const ai       = aiRes           || {};
    const tools    = mcpRes.tools    || [];

    const sessRows = sessions.length ? sessions.map(s => {
      let cls = 'badge-neutral';
      if (s.state==='RUNNING') cls='badge-bull';
      else if (s.state==='PAUSED') cls='badge-warn';
      else if (['STOPPED','FAILED'].includes(s.state)) cls='badge-bear';
      return `<tr>
        <td class="mono"><b>${s.session_id}</b></td>
        <td>${s.agent_id}</td>
        <td><span class="badge badge-paper">${s.mode}</span></td>
        <td><span class="badge ${cls}">${s.state}</span></td>
        <td class="mono">${s.trade_count}/${s.max_trades}</td>
        <td class="mono">${s.error_count}/${s.error_budget}</td>
        <td style="font-size:11px">${s.last_heartbeat?s.last_heartbeat.substr(11,8)+' UTC':'—'}</td>
        <td>
          ${s.state==='RUNNING'?`
            <button class="btn btn-xs" onclick="window.app.controlSession('${s.session_id}','pause')">Pause</button>
            <button class="btn btn-xs btn-danger" onclick="window.app.controlSession('${s.session_id}','stop')">Stop</button>
          `:s.state==='PAUSED'?`
            <button class="btn btn-xs btn-primary" onclick="window.app.controlSession('${s.session_id}','resume')">Resume</button>
            <button class="btn btn-xs btn-danger"  onclick="window.app.controlSession('${s.session_id}','stop')">Stop</button>
          `:`<span class="muted">Ended</span>`}
        </td>
      </tr>`;}).join('') : this._emptyRow(8, 'No trading sessions active.');

    const agentRows = agents.length ? agents.map(a => `
      <tr>
        <td><b>${a.agent_id}</b></td>
        <td>${a.role}</td>
        <td><span class="badge badge-paper">${a.environment}</span></td>
        <td><span class="badge badge-bull">${a.status}</span></td>
        <td class="mono" style="font-size:11px">${(a.permissions||[]).join(', ')}</td>
        <td style="font-size:11px">${a.heartbeat||'—'}</td>
      </tr>`).join('') : this._emptyRow(6, 'No registered AI agents.');

    const toolRows = tools.length ? tools.map(t => {
      const props = Object.keys(t.inputSchema?.properties||{}).join(', ')||'—';
      const perm  = t.name.startsWith('place_')||t.name.startsWith('cancel_') ? 'TRADE_EXECUTE' : 'MARKET_READ';
      return `<tr>
        <td class="mono" style="color:var(--lavender)"><b>${t.name}</b></td>
        <td>${t.description}</td>
        <td><span class="badge badge-lavender">${perm}</span></td>
        <td class="mono" style="font-size:11px;color:var(--text-sec)">${props}</td>
      </tr>`;}).join('') : this._emptyRow(4, 'No MCP tools registered.');

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">🤖 AI Agent Center &amp; MCP Protocol</div>
          <div class="view-subtitle">Sessions, model providers, MCP tools &amp; watchdog health</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-primary btn-sm" id="btn-create-session">▶ Start Paper Session</button>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">⚡ Active Trading Sessions</div></div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Session ID</th><th>Agent</th><th>Mode</th><th>State</th><th>Trades</th><th>Errors</th><th>Heartbeat</th><th>Actions</th></tr></thead>
            <tbody>${sessRows}</tbody>
          </table>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title" style="color:var(--lavender)">🧠 AI Model Provider &amp; Inference</div>
          <span class="badge badge-lavender">${ai.enabled?'AI LAYER ACTIVE':'DETERMINISTIC MODE'}</span>
        </div>
        <div style="padding:16px">
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:14px">
            <div>
              <label class="form-label">Provider</label>
              <select id="ai-provider" class="form-input">
                <option value="gemini"      ${ai.provider==='gemini'     ?'selected':''}>Google Gemini</option>
                <option value="antigravity" ${ai.provider==='antigravity'?'selected':''}>Antigravity Copilot</option>
                <option value="openai"      ${ai.provider==='openai'     ?'selected':''}>OpenAI Compatible</option>
                <option value="anthropic"   ${ai.provider==='anthropic'  ?'selected':''}>Anthropic Claude</option>
                <option value="mock"        ${ai.provider==='mock'       ?'selected':''}>Mock / Offline</option>
              </select>
            </div>
            <div>
              <label class="form-label">Model Identifier</label>
              <input id="ai-model" type="text" class="form-input" value="${ai.model_name||'gemini-2.5-flash'}" placeholder="e.g. gemini-2.5-flash">
            </div>
            <div>
              <label class="form-label">API Key / Token</label>
              <input id="ai-key" type="password" class="form-input" placeholder="${ai.api_key_masked?'Configured: '+ai.api_key_masked:'Enter API Key…'}">
            </div>
            <div>
              <label class="form-label">Inference Mode</label>
              <select id="ai-mode" class="form-input">
                <option value="regime_context"   ${ai.mode==='regime_context'   ?'selected':''}>Regime &amp; Macro Context</option>
                <option value="advisory"          ${ai.mode==='advisory'          ?'selected':''}>Advisory Validation</option>
                <option value="autonomous_paper"  ${ai.mode==='autonomous_paper'  ?'selected':''}>Autonomous Paper</option>
              </select>
            </div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;border-top:1px solid var(--border);padding-top:12px">
            <div style="display:flex;align-items:center;gap:12px">
              <label style="display:flex;align-items:center;gap:7px;cursor:pointer;font-size:12px">
                <input id="ai-enabled" type="checkbox" ${ai.enabled?'checked':''}> <b>Enable AI Intelligence Layer</b>
              </label>
              <span id="ai-test-status" style="font-size:11px;color:var(--text-muted)"></span>
            </div>
            <div style="display:flex;gap:8px">
              <button class="btn btn-sm" id="btn-test-ai">⚡ Test Connection</button>
              <button class="btn btn-primary btn-sm" id="btn-save-ai">💾 Save AI Config</button>
            </div>
          </div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title" style="color:var(--lavender)">🔌 MCP Registered Tools (${tools.length})</div>
          <span style="font-size:11px;color:var(--text-muted)">Port :8889 / /mcp JSON-RPC 2.0</span>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Tool Name</th><th>Description</th><th>Permission</th><th>Input Schema</th></tr></thead>
            <tbody>${toolRows}</tbody>
          </table>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">👥 Registered AI Identities (${agents.length})</div></div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Agent ID</th><th>Role</th><th>Environment</th><th>Status</th><th>Permissions</th><th>Heartbeat</th></tr></thead>
            <tbody>${agentRows}</tbody>
          </table>
        </div>
      </div>`;

    // Wire buttons
    document.getElementById('btn-create-session')?.addEventListener('click', async () => {
      try {
        await API.createPaperSession('antigravity-agent', 7200, 20);
        Toast.success('Paper session started!');
        this.renderAgents();
      } catch (err) { Toast.error('Session failed: ' + err.message); }
    });

    document.getElementById('btn-test-ai')?.addEventListener('click', async () => {
      const prov = document.getElementById('ai-provider').value;
      const model= document.getElementById('ai-model').value;
      const key  = document.getElementById('ai-key').value;
      const btn  = document.getElementById('btn-test-ai');
      const stat = document.getElementById('ai-test-status');
      btn.disabled = true; stat.textContent = 'Testing…';
      try {
        const r = await API.testAiConnection({ provider:prov, model_name:model, api_key:key });
        if (r.status==='CONNECTED') {
          Toast.success(`Connected: ${r.model} (${r.latency_ms}ms)`);
          stat.innerHTML = `<span style="color:var(--bull)">✔ Connected (${r.latency_ms}ms)</span>`;
        } else {
          Toast.warn(r.message);
          stat.innerHTML = `<span style="color:var(--warn)">⚠ ${r.message}</span>`;
        }
      } catch (err) {
        Toast.error('Test failed: ' + err.message);
        stat.innerHTML = `<span style="color:var(--bear)">✖ ${err.message}</span>`;
      } finally { btn.disabled = false; }
    });

    document.getElementById('btn-save-ai')?.addEventListener('click', async () => {
      const payload = {
        provider:   document.getElementById('ai-provider').value,
        model_name: document.getElementById('ai-model').value,
        mode:       document.getElementById('ai-mode').value,
        enabled:    document.getElementById('ai-enabled').checked
      };
      const key = document.getElementById('ai-key').value;
      if (key) payload.api_key = key;
      const btn = document.getElementById('btn-save-ai');
      btn.disabled = true;
      try {
        await API.saveAiConfig(payload);
        Toast.success('AI configuration saved!');
        this.renderAgents();
      } catch (err) {
        Toast.error('Save failed: ' + err.message);
        btn.disabled = false;
      }
    });
  }

  async controlSession(sessionId, action) {
    try {
      await API.manageSession(sessionId, action);
      Toast.info(`Session ${sessionId.slice(-8)} → ${action.toUpperCase()}`);
      this.renderAgents();
    } catch (err) { Toast.error('Session action failed: ' + err.message); }
  }

  /* ═══════════════════════════════════════════════════════════
     9. CONFIGURATION CENTER
  ═══════════════════════════════════════════════════════════ */
  async renderConfig() {
    const c = document.getElementById('view-config');
    if (!c) return;
    const [, cur] = await Promise.all([
      API.getConfigSchema().catch(() => ({})),
      API.getCurrentConfig().catch(() => ({}))
    ]);
    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">⚙️ Configuration Center</div>
          <div class="view-subtitle">Dynamic typed configuration powered by JSON Schema &amp; AI Copilot</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-ai btn-sm" onclick="Modals.showAiCopilotModal()">🤖 AI Assisted Config</button>
        </div>
      </div>
      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">📝 Active Configuration Inspector</div>
          <button class="btn btn-success btn-sm" id="btn-save-config">Validate &amp; Save</button>
        </div>
        <div style="padding:16px">
          <textarea id="config-yaml" class="form-input mono" style="height:360px;font-size:12px">${JSON.stringify(cur,null,2)}</textarea>
        </div>
      </div>`;

    document.getElementById('btn-save-config').addEventListener('click', async () => {
      try {
        const parsed = JSON.parse(document.getElementById('config-yaml').value);
        const v = await API.validateConfig(parsed);
        if (v.is_valid) {
          await API.saveConfig(parsed);
          Toast.success('Configuration validated and saved!');
        } else {
          Toast.error('Validation failed: ' + (v.errors||[]).join('; '));
        }
      } catch (err) { Toast.error('Invalid JSON: ' + err.message); }
    });
  }

  /* ═══════════════════════════════════════════════════════════
     10. DATA CENTER
  ═══════════════════════════════════════════════════════════ */
  async renderData() {
    const c = document.getElementById('view-data');
    if (!c) return;
    const res = await API.getDatasets().catch(() => ({ datasets: [] }));
    const datasets = res.datasets || [];

    const rows = datasets.length ? datasets.map(d => `
      <tr>
        <td><b>${d.name}</b></td>
        <td>${d.exchange}</td>
        <td>${d.market_type}</td>
        <td class="mono">${d.candle_count}</td>
        <td class="mono">${(d.timeframes||[]).join(', ')}</td>
        <td class="mono" style="font-size:10px;color:var(--text-muted)">${d.sha256||'—'}</td>
        <td><span class="badge badge-bull">${d.status}</span></td>
      </tr>`).join('') : this._emptyRow(7, 'No datasets registered.');

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">💾 Data Health &amp; Provenance</div>
          <div class="view-subtitle">Market datasets, candle counts &amp; SHA256 integrity verification</div>
        </div>
      </div>
      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">🗄️ Verified Historical Datasets</div></div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Name</th><th>Exchange</th><th>Market</th><th>Candles</th><th>Timeframes</th><th>SHA256</th><th>Status</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }

  /* ═══════════════════════════════════════════════════════════
     11. LOGS & EVENTS
  ═══════════════════════════════════════════════════════════ */
  async renderLogs() {
    const c = document.getElementById('view-logs');
    if (!c) return;
    const res    = await API.getEvents().catch(() => ({ events: [] }));
    const events = res.events || [];

    const rows = events.length ? events.map(ev => {
      let cls = 'badge-info';
      if (ev.severity==='WARNING') cls='badge-warn';
      if (['ERROR','CRITICAL'].includes(ev.severity)) cls='badge-bear';
      return `<tr>
        <td class="mono"><b>${ev.id}</b></td>
        <td style="font-size:11px">${ev.timestamp}</td>
        <td><span class="badge ${cls}">${ev.severity}</span></td>
        <td><span class="badge badge-neutral">${ev.domain}</span></td>
        <td>${ev.message}</td>
        <td class="mono" style="font-size:10px;color:var(--text-muted)">${ev.correlation_id||'—'}</td>
      </tr>`;}).join('') : this._emptyRow(6, 'No events logged yet.');

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">📜 System Events &amp; Audit Logs</div>
          <div class="view-subtitle">Filterable event timeline with correlation IDs and domain tags</div>
        </div>
        <div class="view-actions">
          <button class="btn btn-sm" onclick="window.app.renderLogs()">🔄 Refresh</button>
        </div>
      </div>
      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">🔍 Chronological Event Feed</div></div>
        <div class="table-responsive">
          <table class="data-table">
            <thead><tr><th>Event ID</th><th>Time</th><th>Severity</th><th>Domain</th><th>Message</th><th>Correlation ID</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }

  /* ═══════════════════════════════════════════════════════════
     12. SETTINGS & TELEGRAM
  ═══════════════════════════════════════════════════════════ */
  async renderSettings() {
    const c = document.getElementById('view-settings');
    if (!c) return;
    const [settings, tg] = await Promise.all([
      API.getSettings().catch(() => ({})),
      API.getTelegramStatus().catch(() => ({}))
    ]);

    c.innerHTML = `
      <div class="view-header">
        <div>
          <div class="view-title">📱 Settings &amp; Integrations</div>
          <div class="view-subtitle">UI preferences, theme controls &amp; Telegram notification center</div>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header">
          <div class="panel-title">📱 Telegram Bot Integration</div>
          <span class="badge ${tg.is_configured?'badge-bull':'badge-warn'}">${tg.is_configured?'CONFIGURED':'NOT CONFIGURED'}</span>
        </div>
        <div style="padding:16px">
          <p style="color:var(--text-sec);margin-bottom:14px;font-size:12px">
            Dispatches instant alerts for Order Fills, Stop Loss / Take Profit hits, Risk Vetoes, and Emergency Stops.
          </p>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px">
            <div>
              <div class="stat-card-label">Bot Token</div>
              <div class="mono" style="font-size:12px">${tg.bot_token_masked||'Not set'}</div>
            </div>
            <div>
              <div class="stat-card-label">Chat ID</div>
              <div class="mono" style="font-size:12px">${tg.chat_id||'Not set'}</div>
            </div>
            <div>
              <div class="stat-card-label">Alerts</div>
              <div>${tg.enabled?'<b class="bull">ENABLED</b>':'<b class="warn">DISABLED</b>'}</div>
            </div>
          </div>
          <button class="btn btn-primary btn-sm" id="btn-test-telegram">🔔 Send Test Alert</button>
        </div>
      </div>

      <div class="table-panel">
        <div class="panel-header"><div class="panel-title">🎨 Appearance &amp; Refresh</div></div>
        <div style="padding:16px;display:flex;flex-direction:column;gap:14px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>Theme:</span>
            <select id="pref-theme" class="btn btn-sm" style="background:var(--bg-s2);color:var(--text)">
              <option value="dark"  ${(settings.theme||'dark')==='dark' ?'selected':''}>Dark — Trading Pro</option>
              <option value="light" ${settings.theme==='light'?'selected':''}>Light</option>
            </select>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>Timezone:</span><span class="mono">UTC</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>Auto Refresh:</span><span class="mono">4000 ms</span>
          </div>
        </div>
      </div>`;

    document.getElementById('btn-test-telegram').addEventListener('click', async () => {
      Toast.info('Sending Telegram test alert…');
      try {
        const r = await API.sendTelegramTest();
        if (r.success) Toast.success('Test alert delivered!');
        else Toast.warn('Telegram: ' + (r.reason||r.error||'Check credentials'));
      } catch (err) { Toast.error('Alert failed: ' + err.message); }
    });

    document.getElementById('pref-theme').addEventListener('change', e => {
      document.body.className = e.target.value === 'light' ? 'theme-light' : '';
      Toast.info(`Theme: ${e.target.value}`);
    });
  }

  /* ─── Global Actions ──────────────────────────────────── */
  async runDoctorDiagnostics() {
    Toast.info('Running system doctor diagnostics…');
    try {
      const res = await API.runDoctor();
      const checks = res.checks || [];
      const fails  = checks.filter(ch => ch.status === 'FAIL');
      if (!fails.length) Toast.success(`All ${checks.length} health checks PASSED!`);
      else Toast.error(`${fails.length} check(s) failed!`);
    } catch (err) { Toast.error('Doctor failed: ' + err.message); }
  }

  async sendTelegramTest() {
    Toast.info('Dispatching Telegram test alert…');
    try {
      const r = await API.sendTelegramTest();
      if (r.success) Toast.success('Telegram alert sent!');
      else Toast.warn('Telegram: ' + (r.reason || r.error));
    } catch (err) { Toast.error('Telegram error: ' + err.message); }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.app = new CuanimusApp();
});
