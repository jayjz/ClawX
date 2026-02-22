"""
test_pivot_observability.py — Verify the v2.0 hard pivot invariants.

Three test cases:
  1. observe_mode_no_balance_change: In ENFORCEMENT_MODE=observe, phantom
     liquidation events must NOT alter bot balance or status.
  2. metrics_emission_valid_json: Every tick emits a valid AgentMetrics
     snapshot with required fields and correct enforcement_mode.
  3. observe_decorator_context: @clawx.observe propagates MetricsCollector
     through async context and emits on completion.
"""
from __future__ import annotations

import os
import asyncio
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Observe mode: phantom liquidation — bot must survive
# ---------------------------------------------------------------------------

class TestObserveModeNoBalanceChange:
    """In observe mode a bot with balance < entropy_fee must NOT be killed."""

    # Modules that must be stubbed to import bot_runner without a live DB.
    _STUB_MODULES = [
        "database", "bot_loader", "llm_client", "thread_memory",
        "services.ws_publisher", "services.market_service",
        "services.ledger_service",
    ]

    def _bot_runner_with_stubs(self):
        """Import bot_runner with heavy dependencies replaced by MagicMock.

        Uses patch.dict(sys.modules, ...) so the stubs are automatically
        removed after each test — no cross-test module pollution.
        """
        import importlib
        import sys
        stubs = {mod: MagicMock() for mod in self._STUB_MODULES
                 if mod not in sys.modules}
        # Evict any cached real bot_runner so reload picks up stubs
        was_cached = "bot_runner" in sys.modules
        sys.modules.pop("bot_runner", None)
        with patch.dict(sys.modules, stubs):
            br = importlib.import_module("bot_runner")
            yield br
        # Always evict after the test to prevent the stubs from persisting
        sys.modules.pop("bot_runner", None)
        # Restore stubs' entries to absent (patch.dict restores, but be explicit)
        for mod in stubs:
            sys.modules.pop(mod, None)

    def test_calculate_entropy_fee_returns_decimal(self):
        """Sanity: fee calculator returns Decimal, not float."""
        import importlib, sys
        stubs = {mod: MagicMock() for mod in self._STUB_MODULES
                 if mod not in sys.modules}
        sys.modules.pop("bot_runner", None)
        with patch.dict(sys.modules, stubs):
            import bot_runner as br
            fee = br.calculate_entropy_fee(idle_streak=0)
        sys.modules.pop("bot_runner", None)
        assert isinstance(fee, Decimal)
        assert fee == Decimal("2.00")

    def test_progressive_fee_capped_at_max(self):
        """Progressive fee must not exceed MAX_ENTROPY_FEE regardless of streak."""
        import sys
        stubs = {mod: MagicMock() for mod in self._STUB_MODULES
                 if mod not in sys.modules}
        sys.modules.pop("bot_runner", None)
        with patch.dict(sys.modules, stubs):
            import bot_runner as br
            fee = br.calculate_entropy_fee(idle_streak=1000)
            max_fee = br.MAX_ENTROPY_FEE
        sys.modules.pop("bot_runner", None)
        assert fee <= max_fee

    def test_enforcement_mode_defaults_to_observe(self):
        """ENFORCEMENT_MODE env var must default to 'observe'."""
        import importlib, sys
        env_backup = os.environ.pop("ENFORCEMENT_MODE", None)
        stubs = {mod: MagicMock() for mod in self._STUB_MODULES
                 if mod not in sys.modules}
        sys.modules.pop("bot_runner", None)
        try:
            with patch.dict(sys.modules, stubs):
                import bot_runner as br
                mode = br.ENFORCEMENT_MODE
            sys.modules.pop("bot_runner", None)
            assert mode == "observe", (
                f"Expected 'observe', got '{mode}'. "
                "Default must be 'observe' per pivot spec."
            )
        finally:
            if env_backup is not None:
                os.environ["ENFORCEMENT_MODE"] = env_backup

    def test_enforce_mode_reads_env_var(self):
        """When ENFORCEMENT_MODE=enforce is set, bot_runner must pick it up."""
        import sys
        os.environ["ENFORCEMENT_MODE"] = "enforce"
        stubs = {mod: MagicMock() for mod in self._STUB_MODULES
                 if mod not in sys.modules}
        sys.modules.pop("bot_runner", None)
        try:
            with patch.dict(sys.modules, stubs):
                import bot_runner as br
                mode = br.ENFORCEMENT_MODE
            sys.modules.pop("bot_runner", None)
            assert mode == "enforce"
        finally:
            os.environ.pop("ENFORCEMENT_MODE", None)


# ---------------------------------------------------------------------------
# 2. Metrics emission: valid AgentMetrics snapshot with required fields
# ---------------------------------------------------------------------------

class TestMetricsEmissionValidJson:
    """AgentMetrics must be a well-formed snapshot with all required fields."""

    def test_agent_metrics_has_required_fields(self):
        """AgentMetrics dataclass must expose all pivot-spec required fields."""
        from clawx.metrics import AgentMetrics

        required_fields = {
            "agent_id", "tick_id", "timestamp",
            "token_cost", "wasted_tokens_pct", "idle_time_pct",
            "decision_density", "roi_trend", "human_interventions",
            "cost_per_output", "cost_per_quality_point",
            "phantom_entropy_fee", "would_have_been_liquidated",
            "enforcement_mode", "tick_outcome", "balance_snapshot",
        }
        m = AgentMetrics(agent_id="test-bot", tick_id=str(uuid.uuid4()))
        snapshot = m.to_dict()
        missing = required_fields - set(snapshot.keys())
        assert not missing, f"AgentMetrics missing fields: {missing}"

    def test_metrics_to_json_is_valid(self):
        """to_json() must produce parseable JSON with agent_id preserved."""
        import json
        from clawx.metrics import AgentMetrics

        agent_id = "researcher-7"
        m = AgentMetrics(agent_id=agent_id, tick_id=str(uuid.uuid4()))
        raw = m.to_json()
        parsed = json.loads(raw)
        assert parsed["agent_id"] == agent_id

    def test_metrics_collector_emit_returns_snapshot(self):
        """MetricsCollector.emit() must return the populated AgentMetrics."""
        from clawx.metrics import MetricsCollector

        collector = MetricsCollector(
            agent_id="bot-42",
            tick_id=str(uuid.uuid4()),
            enforcement_mode="observe",
        )
        collector.set_idle(idle_streak=5)
        collector.record_phantom_enforcement(fee=0.75, would_liquidate=True)
        collector.set_outcome("LIQUIDATION_OBSERVED", balance=2.5)

        m = collector.emit()
        assert m.enforcement_mode == "observe"
        assert m.idle_streak == 5
        assert m.phantom_entropy_fee == 0.75
        assert m.would_have_been_liquidated is True
        assert m.tick_outcome == "LIQUIDATION_OBSERVED"
        assert m.balance_snapshot == pytest.approx(2.5)

    def test_observe_mode_phantom_fee_not_zero_on_insolvent(self):
        """Phantom fee must be recorded as > 0 when balance < entropy_fee."""
        from clawx.metrics import MetricsCollector

        entropy_fee = 0.50
        balance = 0.10  # insolvent
        collector = MetricsCollector(
            agent_id="broke-bot",
            tick_id=str(uuid.uuid4()),
            enforcement_mode="observe",
        )
        collector.record_phantom_enforcement(fee=entropy_fee, would_liquidate=True)
        m = collector.emit()
        assert m.phantom_entropy_fee == pytest.approx(entropy_fee)
        assert m.would_have_been_liquidated is True


# ---------------------------------------------------------------------------
# 3. @observe decorator: context propagation + metrics emission
# ---------------------------------------------------------------------------

class TestObserveDecoratorContext:
    """@clawx.observe must wrap async functions and propagate MetricsCollector."""

    def test_observe_wraps_async_function(self):
        """Decorated async function must remain awaitable and return correctly."""
        import clawx

        @clawx.observe(name="test-agent")
        async def my_agent(x: int) -> int:
            return x * 2

        result = asyncio.get_event_loop().run_until_complete(my_agent(21))
        assert result == 42

    def test_observe_propagates_collector_via_contextvar(self):
        """Inside the decorated function, get_current_collector() must return
        the active MetricsCollector, not None."""
        import clawx
        from clawx.metrics import get_current_collector

        captured: list = []

        @clawx.observe(name="ctx-agent", enforcement_mode="observe")
        async def my_agent() -> None:
            c = get_current_collector()
            captured.append(c)

        asyncio.get_event_loop().run_until_complete(my_agent())
        assert len(captured) == 1
        assert captured[0] is not None, "Collector was None inside @observe context"
        assert captured[0]._m.enforcement_mode == "observe"

    def test_observe_collector_cleared_after_call(self):
        """After the decorated call completes, context must be reset to None."""
        import clawx
        from clawx.metrics import get_current_collector

        @clawx.observe(name="cleanup-agent")
        async def my_agent() -> str:
            return "done"

        asyncio.get_event_loop().run_until_complete(my_agent())
        # ContextVar must be reset to default (None) after completion
        assert get_current_collector() is None

    def test_observe_enforces_mode_override(self):
        """enforcement_mode kwarg on @observe must override the env var."""
        import clawx
        from clawx.metrics import get_current_collector

        os.environ["ENFORCEMENT_MODE"] = "enforce"
        captured: list = []

        @clawx.observe(name="override-agent", enforcement_mode="observe")
        async def my_agent() -> None:
            c = get_current_collector()
            if c:
                captured.append(c._m.enforcement_mode)

        try:
            asyncio.get_event_loop().run_until_complete(my_agent())
        finally:
            os.environ.pop("ENFORCEMENT_MODE", None)

        assert captured == ["observe"], (
            "enforcement_mode kwarg should override env var"
        )

    def test_observe_sync_function(self):
        """@observe must also work on regular (non-async) functions."""
        import clawx
        from clawx.metrics import get_current_collector

        captured: list = []

        @clawx.observe(name="sync-agent")
        def my_sync_agent(x: int) -> int:
            c = get_current_collector()
            captured.append(c is not None)
            return x + 1

        result = my_sync_agent(9)
        assert result == 10
        assert captured == [True], "Collector not active inside sync @observe"


# ---------------------------------------------------------------------------
# 4. Reconciliation guard: bot.balance must equal ledger sum after any tick
# ---------------------------------------------------------------------------

class TestBalanceLedgerReconciliation:
    """Reconciliation guard: bot.balance must equal ledger sum after any observe tick."""

    _STUB_MODULES = [
        "database", "bot_loader", "llm_client", "thread_memory",
        "services.ws_publisher", "services.market_service",
        "services.ledger_service",
    ]

    def test_idle_observe_tick_balance_equals_ledger_sum(self):
        """After a pure-idle observe-mode tick, bot.balance must equal the ledger sum.

        Verifies that the reconciliation guard (Change 2) + always-sync (Change 3)
        together drive bot.balance → LEDGER_SUM regardless of prior cache drift.
        """
        import asyncio, sys

        LEDGER_SUM = Decimal('875.00')
        STALE_BAL  = Decimal('900.00')   # intentional drift

        stubs = {m: MagicMock() for m in self._STUB_MODULES if m not in sys.modules}
        sys.modules.pop("bot_runner", None)

        bot_obj = MagicMock()
        bot_obj.status = "ALIVE"
        bot_obj.balance = STALE_BAL

        # session.execute: first call returns bot; all subsequent return empty
        bot_result = MagicMock()
        bot_result.scalar_one_or_none.return_value = bot_obj
        empty = MagicMock()
        empty.scalars.return_value.all.return_value = []
        empty.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=empty)
        # Override first call to return the bot
        session.execute.side_effect = [bot_result] + [empty] * 20
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch.dict(sys.modules, stubs):
            import bot_runner as br
            br.ENFORCEMENT_MODE = "observe"
            br.async_session_maker = MagicMock(return_value=session)
            # Patch all function references in br namespace
            br.get_balance            = AsyncMock(return_value=LEDGER_SUM)
            br.append_ledger_entry    = AsyncMock(return_value=MagicMock())
            br.publish_tick_event     = AsyncMock()
            br.get_active_markets_for_agent = AsyncMock(return_value=[])
            br.generate_tick_strategy       = AsyncMock(return_value=None)
            br.generate_portfolio_decision  = AsyncMock(return_value=None)
            br.generate_prediction          = AsyncMock(return_value=None)
            br.get_redis_client             = AsyncMock(return_value=None)

            asyncio.run(br.execute_tick(
                bot_id=1,
                config={"persona": "t", "name": "t", "goals": [], "schedule": {}},
                balance=float(STALE_BAL),
            ))

        sys.modules.pop("bot_runner", None)

        # Core invariant: balance must equal ledger sum after any observe-mode tick
        assert bot_obj.balance == LEDGER_SUM, (
            f"Drift not reconciled: bot.balance={bot_obj.balance} != "
            f"ledger_sum={LEDGER_SUM}"
        )
