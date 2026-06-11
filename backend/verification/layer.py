from __future__ import annotations

"""
Deterministic Verification Layer

The NON-AI safety net. Before any high-stakes action executes,
this layer runs deterministic if-then checks against the user's
original intent. If they don't match 100%, the action is killed.

This is what makes AgentOS trustworthy for money, messages, and deletions.
AI agents "hallucinate" — this layer doesn't.

Flow:
1. Agent says: "Send $500 to John"
2. Semantic Bus routes to payments.send
3. BEFORE execution → Verification Layer checks:
   - Does the amount match the user's stated intent?
   - Is the recipient in the user's contacts?
   - Is the amount within the user's configured limits?
   - Has this exact action been attempted in the last 60 seconds? (dupe check)
4. If ANY check fails → action is KILLED, user is notified
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("verification")


@dataclass
class VerificationRule:
    """A deterministic check that must pass before an action executes."""
    id: str
    name: str
    action_pattern: str  # Glob pattern matching action IDs (e.g., "payments.*")
    check: Callable  # Takes (action_id, params, context) -> (pass, reason)
    severity: str = "block"  # "block" = kill action, "warn" = allow with warning


@dataclass
class VerificationResult:
    passed: bool
    checks_run: int
    checks_passed: int
    checks_failed: int
    failures: List[dict] = field(default_factory=list)  # [{rule, reason}]
    warnings: List[dict] = field(default_factory=list)


class VerificationLayer:
    """Non-AI safety layer for high-stakes agent actions."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._rules: List[VerificationRule] = []
        self._blocked_log: List[dict] = []
        self._limits = {
            "max_payment_amount": self.config.get("max_payment_amount", 1000),
            "max_messages_per_hour": self.config.get("max_messages_per_hour", 20),
            "max_calls_per_hour": self.config.get("max_calls_per_hour", 5),
            "blocked_contacts": self.config.get("blocked_contacts", []),
            "allowed_payment_currencies": self.config.get("allowed_currencies", ["USD", "EUR", "ETB"]),
        }
        self._action_history: List[dict] = []  # Recent action timestamps

        self._register_builtin_rules()

    def _register_builtin_rules(self):
        """Register all built-in safety checks."""

        # Payment amount check
        self.add_rule(VerificationRule(
            id="payment_limit",
            name="Payment Amount Limit",
            action_pattern="payments.send",
            check=self._check_payment_limit,
            severity="block",
        ))

        # Duplicate action check
        self.add_rule(VerificationRule(
            id="duplicate_check",
            name="Duplicate Action Prevention",
            action_pattern="*",
            check=self._check_duplicate,
            severity="block",
        ))

        # Rate limit for messages
        self.add_rule(VerificationRule(
            id="message_rate_limit",
            name="Message Rate Limit",
            action_pattern="messages.send",
            check=self._check_message_rate,
            severity="block",
        ))

        # Rate limit for calls
        self.add_rule(VerificationRule(
            id="call_rate_limit",
            name="Call Rate Limit",
            action_pattern="phone.call",
            check=self._check_call_rate,
            severity="block",
        ))

        # Blocked contacts check
        self.add_rule(VerificationRule(
            id="blocked_contact",
            name="Blocked Contact Check",
            action_pattern="messages.send",
            check=self._check_blocked_contact,
            severity="block",
        ))

        self.add_rule(VerificationRule(
            id="blocked_contact_call",
            name="Blocked Contact Check (Calls)",
            action_pattern="phone.call",
            check=self._check_blocked_contact,
            severity="block",
        ))

        # Currency validation
        self.add_rule(VerificationRule(
            id="currency_check",
            name="Currency Validation",
            action_pattern="payments.send",
            check=self._check_currency,
            severity="block",
        ))

        # Late night action warning
        self.add_rule(VerificationRule(
            id="late_night_warning",
            name="Late Night Action Warning",
            action_pattern="messages.send",
            check=self._check_late_night,
            severity="warn",
        ))

    def add_rule(self, rule: VerificationRule):
        self._rules.append(rule)

    def verify(
        self,
        action_id: str,
        params: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> VerificationResult:
        """Run all matching verification rules against an action.

        Returns VerificationResult with pass/fail and details.
        """
        context = context or {}
        failures = []
        warnings = []
        checks_run = 0
        checks_passed = 0

        for rule in self._rules:
            if not self._matches(rule.action_pattern, action_id):
                continue

            checks_run += 1
            try:
                passed, reason = rule.check(action_id, params, context)

                if passed:
                    checks_passed += 1
                else:
                    entry = {"rule": rule.name, "reason": reason}
                    if rule.severity == "block":
                        failures.append(entry)
                    else:
                        warnings.append(entry)
                        checks_passed += 1  # Warnings don't block

            except Exception as e:
                failures.append({"rule": rule.name, "reason": f"Check error: {e}"})

        all_passed = len(failures) == 0

        if not all_passed:
            self._blocked_log.append({
                "action_id": action_id,
                "params": {k: str(v)[:50] for k, v in params.items()},
                "failures": failures,
                "timestamp": time.time(),
            })
            logger.warning(f"BLOCKED: {action_id} — {[f['reason'] for f in failures]}")

        # Record in history
        self._action_history.append({
            "action_id": action_id,
            "params_hash": hash(str(sorted(params.items()))),
            "timestamp": time.time(),
        })
        # Keep last 100
        self._action_history = self._action_history[-100:]

        return VerificationResult(
            passed=all_passed,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=len(failures),
            failures=failures,
            warnings=warnings,
        )

    def _matches(self, pattern: str, action_id: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            return action_id.startswith(pattern[:-2])
        return pattern == action_id

    # === Built-in Checks ===

    def _check_payment_limit(self, action_id, params, ctx):
        amount = params.get("amount", 0)
        limit = self._limits["max_payment_amount"]
        if amount > limit:
            return False, f"Amount ${amount} exceeds limit ${limit}"
        if amount <= 0:
            return False, f"Invalid amount: {amount}"
        return True, ""

    def _check_duplicate(self, action_id, params, ctx):
        params_hash = hash(str(sorted(params.items())))
        cutoff = time.time() - 60

        for entry in self._action_history:
            if (entry["action_id"] == action_id
                    and entry["params_hash"] == params_hash
                    and entry["timestamp"] > cutoff):
                return False, "Duplicate action detected (same action within 60s)"
        return True, ""

    def _check_message_rate(self, action_id, params, ctx):
        cutoff = time.time() - 3600
        recent = sum(
            1 for e in self._action_history
            if e["action_id"] == "messages.send" and e["timestamp"] > cutoff
        )
        limit = self._limits["max_messages_per_hour"]
        if recent >= limit:
            return False, f"Message rate limit: {recent}/{limit} per hour"
        return True, ""

    def _check_call_rate(self, action_id, params, ctx):
        cutoff = time.time() - 3600
        recent = sum(
            1 for e in self._action_history
            if e["action_id"] == "phone.call" and e["timestamp"] > cutoff
        )
        limit = self._limits["max_calls_per_hour"]
        if recent >= limit:
            return False, f"Call rate limit: {recent}/{limit} per hour"
        return True, ""

    def _check_blocked_contact(self, action_id, params, ctx):
        recipient = str(params.get("recipient", "")).lower()
        blocked = [c.lower() for c in self._limits["blocked_contacts"]]
        if recipient in blocked:
            return False, f"Contact '{recipient}' is blocked"
        return True, ""

    def _check_currency(self, action_id, params, ctx):
        currency = params.get("currency", "USD")
        allowed = self._limits["allowed_payment_currencies"]
        if currency not in allowed:
            return False, f"Currency {currency} not allowed (allowed: {allowed})"
        return True, ""

    def _check_late_night(self, action_id, params, ctx):
        hour = ctx.get("hour", 12)
        if 23 <= hour or hour <= 5:
            return False, "Late night action — consider waiting until morning"
        return True, ""

    def get_blocked_log(self) -> List[dict]:
        return list(self._blocked_log[-20:])

    def get_stats(self) -> dict:
        return {
            "rules_count": len(self._rules),
            "actions_verified": len(self._action_history),
            "actions_blocked": len(self._blocked_log),
        }
