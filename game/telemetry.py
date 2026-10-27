"""Collects the player's actions during a wave and builds the WaveTelemetry
snapshot for the director. Pure Python (no Ursina), so it is unit-tested."""
from shared.models import WaveTelemetry, WeaponUsage


class WaveTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self._usage: dict[str, dict[str, int]] = {}
        self.damage_taken = 0.0

    def record_attack(self, weapon_id: str, hit: bool, kills: int = 0):
        usage = self._usage.setdefault(weapon_id, {"attacks": 0, "hits": 0, "kills": 0})
        usage["attacks"] += 1
        usage["hits"] += int(hit)
        usage["kills"] += kills

    def record_damage(self, amount: float):
        self.damage_taken += amount

    def build(self, wave: int, duration_s: float, player_hp_remaining: float,
              deaths: int = 0) -> WaveTelemetry:
        return WaveTelemetry.from_counts(
            wave=wave, duration_s=duration_s, damage_taken=self.damage_taken,
            player_hp_remaining=player_hp_remaining, deaths=deaths,
            weapon_usage={name: WeaponUsage(**u) for name, u in self._usage.items()},
        )
