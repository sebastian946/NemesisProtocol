"""Sistema de oleadas: spawnea N enemigos por ronda en puntos aleatorios,
detecta cuando mueren todos, hace una pausa y lanza la siguiente.

Hooks para las siguientes etapas:
- on_wave_start(wave, stats): al spawnear la oleada.
- on_wave_end(wave, summary): al morir el último enemigo → aquí se conecta la telemetría.
- set_stats_for_next_wave(stats): aquí entrará apply_adaptation(BASE_STATS, adaptación).
"""
from math import ceil
from random import uniform

from ursina import *

import time

from enemy import Enemy
from shared.models import BASE_STATS, EnemyStats

WAVE_BREAK_SECONDS = 5     # pausa entre oleadas
FIRST_WAVE_DELAY = 3
MIN_SPAWN_DISTANCE = 12    # nunca aparecen pegados al jugador
SPAWN_MARGIN = 3           # distancia mínima a las paredes
MAX_ENEMIES_PER_WAVE = 12


def enemies_for_wave(wave: int) -> int:
    """Oleada 1 → 3 enemigos, +1 por oleada hasta el tope."""
    return min(2 + wave, MAX_ENEMIES_PER_WAVE)


class WaveManager(Entity):
    def __init__(self, player, arena_half, obstacles, on_attack_player,
                 kill_sound=None, on_wave_start=None, on_wave_end=None):
        super().__init__()
        self.player = player
        self.arena_half = arena_half
        self.obstacles = obstacles
        self.on_attack_player = on_attack_player
        self.kill_sound = kill_sound
        self.on_wave_start = on_wave_start or (lambda wave, stats: None)
        self.on_wave_end = on_wave_end or (lambda wave, summary: None)

        self.wave = 0
        self.enemies: list[Enemy] = []
        self.stats: EnemyStats = BASE_STATS   # stats de la próxima oleada
        self._wave_started_at = 0.0
        self._break_left = 0.0

        # --- UI ---
        self.wave_label = Text(text="", origin=(0, .5), position=window.top + Vec2(0, -.02),
                               scale=1.6, color=color.rgb32(240, 240, 240))
        self.status_label = Text(text="", origin=(0, .5), position=window.top + Vec2(0, -.08),
                                 scale=1, color=color.rgb32(200, 200, 200))
        self.banner = Text(text="", origin=(0, 0), position=(0, .18), scale=2.6,
                           color=color.rgb32(255, 210, 80), enabled=False)

    # --- API pública ---
    def start(self):
        self.wave = 0
        self.stats = BASE_STATS
        self.wave_label.text = "OLEADA 1"
        self._begin_break(FIRST_WAVE_DELAY)

    def restart(self):
        for enemy in self.enemies:
            destroy(enemy)
        self.enemies.clear()
        self.start()

    def set_stats_for_next_wave(self, stats: EnemyStats):
        """Punto de entrada de las adaptaciones (Etapas 3 y 4)."""
        self.stats = stats

    @property
    def alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    # --- Ciclo de la oleada ---
    def update(self):
        if self._break_left <= 0:
            return
        self._break_left -= time.dt
        self.status_label.text = f"Siguiente oleada en {ceil(max(self._break_left, 0))}..."
        if self._break_left <= 0:
            self._start_next_wave()

    def _begin_break(self, seconds):
        self._break_left = seconds

    def _start_next_wave(self):
        self.wave += 1
        self._wave_started_at = time.time()
        count = enemies_for_wave(self.wave)
        for _ in range(count):
            x, z = self._random_spawn_point()
            self.enemies.append(Enemy(self.player, self.stats, x=x, z=z,
                                      on_attack_player=self.on_attack_player,
                                      on_death=self._on_enemy_death))
        self.wave_label.text = f"OLEADA {self.wave}"
        self._update_status()
        self._show_banner(f"OLEADA {self.wave}")
        self.on_wave_start(self.wave, self.stats)

    def _on_enemy_death(self, enemy):
        if self.kill_sound:
            self.kill_sound.play()
        destroy(enemy, delay=.4)  # deja terminar la animación de muerte
        self.enemies.remove(enemy)
        self._update_status()
        if not self.alive_enemies:
            self._end_wave()

    def _end_wave(self):
        summary = {
            "wave": self.wave,
            "enemies": enemies_for_wave(self.wave),
            "duration_s": round(time.time() - self._wave_started_at, 1),
            "player_hp": self.player.hp,
        }
        self.on_wave_end(self.wave, summary)
        self._show_banner(f"OLEADA {self.wave} SUPERADA")
        self._begin_break(WAVE_BREAK_SECONDS)

    # --- Helpers ---
    def _update_status(self):
        self.status_label.text = f"Enemigos: {len(self.alive_enemies)}"

    def _show_banner(self, text, seconds=2):
        self.banner.text = text
        self.banner.enabled = True
        invoke(setattr, self.banner, "enabled", False, delay=seconds)

    def _random_spawn_point(self):
        limit = self.arena_half - SPAWN_MARGIN
        for _ in range(60):
            x, z = uniform(-limit, limit), uniform(-limit, limit)
            if distance_xz(Vec3(x, 0, z), self.player.position) < MIN_SPAWN_DISTANCE:
                continue
            if any(self._inside_obstacle(x, z, o) for o in self.obstacles):
                continue
            if any(distance_xz(Vec3(x, 0, z), e.position) < 2 for e in self.enemies):
                continue
            return x, z
        return limit, limit  # fallback: esquina

    @staticmethod
    def _inside_obstacle(x, z, obstacle, padding=1.2):
        return (abs(x - obstacle.x) < obstacle.scale_x / 2 + padding
                and abs(z - obstacle.z) < obstacle.scale_z / 2 + padding)
