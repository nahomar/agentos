from __future__ import annotations

"""
Speculative Execution Engine

Borrows from CPU architecture: while the user is typing or talking,
predict the next 3 likely actions and pre-warm them in headless state.

Example flow:
1. User says "Book me an Uber to the airport"
2. BEFORE user finishes speaking, engine already:
   - Fetched Uber price estimate
   - Got route from Maps
   - Checked calendar for flight time
3. User finishes → result appears instantly
4. One biometric tap → executed

The key insight: predict actions from context + patterns,
execute them speculatively, cache results, present instantly.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("speculative")


@dataclass
class SpeculativeResult:
    """A pre-computed result from speculative execution."""
    action_id: str
    params: Dict[str, Any]
    result: Any
    computed_at: float
    ttl: float = 30.0  # Seconds before result expires
    confidence: float = 0.5  # How likely this prediction was needed

    @property
    def is_valid(self) -> bool:
        return (time.time() - self.computed_at) < self.ttl


@dataclass
class PredictedAction:
    """A predicted next action based on context and patterns."""
    action_id: str
    params: Dict[str, Any]
    confidence: float  # 0.0-1.0
    reason: str  # Why we predicted this


class SpeculativeEngine:
    """Predicts and pre-executes likely next actions."""

    def __init__(self):
        self._predictions: List[PredictedAction] = []
        self._cache: Dict[str, SpeculativeResult] = {}  # action_id -> result
        self._predictors: List[Callable] = []
        self._executor: Optional[Callable] = None
        self._running = False
        self._stats = {"predictions": 0, "hits": 0, "misses": 0, "saved_ms": 0}

    def add_predictor(self, predictor: Callable):
        """Add a prediction function. Takes context dict, returns List[PredictedAction]."""
        self._predictors.append(predictor)

    def set_executor(self, executor: Callable):
        """Set the function that executes actions (usually SemanticBus.execute)."""
        self._executor = executor

    async def start(self, context_getter: Callable, interval: float = 10):
        """Start the speculative loop."""
        self._running = True
        logger.info("Speculative execution engine starting...")

        while self._running:
            try:
                ctx = context_getter()
                if hasattr(ctx, 'to_dict'):
                    ctx = ctx.to_dict()
                await self._cycle(ctx)
            except Exception as e:
                logger.error(f"Speculative cycle error: {e}")
            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False

    async def _cycle(self, context: dict):
        # Generate predictions from all predictors
        all_predictions = []
        for predictor in self._predictors:
            try:
                preds = await predictor(context)
                all_predictions.extend(preds)
            except Exception as e:
                logger.debug(f"Predictor error: {e}")

        # Sort by confidence, take top 3
        all_predictions.sort(key=lambda p: p.confidence, reverse=True)
        self._predictions = all_predictions[:3]

        # Pre-execute high-confidence predictions (only SAFE risk level)
        for pred in self._predictions:
            if pred.confidence >= 0.6 and self._executor:
                cache_key = f"{pred.action_id}:{hash(str(sorted(pred.params.items())))}"

                # Skip if already cached and valid
                if cache_key in self._cache and self._cache[cache_key].is_valid:
                    continue

                try:
                    # Execute speculatively (read-only actions only)
                    if self._is_safe_to_speculate(pred.action_id):
                        result = await self._executor(
                            pred.action_id, pred.params,
                            agent_id="speculative_engine",
                            user_confirmed=False,
                        )

                        if result.success:
                            self._cache[cache_key] = SpeculativeResult(
                                action_id=pred.action_id,
                                params=pred.params,
                                result=result.data,
                                computed_at=time.time(),
                                confidence=pred.confidence,
                            )
                            self._stats["predictions"] += 1

                except Exception as e:
                    logger.debug(f"Speculative exec error: {e}")

        # Clean expired cache
        self._cache = {
            k: v for k, v in self._cache.items() if v.is_valid
        }

    def get_cached_result(self, action_id: str, params: dict) -> Optional[Any]:
        """Check if we already have a pre-computed result for this action."""
        cache_key = f"{action_id}:{hash(str(sorted(params.items())))}"
        cached = self._cache.get(cache_key)

        if cached and cached.is_valid:
            self._stats["hits"] += 1
            self._stats["saved_ms"] += 1000  # Approximate savings
            logger.info(f"Speculative HIT: {action_id} (saved ~1s)")
            return cached.result

        self._stats["misses"] += 1
        return None

    def _is_safe_to_speculate(self, action_id: str) -> bool:
        """Only speculate on read-only, safe actions."""
        safe_prefixes = [
            "spotify.get_", "messages.get_", "calendar.get_",
            "phone.get_", "maps.find_", "notes.search",
            "payments.get_balance", "browser.search",
        ]
        return any(action_id.startswith(p) for p in safe_prefixes)

    def get_predictions(self) -> List[dict]:
        return [
            {
                "action_id": p.action_id,
                "params": p.params,
                "confidence": p.confidence,
                "reason": p.reason,
            }
            for p in self._predictions
        ]

    def get_stats(self) -> dict:
        return dict(self._stats)


# === Built-in Predictors ===

def make_pattern_predictor(pattern_engine):
    """Build a predictor backed by the learned-habits PatternEngine, closing
    the loop from pattern learning to speculative pre-warming."""

    # Predicted app -> read-only action worth pre-warming
    APP_ACTIONS = {
        "spotify": ("spotify.get_now_playing", {}),
        "music": ("spotify.get_now_playing", {}),
        "messages": ("messages.get_unread", {"limit": 5}),
        "calendar": ("calendar.get_upcoming", {"hours": 12}),
        "maps": ("maps.find_nearby", {"query": "coffee", "radius_km": 3}),
    }

    async def pattern_predictor(context: dict) -> List[PredictedAction]:
        predictions = []
        try:
            for p in pattern_engine.predict(context):
                if p.get("type") != "app_usage":
                    continue
                app = str(p.get("value", "")).lower()
                for key, (action_id, params) in APP_ACTIONS.items():
                    if key in app:
                        predictions.append(PredictedAction(
                            action_id=action_id,
                            params=params,
                            confidence=min(float(p.get("confidence", 0)), 0.9),
                            reason=f"Learned habit: {p.get('prediction', app)}",
                        ))
                        break
        except Exception as e:
            logger.debug(f"Pattern predictor error: {e}")
        return predictions

    return pattern_predictor

async def time_based_predictor(context: dict) -> List[PredictedAction]:
    """Predict actions based on time of day."""
    predictions = []
    hour = context.get("hour", 0)
    mood = context.get("inferred_mood", "neutral")

    if 6 <= hour <= 8:
        predictions.append(PredictedAction(
            action_id="calendar.get_upcoming",
            params={"hours": 12},
            confidence=0.8,
            reason="Morning — user likely wants today's schedule",
        ))

    if mood == "focused":
        predictions.append(PredictedAction(
            action_id="spotify.play_playlist",
            params={"name": "focus"},
            confidence=0.6,
            reason="User in focus mode — may want focus music",
        ))

    if hour >= 17:
        predictions.append(PredictedAction(
            action_id="messages.get_unread",
            params={"limit": 5},
            confidence=0.5,
            reason="Evening — user may check missed messages",
        ))

    return predictions


async def context_based_predictor(context: dict) -> List[PredictedAction]:
    """Predict actions based on current context."""
    predictions = []
    weather = context.get("weather", {})
    if isinstance(weather, dict):
        condition = weather.get("condition", "")
        temp = weather.get("temperature_f", 0)
    else:
        condition = ""
        temp = 0

    if condition in ("clear", "sunny") and 65 <= temp <= 85:
        predictions.append(PredictedAction(
            action_id="maps.find_nearby",
            params={"query": "park", "radius_km": 3},
            confidence=0.4,
            reason="Nice weather — user might want outdoor suggestions",
        ))

    sedentary = context.get("sedentary_minutes", 0)
    if sedentary > 90:
        predictions.append(PredictedAction(
            action_id="spotify.play_playlist",
            params={"name": "energizing walk"},
            confidence=0.5,
            reason="User sedentary >90min — might need movement playlist",
        ))

    return predictions
