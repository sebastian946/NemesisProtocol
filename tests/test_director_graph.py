"""Tests for the LangGraph workflow (director/graph.py) with a fake LLM.

The fake returns scripted DirectorDecisions, so every path of the graph
(approve, review → retry, out of retries, error → fallback) runs offline.
"""
from director import Director
from director.graph import MAX_ATTEMPTS, build_director_graph, build_profile, review_decision
from director.llm import DirectorDecision, StatChange
from shared.models import STAT_LIMITS, WaveTelemetry, WeaponUsage


class ScriptedLLM:
    """Returns the scripted decisions in order and records the messages it got."""

    def __init__(self, *decisions):
        self.decisions = list(decisions)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        item = self.decisions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def pistol_wave():
    return WaveTelemetry.from_counts(wave=2, duration_s=30, damage_taken=40, player_hp_remaining=60,
                                     deaths=0, weapon_usage={"pistol": WeaponUsage(attacks=20, hits=12, kills=4)})


GOOD = DirectorDecision(name="anti-pistola", reason="Tu pistola ya no basta.", ranged_enabled=False,
                        changes=[StatChange(stat="resist_pierce", op="add", value=.3),
                                 StatChange(stat="speed", op="multiply", value=1.2)])
# armor +5 on a 0-1 stat: the exact mistake Claude made in a real call
OUT_OF_RANGE = DirectorDecision(name="anti-pistola", reason="...", ranged_enabled=False,
                                changes=[StatChange(stat="armor", op="add", value=5)])
OFF_TARGET = DirectorDecision(name="más vida", reason="...", ranged_enabled=False,
                              changes=[StatChange(stat="hp", op="multiply", value=1.2)])


def run(llm):
    return build_director_graph(llm).invoke({"telemetry": pistol_wave(), "history": []})


# --- Review step ---

def test_review_aprueba_una_buena_evolucion():
    assert review_decision(GOOD, build_profile(pistol_wave())) == []


def test_review_detecta_valores_fuera_de_limite():
    issues = review_decision(OUT_OF_RANGE, build_profile(pistol_wave()))
    assert any("armor" in i and "limits" in i for i in issues)


def test_review_exige_contrarrestar_el_arma_dominante():
    issues = review_decision(OFF_TARGET, build_profile(pistol_wave()))
    assert any("pistol" in i for i in issues)


def test_perfil_del_jugador():
    profile = build_profile(pistol_wave())
    assert profile["dominant_weapon"] == "pistol"
    assert profile["play_style"] == "specialist"
    assert "resist_pierce" in profile["counter_stats"]


# --- Graph paths ---

def test_sin_llm_el_grafo_usa_reglas():
    state = run(None)
    assert state["source"] == "reglas"
    assert state["adaptation"].name == "anti-pistola"


def test_evolucion_aprobada_al_primer_intento():
    llm = ScriptedLLM(GOOD)
    state = run(llm)
    assert state["source"] == "claude"
    assert state["attempts"] == 1
    assert state["stats"].resist_pierce == .3


def test_review_pide_correccion_y_claude_la_corrige():
    llm = ScriptedLLM(OUT_OF_RANGE, GOOD)
    state = run(llm)
    assert state["attempts"] == 2
    assert state["adaptation"].name == "anti-pistola"
    assert state["stats"].resist_pierce == .3
    feedback = llm.calls[1][-1].content          # the reviewer's message is sent back to Claude
    assert "armor" in feedback and "rejected" in feedback
    assert any("armor" in i for i in state["review_log"])


def test_sin_reintentos_se_usa_la_propuesta_limitada():
    llm = ScriptedLLM(*[OUT_OF_RANGE] * MAX_ATTEMPTS)
    state = run(llm)
    assert len(llm.calls) == MAX_ATTEMPTS
    assert state["source"] == "claude"
    assert state["stats"].armor == STAT_LIMITS["armor"][1]   # clamps are the last line of defense


def test_error_del_llm_cae_a_las_reglas():
    state = run(ScriptedLLM(TimeoutError("sin red")))
    assert state["source"] == "reglas"
    assert "sin red" in state["error"]


def test_error_de_autenticacion_desactiva_claude():
    class AuthenticationError(Exception):
        pass

    director = Director(llm=ScriptedLLM(AuthenticationError("invalid x-api-key")), log_dir=None)
    assert director.mode == "claude"
    decision = director.decide(pistol_wave())
    assert decision.source == "reglas"
    assert director.mode == "reglas"
    assert director.decide(pistol_wave()).source == "reglas"   # no second call to the API


def test_director_pasa_el_historial_a_claude():
    llm = ScriptedLLM(GOOD, GOOD)
    director = Director(llm=llm, log_dir=None)
    director.decide(pistol_wave())
    director.decide(pistol_wave())
    assert "anti-pistola" in llm.calls[1][1].content   # previous_evolutions in the prompt
