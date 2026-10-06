/**
 * CUANIMUS Web Control Center — UI Components & Interaction Modules.
 * Includes Toast Manager, Modal Controllers, Decision Trace Inspector,
 * AI Configuration Assistant, and Command Palette (Ctrl+K).
 */

// 1. Toast Notification Manager
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

  show(message, type = 'info', duration = 3500) {
    if (!this.container) this.init();
    const el = document.createElement('div');
    el.className = `toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warn') icon = '⚠️';

    el.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    this.container.appendChild(el);

    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateX(100%)';
      el.style.transition = 'all 0.25s ease';
      setTimeout(() => el.remove(), 250);
    }, duration);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg) { this.show(msg, 'error'); },
  warn(msg) { this.show(msg, 'warn'); },
  info(msg) { this.show(msg, 'info'); }
};

// 2. Modal Controller
const Modals = {
  open(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
  },

  close(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  },

  // User Login Modal
  showLoginModal(onSuccess = null) {
    const modalHtml = `
      <div id="modal-login" class="modal-overlay active">
        <div class="modal-box" style="max-width: 420px;">
          <div class="modal-header">
            <div class="modal-title" style="display: flex; align-items: center; gap: 8px;">
              <span>🔐</span> CUANIMUS AUTHENTICATION
            </div>
            <button class="modal-close" onclick="Modals.close('modal-login')">✕</button>
          </div>
          <div class="modal-body">
            <p style="color: #9baac3; margin-bottom: 14px; font-size: 12px;">
              Sign in with your Operator or Administrator credentials to unlock trading controls.
            </p>
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 11px; color: #9baac3; margin-bottom: 4px;">Username</label>
              <input type="text" id="login-username" class="cmd-input" style="border: 1px solid #334155; border-radius: 4px; padding: 8px 12px;" placeholder="admin" autofocus>
            </div>
            <div style="margin-bottom: 14px;">
              <label style="display: block; font-size: 11px; color: #9baac3; margin-bottom: 4px;">Password</label>
              <input type="password" id="login-password" class="cmd-input" style="border: 1px solid #334155; border-radius: 4px; padding: 8px 12px;" placeholder="••••••••••••">
            </div>
            <div id="login-error-msg" style="color: #f73859; font-size: 11px; margin-bottom: 8px; display: none;"></div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" id="btn-submit-login" style="width: 100%;">Sign In</button>
          </div>
        </div>
      </div>
    `;

    const old = document.getElementById('modal-login');
    if (old) old.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const submit = async () => {
      const u = document.getElementById('login-username').value.trim();
      const p = document.getElementById('login-password').value;
      const errBox = document.getElementById('login-error-msg');
      if (!u || !p) return;

      try {
        const res = await API.login(u, p);
        Toast.success(`Welcome back, ${res.username} [${res.role}]!`);
        Modals.close('modal-login');
        if (onSuccess) onSuccess(res);
        if (window.app) window.app.checkAuthStatus();
      } catch (err) {
        errBox.textContent = err.message || "Invalid credentials";
        errBox.style.display = 'block';
      }
    };

    document.getElementById('btn-submit-login').addEventListener('click', submit);
    document.getElementById('login-password').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submit();
    });
  },

  // Emergency Stop Confirmation Modal
  showEmergencyStopModal() {
    const modalHtml = `
      <div id="modal-emergency-stop" class="modal-overlay active">
        <div class="modal-box" style="border-color: #f73859;">
          <div class="modal-header" style="background-color: rgba(247, 56, 89, 0.15);">
            <div class="modal-title" style="color: #f73859; display: flex; align-items: center; gap: 8px;">
              <span>🚨</span> CONFIRM EMERGENCY KILL SWITCH
            </div>
            <button class="modal-close" onclick="Modals.close('modal-emergency-stop')">✕</button>
          </div>
          <div class="modal-body">
            <p style="font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 8px;">
              Are you sure you want to trigger the global human kill-switch?
            </p>
            <ul style="padding-left: 18px; margin-bottom: 12px; color: #9baac3; line-height: 1.6;">
              <li>All active AI Agent and Paper trading sessions will be halted immediately.</li>
              <li>The independent <b>RiskEngine</b> will lock out all new orders.</li>
              <li>Pending unfilled limit orders will be cancelled.</li>
              <li>A high-priority alert will be dispatched to Telegram.</li>
            </ul>
            <div style="margin-top: 12px;">
              <label style="display:block; font-size: 11px; color: #9baac3; margin-bottom: 4px;">Reason for Emergency Stop:</label>
              <input type="text" id="emergency-reason-input" class="cmd-input" style="border: 1px solid #334155; border-radius: 4px; padding: 8px 12px;" value="Operator manual intervention via Web UI">
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="Modals.close('modal-emergency-stop')">Cancel</button>
            <button class="btn btn-danger" id="btn-confirm-emergency-kill">
              EXECUTE EMERGENCY STOP
            </button>
          </div>
        </div>
      </div>
    `;

    const old = document.getElementById('modal-emergency-stop');
    if (old) old.remove();

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    document.getElementById('btn-confirm-emergency-kill').addEventListener('click', async () => {
      const reason = document.getElementById('emergency-reason-input').value;
      try {
        const res = await API.triggerEmergencyStop(reason);
        Toast.error("EMERGENCY KILL SWITCH ACTIVATED. System Locked.");
        Modals.close('modal-emergency-stop');
        window.app.refreshAll();
      } catch (err) {
        Toast.error("Failed to execute emergency stop: " + err.message);
      }
    });
  },

  // Decision Trace Inspector Modal
  showDecisionTraceModal(trace) {
    if (!trace) return;

    let stepsHtml = '';
    (trace.steps || []).forEach(step => {
      let dotClass = 'pass';
      if (step.status === 'VETOED' || step.status === 'ABSTAINED') dotClass = 'veto';
      if (step.status === 'WARNING') dotClass = 'warn';

      stepsHtml += `
        <div class="timeline-item">
          <div class="timeline-dot ${dotClass}"></div>
          <div class="timeline-content">
            <div class="timeline-title">
              <span>${step.stage}: ${step.title}</span>
              <span class="badge ${step.status === 'PASS' || step.status === 'APPROVED' || step.status === 'FILLED' ? 'badge-bull' : 'badge-bear'}">${step.status}</span>
            </div>
            <div class="timeline-detail">${step.detail}</div>
          </div>
        </div>
      `;
    });

    const modalHtml = `
      <div id="modal-decision-trace" class="modal-overlay active">
        <div class="modal-box" style="max-width: 680px;">
          <div class="modal-header">
            <div class="modal-title">
              <span>🔍</span> DECISION TRACE: ${trace.symbol || 'MARKET'} (${trace.trace_id || ''})
            </div>
            <button class="modal-close" onclick="Modals.close('modal-decision-trace')">✕</button>
          </div>
          <div class="modal-body">
            <div style="margin-bottom: 12px; display: flex; justify-content: space-between; font-size: 11px; color: #9baac3;">
              <span>Timestamp: <b>${trace.timestamp || 'N/A'}</b></span>
              <span>Trade ID: <b>${trace.trade_id || 'Signal Abstained'}</b></span>
            </div>
            <div class="timeline">
              ${stepsHtml}
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" onclick="Modals.close('modal-decision-trace')">Close</button>
          </div>
        </div>
      </div>
    `;

    const old = document.getElementById('modal-decision-trace');
    if (old) old.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);
  },

  // AI Configuration Assistant Copilot Modal
  showAiCopilotModal() {
    const modalHtml = `
      <div id="modal-ai-copilot" class="modal-overlay active">
        <div class="modal-box" style="max-width: 640px;">
          <div class="modal-header">
            <div class="modal-title" style="display: flex; align-items: center; gap: 8px;">
              <span>🤖</span> CUANIMUS AI CONFIGURATION COPILOT
            </div>
            <button class="modal-close" onclick="Modals.close('modal-ai-copilot')">✕</button>
          </div>
          <div class="modal-body">
            <p style="color: #9baac3; margin-bottom: 12px;">
              Describe your desired trading setup in plain language. CUANIMUS AI Agent will propose a typed, validated configuration.
            </p>
            <div style="display: flex; gap: 8px; margin-bottom: 14px;">
              <input type="text" id="copilot-prompt-input" class="cmd-input" style="border: 1px solid #334155; border-radius: 4px; padding: 10px 14px;" placeholder="e.g. Setup conservative ETH paper trading with 0.5% risk and structure_v2b">
              <button class="btn btn-primary" id="btn-copilot-generate">Generate</button>
            </div>
            <div id="copilot-result-container" style="display: none; background: #0c101a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;">
              <div style="font-weight: 700; color: #38bdf8; margin-bottom: 6px;" id="copilot-summary-text"></div>
              <div style="font-size: 11px; color: #94a3b8; margin-bottom: 8px;">Proposed Diff Preview:</div>
              <div id="copilot-diff-list" style="font-family: monospace; font-size: 11px; max-height: 180px; overflow-y: auto; background: #161d2f; padding: 8px; border-radius: 4px;"></div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="Modals.close('modal-ai-copilot')">Cancel</button>
            <button class="btn btn-success" id="btn-copilot-apply" style="display: none;">Apply Configuration</button>
          </div>
        </div>
      </div>
    `;

    const old = document.getElementById('modal-ai-copilot');
    if (old) old.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    let activeProposal = null;

    document.getElementById('btn-copilot-generate').addEventListener('click', async () => {
      const prompt = document.getElementById('copilot-prompt-input').value.trim();
      if (!prompt) return;

      Toast.info("Agent evaluating configuration intent...");
      try {
        const res = await API.proposeConfig(prompt);
        activeProposal = res;

        document.getElementById('copilot-summary-text').innerText = res.summary || "Configuration Proposal Generated";
        let diffHtml = '';
        (res.diff || []).forEach(d => {
          diffHtml += `<div style="padding: 2px 0;"><span style="color: var(--color-text-secondary);">${d.path}:</span> <span style="color: var(--color-danger);">${JSON.stringify(d.from)}</span> → <span style="color: var(--color-primary);">${JSON.stringify(d.to)}</span></div>`;
        });
        document.getElementById('copilot-diff-list').innerHTML = diffHtml || "<div>No changes required.</div>";
        document.getElementById('copilot-result-container').style.display = 'block';
        document.getElementById('btn-copilot-apply').style.display = 'inline-flex';
      } catch (err) {
        Toast.error("Failed to generate configuration: " + err.message);
      }
    });

    document.getElementById('btn-copilot-apply').addEventListener('click', async () => {
      if (!activeProposal) return;
      try {
        await API.saveConfig(activeProposal.proposed_configuration, "cuanimus.user.yaml");
        Toast.success("New configuration applied and saved to cuanimus.user.yaml!");
        Modals.close('modal-ai-copilot');
        window.app.refreshAll();
      } catch (err) {
        Toast.error("Failed to apply configuration: " + err.message);
      }
    });
  },

  // Trading Profile Creator / Editor Modal
  async showProfileModal(profile = null, onSaved = null) {
    const isEdit = !!profile;
    const p = profile || {
      profile_id: '',
      name: '',
      symbol: 'ADA/USDT:USDT',
      timeframe: '15m',
      decision_mode: 'strategy',
      strategy_id: 'hybrid_v2c',
      agent_id: 'trader-paper',
      risk_profile: 'conservative',
      execution_mode: 'paper',
      max_open_positions: 1,
      max_trades_per_day: 10,
      stop_loss_pct: 1.5,
      take_profit_pct: 3.0,
      enabled: true
    };

    let strategies = ['hybrid_v2c', 'pullback_v2a', 'structure_v2b', 'baseline_v0', 'atr_v1'];
    let agents = ['trader-paper', 'advisory-default', 'supervisor-admin'];
    let pairs = ['ADA/USDT:USDT', 'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'XRP/USDT:USDT', 'BNB/USDT:USDT'];

    try {
      const [stratRes, agentRes, pairRes] = await Promise.all([
        API.getStrategies().catch(() => ({ strategies: [] })),
        API.getAgents().catch(() => ({ agents: [] })),
        API.getPairs().catch(() => ({ pairs: [] }))
      ]);
      if (stratRes.strategies && stratRes.strategies.length) strategies = stratRes.strategies.map(s => s.strategy_id || s.id);
      if (agentRes.agents && agentRes.agents.length) agents = agentRes.agents.map(a => a.agent_id);
      if (pairRes.pairs && pairRes.pairs.length) pairs = pairRes.pairs.map(pr => pr.internal || pr.symbol || pr);
    } catch (_) {}

    const stratOptions = strategies.map(s => `<option value="${s}" ${s === p.strategy_id ? 'selected' : ''}>${s}</option>`).join('');
    const agentOptions = agents.map(a => `<option value="${a}" ${a === p.agent_id ? 'selected' : ''}>${a}</option>`).join('');
    const pairOptions = pairs.map(pr => `<option value="${pr}" ${pr === p.symbol ? 'selected' : ''}>${pr}</option>`).join('');

    const modalHtml = `
      <div id="modal-trading-profile" class="modal-overlay active">
        <div class="modal-box" style="max-width: 620px;">
          <div class="modal-header">
            <div class="modal-title" style="display: flex; align-items: center; gap: 8px;">
              <span>🚀</span> ${isEdit ? 'EDIT TRADING PROFILE' : 'CREATE TRADING PROFILE'}
            </div>
            <button class="modal-close" onclick="Modals.close('modal-trading-profile')">✕</button>
          </div>
          <div class="modal-body">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Profile Name</label>
                <input type="text" id="prof-input-name" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;" value="${p.name || ''}" placeholder="e.g. ADA-15M-HYBRID">
              </div>
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Trading Pair</label>
                <select id="prof-input-symbol" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;">
                  ${pairOptions}
                </select>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px;">
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Timeframe</label>
                <select id="prof-input-timeframe" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;">
                  <option value="5m" ${p.timeframe === '5m' ? 'selected' : ''}>5m (Scalp)</option>
                  <option value="15m" ${p.timeframe === '15m' ? 'selected' : ''}>15m (Intraday Standard)</option>
                  <option value="1h" ${p.timeframe === '1h' ? 'selected' : ''}>1h (Swing Context)</option>
                  <option value="4h" ${p.timeframe === '4h' ? 'selected' : ''}>4h (Macro Trend)</option>
                </select>
              </div>
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Decision Mode</label>
                <select id="prof-input-decision-mode" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;">
                  <option value="strategy" ${p.decision_mode === 'strategy' ? 'selected' : ''}>Mode A: Strategy Template</option>
                  <option value="ai_agent" ${p.decision_mode === 'ai_agent' ? 'selected' : ''}>Mode B: AI Agent Autotrade</option>
                  <option value="hybrid" ${p.decision_mode === 'hybrid' ? 'selected' : ''}>Mode C: Hybrid (Strategy Filter + AI)</option>
                </select>
              </div>
            </div>

            <div id="prof-field-strategy" style="margin-bottom: 12px; background: rgba(69, 255, 202, 0.05); border: 1px solid rgba(69, 255, 202, 0.2); padding: 10px; border-radius: 6px;">
              <label style="display: block; font-size: 11px; color: var(--color-primary); margin-bottom: 4px; font-weight: 600;">Strategy Template (Quantitative Entry Rules)</label>
              <select id="prof-input-strategy" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;">
                ${stratOptions}
              </select>
            </div>

            <div id="prof-field-agent" style="margin-bottom: 12px; background: rgba(214, 123, 255, 0.05); border: 1px solid rgba(214, 123, 255, 0.2); padding: 10px; border-radius: 6px;">
              <label style="display: block; font-size: 11px; color: var(--color-accent-purple); margin-bottom: 4px; font-weight: 600;">AI Agent (Agent Gateway & Structured Intent)</label>
              <select id="prof-input-agent" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;">
                ${agentOptions}
              </select>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Risk Engine Profile</label>
                <select id="prof-input-risk" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;">
                  <option value="conservative" ${p.risk_profile === 'conservative' ? 'selected' : ''}>Conservative (0.5% risk, max 3x)</option>
                  <option value="balanced" ${p.risk_profile === 'balanced' ? 'selected' : ''}>Balanced (1.0% risk, max 5x)</option>
                  <option value="aggressive" ${p.risk_profile === 'aggressive' ? 'selected' : ''}>Aggressive (1.5% risk, max 7x)</option>
                </select>
              </div>
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Execution Mode</label>
                <select id="prof-input-exec" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 8px 12px;">
                  <option value="paper" ${p.execution_mode === 'paper' ? 'selected' : ''}>PAPER (Safe Simulation)</option>
                  <option value="testnet" ${p.execution_mode === 'testnet' ? 'selected' : ''}>TESTNET (Binance Futures Testnet)</option>
                </select>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px;">
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Max Pos</label>
                <input type="number" id="prof-input-max-pos" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 8px;" value="${p.max_open_positions || 1}" min="1" max="5">
              </div>
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Max Trades/Day</label>
                <input type="number" id="prof-input-max-trades" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 8px;" value="${p.max_trades_per_day || 10}" min="1" max="50">
              </div>
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Stop Loss %</label>
                <input type="number" step="0.1" id="prof-input-sl" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 8px;" value="${p.stop_loss_pct || 1.5}">
              </div>
              <div>
                <label style="display: block; font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Take Profit %</label>
                <input type="number" step="0.1" id="prof-input-tp" class="cmd-input" style="border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 8px;" value="${p.take_profit_pct || 3.0}">
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="Modals.close('modal-trading-profile')">Cancel</button>
            <button class="btn btn-primary" id="btn-save-trading-profile">
              ${isEdit ? 'Save Changes' : 'Create Profile'}
            </button>
          </div>
        </div>
      </div>
    `;

    const old = document.getElementById('modal-trading-profile');
    if (old) old.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modeSelect = document.getElementById('prof-input-decision-mode');
    const stratField = document.getElementById('prof-field-strategy');
    const agentField = document.getElementById('prof-field-agent');

    const updateVisibility = () => {
      const mode = modeSelect.value;
      if (mode === 'strategy') {
        stratField.style.display = 'block';
        agentField.style.display = 'none';
      } else if (mode === 'ai_agent') {
        stratField.style.display = 'none';
        agentField.style.display = 'block';
      } else {
        stratField.style.display = 'block';
        agentField.style.display = 'block';
      }
    };
    modeSelect.addEventListener('change', updateVisibility);
    updateVisibility();

    document.getElementById('btn-save-trading-profile').addEventListener('click', async () => {
      const name = document.getElementById('prof-input-name').value.trim();
      if (!name) {
        Toast.warn("Please enter a profile name");
        return;
      }
      const data = {
        name,
        symbol: document.getElementById('prof-input-symbol').value,
        timeframe: document.getElementById('prof-input-timeframe').value,
        decision_mode: document.getElementById('prof-input-decision-mode').value,
        strategy_id: document.getElementById('prof-input-strategy').value,
        agent_id: document.getElementById('prof-input-agent').value,
        risk_profile: document.getElementById('prof-input-risk').value,
        execution_mode: document.getElementById('prof-input-exec').value,
        max_open_positions: parseInt(document.getElementById('prof-input-max-pos').value) || 1,
        max_trades_per_day: parseInt(document.getElementById('prof-input-max-trades').value) || 10,
        stop_loss_pct: parseFloat(document.getElementById('prof-input-sl').value) || 1.5,
        take_profit_pct: parseFloat(document.getElementById('prof-input-tp').value) || 3.0,
      };

      try {
        if (isEdit && p.profile_id) {
          await API.updateTradingProfile(p.profile_id, data);
          Toast.success(`Profile '${name}' updated successfully!`);
        } else {
          await API.createTradingProfile(data);
          Toast.success(`Trading profile '${name}' created!`);
        }
        Modals.close('modal-trading-profile');
        if (onSaved) onSaved();
      } catch (err) {
        Toast.error("Failed to save profile: " + err.message);
      }
    });
  },

  // Autonomous Decision Trace Modal
  showAutonomousTraceModal(trace) {
    if (!trace) return;
    const raw = trace.raw_trace || {};
    const modalHtml = `
      <div id="modal-auto-trace" class="modal-overlay active">
        <div class="modal-box" style="max-width: 660px;">
          <div class="modal-header">
            <div class="modal-title" style="display: flex; align-items: center; gap: 8px;">
              <span>🔍</span> AUTONOMOUS DECISION TRACE: ${trace.symbol} (${trace.timeframe})
            </div>
            <button class="modal-close" onclick="Modals.close('modal-auto-trace')">✕</button>
          </div>
          <div class="modal-body">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 11px; margin-bottom: 12px; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px;">
              <div>Trace ID: <b>${trace.trace_id}</b></div>
              <div>Timestamp: <b>${trace.decision_timestamp}</b></div>
              <div>Decision Mode: <b style="text-transform: uppercase;">${trace.decision_mode}</b></div>
              <div>Market Price: <b>${trace.market_price}</b></div>
            </div>

            <div class="timeline">
              <div class="timeline-item">
                <div class="timeline-dot pass"></div>
                <div class="timeline-content">
                  <div class="timeline-title">
                    <span>1. Market Data Boundary</span>
                    <span class="badge badge-bull">CLOSED BAR</span>
                  </div>
                  <div class="timeline-detail">Candle: ${trace.candle_timestamp} on Binance Futures. Price: ${trace.market_price}. Causal evaluation boundary verified.</div>
                </div>
              </div>

              <div class="timeline-item">
                <div class="timeline-dot ${trace.strategy_signal === 'HOLD' || trace.strategy_signal === 'N/A' ? 'warn' : 'pass'}"></div>
                <div class="timeline-content">
                  <div class="timeline-title">
                    <span>2. Strategy Template Signal</span>
                    <span class="badge ${trace.strategy_signal === 'LONG' || trace.strategy_signal === 'SHORT' ? 'badge-bull' : 'badge-neutral'}">${trace.strategy_signal}</span>
                  </div>
                  <div class="timeline-detail">${trace.strategy_signal === 'N/A' ? 'Not applicable for AI-only mode.' : 'Evaluated via Strategy Template.'}</div>
                </div>
              </div>

              <div class="timeline-item">
                <div class="timeline-dot ${trace.ai_decision === 'HOLD' || trace.ai_decision === 'N/A' ? 'warn' : 'pass'}"></div>
                <div class="timeline-content">
                  <div class="timeline-title">
                    <span>3. AI Agent Decision</span>
                    <span class="badge ${trace.ai_decision === 'LONG' || trace.ai_decision === 'APPROVE' ? 'badge-bull' : 'badge-neutral'}">${trace.ai_decision} (${Math.round((trace.ai_confidence || 0) * 100)}%)</span>
                  </div>
                  <div class="timeline-detail">${trace.ai_decision === 'N/A' ? 'Not applicable for Strategy-only mode.' : 'Agent evaluated market context and produced structured intent.'}</div>
                </div>
              </div>

              <div class="timeline-item">
                <div class="timeline-dot ${trace.policy_result === 'APPROVED' ? 'pass' : (trace.policy_result === 'VETOED' ? 'veto' : 'warn')}"></div>
                <div class="timeline-content">
                  <div class="timeline-title">
                    <span>4. Agent Policy Guard</span>
                    <span class="badge ${trace.policy_result === 'APPROVED' ? 'badge-bull' : (trace.policy_result === 'VETOED' ? 'badge-bear' : 'badge-neutral')}">${trace.policy_result}</span>
                  </div>
                  <div class="timeline-detail">Environment, risk bounds, and mandatory SL verification.</div>
                </div>
              </div>

              <div class="timeline-item">
                <div class="timeline-dot ${trace.risk_result === 'APPROVED' ? 'pass' : (trace.risk_result === 'VETOED' ? 'veto' : 'warn')}"></div>
                <div class="timeline-content">
                  <div class="timeline-title">
                    <span>5. Risk Engine (FINAL AUTHORITY)</span>
                    <span class="badge ${trace.risk_result === 'APPROVED' ? 'badge-bull' : (trace.risk_result === 'VETOED' ? 'badge-bear' : 'badge-neutral')}">${trace.risk_result}</span>
                  </div>
                  <div class="timeline-detail">Emergency stop clearance, portfolio drawdown limits, and position sizing.</div>
                </div>
              </div>

              <div class="timeline-item">
                <div class="timeline-dot ${trace.execution_status === 'EXECUTED' ? 'pass' : 'veto'}"></div>
                <div class="timeline-content">
                  <div class="timeline-title">
                    <span>6. Execution Coordinator</span>
                    <span class="badge ${trace.execution_status === 'EXECUTED' ? 'badge-bull' : 'badge-bear'}">${trace.execution_status}</span>
                  </div>
                  <div class="timeline-detail">Order ID: ${trace.order_id || 'None'}. Status: ${trace.execution_status}.</div>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" onclick="Modals.close('modal-auto-trace')">Close</button>
          </div>
        </div>
      </div>
    `;

    const old = document.getElementById('modal-auto-trace');
    if (old) old.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }
};

// 3. Command Palette (Ctrl+K)
const CommandPalette = {
  commands: [
    { title: "Navigate: Overview Dashboard", action: () => window.app.navigate('overview') },
    { title: "Navigate: Trading Terminal", action: () => window.app.navigate('trading') },
    { title: "Navigate: Markets & Regimes", action: () => window.app.navigate('markets') },
    { title: "Navigate: Research & Backtesting Lab", action: () => window.app.navigate('research') },
    { title: "Navigate: Risk Center & Limits", action: () => window.app.navigate('risk') },
    { title: "Navigate: Autonomous Trading Engine", action: () => window.app.navigate('autonomous') },
    { title: "Navigate: AI Agent Center", action: () => window.app.navigate('agents') },
    { title: "Navigate: Configuration Center", action: () => window.app.navigate('config') },
    { title: "Navigate: Settings & Telegram", action: () => window.app.navigate('settings') },
    { title: "Action: Create Autonomous Trading Profile", action: () => Modals.showProfileModal() },
    { title: "Action: Ask AI Copilot to Configure", action: () => Modals.showAiCopilotModal() },
    { title: "Action: Run Diagnostic Doctor", action: () => window.app.runDoctorDiagnostics() },
    { title: "Action: Send Telegram Test Alert", action: () => window.app.sendTelegramTest() },
    { title: "Safety: Trigger Emergency Kill Switch", action: () => Modals.showEmergencyStopModal() },
  ],

  init() {
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        this.open();
      }
      if (e.key === 'Escape') {
        this.close();
      }
    });
  },

  open() {
    let listHtml = '';
    this.commands.forEach((cmd, idx) => {
      listHtml += `
        <div class="cmd-item" data-index="${idx}">
          <span>${cmd.title}</span>
          <span class="cmd-shortcut">Enter</span>
        </div>
      `;
    });

    const modalHtml = `
      <div id="modal-cmd-palette" class="modal-overlay active">
        <div class="modal-box cmd-palette-box">
          <input type="text" id="cmd-search-input" class="cmd-input" placeholder="Type a command or search view (e.g. Risk, Backtest, Agent)..." autofocus>
          <div class="cmd-list" id="cmd-list-container">
            ${listHtml}
          </div>
        </div>
      </div>
    `;

    const old = document.getElementById('modal-cmd-palette');
    if (old) old.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const input = document.getElementById('cmd-search-input');
    input.focus();

    input.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      const items = document.querySelectorAll('.cmd-item');
      items.forEach((item, idx) => {
        const text = this.commands[idx].title.toLowerCase();
        item.style.display = text.includes(q) ? 'flex' : 'none';
      });
    });

    document.querySelectorAll('.cmd-item').forEach(item => {
      item.addEventListener('click', () => {
        const idx = parseInt(item.getAttribute('data-index'));
        this.close();
        this.commands[idx].action();
      });
    });

    document.getElementById('modal-cmd-palette').addEventListener('click', (e) => {
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
