"""
CUANIMUS Custom Exception Hierarchy.
"""

class CuanimusException(Exception):
    pass

class RiskVetoException(CuanimusException):
    def __init__(self, reason: str):
        super().__init__(f"Risk Veto: {reason}")
        self.reason = reason

class InvalidOrderStateTransition(CuanimusException):
    def __init__(self, current_state: str, target_state: str):
        super().__init__(f"Illegal transition: {current_state} -> {target_state}")
        self.current_state = current_state
        self.target_state = target_state

class OrderTimeoutException(CuanimusException):
    pass

class ExchangeReconciliationException(CuanimusException):
    pass

class ClockDriftException(CuanimusException):
    pass

class LookaheadViolationError(CuanimusException):
    pass

class SafetyViolationError(CuanimusException):
    pass

class FatalSafetyViolationError(SafetyViolationError):
    pass


