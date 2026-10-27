"""LangGraph workflow of the AI Director.

    START → analyze ─┬─(LLM available)──► propose ─┬─(ok)───► review ─┬─(approved)──► finalize → END
                     │                              │                  ├─(issues, retry)─► propose
                     │                              │                  └─(issues, no retries left)─► finalize
                     └─(no LLM)──► fallback ◄───────┴─(error)
                                      └──► finalize

- analyze:  pure. Builds the player profile and the rule-based suggestion.
- propose:  Claude (LangChain structured output) designs the evolution.
- review:   pure. Checks the proposal against the game's rules and sends
            concrete feedback back to Claude when something is off.
- fallback: rule-based suggestion when Claude is unavailable or fails.
- finalize: applies the adaptation to BASE_STATS (clamped).
"""
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from director.llm import DirectorDecision, build_messages, decision_to_adaptation
from director.profiles import WEAPON_PROFILES
from director.rules import DOMINANCE_THRESHOLD, dominant_share, rule_based_adaptation
from shared.models import BASE_STATS, STAT_LIMITS, Adaptation, EnemyStats, WaveTelemetry, apply_adaptation

MAX_ATTEMPTS = 2       # first proposal + one corrected proposal
MAX_CHANGES = 6


class DirectorState(TypedDict, total=False):
    # input
    telemetry: WaveTelemetry
    history: list[Adaptation]
    language: str        # "es" | "en": language of the evolution's name and reason
    # analyze
    profile: dict
    suggestion: Adaptation
    # propose / review loop
    decision: DirectorDecision | None
    attempts: int
    issues: list[str]
    review_log: Annotated[list[str], operator.add]   # every issue found, across attempts
    # output
    adaptation: Adaptation
    stats: EnemyStats
    source: str          # "claude" | "reglas"
    error: str | None


# --- Pure helpers ------------------------------------------------------------

def build_profile(telemetry: WaveTelemetry, player_max_hp: float = 100) -> dict:
    weapon = telemetry.dominant_weapon
    share = dominant_share(telemetry)
    hp_ratio = telemetry.player_hp_remaining / player_max_hp
    profile = {
        "dominant_weapon": weapon,
        "dominance": round(share, 2),
        "play_style": ("specialist" if share >= DOMINANCE_THRESHOLD else "generalist"),
        "performance": ("dominant" if hp_ratio >= .7 else "close call" if hp_ratio >= .3 else "struggling"),
        "accuracy": round(telemetry.accuracy, 2),
    }
    if weapon in WEAPON_PROFILES:
        profile["damage_type"] = WEAPON_PROFILES[weapon]["damage_type"]
        profile["counter_stats"] = WEAPON_PROFILES[weapon]["counter_stats"]
    return profile


def unclamped_values(adaptation: Adaptation) -> dict[str, Any]:
    """Same order as apply_adaptation but WITHOUT clamps, to detect values the
    clamp would silently cut (a sign the model misread a stat's scale)."""
    values = BASE_STATS.model_dump()
    for stat, value in adaptation.overrides.items():
        values[stat] = value
    for stat, delta in adaptation.deltas.items():
        values[stat] += delta
    for stat, factor in adaptation.multipliers.items():
        values[stat] *= factor
    return values


def review_decision(decision: DirectorDecision, profile: dict) -> list[str]:
    """Returns the problems found (empty list = approved)."""
    issues = []
    try:
        adaptation = decision_to_adaptation(decision)
    except ValueError as exc:
        return [f"invalid adaptation: {exc}"]

    values = unclamped_values(adaptation)
    for stat, (low, high) in STAT_LIMITS.items():
        if not low - 1e-9 <= values[stat] <= high + 1e-9:
            issues.append(f"{stat} would end at {values[stat]:g}, outside its limits [{low}, {high}]")

    if not decision.changes:
        issues.append("the evolution changes no stats")
    elif len(decision.changes) > MAX_CHANGES:
        issues.append(f"too many changes ({len(decision.changes)}); use at most {MAX_CHANGES}")

    counters = set(profile.get("counter_stats", []))
    if profile.get("play_style") == "specialist" and counters:
        touched = {c.stat for c in decision.changes} | ({"ranged_enabled"} if decision.ranged_enabled else set())
        if not touched & counters:
            issues.append(f"the player relies on {profile['dominant_weapon']} but no change counters it; "
                          f"use at least one of {sorted(counters)}")
    return issues


# --- Graph -------------------------------------------------------------------

def build_director_graph(llm=None):
    """`llm` is any Runnable that maps messages → DirectorDecision (see
    director.llm.build_llm). With llm=None the graph always uses the rules."""

    def analyze(state: DirectorState) -> dict:
        telemetry = state["telemetry"]
        return {"profile": build_profile(telemetry), "suggestion": rule_based_adaptation(telemetry),
                "attempts": 0, "issues": [], "decision": None, "error": None}

    def propose(state: DirectorState) -> dict:
        messages = build_messages(state["telemetry"], state["profile"], state.get("history", []),
                                  state["suggestion"], state.get("decision"), state.get("issues"),
                                  language=state.get("language"))
        try:
            decision = llm.invoke(messages)
            if decision is None:
                raise RuntimeError("the model returned no structured output")
            return {"decision": decision, "attempts": state["attempts"] + 1, "error": None}
        except Exception as exc:  # network, timeout, auth, refusal, invalid JSON...
            return {"error": f"{type(exc).__name__}: {exc}", "attempts": state["attempts"] + 1}

    def review(state: DirectorState) -> dict:
        issues = review_decision(state["decision"], state["profile"])
        return {"issues": issues, "review_log": issues}

    def fallback(state: DirectorState) -> dict:
        return {"adaptation": state["suggestion"], "source": "reglas"}

    def finalize(state: DirectorState) -> dict:
        update = {}
        if "adaptation" not in state:   # came from review: Claude's proposal (clamped if needed)
            update = {"adaptation": decision_to_adaptation(state["decision"]), "source": "claude"}
        adaptation = update.get("adaptation", state.get("adaptation"))
        update["stats"] = apply_adaptation(BASE_STATS, adaptation)
        return update

    def after_analyze(state: DirectorState) -> str:
        return "propose" if llm is not None else "fallback"

    def after_propose(state: DirectorState) -> str:
        return "fallback" if state.get("error") else "review"

    def after_review(state: DirectorState) -> str:
        if state["issues"] and state["attempts"] < MAX_ATTEMPTS:
            return "propose"
        return "finalize"     # approved, or out of retries: the clamps keep it safe

    graph = StateGraph(DirectorState)
    graph.add_node("analyze", analyze)
    graph.add_node("propose", propose)
    graph.add_node("review", review)
    graph.add_node("fallback", fallback)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "analyze")
    graph.add_conditional_edges("analyze", after_analyze, ["propose", "fallback"])
    graph.add_conditional_edges("propose", after_propose, ["review", "fallback"])
    graph.add_conditional_edges("review", after_review, ["propose", "finalize"])
    graph.add_edge("fallback", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
