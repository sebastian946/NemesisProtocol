"""Deterministic counter-adaptations. Always available (no network, no API key)
and used as the fallback whenever the LLM fails, times out or is disabled.

Every adaptation is built from scratch for the NEXT wave and applied to
BASE_STATS (Rule 1), so "evolution" comes from two sources:
- the counter to the player's dominant weapon in the last wave;
- a difficulty curve that depends on the wave number and on how easily the
  player cleared it.
"""
from shared.i18n import t
from shared.models import Adaptation, WaveTelemetry

# Below this share the player is considered a generalist (no clear favorite).
DOMINANCE_THRESHOLD = 0.55

# Keyed by weapon id. The name and reason of each counter come from shared/i18n.py
# ("counter.<id>.name" / "counter.<id>.reason") in the active language.
COUNTERS: dict[str, dict] = {
    "sword": dict(
        deltas={"resist_slash": 0.45},
        overrides={"ranged_enabled": True, "ranged_range": 14.0},
    ),
    "hammer": dict(
        deltas={"resist_blunt": 0.45},
        multipliers={"speed": 1.3, "attack_speed": 1.4},
    ),
    "pistol": dict(
        deltas={"resist_pierce": 0.35, "armor": 0.25},
        multipliers={"speed": 1.2},
    ),
    "shotgun": dict(
        deltas={"resist_pierce": 0.3},
        overrides={"ranged_enabled": True, "ranged_range": 18.0},
        multipliers={"hp": 1.15},
    ),
    "bow": dict(
        deltas={"resist_pierce": 0.25},
        overrides={"detection_range": 40.0},
        multipliers={"speed": 1.45, "size": 0.75},
    ),
}

GENERALIST = dict(
    deltas={"armor": 0.2},
    multipliers={"hp": 1.2},
)


def wave_hp_multiplier(next_wave: int) -> float:
    """+10% HP per wave after the first (clamped later by STAT_LIMITS)."""
    return 1 + 0.1 * (next_wave - 1)


def dominant_share(telemetry: WaveTelemetry) -> float:
    weapon = telemetry.dominant_weapon
    if weapon is None:
        return 0.0
    return (telemetry.attack_share.get(weapon, 0) + telemetry.kill_share.get(weapon, 0)) / 2


def rule_based_adaptation(telemetry: WaveTelemetry, player_max_hp: float = 100) -> Adaptation:
    """Picks the counter to the wave's dominant weapon plus the difficulty curve."""
    weapon = telemetry.dominant_weapon
    if weapon in COUNTERS and dominant_share(telemetry) >= DOMINANCE_THRESHOLD:
        key, base = weapon, COUNTERS[weapon]
    else:
        key, base = "generalist", GENERALIST

    deltas = dict(base.get("deltas", {}))
    multipliers = dict(base.get("multipliers", {}))
    overrides = dict(base.get("overrides", {}))
    reason = t(f"counter.{key}.reason")

    next_wave = telemetry.wave + 1
    multipliers["hp"] = multipliers.get("hp", 1.0) * wave_hp_multiplier(next_wave)

    # The player barely got scratched: enemies hit harder.
    if telemetry.player_hp_remaining >= 0.7 * player_max_hp:
        multipliers["melee_damage"] = multipliers.get("melee_damage", 1.0) * 1.3
        reason += t("counter.untouched")

    return Adaptation(name=t(f"counter.{key}.name"), reason=reason, deltas=deltas,
                      multipliers=multipliers, overrides=overrides)
