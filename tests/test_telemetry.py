"""Tests for the WaveTelemetry contract (game → director)."""
import pytest
from pydantic import ValidationError

from shared.models import WaveTelemetry, WeaponUsage

# Sample wave: a "gunslinger" player who finishes enemies off with the sword
USAGE = {
    "Pistola": WeaponUsage(attacks=20, hits=12, kills=3),
    "Espada": WeaponUsage(attacks=5, hits=5, kills=1),
}


def make_wave(**overrides):
    values = dict(wave=3, duration_s=40.0, damage_taken=35, player_hp_remaining=65,
                  deaths=0, weapon_usage=USAGE)
    values.update(overrides)
    return WaveTelemetry.from_counts(**values)


# --- Metrics derived from the counts ---

def test_precision_es_hits_sobre_attacks():
    assert make_wave().accuracy == pytest.approx(17 / 25)


def test_tiempo_promedio_por_kill():
    assert make_wave().avg_time_per_kill_s == pytest.approx(40 / 4)


def test_porcentajes_por_arma_suman_uno():
    t = make_wave()
    assert t.attack_share == pytest.approx({"Pistola": .8, "Espada": .2})
    assert t.kill_share == pytest.approx({"Pistola": .75, "Espada": .25})
    assert sum(t.attack_share.values()) == pytest.approx(1)
    assert sum(t.kill_share.values()) == pytest.approx(1)


def test_arma_dominante_es_la_pistola():
    assert make_wave().dominant_weapon == "Pistola"


def test_oleada_sin_ataques_no_divide_por_cero():
    t = make_wave(weapon_usage={})
    assert t.accuracy == 0
    assert t.avg_time_per_kill_s is None
    assert t.attack_share == {}
    assert t.dominant_weapon is None


# --- Contract: this is what travels over HTTP ---

def test_json_ida_y_vuelta_conserva_todo():
    original = make_wave()
    restored = WaveTelemetry.model_validate_json(original.model_dump_json())
    assert restored == original


def test_el_json_incluye_los_porcentajes_y_el_arma_dominante():
    data = make_wave().model_dump()
    assert data["attack_share"]["Pistola"] == pytest.approx(.8)
    assert data["kill_share"]["Espada"] == pytest.approx(.25)
    assert data["dominant_weapon"] == "Pistola"


# --- Validation ---

def test_hits_no_pueden_superar_attacks():
    with pytest.raises(ValidationError):
        WeaponUsage(attacks=3, hits=5)


def test_precision_fuera_de_rango_falla():
    with pytest.raises(ValidationError):
        WaveTelemetry(wave=1, duration_s=10, accuracy=1.5, damage_taken=0,
                      player_hp_remaining=100)


def test_oleada_cero_no_es_valida():
    with pytest.raises(ValidationError):
        make_wave(wave=0)


def test_es_inmutable():
    with pytest.raises(ValidationError):
        make_wave().deaths = 5
