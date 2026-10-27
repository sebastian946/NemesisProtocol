"""Director facade used by the game.

- decide(): synchronous, runs the LangGraph workflow (director/graph.py) and
  always returns a Decision: Claude's reviewed evolution, or the rules.
- decide_async(): runs decide() in a worker thread so the game loop never
  blocks; the game polls the returned Future during the break between waves.
- Every decision is appended to telemetry/director_log.jsonl for analysis.
  With LANGSMITH_TRACING=true in .env, each graph run is also traced in LangSmith.
"""
import json
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from director.graph import build_director_graph
from shared.env import load_env
from shared.i18n import get_language
from shared.models import Adaptation, EnemyStats, WaveTelemetry

LOG_DIR = Path(__file__).resolve().parent.parent / "telemetry"
AUTH_ERRORS = ("AuthenticationError", "PermissionDeniedError")


@dataclass(frozen=True)
class Decision:
    adaptation: Adaptation
    stats: EnemyStats       # = apply_adaptation(BASE_STATS, adaptation), already clamped
    source: str             # "claude" | "reglas"
    error: str | None = None
    attempts: int = 0       # Claude proposals made (2 = the review asked for a correction)
    issues: list[str] = field(default_factory=list)   # what the review step flagged


class Director:
    def __init__(self, use_llm: bool | None = None, log_dir: Path | None = LOG_DIR, llm=None):
        load_env()
        if use_llm is None:
            use_llm = (bool(os.environ.get("ANTHROPIC_API_KEY"))
                       and os.environ.get("NEMESIS_DIRECTOR", "claude").lower() != "rules")
        self._llm_error = None
        if llm is None and use_llm:
            try:
                from director.llm import build_llm
                llm = build_llm()
            except Exception as exc:  # langchain-anthropic missing or misconfigured
                self._llm_error = f"{type(exc).__name__}: {exc}"
        self._set_llm(llm)
        self.log_dir = log_dir
        self.history: list[Adaptation] = []
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="director")

    def _set_llm(self, llm):
        self._llm = llm
        self.graph = build_director_graph(llm)

    @property
    def mode(self) -> str:
        return "claude" if self._llm else "reglas"

    def reset(self):
        """New run (player died): evolutions start over from the base."""
        self.history.clear()

    def decide(self, telemetry: WaveTelemetry) -> Decision:
        state = self.graph.invoke(
            {"telemetry": telemetry, "history": list(self.history), "language": get_language()},
            config={"run_name": f"director-wave-{telemetry.wave}",
                    "tags": ["nemesis-protocol", self.mode],
                    "metadata": {"wave": telemetry.wave, "dominant_weapon": telemetry.dominant_weapon}},
        )
        error = state.get("error") or (self._llm_error if state["source"] == "reglas" else None)
        if error and error.split(":")[0] in AUTH_ERRORS:
            self._set_llm(None)     # bad key: stop paying the round-trip on every wave
            self._llm_error = error
        decision = Decision(state["adaptation"], state["stats"], state["source"], error,
                            state.get("attempts", 0), state.get("review_log", []))
        self.history.append(decision.adaptation)
        self._log(telemetry, decision)
        return decision

    def decide_async(self, telemetry: WaveTelemetry) -> Future:
        return self._executor.submit(self.decide, telemetry)

    def _log(self, telemetry: WaveTelemetry, decision: Decision):
        if self.log_dir is None:
            return
        try:
            self.log_dir.mkdir(exist_ok=True)
            record = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "telemetry": telemetry.model_dump(),
                "source": decision.source,
                "attempts": decision.attempts,
                "review_issues": decision.issues,
                "error": decision.error,
                "adaptation": decision.adaptation.model_dump(),
                "next_wave_stats": decision.stats.model_dump(),
            }
            with open(self.log_dir / "director_log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass  # logging must never break the game
