# CUANIMUS Agent Architecture

## 1. Architectural Mission & Invariants

CUANIMUS transforms into an agent-accessible quantitative trading platform where autonomous AI agents (Codex, Antigravity, Claude Desktop, Cursor, Hermes) can understand user intent, assist configuration, inspect market conditions, prepare trades, and execute automated trading in **PAPER** and **TESTNET** modes (`PAPER_AUTO`, `TESTNET_AUTO`).

CUANIMUS retains absolute, final authority over configuration validity, risk guardrails, safety invariants, and execution dispatching.

```mermaid
flowchart TD
    subgraph ClientLayer ["AI Agent Client Layer"]
        A1["Antigravity IDE / CLI"]
        A2["Codex / Claude Desktop"]
        A3["Cursor IDE"]
        A4["Hermes / Autonomous Bot"]
    end

    subgraph MCPGateway ["CUANIMUS MCP & Agent Gateway"]
        M1["JSON-RPC 2.0 Engine (stdio / http)"]
        M2["Agent Identity & RBAC (Default-Deny)"]
        M3["Agent Trading Policy Gate"]
        M4["Configuration Proposal Engine"]
        M5["Two-Step Intent Pipeline"]
    end

    subgraph CoreEngine ["CUANIMUS Quantitative Core"]
        C1["Strategy Registry & Plugins"]
        C2["Independent Risk Engine"]
        C3["Portfolio State & Sizing"]
        C4["Order Lifecycle FSM"]
        C5["Paper Execution Safety Guard"]
    end

    subgraph Infrastructure ["Execution & Data Layer"]
        E1["Paper Simulated Engine"]
        E2["Binance Futures Testnet (Isolated)"]
        E3["Real Capital Live (STRICTLY DISABLED / NO-GO)"]
    end

    A1 --> M1
    A2 --> M1
    A3 --> M1
    A4 --> M1

    M1 --> M2
    M2 --> M3
    M3 --> M4
    M3 --> M5

    M4 --> C1
    M5 --> C1
    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> C5

    C5 --> E1
    C5 --> E2
    C5 -.->|BLOCKED BY GATE| E3
```

---

## 2. Decoupling Invariants

1. **No Direct Exchange Access**: Agents NEVER possess exchange API keys or connect directly to Binance sockets/REST endpoints. All requests pass through CUANIMUS MCP tools.
2. **No Direct Database Access**: Agents cannot issue raw SQL queries or alter trade history records.
3. **No Dynamic Python Code Execution**: Agents cannot run `eval()` or `exec()` on the host machine.
4. **Mandatory Two-Step Execution Pipeline**:
   $$\text{Agent Trade Intent} \longrightarrow \text{Schema \& Policy Check} \longrightarrow \text{RiskEngine Assessment} \longrightarrow \text{PaperExecutionSafetyGuard}$$
5. **Single Trading Core**: MCP is strictly an adapter/gateway layer over existing application services, Control Plane API, Strategy Registry, Risk Engine, and Order Lifecycle FSM.

---

## 3. Execution Pipeline Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Agent as AI Agent (MCP)
    participant Gateway as MCP Server & Policy
    participant Core as CUANIMUS RiskEngine
    participant Safety as Paper Safety Guard
    actor Human as Human Operator

    Agent->>Gateway: tools/call: trading.create_intent(symbol, sl, price, idempotency_key)
    Gateway-->>Agent: AgentTradeIntent (status: CREATED)
    
    Agent->>Gateway: tools/call: trading.validate_intent(intent_id)
    Gateway->>Gateway: Policy Evaluation (Whitelist, Leverage Cap, SL Presence)
    Gateway->>Core: RiskEngine.evaluate_intent()
    Core-->>Gateway: RiskEvaluation (Approved Stake, Contract Sizing, Mandatory SL)
    Gateway-->>Agent: IntentValidationResult (status: VALIDATED)

    Agent->>Gateway: tools/call: trading.execute_intent(intent_id, idempotency_key)
    Gateway->>Safety: execute_paper_order()
    Safety-->>Gateway: Execution Order Record (status: FILLED_SIMULATED)
    Gateway-->>Agent: Execution Result

    opt Emergency Intervention
        Human->>Gateway: session.emergency_stop()
        Gateway->>Core: RiskEngine.trigger_emergency_stop()
        Gateway-->>Agent: ALL SESSIONS HALTED
    end
```
