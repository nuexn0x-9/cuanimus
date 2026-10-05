# CUANIMUS Automated Trading on Paper and Testnet

## 1. Supported Execution Modes

CUANIMUS provides two distinct automated trading modes for AI agents:

| Mode | Environment | Description | Safety Status |
| :--- | :--- | :--- | :--- |
| `PAPER_AUTO` | Simulated | Zero network calls to live exchange. Uses `PaperExecutionSafetyGuard` and realistic fee/slippage models. | **SAFE** |
| `TESTNET_AUTO` | Binance Futures Testnet | Isolated sandbox using testnet credentials. Mainnet exchange URLs are strictly blocked. | **SAFE** |
| `LIVE_AUTO` | Real Capital | **STRICTLY DISABLED / PROHIBITED**. Phase 6 and Phase 7 safety invariants block live trading. | **NO-GO** |

---

## 2. Two-Step Intent Flow & Idempotency

Autonomous trading never uses single-click unvalidated order endpoints. Every trade must progress through two mandatory steps:

$$\text{Step 1: } \texttt{trading.create\_intent} \longrightarrow \text{Step 2: } \texttt{trading.validate\_intent} \longrightarrow \text{Step 3: } \texttt{trading.execute\_intent}$$

```python
# 1. Create trade intent with unique idempotency key
intent = client.call_tool("trading.create_intent", {
    "idempotency_key": "eth_pullback_bar_1042",
    "symbol": "ETH/USDT:USDT",
    "direction": "LONG",
    "entry_price": 3120.0,
    "stop_loss": 3050.0,
    "leverage": 3.0,
    "strategy_id": "v2_pullback"
})

# 2. Pre-flight validation against Policy and RiskEngine
val = client.call_tool("trading.validate_intent", {
    "intent_id": intent["intent_id"]
})

# 3. Execution under PaperExecutionSafetyGuard
if val["is_valid"]:
    result = client.call_tool("trading.execute_intent", {
        "intent_id": intent["intent_id"],
        "idempotency_key": "eth_pullback_bar_1042"
    })
```
