"""Tests for the LANGUAGE variable (shared/i18n.py) and its effect on the director."""
import pytest

from director.graph import build_director_graph
from director.llm import build_messages
from director.rules import rule_based_adaptation
from shared.i18n import STRINGS, get_language, language_name, t, weapon_name
from shared.models import WaveTelemetry, WeaponUsage


def pistol_wave():
    return WaveTelemetry.from_counts(wave=1, duration_s=30, damage_taken=50, player_hp_remaining=50,
                                     deaths=0, weapon_usage={"pistol": WeaponUsage(attacks=20, hits=10, kills=3)})


def test_ambos_idiomas_tienen_las_mismas_claves():
    assert STRINGS["es"].keys() == STRINGS["en"].keys()


@pytest.mark.parametrize("raw, expected", [
    ("es", "es"), ("en", "en"), ("EN", "en"), ("english", "en"), ("Español", "es"),
    ("spanish", "es"), ("fr", "es"), (" en ", "en"),
])
def test_valores_aceptados_de_language(monkeypatch, raw, expected):
    monkeypatch.setenv("LANGUAGE", raw)
    assert get_language() == expected


def test_sin_variable_el_idioma_es_espanol(monkeypatch):
    monkeypatch.delenv("LANGUAGE")
    monkeypatch.setattr("shared.i18n.load_env", lambda: None)   # ignore the developer's .env
    assert get_language() == "es"


def test_textos_del_hud_cambian_de_idioma(monkeypatch):
    assert t("wave.label", wave=3) == "OLEADA 3"
    assert weapon_name("pistol") == "Pistola"
    monkeypatch.setenv("LANGUAGE", "en")
    assert t("wave.label", wave=3) == "WAVE 3"
    assert weapon_name("pistol") == "Pistol"


def test_clave_desconocida_no_rompe_el_juego():
    assert t("does.not.exist") == "does.not.exist"


def test_reglas_en_ingles(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "en")
    adaptation = rule_based_adaptation(pistol_wave())
    assert adaptation.name == "anti-pistol"
    assert "pistol" in adaptation.reason


def test_el_prompt_pide_el_idioma_activo():
    graph_input = dict(telemetry=pistol_wave(), profile={}, history=[],
                       suggestion=rule_based_adaptation(pistol_wave()))
    english = build_messages(**graph_input, language="en")
    assert "Write `name` and `reason` in English" in english[0].content
    assert '"display_name": "Pistol"' in english[1].content
    spanish = build_messages(**graph_input, language="es")
    assert "in Spanish" in spanish[0].content
    assert language_name("es") == "Spanish"


def test_el_grafo_pasa_el_idioma_a_claude():
    class RecordingLLM:
        def __init__(self):
            self.messages = None

        def invoke(self, messages):
            self.messages = messages
            raise TimeoutError("offline")

    llm = RecordingLLM()
    build_director_graph(llm).invoke({"telemetry": pistol_wave(), "history": [], "language": "en"})
    assert "in English" in llm.messages[0].content


def test_mensaje_de_arranque_muestra_el_idioma(monkeypatch):
    from shared.i18n import describe_language
    monkeypatch.setenv("LANGUAGE", "EN")
    assert describe_language() == "[language] English (LANGUAGE=EN)"
