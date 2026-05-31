# ARCH: Orchestrator (Compat Shim)

> **Phase 22 note:** `Orchestrator` is now a compatibility factory function,
> not a class. It accepts the same constructor arguments as before and returns
> an `EventDrivenFlow` wrapping a `Pipeline`. The canonical architecture
> documentation lives in `ARCH_flow.md`. This file is preserved for historical
> context and to document the compat contract.

## What `Orchestrator(...)` Does Now

```python
# src/orchestrator.py (simplified)
def Orchestrator(config_path, options=None, **kwargs) -> EventDrivenFlow:
    core = _OrchestratorCore(config_path, options=options, **kwargs)
    return EventDrivenFlow(
        pipeline=Pipeline(core),
        transport=core.transport,
        round_detector=core.round_detector,
        address_detector=core.address_detector,
    )
```

`EventDrivenFlow` delegates unknown attribute gets/sets to the core so that
existing integration points such as `main._attach_reconciler()` continue to
work during the migration.

## Where to Find the Real Architecture

- **`ARCH_flow.md`** — Flow contract, `EventDrivenFlow` (production) and
  `RoundSteppedFlow` (self-play), worked example for adding a third Flow.
- **`src/pipeline.py`** — `Pipeline` interface: the per-agent capability
  surface that Flows schedule against.
- **`src/flows/event_driven.py`** — Production driver (Telegram/CLI).
- **`src/flows/round_stepped.py`** — Self-play driver (`GameEnvironment`).

## Compat Contract

The following call sites still use `from orchestrator import Orchestrator`
and continue to work without changes:

- `src/main.py` — production entrypoint
- `tests/integration/conftest.py` — Layer 3 fixture
- `tests/test_orchestrator.py` — unit test suite (tests behavior via the
  public `EventDrivenFlow` surface)

The returned object supports:

- `await orch.start()` — starts the event loop
- `await orch.shutdown()` — graceful cleanup
- `orch.transport` — the `Transport` instance
- `orch.state_manager`, `orch.event_store`, etc. — inner core attributes
  (delegated via `__getattr__`)
- `orch.advance_to_round(n)` — delegated to `Pipeline`

## OrchestrationOptions

`OrchestrationOptions` dataclass is unchanged and still passed at construction:

```python
@dataclass
class OrchestrationOptions:
    auto_response_enabled: bool = True   # False in self-play (explicit round stepping)
    total_rounds: int | None = None      # None = production (endgame-blind)
```

These are stored on the inner `_OrchestratorCore`, not on the returned
`EventDrivenFlow` or `Pipeline`. Access via `orch._core.options` if needed
(integration tests; production code should not reach in).

## Usage Example

```python
from orchestrator import Orchestrator

orch = Orchestrator(config_path="config/pipeline.yaml")
await orch.start()   # runs until shutdown signal
await orch.shutdown() # graceful cleanup
```

Production usage is unchanged. For self-play, prefer the `Pipeline` +
`RoundSteppedFlow` interface (see `ARCH_flow.md`).
