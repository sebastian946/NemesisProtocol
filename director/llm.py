"""Claude via LangChain: model factory, structured output schema and prompts.

The model never touches EnemyStats directly. It returns a DirectorDecision
(structured output) that is converted into an Adaptation, which then goes
through the same validators and clamps as any rule-based one (Rule 2).
"""
import json
import os
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from director.profiles import WEAPON_PROFILES
from shared.i18n import language_name, weapon_name
from shared.models import BASE_STATS, STAT_LIMITS, Adaptation, WaveTelemetry

DEFAULT_MODEL = "claude-opus-5-5"
NumericStat = Literal[tuple(STAT_LIMITS)]  # type: ignore[valid-type]


class StatChange(BaseModel):
    stat: NumericStat
    op: Literal["add", "multiply", "set"]
    value: float


class DirectorDecision(BaseModel):
    name: str = Field(description="Short evolution name in the requested language, e.g. anti-pistol")
    reason: str = Field(description="One or two sentences in the requested language, addressed to the player")
    changes: list[StatChange]
    ranged_enabled: bool


SYSTEM_PROMPT = """You are the AI Director of "Nemesis Protocol", a wave-survival arena shooter.
After every wave you read the player's telemetry and design how the enemies evolve for the
next wave so they counter the player's current play style. The game must feel like it is
learning the player: each evolution clearly targets what the player relied on, while staying
beatable. The player should be pushed to switch weapons or tactics, not be crushed.

How your decision is applied:
- Changes are applied to the ORIGINAL base stats, never on top of the previous wave. Describe
  the full evolution for the next wave, not an increment over the last one.
- "set" changes run first, then "add", then "multiply". Final values must stay inside
  stat_limits; 0-1 stats such as armor and resist_* are fractions (0.3 means 30%).
- Damage an enemy takes = weapon_damage * (1 - resist_<type>) * (1 - max(0, armor - weapon_armor_pen)).
- ranged_enabled lets enemies shoot projectiles from up to ranged_range metres.
- Use 2 to 5 changes. Scale overall difficulty gently with the wave number.
- player_profile summarises the telemetry; counter_stats lists the stats that best counter the
  dominant weapon. rule_based_baseline is a reasonable default: improve on it using the
  telemetry details (accuracy, damage taken, time per kill, previous evolutions).

Write `name` and `reason` in {language}. `reason` is in second person, a short taunt shown
on the HUD; refer to weapons by their display_name."""


def build_llm(model: str | None = None, timeout_s: float = 25.0):
    """ChatAnthropic bound to DirectorDecision.

    method="json_schema" uses Claude's native structured outputs. The default
    "function_calling" forces a tool call, which current Opus models reject.
    """
    from langchain_anthropic import ChatAnthropic  # lazy: heavy import

    chat = ChatAnthropic(
        model=model or os.environ.get("NEMESIS_DIRECTOR_MODEL", DEFAULT_MODEL),
        effort="low",          # short structured answer: keep latency low between waves
        max_tokens=4000,
        timeout=timeout_s,
        max_retries=1,
    )
    return chat.with_structured_output(DirectorDecision, method="json_schema")


def build_messages(telemetry: WaveTelemetry, profile: dict, history: list[Adaptation],
                   suggestion: Adaptation, previous: DirectorDecision | None = None,
                   issues: list[str] | None = None, language: str | None = None) -> list:
    weapons = {wid: {**info, "display_name": weapon_name(wid, language)}
               for wid, info in WEAPON_PROFILES.items()}
    context = json.dumps({
        "telemetry_of_wave_just_played": telemetry.model_dump(),
        "next_wave": telemetry.wave + 1,
        "player_profile": profile,
        "player_weapons": weapons,
        "base_enemy_stats": BASE_STATS.model_dump(),
        "stat_limits": STAT_LIMITS,
        "previous_evolutions": [{"name": a.name, "reason": a.reason} for a in history[-4:]],
        "rule_based_baseline": suggestion.model_dump(),
    }, ensure_ascii=False, indent=1)
    messages = [SystemMessage(SYSTEM_PROMPT.format(language=language_name(language))),
                HumanMessage(context)]
    if previous is not None and issues:
        messages += [
            AIMessage(previous.model_dump_json()),
            HumanMessage("The game's reviewer rejected that evolution:\n- " + "\n- ".join(issues)
                         + "\nSend a corrected evolution that fixes every issue."),
        ]
    return messages


def decision_to_adaptation(decision: DirectorDecision) -> Adaptation:
    deltas, multipliers, overrides = {}, {}, {"ranged_enabled": decision.ranged_enabled}
    for change in decision.changes:
        target = {"add": deltas, "multiply": multipliers, "set": overrides}[change.op]
        target[change.stat] = change.value
    return Adaptation(name=decision.name, reason=decision.reason, deltas=deltas,
                      multipliers=multipliers, overrides=overrides)
