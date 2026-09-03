"""Pydantic models shared between the game and the AI Director.

- EnemyStats: EVERYTHING the AI Director may modify lives here (👾 table in the plan).
- BASE_STATS: the single source of truth, immutable.
- Adaptation: describes HOW to change the base (deltas, multipliers, overrides).
- apply_adaptation(): Rule 1 (replace, never accumulate) + Rule 2 (clamps).
- compute_damage(): weapon → enemy damage formula with resistances and armor.
- WaveTelemetry: game → director contract with the metrics of each wave (Stage 2).
"""
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class EnemyStats(BaseModel):
    # frozen: nobody can do `stats.armor += x`. To change stats, build a new
    # one with apply_adaptation(BASE_STATS, adaptation).
    model_config = ConfigDict(frozen=True)

    hp: int = 100
    speed: float = 4.0            # m/s
    size: float = 1.0             # model scale (affects hitbox)
    armor: float = 0.0            # 0-1: reduces % of incoming damage
    armor_pen: float = 0.0        # 0-1: ignores part of the player's defense
    melee_damage: int = 10
    attack_speed: float = 1.0     # attacks per second
    ranged_enabled: bool = False
    ranged_damage: int = 8
    ranged_range: float = 12.0
    resist_slash: float = 0.0     # 0-1: resistance to slash damage
    resist_pierce: float = 0.0    # 0-1: resistance to pierce damage
    resist_blunt: float = 0.0     # 0-1: resistance to blunt damage
    detection_range: float = 20.0


# Rule 1: ONE immutable base. Never modified, only read.
BASE_STATS = EnemyStats()

# Rule 2: limits hard-coded in the game (last line of defense against
# invalid values from the LLM). Rule 2 table in the plan.
# melee_damage and detection_range have no limit in the plan; they are
# bounded anyway so no path is left undefended.
STAT_LIMITS: dict[str, tuple[float, float]] = {
    "hp": (50, 300),
    "speed": (2.0, 7.0),
    "size": (0.7, 1.6),
    "armor": (0.0, 0.5),
    "armor_pen": (0.0, 0.4),
    "melee_damage": (5, 30),
    "attack_speed": (0.5, 2.5),
    "ranged_damage": (5, 20),
    "ranged_range": (8.0, 25.0),
    "resist_slash": (0.0, 0.6),
    "resist_pierce": (0.0, 0.6),
    "resist_blunt": (0.0, 0.6),
    "detection_range": (10.0, 40.0),
}

_INT_STATS = {name for name, field in EnemyStats.model_fields.items() if field.annotation is int}
_NUMERIC_STATS = set(STAT_LIMITS)


class Adaptation(BaseModel):
    """How to transform BASE_STATS. Applied in order: overrides → deltas → multipliers.

    Anti-pistol example: Adaptation(name="anti-pistol",
        deltas={"resist_pierce": 0.4, "armor": 0.2}, multipliers={"speed": 1.3})
    Anti-sword example: Adaptation(name="anti-sword",
        deltas={"resist_slash": 0.4}, overrides={"ranged_enabled": True})
    """
    model_config = ConfigDict(frozen=True)

    name: str
    reason: str = ""                                # explanation for the log
    deltas: dict[str, float] = {}                   # stat += value
    multipliers: dict[str, float] = {}              # stat *= value
    overrides: dict[str, float | bool] = {}         # stat = value (e.g. ranged_enabled)

    @field_validator("deltas", "multipliers")
    @classmethod
    def _numeric_stats_only(cls, value):
        unknown = set(value) - _NUMERIC_STATS
        if unknown:
            raise ValueError(f"unknown or non-numeric stats: {sorted(unknown)}")
        return value

    @field_validator("overrides")
    @classmethod
    def _known_stats_only(cls, value):
        unknown = set(value) - set(EnemyStats.model_fields)
        if unknown:
            raise ValueError(f"unknown stats: {sorted(unknown)}")
        return value


def clamp_stats(values: dict) -> dict:
    """Clamps each stat to its [min, max] range and rounds the integer ones."""
    clamped = dict(values)
    for stat, (low, high) in STAT_LIMITS.items():
        clamped[stat] = min(max(clamped[stat], low), high)
    for stat in _INT_STATS:
        clamped[stat] = int(round(clamped[stat]))
    return clamped


def apply_adaptation(base: EnemyStats, adaptation: Adaptation | None) -> EnemyStats:
    """Returns a NEW EnemyStats = base + adaptation, clamped.

    Pure function: does not modify `base`. Always call it with BASE_STATS so
    the previous adaptation is discarded entirely (Rule 1).
    """
    values = base.model_dump()
    if adaptation is None:
        return EnemyStats(**clamp_stats(values))

    for stat, value in adaptation.overrides.items():
        values[stat] = value
    for stat, delta in adaptation.deltas.items():
        values[stat] += delta
    for stat, factor in adaptation.multipliers.items():
        values[stat] *= factor
    return EnemyStats(**clamp_stats(values))


# ---------------------------------------------------------------------------
# Damage formula (plan, 🧬 section):
#   final_damage = weapon_damage × (1 − resist_type) × (1 − max(0, armor − weapon_armor_pen))
# ---------------------------------------------------------------------------
DAMAGE_TYPES = ("slash", "pierce", "blunt")


def compute_damage(weapon_damage: float, damage_type: str, weapon_armor_pen: float,
                   stats: EnemyStats) -> float:
    """Damage an enemy with `stats` takes from a weapon.

    - resist_<type> reduces damage of that type (sword=slash, hammer=blunt,
      pistol/shotgun/bow=pierce).
    - armor reduces all damage, but the weapon's penetration is subtracted
      first; leftover penetration gives no bonus (max(0, ...)).
    """
    if damage_type not in DAMAGE_TYPES:
        raise ValueError(f"invalid damage_type: {damage_type!r}; use one of {DAMAGE_TYPES}")
    resist = getattr(stats, f"resist_{damage_type}")
    effective_armor = max(0.0, stats.armor - weapon_armor_pen)
    return weapon_damage * (1 - resist) * (1 - effective_armor)


# ---------------------------------------------------------------------------
# Telemetry (Stage 2): snapshot the game sends to the director at the end of
# each wave. The director uses it to pick the counter-adaptation.
# ---------------------------------------------------------------------------
class WeaponUsage(BaseModel):
    """Raw counts for one weapon during a wave. Percentages are derived from
    these, so the game and the director never compute different shares."""
    model_config = ConfigDict(frozen=True)

    attacks: int = Field(0, ge=0)   # attacks performed (shots / swings)
    hits: int = Field(0, ge=0)      # attacks that connected with an enemy
    kills: int = Field(0, ge=0)

    @model_validator(mode="after")
    def _hits_cannot_exceed_attacks(self):
        if self.hits > self.attacks:
            raise ValueError(f"hits ({self.hits}) cannot exceed attacks ({self.attacks})")
        return self


class WaveTelemetry(BaseModel):
    """Metrics for one wave. Build it with `from_counts()` so accuracy and
    time per kill are derived from the counts and cannot contradict them."""
    model_config = ConfigDict(frozen=True)

    wave: int = Field(ge=1)
    duration_s: float = Field(ge=0)
    accuracy: float = Field(ge=0, le=1)                      # hits / attacks
    avg_time_per_kill_s: float | None = Field(None, ge=0)    # None when there were no kills
    damage_taken: float = Field(ge=0)
    player_hp_remaining: float = Field(ge=0)
    deaths: int = Field(0, ge=0)
    weapon_usage: dict[str, WeaponUsage] = {}

    # --- Derived shares: included in the JSON (computed_field) ---
    @computed_field
    @property
    def attack_share(self) -> dict[str, float]:
        """Share of attacks per weapon (0-1)."""
        return self._share("attacks")

    @computed_field
    @property
    def kill_share(self) -> dict[str, float]:
        """Share of kills per weapon (0-1)."""
        return self._share("kills")

    @computed_field
    @property
    def dominant_weapon(self) -> str | None:
        """Weapon that drives the counter-adaptation: average of attack and kill share."""
        if not self.weapon_usage:
            return None
        attack_share, kill_share = self.attack_share, self.kill_share
        return max(self.weapon_usage,
                   key=lambda w: (attack_share.get(w, 0) + kill_share.get(w, 0)) / 2)

    def _share(self, counter: str) -> dict[str, float]:
        total = sum(getattr(u, counter) for u in self.weapon_usage.values())
        if total == 0:
            return {}
        return {name: getattr(u, counter) / total for name, u in self.weapon_usage.items()}

    @classmethod
    def from_counts(cls, wave: int, duration_s: float, damage_taken: float,
                    player_hp_remaining: float, deaths: int,
                    weapon_usage: dict[str, WeaponUsage]) -> "WaveTelemetry":
        attacks = sum(u.attacks for u in weapon_usage.values())
        hits = sum(u.hits for u in weapon_usage.values())
        kills = sum(u.kills for u in weapon_usage.values())
        return cls(
            wave=wave,
            duration_s=duration_s,
            accuracy=hits / attacks if attacks else 0.0,
            avg_time_per_kill_s=duration_s / kills if kills else None,
            damage_taken=damage_taken,
            player_hp_remaining=player_hp_remaining,
            deaths=deaths,
            weapon_usage=weapon_usage,
        )
