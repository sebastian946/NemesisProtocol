"""Translations for everything the player sees and the console logs.

The language comes from the LANGUAGE variable (.env or environment):
"es" (default) or "en". Long forms like "spanish", "español" or "english"
also work. Internal ids (weapon ids, stat names, telemetry keys) never
change with the language; only what is displayed does.
"""
import os

from shared.env import load_env

DEFAULT_LANGUAGE = "es"
SUPPORTED = ("es", "en")
_ALIASES = {"es": "es", "spanish": "es", "español": "es", "espanol": "es",
            "en": "en", "english": "en", "inglés": "en", "ingles": "en"}

STRINGS: dict[str, dict[str, str]] = {
    "es": {
        # weapons
        "weapon.sword": "Espada", "weapon.pistol": "Pistola", "weapon.hammer": "Martillo",
        "weapon.shotgun": "Escopeta", "weapon.bow": "Arco",
        # HUD
        "hud.hint": "Click izquierdo: atacar | Teclas 1-5: cambiar de arma",
        "hud.hp": "HP",
        "hud.game_over": "GAME OVER",
        "wave.label": "OLEADA {wave}",
        "wave.cleared": "OLEADA {wave} SUPERADA",
        "wave.next_in": "Siguiente oleada en {seconds}...",
        "wave.director_thinking": "El Director está analizando tu estilo de juego",
        "wave.enemies": "Enemigos: {count}",
        "panel.base_title": "ENEMIGOS: forma base",
        "panel.base_reason": "El Director ({source}) observa cómo juegas...",
        "panel.evolution": "EVOLUCIÓN: {name}  [{source}]",
        "source.claude_graph": "Claude + LangGraph",
        "source.rules_local": "reglas locales",
        "source.claude": "Claude",
        "source.claude_corrected": "Claude, corregida por el revisor",
        "source.rules": "reglas",
        "value.yes": "SÍ", "value.no": "no",
        "summary.dominant": "Arma dominante: {weapon} ({share})",
        "summary.accuracy": "Precisión {accuracy}",
        "summary.damage": "Daño recibido {damage}",
        # stats
        "stat.hp": "Vida", "stat.speed": "Velocidad", "stat.size": "Tamaño",
        "stat.armor": "Blindaje", "stat.armor_pen": "Penetración",
        "stat.melee_damage": "Daño cuerpo a cuerpo", "stat.attack_speed": "Vel. de ataque",
        "stat.ranged_enabled": "Ataque a distancia", "stat.ranged_damage": "Daño a distancia",
        "stat.ranged_range": "Alcance de disparo", "stat.resist_slash": "Res. a cortes",
        "stat.resist_pierce": "Res. a perforación", "stat.resist_blunt": "Res. a impactos",
        "stat.detection_range": "Detección",
        # rule-based evolutions
        "counter.sword.name": "anti-espada",
        "counter.sword.reason": "Peleas cuerpo a cuerpo con la espada: ahora resisten los cortes y te disparan antes de que llegues.",
        "counter.hammer.name": "anti-martillo",
        "counter.hammer.reason": "Tu martillo es lento: se volvieron resistentes a impactos, más rápidos y atacan más seguido.",
        "counter.pistol.name": "anti-pistola",
        "counter.pistol.reason": "Dependes de la pistola: desarrollaron blindaje, resistencia a perforación y cierran distancia más rápido.",
        "counter.shotgun.name": "anti-escopeta",
        "counter.shotgun.reason": "Tu escopeta solo funciona de cerca: ahora mantienen la distancia y te atacan desde fuera de su alcance.",
        "counter.bow.name": "anti-arco",
        "counter.bow.reason": "Los cazas desde lejos con el arco: ahora son más pequeños, muy rápidos y te detectan desde cualquier punto.",
        "counter.generalist.name": "adaptación general",
        "counter.generalist.reason": "Alternas armas sin un patrón claro: refuerzan su blindaje y su resistencia en general.",
        "counter.untouched": " Terminaste casi intacto, así que golpean más fuerte.",
        # console logs
        "log.language": "[idioma] {name} (LANGUAGE={raw})",
        "log.director_mode": "[director] modo: {mode}",
        "log.wave_start": "[oleada {wave}] {count} enemigos | stats: {stats}",
        "log.wave_cleared": "[oleada {wave}] superada | {telemetry}",
        "log.decision": "[director] {source} (intentos={attempts}, revisión={issues}): {adaptation}",
        "log.fallback": " | respaldo por: {error}",
    },
    "en": {
        "weapon.sword": "Sword", "weapon.pistol": "Pistol", "weapon.hammer": "Hammer",
        "weapon.shotgun": "Shotgun", "weapon.bow": "Bow",
        "hud.hint": "Left click: attack | Keys 1-5: switch weapon",
        "hud.hp": "HP",
        "hud.game_over": "GAME OVER",
        "wave.label": "WAVE {wave}",
        "wave.cleared": "WAVE {wave} CLEARED",
        "wave.next_in": "Next wave in {seconds}...",
        "wave.director_thinking": "The Director is analyzing your play style",
        "wave.enemies": "Enemies: {count}",
        "panel.base_title": "ENEMIES: base form",
        "panel.base_reason": "The Director ({source}) is watching how you play...",
        "panel.evolution": "EVOLUTION: {name}  [{source}]",
        "source.claude_graph": "Claude + LangGraph",
        "source.rules_local": "local rules",
        "source.claude": "Claude",
        "source.claude_corrected": "Claude, corrected by the reviewer",
        "source.rules": "rules",
        "value.yes": "YES", "value.no": "no",
        "summary.dominant": "Dominant weapon: {weapon} ({share})",
        "summary.accuracy": "Accuracy {accuracy}",
        "summary.damage": "Damage taken {damage}",
        "stat.hp": "Health", "stat.speed": "Speed", "stat.size": "Size",
        "stat.armor": "Armor", "stat.armor_pen": "Armor pen.",
        "stat.melee_damage": "Melee damage", "stat.attack_speed": "Attack speed",
        "stat.ranged_enabled": "Ranged attack", "stat.ranged_damage": "Ranged damage",
        "stat.ranged_range": "Shooting range", "stat.resist_slash": "Slash res.",
        "stat.resist_pierce": "Pierce res.", "stat.resist_blunt": "Blunt res.",
        "stat.detection_range": "Detection",
        "counter.sword.name": "anti-sword",
        "counter.sword.reason": "You fight up close with the sword: now they resist slashes and shoot you before you get there.",
        "counter.hammer.name": "anti-hammer",
        "counter.hammer.reason": "Your hammer is slow: they became blunt-resistant, faster, and attack more often.",
        "counter.pistol.name": "anti-pistol",
        "counter.pistol.reason": "You rely on the pistol: they grew armor and pierce resistance, and close the distance faster.",
        "counter.shotgun.name": "anti-shotgun",
        "counter.shotgun.reason": "Your shotgun only works up close: now they keep their distance and hit you from beyond its reach.",
        "counter.bow.name": "anti-bow",
        "counter.bow.reason": "You hunt them from afar with the bow: now they are smaller, very fast, and spot you from anywhere.",
        "counter.generalist.name": "general adaptation",
        "counter.generalist.reason": "You switch weapons with no clear pattern: they reinforce their armor and overall toughness.",
        "counter.untouched": " You finished almost untouched, so they hit harder.",
        "log.language": "[language] {name} (LANGUAGE={raw})",
        "log.director_mode": "[director] mode: {mode}",
        "log.wave_start": "[wave {wave}] {count} enemies | stats: {stats}",
        "log.wave_cleared": "[wave {wave}] cleared | {telemetry}",
        "log.decision": "[director] {source} (attempts={attempts}, review={issues}): {adaptation}",
        "log.fallback": " | fallback because: {error}",
    },
}

LANGUAGE_NAMES = {"es": "Spanish", "en": "English"}   # used in the LLM prompt


def get_language() -> str:
    """Active language code, read on every call so tests and .env changes apply."""
    load_env()
    raw = os.environ.get("LANGUAGE", DEFAULT_LANGUAGE).strip().lower()
    return _ALIASES.get(raw, DEFAULT_LANGUAGE)


def describe_language() -> str:
    """Startup log line: the language in use and the raw LANGUAGE value it came from."""
    language = get_language()
    raw = os.environ.get("LANGUAGE", "<not set: default es>")
    return t("log.language", language, name=language_name(language), raw=raw)


def language_name(language: str | None = None) -> str:
    return LANGUAGE_NAMES[language or get_language()]


def t(key: str, language: str | None = None, **values) -> str:
    """Translated string for `key`, formatted with `values`. Falls back to
    Spanish, then to the key itself, so a missing entry never crashes the game."""
    language = language or get_language()
    text = STRINGS[language].get(key) or STRINGS[DEFAULT_LANGUAGE].get(key) or key
    return text.format(**values) if values else text


def weapon_name(weapon_id: str, language: str | None = None) -> str:
    return t(f"weapon.{weapon_id}", language)
