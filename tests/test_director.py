"""Tests for the AI Director: rule-based counters, LLM output conversion and fallback."""
import pytest

from director import Director
from director.llm import DirectorDecision, StatChange, decision_to_adaptation
from director.rules import COUNTERS, rule_based_adaptation
from shared.i18n import t
from game.telemetry import WaveTracker
from shared.models import BASE_STATS, STAT_LIMITS, WaveTelemetry, WeaponUsage, stat_changes


def wave_with(usage, wave=1, hp_left=50):
    return WaveTelemetry.from_counts(wave=wave, duration_s=30, damage_taken=100 - hp_left,
                                     player_hp_remaining=hp_left, deaths=0, weapon_usage=usage)


def only(weapon, wave=1, hp_left=50):
    return wave_with({weapon: WeaponUsage(attacks=20, hits=10, kills=4)}, wave, hp_left)


# --- Rules: every weapon has a counter that targets it ---

@pytest.mark.parametrize("weapon", list(COUNTERS))
def test_cada_arma_dominante_recibe_su_contra(weapon):
    adaptation = rule_based_adaptation(only(weapon))
    assert adaptation.name == t(f"counter.{weapon}.name")


def test_anti_pistola_reduce_el_dano_de_pistola():
    from shared.models import apply_adaptation, compute_damage
    stats = apply_adaptation(BASE_STATS, rule_based_adaptation(only("pistol")))
    assert compute_damage(25, "pierce", .25, stats) < compute_damage(25, "pierce", .25, BASE_STATS)


def test_anti_espada_activa_ataque_a_distancia():
    from shared.models import apply_adaptation
    stats = apply_adaptation(BASE_STATS, rule_based_adaptation(only("sword")))
    assert stats.ranged_enabled


def test_jugador_sin_arma_dominante_recibe_adaptacion_general():
    usage = {w: WeaponUsage(attacks=5, hits=3, kills=1) for w in ("pistol", "sword", "bow")}
    assert rule_based_adaptation(wave_with(usage)).name == t("counter.generalist.name")


def test_oleada_sin_ataques_no_rompe_las_reglas():
    assert rule_based_adaptation(wave_with({})).name == t("counter.generalist.name")


def test_la_vida_escala_con_la_oleada():
    early = rule_based_adaptation(only("pistol", wave=1)).multipliers["hp"]
    late = rule_based_adaptation(only("pistol", wave=5)).multipliers["hp"]
    assert late > early


def test_jugador_intacto_hace_que_peguen_mas_fuerte():
    assert "melee_damage" in rule_based_adaptation(only("bow", hp_left=95)).multipliers
    assert "melee_damage" not in rule_based_adaptation(only("bow", hp_left=20)).multipliers


# --- LLM output → Adaptation ---

def test_decision_del_llm_se_convierte_en_adaptacion():
    decision = DirectorDecision(name="anti-arco", reason="...", ranged_enabled=False, changes=[
        StatChange(stat="speed", op="multiply", value=1.4),
        StatChange(stat="resist_pierce", op="add", value=.3),
        StatChange(stat="detection_range", op="set", value=40),
    ])
    adaptation = decision_to_adaptation(decision)
    assert adaptation.multipliers == {"speed": 1.4}
    assert adaptation.deltas == {"resist_pierce": .3}
    assert adaptation.overrides == {"ranged_enabled": False, "detection_range": 40}


def test_valores_absurdos_del_llm_quedan_limitados():
    from shared.models import apply_adaptation
    decision = DirectorDecision(name="x", reason="", ranged_enabled=True, changes=[
        StatChange(stat="hp", op="multiply", value=1000),
        StatChange(stat="armor", op="add", value=5),
    ])
    stats = apply_adaptation(BASE_STATS, decision_to_adaptation(decision))
    assert stats.hp == STAT_LIMITS["hp"][1]
    assert stats.armor == STAT_LIMITS["armor"][1]


# --- Director facade ---

def test_director_sin_llm_usa_reglas():
    director = Director(use_llm=False, log_dir=None)
    decision = director.decide(only("shotgun"))
    assert decision.source == "reglas"
    assert decision.adaptation.name == "anti-escopeta"
    assert decision.stats.ranged_enabled


def test_si_el_llm_falla_cae_a_las_reglas():
    class BrokenLLM:
        def invoke(self, messages):
            raise TimeoutError("sin red")

    director = Director(llm=BrokenLLM(), log_dir=None)
    decision = director.decide(only("hammer"))
    assert decision.source == "reglas"
    assert decision.adaptation.name == "anti-martillo"
    assert "sin red" in decision.error


def test_director_registra_historial_y_reset_lo_borra():
    director = Director(use_llm=False, log_dir=None)
    director.decide(only("pistol"))
    director.decide(only("sword", wave=2))
    assert [a.name for a in director.history] == ["anti-pistola", "anti-espada"]
    director.reset()
    assert director.history == []


def test_decide_async_devuelve_la_decision():
    director = Director(use_llm=False, log_dir=None)
    assert director.decide_async(only("bow")).result(timeout=5).adaptation.name == "anti-arco"


def test_director_escribe_log(tmp_path):
    Director(use_llm=False, log_dir=tmp_path).decide(only("pistol"))
    assert (tmp_path / "director_log.jsonl").read_text(encoding="utf-8").count("\n") == 1


# --- Game-side tracker and helpers ---

def test_tracker_cuenta_ataques_aciertos_y_bajas():
    tracker = WaveTracker()
    tracker.record_attack("pistol", hit=True, kills=1)
    tracker.record_attack("pistol", hit=False)
    tracker.record_attack("sword", hit=True)
    tracker.record_damage(30)
    telemetry = tracker.build(wave=2, duration_s=20, player_hp_remaining=70)
    assert telemetry.weapon_usage["pistol"] == WeaponUsage(attacks=2, hits=1, kills=1)
    assert telemetry.accuracy == pytest.approx(2 / 3)
    assert telemetry.damage_taken == 30
    assert telemetry.dominant_weapon == "pistol"


def test_stat_changes_lista_solo_lo_que_cambio():
    from shared.models import EnemyStats
    changes = stat_changes(EnemyStats(armor=.2, ranged_enabled=True))
    assert changes == {"armor": (0.0, .2), "ranged_enabled": (False, True)}
