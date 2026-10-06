/**
 * CUANIMUS Web Control Center — UI Components v2
 * Toast, Modals (Login, Emergency Stop, Decision Trace, AI Copilot, Trading Profile)
 * Command Palette — All fully wired to real API endpoints.
 */

// ═══════════════════════════════════════════════════════════════
// 1. TOAST MANAGER
// ═══════════════════════════════════════════════════════════════
const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      document.body.appendChild(this.container);
    }
  },

  show(message, type = 'info', duration = 4000) {
    if (!this.container) this.init();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icons = { success: '✅', error: '❌', warn: '⚠️', info: 'ℹ️', ai: '🤖' };
    el.innerHTML = `<span style="flex-shrink:0">${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
    this.container.appendChild(el);
    setTimeout(() => {
      el.style.transition = 'all 0.28s ease';
      el.style.opacity = '0';
      el.style.transform = 'translateX(110%)';
      setTimeout(() => el.remove(), 280);
    }, duration);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg)   { this.show(msg, 'error'); },
  warn(msg)    { this.show(msg, 'warn'); },
  info(msg)    { this.show(msg, 'info'); },
  ai(msg)      { this.show(msg, 'ai'); }
};

// ═══════════════════════════════════════════════════════════════
// 2. MODAL CONTROLLER
// ═══════════════════════════════════════════════════════════════
const Modals = {
  open(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
  },
  close(id) {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('active'); }
  },
  _remove(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  },

  // ─── LOGIN MODAL ──────────────────────────────────────────────
  showLoginModal(onSuccess = null) {
    this._remove('modal-login');
    document.body.insertAdjacentHTML('beforeend', `
      <div id="modal-login" class="modal-overlay active">
        <div class="modal-box" style="max-width:420px">
          <div class="modal-header">
            <div class="modal-title">🔐 CUANIMUS AUTHENTICATION</div>
            <button class="modal-close" onclick="Modals.close('modal-login')">✕</button>
          </div>
          <div class="modal-body">
            <p style="color:var(--text-sec);margin-bottom:16px;font-size:12px">
              Sign in with your Operator credentials to unlock trading controls.
            </p>
            <div style="margin-bottom:12px">
              <label class="form-label">Username</label>
              <input type="text" id="login-username" class="form-input" placeholder="admin" autofocus>
            </div>
            <div style="margin-bottom:6px">
              <label class="form-label">Password</label>
              <input type="password" id="login-password" class="form-input" placeholder="••••••••••">
            </div>
            <div id="login-error-msg" style="color:var(--bear);font-size:11px;margin-top:6px;display:none"></div>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="Modals.close('modal-login')">Cancel</button>
            <button class="btn btn-primary" id="btn-submit-login">Sign In</button>
          </div>
        </div>
      </div>
    `);

    const submit = async () => {
      const u = document.getElementById('login-username').value.trim();
      const p = document.getElementById('login-password').value;
      const errBox = document.getElementById('login-error-msg');
      errBox.style.display = 'none';
      if (!u || !p) { errBox.textContent = 'Username and password required'; errBox.style.display = 'block'; return; }
      document.getElementById('btn-submit-login').disabled = true;
      try {
        const res = await API.login(u, p);
        Toast.success(`Welcome back, ${res.username} [${res.role}]!`);
        this.close('modal-login');
        if (onSuccess) onSuccess(res);
        if (window.app) window.app.checkAuthStatus();
      } catch (err) {
        errBox.textContent = err.message || 'Invalid credentials';
        errBox.style.display = 'block';
        document.getElementById('btn-submit-login').disabled = false;
      }
    };

    document.getElementById('btn-submit-login').addEventListener('click', submit);
    document.getElementById('login-password').addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
    document.getElementById('modal-login').addEventListener('click', e => { if (e.target.id === 'modal-login') this.close('modal-login'); });
  },

  // ─── EMERGENCY STOP MODAL ─────────────────────────────────────
  showEmergencyStopModal() {
    this._remove('modal-emergency-stop');
    document.body.insertAdjacentHTML('beforeend', `
      <div id="modal-emergency-stop" class="modal-overlay active">
        <div class="modal-box" style="border-color:#ff4d72">
          <div class="modal-header" style="background:rgba(255,77,114,0.12)">
            <div class="modal-title" style="color:#ff4d72">🚨 CONFIRM EMERGENCY KILL SWITCH</div>
            <button class="modal-close" onclick="Modals.close('modal-emergency-stop')">✕</button>
          </div>
          <div class="modal-body">
            <p style="font-size:13px;font-weight:700;margin-bottom:10px">
              Are you sure you want to trigger the global human kill-switch?
            </p>
            <ul style="padding-left:18px;margin-bottom:14px;color:var(--text-sec);line-height:1.7;font-size:12px">
              <li>All active trading sessions will be halted <b>immediately</b>.</li>
              <li>The independent RiskEngine will lock out all new orders.</li>
              <li>Pending unfilled limit orders will be cancelled.</li>
              <li>High-priority alert dispatched to Telegram.</li>
            </ul>
            <div>
              <label class="form-label">Reason for Emergency Stop:</label>
              <input type="text" id="emergency-reason-input" class="form-input" value="Operator manual intervention via Web UI">
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="Modals.close('modal-emergency-stop')">Cancel</button>
            <button class="btn btn-danger" id="btn-confirm-emergency-kill">⛔ EXECUTE EMERGENCY STOP</button>
          </div>
        </div>
      </div>
    `);

    document.getElementById('btn-confirm-emergency-kill').addEventListener('click', async () => {
      const reason = document.getElementById('emergency-reason-input').value || 'Operator Emergency Stop';
      document.getElementById('btn-confirm-emergency-kill').disabled = true;
      try {
        await API.triggerEmergencyStop(reason);
        Toast.error('EMERGENCY KILL SWITCH ACTIVATED. System Locked.');
        this.close('modal-emergency-stop');
        if (window.app) window.app.refreshAll();
      } catch (err) {
        Toast.error('Failed to execute emergency stop: ' + err.message);
        document.getElementById('btn-confirm-emergency-kill').disabled = false;
      }
    });

    document.getElementById('modal-emergency-stop').addEventListener('click', e => {
      if (e.target.id === 'modal-emergency-stop') this.close('modal-emergency-stop');
    });
  },

  // ─── DECISION TRACE MODAL ─────────────────────────────────────
  showDecisionTraceModal(trace) {
    if (!trace) return;
    let stepsHtml = '';
    (trace.steps || []).forEach(step => {
      const isOk = ['PASS', 'APPROVED', 'FILLED', 'EXECUTED'].includes(step.status);
      const dotClass = isOk ? 'pass' : (step.status === 'VETOED' ? 'veto' : 'warn');
      stepsHtml += `
        <div class="timeline-item">
          <div class="timeline-dot ${dotClass}"></div>
          <div class="timeline-content">
            <div class="timeline-title">
              <span>${step.stage}: ${step.title}</span>
              <span class="badge ${isOk ? 'badge-bull' : 'badge-bear'}">${step.status}</span>
            </div>
            <div class="timeline-detail">${step.detail}</div>
          </div>
        </div>`;
    });

    this._remove('modal-decision-trace');
    document.body.insertAdjacentHTML('beforeend', `
      <div id="modal-decision-trace" class="modal-overlay active">
        <div class="modal-box" style="max-width:680px">
          <div class="modal-header">
            <div class="modal-title">🔍 DECISION TRACE: ${trace.symbol || 'MARKET'}</div>
            <button class="modal-close" onclick="Modals.close('modal-decision-trace')">✕</button>
          </div>
          <div class="modal-body">
            <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-sec);margin-bottom:12px;background:var(--bg-s3);padding:8px;border-radius:6px">
              <span>Timestamp: <b>${trace.timestamp || 'N/A'}</b></span>
              <span>Trade ID: <b>${trace.trade_id || 'Signal Abstained'}</b></span>
            </div>
            <div class="timeline">${stepsHtml || '<p style="color:var(--text-muted);text-align:center">No trace steps available.</p>'}</div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" onclick="Modals.close('modal-decision-trace')">Close</button>
          </div>
        </div>
      </div>
    `);
    document.getElementById('modal-decision-trace').addEventListener('click', e => {
      if (e.target.id === 'modal-decision-trace') this.close('modal-decision-trace');
    });
  },

  // ─── AUTONOMOUS TRACE MODAL ───────────────────────────────────
  showAutonomousTraceModal(trace) {
    if (!trace) return;

    const traceRows = [
      {
        step: '1. Market Data Boundary',
        badge: '<span class="badge badge-bull">CLOSED BAR</span>',
        detail: `Candle: ${trace.candle_timestamp} · Price: ${trace.market_price}. Causal evaluation boundary verified.`,
        dot: 'pass'
      },
      {
        step: '2. Strategy Template Signal',
        badge: `<span class="badge ${trace.strategy_signal === 'LONG' || trace.strategy_signal === 'SHORT' ? 'badge-bull' : 'badge-neutral'}">${trace.strategy_signal || 'N/A'}</span>`,
        detail: trace.strategy_signal === 'N/A' ? 'Not applicable for AI-only mode.' : 'Evaluated via Strategy Template. Strictly closed candle data.',
        dot: trace.strategy_signal === 'HOLD' || trace.strategy_signal === 'N/A' ? 'warn' : 'pass'
      },
      {
        step: '3. AI Agent Decision',
        badge: `<span class="badge ${trace.ai_decision === 'LONG' || trace.ai_decision === 'APPROVE' ? 'badge-bull' : 'badge-neutral'}">${trace.ai_decision || 'N/A'} ${trace.ai_confidence ? '(' + Math.round(trace.ai_confidence * 100) + '%)' : ''}</span>`,
        detail: trace.ai_decision === 'N/A' ? 'Not applicable for Strategy-only mode.' : 'Agent evaluated market context and produced structured intent.',
        dot: trace.ai_decision === 'N/A' || trace.ai_decision === 'HOLD' ? 'warn' : 'pass'
      },
      {
        step: '4. Agent Policy Guard',
        badge: `<span class="badge ${trace.policy_result === 'APPROVED' ? 'badge-bull' : 'badge-bear'}">${trace.policy_result || 'N/A'}</span>`,
        detail: 'Environment bounds, risk limits, and mandatory SL verification.',
        dot: trace.policy_result === 'APPROVED' ? 'pass' : 'veto'
      },
      {
        step: '5. Risk Engine (FINAL AUTHORITY)',
        badge: `<span class="badge ${trace.risk_result === 'APPROVED' ? 'badge-bull' : 'badge-bear'}">${trace.risk_result || 'N/A'}</span>`,
        detail: 'Emergency stop clearance, portfolio drawdown limits, and position sizing.',
        dot: trace.risk_result === 'APPROVED' ? 'pass' : 'veto'
      },
      {
        step: '6. Execution Coordinator',
        badge: `<span class="badge ${trace.execution_status === 'EXECUTED' ? 'badge-bull' : 'badge-bear'}">${trace.execution_status || 'N/A'}</span>`,
        detail: `Order ID: ${trace.order_id || 'None'}. Status: ${trace.execution_status || 'N/A'}.`,
        dot: trace.execution_status === 'EXECUTED' ? 'pass' : 'veto'
      }
    ];

    const timelineHtml = traceRows.map(r => `
      <div class="timeline-item">
        <div class="timeline-dot ${r.dot}"></div>
        <div class="timeline-content">
          <div class="timeline-title"><span>${r.step}</span>${r.badge}</div>
          <div class="timeline-detail">${r.detail}</div>
        </div>
      </div>`).join('');

    this._remove('modal-auto-trace');
    document.body.insertAdjacentHTML('beforeend', `
      <div id="modal-auto-trace" class="modal-overlay active">
        <div class="modal-box" style="max-width:680px">
          <div class="modal-header">
            <div class="modal-title">🔍 AUTONOMOUS TRACE: ${trace.symbol} (${trace.timeframe})</div>
            <button class="modal-close" onclick="Modals.close('modal-auto-trace')">✕</button>
          </div>
          <div class="modal-body">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;background:var(--bg-s3);padding:10px;border-radius:6px;margin-bottom:14px">
              <div>Trace ID: <b>${trace.trace_id}</b></div>
              <div>Timestamp: <b>${trace.decision_timestamp}</b></div>
              <div>Mode: <b style="text-transform:uppercase">${trace.decision_mode}</b></div>
              <div>Market Price: <b>$${trace.market_price}</b></div>
            </div>
            <div class="timeline">${timelineHtml}</div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" onclick="Modals.close('modal-auto-trace')">Close</button>
          </div>
        </div>
      </div>
    `);
    document.getElementById('modal-auto-trace').addEventListener('click', e => {
      if (e.target.id === 'modal-auto-trace') this.close('modal-auto-trace');
    });
  },

  // ─── AI COPILOT MODAL ────────────────────────────────────────
  showAiCopilotModal() {
    this._remove('modal-ai-copilot');
    document.body.insertAdjacentHTML('beforeend', `
      <div id="modal-ai-copilot" class="modal-overlay active">
        <div class="modal-box" style="max-width:640px">
          <div class="modal-header">
            <div class="modal-title" style="color:var(--lavender)">🤖 AI CONFIGURATION COPILOT</div>
            <button class="modal-close" onclick="Modals.close('modal-ai-copilot')">✕</button>
          </div>
          <div class="modal-body">
            <p style="color:var(--text-sec);margin-bottom:14px;font-size:12px">
              Describe your desired trading setup in plain language. CUANIMUS AI Agent will propose a validated configuration.
            </p>
            <div style="display:flex;gap:8px;margin-bottom:16px">
              <input type="text" id="copilot-prompt-input" class="form-input" placeholder="e.g. Conservative ETH paper trading with 0.5% risk and hybrid_v2c strategy">
              <button class="btn btn-ai" id="btn-copilot-generate" style="white-space:nowrap">Generate ✨</button>
            </div>
            <div id="copilot-result-container" style="display:none;background:var(--bg-s3);border:1px solid var(--lavender-border);border-radius:8px;padding:14px">
              <div style="font-weight:700;color:var(--lavender);margin-bottom:8px" id="copilot-summary-text"></div>
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Proposed Changes:</div>
              <div id="copilot-diff-list" style="font-family:var(--mono);font-size:11px;max-height:180px;overflow-y:auto;background:var(--bg-app);padding:10px;border-radius:5px"></div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="Modals.close('modal-ai-copilot')">Cancel</button>
            <button class="btn btn-primary" id="btn-copilot-apply" style="display:none">✅ Apply Configuration</button>
          </div>
        </div>
      </div>
    `);

    let activeProposal = null;

    document.getElementById('btn-copilot-generate').addEventListener('click', async () => {
      const prompt = document.getElementById('copilot-prompt-input').value.trim();
      if (!prompt) return;
      const btn = document.getElementById('btn-copilot-generate');
      btn.disabled = true;
      btn.textContent = '⏳ Thinking...';
      Toast.ai('AI Agent evaluating configuration intent...');
      try {
        const res = await API.proposeConfig(prompt);
        activeProposal = res;
        document.getElementById('copilot-summary-text').textContent = res.summary || 'Configuration Proposal Generated';
        let diffHtml = '';
        (res.diff || []).forEach(d => {
          diffHtml += `<div style="padding:3px 0"><span style="color:var(--text-sec)">${d.path}:</span> <span style="color:var(--bear)">${JSON.stringify(d.from)}</span> → <span style="color:var(--bull)">${JSON.stringify(d.to)}</span></div>`;
        });
        document.getElementById('copilot-diff-list').innerHTML = diffHtml || '<div style="color:var(--text-muted)">No changes required.</div>';
        document.getElementById('copilot-result-container').style.display = 'block';
        document.getElementById('btn-copilot-apply').style.display = 'inline-flex';
      } catch (err) {
        Toast.error('Failed to generate configuration: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Generate ✨';
      }
    });

    document.getElementById('btn-copilot-apply').addEventListener('click', async () => {
      if (!activeProposal) return;
      const btn = document.getElementById('btn-copilot-apply');
      btn.disabled = true;
      try {
        await API.saveConfig(activeProposal.proposed_configuration, 'cuanimus.user.yaml');
        Toast.success('Configuration applied and saved!');
        this.close('modal-ai-copilot');
        if (window.app) window.app.refreshAll();
      } catch (err) {
        Toast.error('Failed to apply configuration: ' + err.message);
        btn.disabled = false;
      }
    });

    document.getElementById('modal-ai-copilot').addEventListener('click', e => {
      if (e.target.id === 'modal-ai-copilot') this.close('modal-ai-copilot');
    });
  },

  // ─── TRADING PROFILE CREATE/EDIT MODAL ───────────────────────
  async showProfileModal(profile = null, onSaved = null) {
    const isEdit = !!profile;
    const p = profile || {
      profile_id: '',
      name: '',
      symbol: 'ADA/USDT:USDT',
      timeframe: '15m',
      decision_mode: 'strategy',
      strategy_id: 'hybrid_v2c',
      agent_id: '',
      risk_profile: 'conservative',
      execution_mode: 'paper',
      max_open_positions: 1,
      max_trades_per_day: 10,
      stop_loss_pct: 1.5,
      take_profit_pct: 3.0,
      enabled: true
    };

    // Fetch real data from API
    let strategies = ['hybrid_v2c', 'pullback_v2a', 'structure_v2b', 'baseline_v0', 'atr_v1'];
    let agents = [];
    let pairs = ['ADA/USDT:USDT', 'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'XRP/USDT:USDT', 'BNB/USDT:USDT'];

    try {
      const [stratRes, agentRes, pairRes] = await Promise.all([
        API.getStrategies().catch(() => ({ strategies: [] })),
        API.getAgents().catch(() => ({ agents: [] })),
        API.getPairs().catch(() => ({ pairs: [] }))
      ]);
      if (stratRes.strategies?.length) strategies = stratRes.strategies.map(s => ({ id: s.strategy_id, name: s.name || s.strategy_id }));
      else strategies = strategies.map(s => ({ id: s, name: s }));
      if (agentRes.agents?.length) agents = agentRes.agents.map(a => ({ id: a.agent_id, name: a.agent_id }));
      if (pairRes.pairs?.length) pairs = pairRes.pairs.map(pr => pr.internal || pr.symbol || pr);
    } catch (_) {}

    const stratOpts = strategies.map(s => `<option value="${s.id}" ${s.id === p.strategy_id ? 'selected' : ''}>${s.id}</option>`).join('');
    const agentOpts = agents.length
      ? agents.map(a => `<option value="${a.id}" ${a.id === p.agent_id ? 'selected' : ''}>${a.id}</option>`).join('')
      : '<option value="">No agents configured</option>';
    const pairOpts = pairs.map(pr => `<option value="${pr}" ${pr === p.symbol ? 'selected' : ''}>${pr}</option>`).join('');

    this._remove('modal-trading-profile');
    document.body.insertAdjacentHTML('beforeend', `
      <div id="modal-trading-profile" class="modal-overlay active">
        <div class="modal-box" style="max-width:640px">
          <div class="modal-header">
            <div class="modal-title">🚀 ${isEdit ? 'EDIT TRADING PROFILE' : 'CREATE TRADING PROFILE'}</div>
            <button class="modal-close" onclick="Modals.close('modal-trading-profile')">✕</button>
          </div>
          <div class="modal-body">

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
              <div>
                <label class="form-label">Profile Name</label>
                <input type="text" id="prof-name" class="form-input" value="${p.name || ''}" placeholder="e.g. ADA-15M-HYBRID">
              </div>
              <div>
                <label class="form-label">Trading Pair</label>
                <select id="prof-symbol" class="form-input">${pairOpts}</select>
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
              <div>
                <label class="form-label">Timeframe</label>
                <select id="prof-timeframe" class="form-input">
                  <option value="5m"  ${p.timeframe==='5m' ?'selected':''}>5m — Scalp</option>
                  <option value="15m" ${p.timeframe==='15m'?'selected':''}>15m — Intraday</option>
                  <option value="1h"  ${p.timeframe==='1h' ?'selected':''}>1h — Swing</option>
                  <option value="4h"  ${p.timeframe==='4h' ?'selected':''}>4h — Macro Trend</option>
                </select>
              </div>
              <div>
                <label class="form-label">Decision Mode</label>
                <select id="prof-decision-mode" class="form-input">
                  <option value="strategy" ${p.decision_mode==='strategy' ?'selected':''}>Mode A — Strategy Template</option>
                  <option value="ai_agent" ${p.decision_mode==='ai_agent' ?'selected':''}>Mode B — AI Agent Autotrade</option>
                  <option value="hybrid"   ${p.decision_mode==='hybrid'   ?'selected':''}>Mode C — Hybrid (Strategy + AI)</option>
                </select>
              </div>
            </div>

            <div id="prof-field-strategy" class="field-group-strategy">
              <div class="field-group-label-strategy">🧠 Strategy Template (Quantitative Rules)</div>
              <select id="prof-strategy" class="form-input">${stratOpts}</select>
            </div>

            <div id="prof-field-agent" class="field-group-agent">
              <div class="field-group-label-agent">🤖 AI Agent (Agent Gateway & Structured Intent)</div>
              <select id="prof-agent" class="form-input">${agentOpts}</select>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
              <div>
                <label class="form-label">Risk Engine Profile</label>
                <select id="prof-risk" class="form-input">
                  <option value="conservative" ${p.risk_profile==='conservative'?'selected':''}>Conservative — 0.5% risk, max 3×</option>
                  <option value="balanced"     ${p.risk_profile==='balanced'    ?'selected':''}>Balanced — 1.0% risk, max 5×</option>
                  <option value="aggressive"   ${p.risk_profile==='aggressive'  ?'selected':''}>Aggressive — 1.5% risk, max 7×</option>
                </select>
              </div>
              <div>
                <label class="form-label">Execution Mode</label>
                <select id="prof-exec" class="form-input">
                  <option value="paper"   ${p.execution_mode==='paper'  ?'selected':''}>📄 PAPER — Safe Simulation</option>
                  <option value="testnet" ${p.execution_mode==='testnet'?'selected':''}>🧪 TESTNET — Binance Futures Testnet</option>
                  <option value="live"    ${p.execution_mode==='live'   ?'selected':''}>⚡ LIVE — Binance Real Capital</option>
                </select>
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px">
              <div>
                <label class="form-label">Max Positions</label>
                <input type="number" id="prof-max-pos" class="form-input" value="${p.max_open_positions||1}" min="1" max="10">
              </div>
              <div>
                <label class="form-label">Max Trades/Day</label>
                <input type="number" id="prof-max-trades" class="form-input" value="${p.max_trades_per_day||10}" min="1" max="50">
              </div>
              <div>
                <label class="form-label">Stop Loss %</label>
                <input type="number" step="0.1" id="prof-sl" class="form-input" value="${p.stop_loss_pct||1.5}">
              </div>
              <div>
                <label class="form-label">Take Profit %</label>
                <input type="number" step="0.1" id="prof-tp" class="form-input" value="${p.take_profit_pct||3.0}">
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn" onclick="Modals.close('modal-trading-profile')">Cancel</button>
            <button class="btn btn-primary" id="btn-save-profile">
              ${isEdit ? '💾 Save Changes' : '🚀 Create Profile'}
            </button>
          </div>
        </div>
      </div>
    `);

    // Decision mode visibility logic
    const modeSelect = document.getElementById('prof-decision-mode');
    const stratField = document.getElementById('prof-field-strategy');
    const agentField = document.getElementById('prof-field-agent');
    const updateVis = () => {
      const m = modeSelect.value;
      stratField.style.display = (m === 'strategy' || m === 'hybrid') ? 'block' : 'none';
      agentField.style.display  = (m === 'ai_agent' || m === 'hybrid') ? 'block' : 'none';
    };
    modeSelect.addEventListener('change', updateVis);
    updateVis();

    // Save button
    document.getElementById('btn-save-profile').addEventListener('click', async () => {
      const name = document.getElementById('prof-name').value.trim();
      if (!name) { Toast.warn('Please enter a profile name'); return; }

      const btn = document.getElementById('btn-save-profile');
      btn.disabled = true;

      const data = {
        name,
        symbol:              document.getElementById('prof-symbol').value,
        timeframe:           document.getElementById('prof-timeframe').value,
        decision_mode:       document.getElementById('prof-decision-mode').value,
        strategy_id:         document.getElementById('prof-strategy').value,
        agent_id:            document.getElementById('prof-agent').value,
        risk_profile:        document.getElementById('prof-risk').value,
        execution_mode:      document.getElementById('prof-exec').value,
        max_open_positions:  parseInt(document.getElementById('prof-max-pos').value)    || 1,
        max_trades_per_day:  parseInt(document.getElementById('prof-max-trades').value) || 10,
        stop_loss_pct:       parseFloat(document.getElementById('prof-sl').value)       || 1.5,
        take_profit_pct:     parseFloat(document.getElementById('prof-tp').value)       || 3.0,
      };

      try {
        if (isEdit && p.profile_id) {
          await API.updateTradingProfile(p.profile_id, data);
          Toast.success(`Profile '${name}' updated!`);
        } else {
          await API.createTradingProfile(data);
          Toast.success(`Trading profile '${name}' created!`);
        }
        this.close('modal-trading-profile');
        if (onSaved) onSaved();
      } catch (err) {
        Toast.error('Failed to save profile: ' + err.message);
        btn.disabled = false;
      }
    });

    document.getElementById('modal-trading-profile').addEventListener('click', e => {
      if (e.target.id === 'modal-trading-profile') this.close('modal-trading-profile');
    });
  }
};

// ═══════════════════════════════════════════════════════════════
// 3. COMMAND PALETTE (Ctrl+K)
// ═══════════════════════════════════════════════════════════════
const CommandPalette = {
  commands: [
    { title: '📊  Overview Dashboard',       action: () => window.app.navigate('overview') },
    { title: '⚡  Trading Terminal',          action: () => window.app.navigate('trading') },
    { title: '🌐  Markets & Regimes',         action: () => window.app.navigate('markets') },
    { title: '🧠  Strategy Center',           action: () => window.app.navigate('strategies') },
    { title: '🧪  Research & Backtesting',    action: () => window.app.navigate('research') },
    { title: '🛡️  Risk Control Center',       action: () => window.app.navigate('risk') },
    { title: '🚀  Autonomous Trading Engine', action: () => window.app.navigate('autonomous') },
    { title: '🤖  AI Agent Center',           action: () => window.app.navigate('agents') },
    { title: '⚙️  Configuration Center',      action: () => window.app.navigate('config') },
    { title: '💾  Data Center',               action: () => window.app.navigate('data') },
    { title: '📜  Logs & Events',             action: () => window.app.navigate('logs') },
    { title: '📱  Settings & Telegram',       action: () => window.app.navigate('settings') },
    { title: '✨  Create Autonomous Trading Profile', action: () => Modals.showProfileModal() },
    { title: '🤖  Ask AI Copilot',            action: () => Modals.showAiCopilotModal() },
    { title: '🩺  Run System Diagnostics',    action: () => window.app.runDoctorDiagnostics() },
    { title: '🔔  Send Telegram Test Alert',  action: () => window.app.sendTelegramTest() },
    { title: '🚨  Emergency Kill Switch',     action: () => Modals.showEmergencyStopModal() },
  ],

  init() {
    window.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        this.open();
      }
      if (e.key === 'Escape') this.close();
    });
  },

  open() {
    this.close();
    const listHtml = this.commands.map((cmd, idx) => `
      <div class="cmd-item" data-index="${idx}">
        <span>${cmd.title}</span>
        <span class="cmd-shortcut">↵</span>
      </div>`).join('');

    document.body.insertAdjacentHTML('beforeend', `
      <div id="modal-cmd-palette" class="modal-overlay active">
        <div class="modal-box cmd-palette-box">
          <input type="text" id="cmd-search-input" class="cmd-palette-search" placeholder="Search commands (e.g. Risk, Backtest, Profile)..." autofocus>
          <div class="cmd-list" id="cmd-list-container">${listHtml}</div>
        </div>
      </div>
    `);

    document.getElementById('cmd-search-input').addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll('.cmd-item').forEach((item, idx) => {
        item.style.display = this.commands[idx].title.toLowerCase().includes(q) ? 'flex' : 'none';
      });
    });

    document.querySelectorAll('.cmd-item').forEach(item => {
      item.addEventListener('click', () => {
        const idx = parseInt(item.getAttribute('data-index'));
        this.close();
        this.commands[idx].action();
      });
    });

    document.getElementById('modal-cmd-palette').addEventListener('click', e => {
      if (e.target.id === 'modal-cmd-palette') this.close();
    });
  },

  close() {
    const el = document.getElementById('modal-cmd-palette');
    if (el) el.remove();
  }
};

window.Toast = Toast;
window.Modals = Modals;
window.CommandPalette = CommandPalette;
