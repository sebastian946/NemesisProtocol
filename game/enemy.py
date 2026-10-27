"""Enemy class: an enemy driven 100% by its EnemyStats.

Changing the stats changes the behavior without touching any other code:
chasing (speed, detection_range), size/hitbox (size), melee (melee_damage,
attack_speed), ranged attacks (ranged_enabled, ranged_damage, ranged_range),
health (hp) and damage mitigation (armor, resist_*).

The look also comes from the stats, so the player can SEE each evolution:
body tint = strongest resistance, steel plates = armor, arm cannon = ranged.
"""
from math import cos, radians, sin

from ursina import *

import time

from shared.models import BASE_STATS, EnemyStats, compute_damage

BODY_COLOR = color.rgb32(150, 45, 45)
HEAD_COLOR = color.rgb32(170, 60, 60)
EYE_COLOR = color.rgb32(255, 220, 90)
PLATE_COLOR = color.rgb32(120, 125, 135)
CANNON_COLOR = color.rgb32(40, 40, 48)
PROJECTILE_COLOR = color.rgb32(255, 120, 40)

# Body tint for the dominant resistance (slash=green, pierce=blue, blunt=purple)
RESIST_TINTS = {
    "resist_slash": color.rgb32(60, 140, 70),
    "resist_pierce": color.rgb32(55, 90, 170),
    "resist_blunt": color.rgb32(120, 60, 150),
}

ATTACK_RANGE = 1.8      # meters at which the melee attack connects
AVOID_ANGLES = (0, 40, -40, 75, -75)  # detours used to walk around obstacles
PROJECTILE_SPEED = 16   # m/s, slow enough to be dodged
RANGED_COOLDOWN_FACTOR = 1.8   # shooting is slower than melee: 1.8 / attack_speed seconds
RANGED_KEEP_DISTANCE = .6      # ranged enemies stop at 60% of their range


def _rotated_y(direction, degrees):
    r = radians(degrees)
    return Vec3(direction.x * cos(r) - direction.z * sin(r), 0,
                direction.x * sin(r) + direction.z * cos(r))


def _body_color(stats: EnemyStats):
    name, value = max(((n, getattr(stats, n)) for n in RESIST_TINTS), key=lambda nv: nv[1])
    if value < .1:
        return BODY_COLOR
    return lerp(BODY_COLOR, RESIST_TINTS[name], min(1, value / .45))


class Projectile(Entity):
    """Enemy shot: flies straight, hurts the player on contact, stops at walls."""

    def __init__(self, start, target, damage, max_range, player, on_hit, ignore):
        super().__init__(model="sphere", color=PROJECTILE_COLOR, scale=.3,
                         position=start, unlit=True)
        self.direction = (target - start).normalized()
        self.damage = damage
        self.player = player
        self.on_hit = on_hit
        self.ignore_entities = ignore   # NOT `self.ignore`: Ursina skips update() on entities with ignore=True
        self.distance_left = max_range * 1.2

    def update(self):
        step = PROJECTILE_SPEED * time.dt
        blocked = raycast(self.world_position, self.direction, distance=step,
                          ignore=(self, self.player, *self.ignore_entities))
        self.position += self.direction * step
        self.distance_left -= step
        if distance(self.world_position, self.player.position + Vec3(0, 1, 0)) < .9:
            self.on_hit(self.damage)
            destroy(self)
        elif blocked.hit or self.distance_left <= 0:
            destroy(self)


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
        self._next_shot_time = time.time() + 1.5   # grace period after spawning

        self.collider = BoxCollider(self, center=Vec3(0, 0, 0), size=Vec3(1, 2, 1))
        self.body = Entity(parent=self, model="cube", color=_body_color(stats),
                           scale=(.6, 1.1, .4), y=-.2)
        self.head = Entity(parent=self, model="sphere", color=HEAD_COLOR,
                           scale=(.45, .4, .45), y=.55)
        # eyes: make it obvious where the enemy is looking
        for ex in (-.1, .1):
            Entity(parent=self.head, model="cube", color=EYE_COLOR, unlit=True,
                   scale=(.18, .12, .1), position=(ex, .1, .45))
        self._build_evolution_parts(stats)
        self.bar_bg = Entity(parent=self, model="quad", color=color.rgb32(35, 35, 35),
                             scale=(.9, .08), y=1.2, billboard=True, unlit=True)
        self.bar = Entity(parent=self.bar_bg, model="quad", color=color.rgb32(90, 200, 90),
                          origin_x=-.5, x=-.5, z=-.01, unlit=True)
        # spawn: grows up from the ground
        self.scale = .01
        self.animate_scale(Vec3(stats.size), duration=.3, curve=curve.out_back)

    def _build_evolution_parts(self, stats):
        if stats.armor >= .1:
            # chest plate and shoulder pads, bigger with more armor
            thickness = .04 + stats.armor * .12
            Entity(parent=self.body, model="cube", color=PLATE_COLOR,
                   scale=(1.1, .55, thickness / .4 + 1), y=.15)
            for sx in (-.6, .6):
                Entity(parent=self.body, model="cube", color=PLATE_COLOR.tint(-.1),
                       scale=(.45, .2, 1.3), position=(sx, .42, 0))
        if stats.ranged_enabled:
            self.cannon = Entity(parent=self, model="cube", color=CANNON_COLOR,
                                 scale=(.14, .14, .6), position=(.42, 0, .25))
            Entity(parent=self.cannon, model="cube", color=PROJECTILE_COLOR, unlit=True,
                   scale=(.7, .7, .1), z=.5)
        if stats.speed >= 5:
            # glowing stripes on fast enemies
            for sy in (.1, -.15):
                Entity(parent=self.body, model="cube", color=color.rgb32(255, 170, 40),
                       unlit=True, scale=(1.02, .08, 1.02), y=sy)

    # --- AI: chase, shoot and attack ---
    def update(self):
        if not self.alive:
            return
        to_player = self.player.position - self.position
        to_player.y = 0
        distance_to_player = to_player.length()
        if distance_to_player > self.stats.detection_range:
            return

        self.look_at_2d(self.player.position, "y")
        if distance_to_player <= ATTACK_RANGE:
            self._try_melee()
            return
        if (self.stats.ranged_enabled and distance_to_player <= self.stats.ranged_range
                and self._has_line_of_sight(distance_to_player)):
            self._try_shoot()
            if distance_to_player <= self.stats.ranged_range * RANGED_KEEP_DISTANCE:
                return   # close enough: hold position and keep shooting
        self._chase(to_player.normalized())

    def _chase(self, direction):
        # walks around obstacles by trying increasing detours left and right
        for angle in AVOID_ANGLES:
            candidate = _rotated_y(direction, angle)
            blocked = raycast(self.world_position, candidate,
                              distance=self.stats.size + .5,
                              ignore=(self, self.player)).hit
            if not blocked:
                self.position += candidate * self.stats.speed * time.dt
                return

    def _has_line_of_sight(self, distance_to_player):
        target = self.player.position + Vec3(0, 1, 0)
        hit = raycast(self.world_position, (target - self.world_position).normalized(),
                      distance=distance_to_player, ignore=(self, self.player))
        return not hit.hit or getattr(hit.entity, "alive", False)  # other enemies don't block

    def _try_melee(self):
        now = time.time()
        if now < self._next_attack_time:
            return
        self._next_attack_time = now + 1 / self.stats.attack_speed
        # short lunge forward
        self.body.animate_position(Vec3(0, -.1, .25), duration=.08, curve=curve.out_expo)
        self.body.animate_position(Vec3(0, -.2, 0), duration=.2, delay=.1)
        self.on_attack_player(self.stats.melee_damage)

    def _try_shoot(self):
        now = time.time()
        if now < self._next_shot_time:
            return
        self._next_shot_time = now + RANGED_COOLDOWN_FACTOR / self.stats.attack_speed
        start = self.cannon.world_position if hasattr(self, "cannon") else self.world_position
        Projectile(start, self.player.position + Vec3(0, 1, 0), self.stats.ranged_damage,
                   self.stats.ranged_range, self.player, self.on_attack_player, ignore=(self,))
        if hasattr(self, "cannon"):
            self.cannon.animate_position(Vec3(.42, 0, .1), duration=.05)
            self.cannon.animate_position(Vec3(.42, 0, .25), duration=.2, delay=.06)

    # --- Damage and death ---
    def take_damage(self, weapon_damage, damage_type="pierce", armor_pen=0.0):
        """Applies the plan's formula: per-type resistance + armor vs penetration."""
        if not self.alive:
            return 0
        damage = compute_damage(weapon_damage, damage_type, armor_pen, self.stats)
        self.hp = max(0, self.hp - damage)
        self.bar.scale_x = self.hp / self.stats.hp
        self.body.blink(color.white, duration=.12)
        self._show_damage_number(damage, weapon_damage)
        if self.hp <= 0:
            self.die()
        return damage

    def _show_damage_number(self, damage, weapon_damage):
        # floating number that rises and fades; yellow when the enemy mitigated part of the damage
        mitigated = damage < weapon_damage - .01
        label = Text(text=str(round(damage)), parent=scene, billboard=True, scale=14,
                     origin=(0, 0), position=self.world_position + Vec3(0, 1.4 * self.scale_y, 0),
                     color=color.rgb32(255, 200, 60) if mitigated else color.white)
        label.animate_position(label.position + Vec3(0, .8, 0), duration=.6, curve=curve.out_quad)
        destroy(label, delay=.6)

    def die(self):
        self.alive = False
        self.collider = None
        self.animate_scale(Vec3(.01, .01, .01), duration=.25, curve=curve.in_back)
        self.on_death(self)
