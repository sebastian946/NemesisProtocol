"""Tests de las Reglas 1 y 2 del plan (BASE_STATS + apply_adaptation + clamps)."""
import pytest
from pydantic import ValidationError

from shared.models import BASE_STATS, STAT_LIMITS, Adaptation, EnemyStats, apply_adaptation

ANTI_PISTOLA = Adaptation(name="anti-pistola",
                          deltas={"resist_pierce": 0.4, "armor": 0.2},
                          multipliers={"speed": 1.3})
ANTI_ESPADA = Adaptation(name="anti-espada",
                         deltas={"resist_slash": 0.4},
                         overrides={"ranged_enabled": True},
                         multipliers={"ranged_range": 1.5})


# --- Regla 1: reemplazo, no acumulación ---

def test_base_stats_es_inmutable():
    with pytest.raises(ValidationError):
        BASE_STATS.hp = 999


def test_apply_no_modifica_la_base():
    before = BASE_STATS.model_dump()
    apply_adaptation(BASE_STATS, ANTI_PISTOLA)
    assert BASE_STATS.model_dump() == before


def test_aplicar_dos_adaptaciones_equivale_a_solo_la_ultima():
    # Oleada 3: anti-pistola. Oleada 4: anti-espada (la anterior se descarta).
    oleada_3 = apply_adaptation(BASE_STATS, ANTI_PISTOLA)
    oleada_4 = apply_adaptation(BASE_STATS, ANTI_ESPADA)   # SIEMPRE desde la base
    solo_ultima = apply_adaptation(BASE_STATS, ANTI_ESPADA)

    assert oleada_4 == solo_ultima
    assert oleada_4.resist_pierce == BASE_STATS.resist_pierce  # anti-pistola no se acumuló
    assert oleada_3.resist_pierce == pytest.approx(0.4)


def test_acumulacion_encadenada_se_detecta():
    # Si alguien hace lo PROHIBIDO (encadenar), el resultado difiere de solo-la-última.
    encadenado = apply_adaptation(apply_adaptation(BASE_STATS, ANTI_PISTOLA), ANTI_ESPADA)
    correcto = apply_adaptation(BASE_STATS, ANTI_ESPADA)
    assert encadenado != correcto


def test_deltas_multiplicadores_y_overrides():
    stats = apply_adaptation(BASE_STATS, ANTI_ESPADA)
    assert stats.resist_slash == pytest.approx(0.4)
    assert stats.ranged_enabled is True
    assert stats.ranged_range == pytest.approx(18.0)       # 12 * 1.5
    assert stats.hp == BASE_STATS.hp                       # lo no mencionado no cambia


def test_sin_adaptacion_devuelve_la_base():
    assert apply_adaptation(BASE_STATS, None) == BASE_STATS


# --- Regla 2: clamps ---

def test_valores_fuera_de_rango_se_recortan():
    exagerada = Adaptation(name="LLM alucinando",
                           deltas={"armor": 5.0, "resist_pierce": 9.0, "hp": -1000},
                           multipliers={"speed": 100})
    stats = apply_adaptation(BASE_STATS, exagerada)
    assert stats.armor == STAT_LIMITS["armor"][1]
    assert stats.resist_pierce == STAT_LIMITS["resist_pierce"][1]
    assert stats.hp == STAT_LIMITS["hp"][0]
    assert stats.speed == STAT_LIMITS["speed"][1]


def test_todos_los_stats_de_la_base_estan_dentro_de_limites():
    for stat, (low, high) in STAT_LIMITS.items():
        assert low <= getattr(BASE_STATS, stat) <= high


def test_enteros_se_redondean():
    stats = apply_adaptation(BASE_STATS, Adaptation(name="x", multipliers={"hp": 1.333}))
    assert isinstance(stats.hp, int)
    assert stats.hp == 133


# --- Validación del modelo Adaptation ---

def test_adaptation_rechaza_stats_desconocidos():
    with pytest.raises(ValidationError):
        Adaptation(name="typo", deltas={"velocidad": 1})


def test_adaptation_rechaza_delta_en_booleano():
    with pytest.raises(ValidationError):
        Adaptation(name="mal", deltas={"ranged_enabled": 1})


def test_enemy_stats_es_inmutable():
    stats = EnemyStats(hp=120)
    with pytest.raises(ValidationError):
        stats.speed = 10
