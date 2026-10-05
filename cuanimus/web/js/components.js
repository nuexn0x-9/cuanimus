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
          diffHtml += `<div style="padding: 2px 0;"><span style="color: #94a3b8;">${d.path}:</span> <span style="color: #f43f5e;">${JSON.stringify(d.from)}</span> → <span style="color: #00c076;">${JSON.stringify(d.to)}</span></div>`;
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
    { title: "Navigate: AI Agent Center", action: () => window.app.navigate('agents') },
    { title: "Navigate: Configuration Center", action: () => window.app.navigate('config') },
    { title: "Navigate: Settings & Telegram", action: () => window.app.navigate('settings') },
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
