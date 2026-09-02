"""Clase Enemy: enemigo controlado 100% por sus EnemyStats.

Cambiar valores del stats cambia el comportamiento sin tocar más código:
persecución (speed, detection_range), tamaño/hitbox (size),
melee (melee_damage, attack_speed) y vida (hp).
"""
from math import cos, radians, sin

from ursina import *

import time

from shared.models import BASE_STATS, EnemyStats

BODY_COLOR = color.rgb32(150, 45, 45)
HEAD_COLOR = color.rgb32(170, 60, 60)
EYE_COLOR = color.rgb32(255, 220, 90)

ATTACK_RANGE = 1.8      # metros a los que conecta el melee
AVOID_ANGLES = (0, 40, -40, 75, -75)  # desvíos para rodear obstáculos


def _rotated_y(direction, degrees):
    r = radians(degrees)
    return Vec3(direction.x * cos(r) - direction.z * sin(r), 0,
                direction.x * sin(r) + direction.z * cos(r))


class Enemy(Entity):
    def __init__(self, player, stats: EnemyStats | None = None, x=0, z=0,
                 on_attack_player=None, on_death=None):
        stats = stats or BASE_STATS
        super().__init__(position=(x, stats.size, z), scale=stats.size)
        self.player = player
        self.stats = stats
        self.hp = stats.hp
        self.on_attack_player = on_attack_player or (lambda damage: None)
        self.on_death = on_death or (lambda enemy: None)
        self.alive = True
        self._next_attack_time = 0.0

        self.collider = BoxCollider(self, center=Vec3(0, 0, 0), size=Vec3(1, 2, 1))
        self.body = Entity(parent=self, model="cube", color=BODY_COLOR,
                           scale=(.6, 1.1, .4), y=-.2)
        self.head = Entity(parent=self, model="sphere", color=HEAD_COLOR,
                           scale=(.45, .4, .45), y=.55)
        # ojos: dejan ver hacia dónde mira
        for ex in (-.1, .1):
            Entity(parent=self.head, model="cube", color=EYE_COLOR, unlit=True,
                   scale=(.18, .12, .1), position=(ex, .1, .45))
        self.bar_bg = Entity(parent=self, model="quad", color=color.rgb32(35, 35, 35),
                             scale=(.9, .08), y=1.2, billboard=True, unlit=True)
        self.bar = Entity(parent=self.bar_bg, model="quad", color=color.rgb32(90, 200, 90),
                          origin_x=-.5, x=-.5, z=-.01, unlit=True)
        # aparición: crece desde el suelo
        self.scale = .01
        self.animate_scale(Vec3(stats.size), duration=.3, curve=curve.out_back)

    # --- IA: perseguir y atacar ---
    def update(self):
        if not self.alive:
            return
        to_player = self.player.position - self.position
        to_player.y = 0
        distance = to_player.length()
        if distance > self.stats.detection_range:
            return

        self.look_at_2d(self.player.position, "y")
        if distance > ATTACK_RANGE:
            self._chase(to_player.normalized())
        else:
            self._try_melee()

    def _chase(self, direction):
        # rodea obstáculos probando desvíos crecientes a izquierda/derecha
        for angle in AVOID_ANGLES:
            candidate = _rotated_y(direction, angle)
            blocked = raycast(self.world_position, candidate,
                              distance=self.stats.size + .5,
                              ignore=(self, self.player)).hit
            if not blocked:
                self.position += candidate * self.stats.speed * time.dt
                return

    def _try_melee(self):
        now = time.time()
        if now < self._next_attack_time:
            return
        self._next_attack_time = now + 1 / self.stats.attack_speed
        # embestida corta hacia adelante
        self.body.animate_position(Vec3(0, -.1, .25), duration=.08, curve=curve.out_expo)
        self.body.animate_position(Vec3(0, -.2, 0), duration=.2, delay=.1)
        self.on_attack_player(self.stats.melee_damage)

    # --- Daño y muerte ---
    def take_damage(self, amount, damage_type="pierce", armor_pen=0.0):
        # la fórmula completa (resistencias y armadura) llega en su propio ticket
        if not self.alive:
            return
        self.hp = max(0, self.hp - amount)
        self.bar.scale_x = self.hp / self.stats.hp
        self.body.blink(color.white, duration=.12)
        if self.hp <= 0:
            self.die()

    def die(self):
        self.alive = False
        self.collider = None
        self.animate_scale(Vec3(.01, .01, .01), duration=.25, curve=curve.in_back)
        self.on_death(self)
