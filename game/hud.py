"""Evolution panel: shows the player what the AI Director changed and why."""
from ursina import *

from shared.i18n import t, weapon_name
from shared.models import BASE_STATS, stat_changes

# 0-1 stats are shown as percentages
PERCENT_STATS = {"armor", "armor_pen", "resist_slash", "resist_pierce", "resist_blunt"}


def describe_change(stat, old, new) -> str:
    label = t(f"stat.{stat}")
    if isinstance(new, bool):
        return f"{label}: {t('value.yes') if new else t('value.no')}"
    if stat in PERCENT_STATS:
        return f"{label}: {old:.0%} -> {new:.0%}"
    if old:
        return f"{label}: {old:g} -> {new:g} ({(new - old) / old:+.0%})"
    return f"{label}: {old:g} -> {new:g}"


class EvolutionPanel(Entity):
    def __init__(self, director_mode: str):
        super().__init__(parent=camera.ui)
        self.director_mode = director_mode
        self.title = Text(parent=self, text="", position=window.top_left + Vec2(.03, -.03),
                          scale=1.1, color=color.rgb32(255, 210, 80))
        self.reason = Text(parent=self, text=" ", position=window.top_left + Vec2(.03, -.075),
                           scale=.8, color=color.rgb32(235, 235, 235))
        self.reason.wordwrap = 48   # must be set after the text exists (Ursina quirk)
        self.changes = Text(parent=self, text="", position=window.top_left + Vec2(.03, -.17),
                            scale=.75, color=color.rgb32(180, 220, 255))
        self.show_base()

    def show_base(self):
        source = t("source.claude_graph" if self.director_mode == "claude" else "source.rules_local")
        self.title.text = t("panel.base_title")
        self.reason.text = t("panel.base_reason", source=source)
        self.changes.text = ""

    def show(self, decision):
        if decision.source == "claude":
            source = t("source.claude_corrected" if decision.attempts > 1 else "source.claude")
        else:
            source = t("source.rules")
        self.title.text = t("panel.evolution", name=decision.adaptation.name, source=source)
        self.reason.text = decision.adaptation.reason
        changes = stat_changes(decision.stats, BASE_STATS)
        self.changes.text = "\n".join(describe_change(s, o, n) for s, (o, n) in changes.items())


def wave_summary_text(telemetry) -> str:
    weapon = telemetry.dominant_weapon
    share = telemetry.attack_share.get(weapon, 0) if weapon else 0
    parts = [t("summary.accuracy", accuracy=f"{telemetry.accuracy:.0%}"),
             t("summary.damage", damage=f"{telemetry.damage_taken:.0f}")]
    if weapon:
        parts.insert(0, t("summary.dominant", weapon=weapon_name(weapon), share=f"{share:.0%}"))
    return "  ·  ".join(parts)
