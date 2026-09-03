"""Tests de la fórmula de daño del plan:
daño_final = daño_arma × (1 − resist_tipo) × (1 − max(0, armor − armor_pen_arma))
"""
import pytest

from shared.models import BASE_STATS, EnemyStats, compute_damage

# Valores de las armas del juego (game/weapons.py)
PISTOLA = dict(weapon_damage=25, damage_type="pierce", weapon_armor_pen=.25)
ESPADA = dict(weapon_damage=25, damage_type="slash", weapon_armor_pen=.10)
MARTILLO = dict(weapon_damage=45, damage_type="blunt", weapon_armor_pen=.40)


# --- Los 3 casos del ticket ---

def test_sin_armadura_ni_resistencias_el_dano_es_el_del_arma():
    assert compute_damage(**PISTOLA, stats=BASE_STATS) == 25


def test_con_armadura_reduce_el_dano():
    # armor 0.5 vs penetración 0.25 de la pistola → armadura efectiva 0.25
    stats = EnemyStats(armor=.5)
    assert compute_damage(**PISTOLA, stats=stats) == pytest.approx(25 * (1 - .25))


def test_con_penetracion_mayor_a_la_armadura_la_anula_sin_bonus():
    # martillo pen 0.40 vs armor 0.30 → max(0, -0.10) = 0 → daño completo, no más
    stats = EnemyStats(armor=.3)
    assert compute_damage(**MARTILLO, stats=stats) == 45


# --- Resultado esperado del ticket ---

def test_enemigo_anti_pistola_recibe_menos_dano_de_pistola_que_de_espada():
    anti_pistola = EnemyStats(resist_pierce=.6)
    de_pistola = compute_damage(**PISTOLA, stats=anti_pistola)
    de_espada = compute_damage(**ESPADA, stats=anti_pistola)
    assert de_pistola == pytest.approx(10)      # 25 × (1 − 0.6)
    assert de_espada == 25
    assert de_pistola < de_espada


# --- Casos de borde ---

def test_resistencia_y_armadura_se_multiplican():
    stats = EnemyStats(resist_slash=.5, armor=.3)
    # espada pen 0.10 → armadura efectiva 0.20
    assert compute_damage(**ESPADA, stats=stats) == pytest.approx(25 * .5 * .8)


def test_solo_afecta_la_resistencia_del_tipo_correcto():
    stats = EnemyStats(resist_slash=.6)   # resiste espada, no pistola
    assert compute_damage(**PISTOLA, stats=stats) == 25
    assert compute_damage(**ESPADA, stats=stats) == pytest.approx(10)


def test_nunca_es_negativo_ni_supera_el_dano_del_arma():
    peor = EnemyStats(resist_pierce=.6, armor=.5)
    assert 0 <= compute_damage(**PISTOLA, stats=peor) <= 25


def test_tipo_de_dano_desconocido_falla():
    with pytest.raises(ValueError):
        compute_damage(25, "fuego", 0, BASE_STATS)
