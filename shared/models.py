"""Modelos Pydantic compartidos entre el juego y el AI Director.

- EnemyStats: TODO lo que el AI Director podrá modificar está aquí (tabla 👾 del plan).
- BASE_STATS: la única fuente de verdad, inmutable.
- Adaptation: describe CÓMO cambiar la base (deltas, multiplicadores, overrides).
- apply_adaptation(): Regla 1 (reemplazo, no acumulación) + Regla 2 (clamps).
"""
from pydantic import BaseModel, ConfigDict, field_validator


class EnemyStats(BaseModel):
    # frozen: nadie puede hacer `stats.armor += x`. Para cambiar stats se
    # construye uno nuevo con apply_adaptation(BASE_STATS, adaptacion).
    model_config = ConfigDict(frozen=True)

    hp: int = 100
    speed: float = 4.0            # m/s
    size: float = 1.0             # escala del modelo (afecta hitbox)
    armor: float = 0.0            # 0-1: reduce % del daño recibido
    armor_pen: float = 0.0        # 0-1: ignora parte de la defensa del jugador
    melee_damage: int = 10
    attack_speed: float = 1.0     # ataques por segundo
    ranged_enabled: bool = False
    ranged_damage: int = 8
    ranged_range: float = 12.0
    resist_slash: float = 0.0     # 0-1: resistencia al daño cortante
    resist_pierce: float = 0.0    # 0-1: resistencia al daño perforante
    resist_blunt: float = 0.0     # 0-1: resistencia al daño contundente
    detection_range: float = 20.0


# Regla 1: UNA sola base inmutable. Nunca se modifica, solo se lee.
BASE_STATS = EnemyStats()

# Regla 2: límites hard-coded en el juego (última línea de defensa contra
# valores inválidos del LLM). Tabla de la Regla 2 del plan.
# melee_damage y detection_range no tienen límite en el plan; se acotan
# igual para que ninguna ruta quede sin defensa.
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
    """Cómo transformar BASE_STATS. Se aplica en orden: overrides → deltas → multipliers.

    Ejemplo anti-pistola: Adaptation(name="anti-pistola",
        deltas={"resist_pierce": 0.4, "armor": 0.2}, multipliers={"speed": 1.3})
    Ejemplo anti-espada: Adaptation(name="anti-espada",
        deltas={"resist_slash": 0.4}, overrides={"ranged_enabled": True})
    """
    model_config = ConfigDict(frozen=True)

    name: str
    reason: str = ""                                # explicación para el log
    deltas: dict[str, float] = {}                   # stat += valor
    multipliers: dict[str, float] = {}              # stat *= valor
    overrides: dict[str, float | bool] = {}         # stat = valor (p. ej. ranged_enabled)

    @field_validator("deltas", "multipliers")
    @classmethod
    def _numeric_stats_only(cls, value):
        unknown = set(value) - _NUMERIC_STATS
        if unknown:
            raise ValueError(f"stats desconocidos o no numéricos: {sorted(unknown)}")
        return value

    @field_validator("overrides")
    @classmethod
    def _known_stats_only(cls, value):
        unknown = set(value) - set(EnemyStats.model_fields)
        if unknown:
            raise ValueError(f"stats desconocidos: {sorted(unknown)}")
        return value


def clamp_stats(values: dict) -> dict:
    """Recorta cada stat a su rango [mín, máx] y redondea los enteros."""
    clamped = dict(values)
    for stat, (low, high) in STAT_LIMITS.items():
        clamped[stat] = min(max(clamped[stat], low), high)
    for stat in _INT_STATS:
        clamped[stat] = int(round(clamped[stat]))
    return clamped


def apply_adaptation(base: EnemyStats, adaptation: Adaptation | None) -> EnemyStats:
    """Devuelve un EnemyStats NUEVO = base + adaptación, con clamps.

    Función pura: no modifica `base`. Llamar siempre con BASE_STATS para que
    la adaptación anterior se descarte por completo (Regla 1).
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
