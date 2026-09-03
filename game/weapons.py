"""Player weapon system.

Values taken from the ⚔️ table in the plan (Notion):
    Sword   — slash,  melee 2m,    high fire rate,   medium damage,    low pen
    Hammer  — blunt,  melee 2.5m,  low fire rate,    high damage,      HIGH pen
    Pistol  — pierce, medium 15m,  medium fire rate, medium damage,    medium pen
    Shotgun — pierce, short 6m,    low fire rate,    very high damage, low pen
    Bow     — pierce, long 30m,    low fire rate,    high damage,      HIGH pen
"""
from pathlib import Path
from random import uniform

from ursina import *

import time

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

STEEL = color.rgb32(200, 205, 215)
DARK_STEEL = color.rgb32(60, 62, 70)
GUNMETAL = color.rgb32(45, 45, 52)
WOOD = color.rgb32(110, 75, 45)
DARK_WOOD = color.rgb32(80, 52, 30)
LEATHER = color.rgb32(90, 60, 40)
FLASH = color.rgb32(255, 220, 120)


def load_sound(name):
    return Audio(SOUNDS_DIR / name, autoplay=False)


class Weapon(Entity):
    """Base class: stats + fire rate + raycast attack from the camera."""

    def __init__(self, name, damage, damage_type, range, fire_rate, armor_pen,
                 attack_sound, rest_position, rest_rotation, **kwargs):
        super().__init__(parent=camera, enabled=False, **kwargs)
        self.weapon_name = name
        self.damage = damage
        self.damage_type = damage_type   # slash | pierce | blunt
        self.range = range               # meters
        self.fire_rate = fire_rate       # attacks per second
        self.armor_pen = armor_pen       # 0-1

        self.rest_position = Vec3(rest_position)
        self.rest_rotation = Vec3(rest_rotation)
        self.position = self.rest_position
        self.rotation = self.rest_rotation

        self.attack_sound = load_sound(attack_sound)
        self.hit_sound = load_sound("hit.wav")
        self._next_attack_time = 0.0

    def equip(self):
        self.enabled = True
        # draw animation: rises from below
        self.position = self.rest_position + Vec3(0, -.4, 0)
        self.rotation = self.rest_rotation
        self.animate_position(self.rest_position, duration=.18, curve=curve.out_quad)

    def unequip(self):
        self.enabled = False

    def try_attack(self, shooter):
        """Attacks if the fire rate allows it. Returns the list of RaycastHitInfo."""
        now = time.time()
        if now < self._next_attack_time:
            return []
        self._next_attack_time = now + 1 / self.fire_rate

        self.attack_sound.play()
        self.animate_attack()
        hits = self.perform_attack(shooter)
        if any(h.hit and hasattr(h.entity, "take_damage") for h in hits):
            self.hit_sound.play()
        return hits

    def perform_attack(self, shooter):
        """A single forward ray by default. Subclasses may override."""
        return [self._fire_ray(camera.forward, self.damage, shooter)]

    def _fire_ray(self, direction, damage, shooter):
        hit = raycast(camera.world_position, direction,
                      distance=self.range, ignore=(shooter,))
        if hit.hit and hasattr(hit.entity, "take_damage"):
            hit.entity.take_damage(damage, self.damage_type, self.armor_pen)
        return hit

    def animate_attack(self):
        pass


# ----------------------------------------------------------------------------
# Melee
# ----------------------------------------------------------------------------

class Sword(Weapon):
    def __init__(self):
        super().__init__(name="Espada", damage=25, damage_type="slash", range=2,
                         fire_rate=2.5, armor_pen=.10,
                         attack_sound="sword_swing.wav",
                         rest_position=(.55, -.5, 1.1),
                         rest_rotation=(-12, 6, -10))
        # pommel, grip, guard and blade
        Entity(parent=self, model="sphere", color=DARK_STEEL, scale=.07, y=-.3)
        Entity(parent=self, model="cube", color=LEATHER, scale=(.045, .22, .045), y=-.18)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.22, .035, .06), y=-.06)
        Entity(parent=self, model="cube", color=STEEL, scale=(.05, .8, .015), y=.35)
        Entity(parent=self, model="cube", color=STEEL.tint(.2), scale=(.018, .8, .017), y=.35)  # edge
        Entity(parent=self, model="cube", color=STEEL, scale=(.05, .07, .015), y=.77,
               rotation_z=45)  # tip

    def animate_attack(self):
        # diagonal slash and back to guard
        self.animate_rotation(Vec3(65, -30, 35), duration=.09, curve=curve.in_out_sine)
        self.animate_rotation(self.rest_rotation, duration=.22, delay=.11, curve=curve.out_quad)


class Hammer(Weapon):
    def __init__(self):
        super().__init__(name="Martillo", damage=45, damage_type="blunt", range=2.5,
                         fire_rate=.8, armor_pen=.40,
                         attack_sound="hammer_swing.wav",
                         rest_position=(.6, -.6, 1.15),
                         rest_rotation=(-25, 12, -14))
        # long handle with leather grip, steel head with bands
        Entity(parent=self, model="cube", color=WOOD, scale=(.055, .95, .055), y=.05)
        Entity(parent=self, model="cube", color=LEATHER, scale=(.062, .28, .062), y=-.3)
        Entity(parent=self, model="sphere", color=DARK_STEEL, scale=.075, y=-.45)
        Entity(parent=self, model="cube", color=STEEL, scale=(.16, .15, .34), y=.52)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.17, .16, .04), y=.52, z=.12)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.17, .16, .04), y=.52, z=-.12)
        Entity(parent=self, model="cube", color=STEEL.tint(.15), scale=(.13, .12, .03),
               y=.52, z=.185)  # striking face

    def animate_attack(self):
        # heavy overhead smash: winds up slightly, then slams down
        self.animate_rotation(self.rest_rotation + Vec3(-30, 0, 5), duration=.1, curve=curve.out_quad)
        self.animate_rotation(Vec3(85, -5, 15), duration=.13, delay=.1, curve=curve.in_quad)
        self.animate_rotation(self.rest_rotation, duration=.45, delay=.3, curve=curve.out_quad)


# ----------------------------------------------------------------------------
# Ranged
# ----------------------------------------------------------------------------

class Pistol(Weapon):
    def __init__(self):
        super().__init__(name="Pistola", damage=25, damage_type="pierce", range=15,
                         fire_rate=1.5, armor_pen=.25,
                         attack_sound="pistol_shot.wav",
                         rest_position=(.45, -.38, .85),
                         rest_rotation=(0, 0, 0))
        # slide, barrel, sight, grip and trigger guard
        Entity(parent=self, model="cube", color=GUNMETAL, scale=(.085, .085, .4))
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.05, .05, .08), z=.24)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.02, .03, .02), y=.055, z=.16)
        Entity(parent=self, model="cube", color=GUNMETAL.tint(-.1), scale=(.075, .22, .11),
               y=-.13, z=-.13, rotation_x=-18)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.06, .015, .12), y=-.06, z=-.02)
        # muzzle flash (shown for an instant when firing)
        self.flash = Entity(parent=self, model="quad", color=FLASH, scale=.22, z=.33,
                            rotation_z=45, enabled=False, unlit=True, billboard=True)

    def animate_attack(self):
        # recoil
        self.animate_position(self.rest_position + Vec3(0, .03, -.12),
                              duration=.05, curve=curve.out_expo)
        self.animate_position(self.rest_position, duration=.16, delay=.06, curve=curve.out_quad)
        self.animate_rotation(self.rest_rotation + Vec3(-10, 0, 0), duration=.05)
        self.animate_rotation(self.rest_rotation, duration=.16, delay=.06)
        self.flash.enabled = True
        invoke(setattr, self.flash, "enabled", False, delay=.06)


class Shotgun(Weapon):
    """Fires PELLETS pellets in a cone. `damage` is per pellet: at point-blank
    they all connect (very high damage); at medium range only some do."""
    PELLETS = 6
    SPREAD = .07   # ~4 degrees of spread

    def __init__(self):
        super().__init__(name="Escopeta", damage=12, damage_type="pierce", range=6,
                         fire_rate=.7, armor_pen=.10,
                         attack_sound="shotgun_blast.wav",
                         rest_position=(.42, -.42, .9),
                         rest_rotation=(0, 0, 0))
        # wooden stock, receiver, double barrel and pump
        Entity(parent=self, model="cube", color=DARK_WOOD, scale=(.07, .13, .32),
               y=-.05, z=-.38, rotation_x=10)
        Entity(parent=self, model="cube", color=GUNMETAL, scale=(.095, .11, .3), z=-.08)
        for bx in (-.026, .026):
            Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.045, .045, .6), x=bx, z=.33)
        Entity(parent=self, model="cube", color=WOOD, scale=(.085, .07, .2), y=-.07, z=.28)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.02, .035, .02), y=.07, z=.55)  # sight
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.06, .015, .12), y=-.08, z=-.12)
        self.flash = Entity(parent=self, model="quad", color=FLASH, scale=.38, z=.68,
                            rotation_z=45, enabled=False, unlit=True, billboard=True)

    def perform_attack(self, shooter):
        hits = []
        for _ in range(self.PELLETS):
            direction = (camera.forward
                         + camera.right * uniform(-self.SPREAD, self.SPREAD)
                         + camera.up * uniform(-self.SPREAD, self.SPREAD)).normalized()
            hits.append(self._fire_ray(direction, self.damage, shooter))
        return hits

    def animate_attack(self):
        # strong recoil
        self.animate_position(self.rest_position + Vec3(0, .05, -.22),
                              duration=.06, curve=curve.out_expo)
        self.animate_position(self.rest_position, duration=.35, delay=.08, curve=curve.out_quad)
        self.animate_rotation(self.rest_rotation + Vec3(-16, 0, 0), duration=.06)
        self.animate_rotation(self.rest_rotation, duration=.35, delay=.08)
        self.flash.enabled = True
        invoke(setattr, self.flash, "enabled", False, delay=.08)


class Bow(Weapon):
    """Hitscan at 30m (the hit is resolved instantly) with a visual arrow
    that flies to the impact point."""
    ARROW_SPEED = 70   # m/s, only for the visual projectile

    def __init__(self):
        super().__init__(name="Arco", damage=50, damage_type="pierce", range=30,
                         fire_rate=.6, armor_pen=.40,
                         attack_sound="bow_shot.wav",
                         rest_position=(.32, -.38, .95),
                         rest_rotation=(0, -12, -8))
        # grip + two-segment limbs (fake the curve) + string
        Entity(parent=self, model="cube", color=LEATHER, scale=(.05, .22, .065))
        for sign in (1, -1):
            Entity(parent=self, model="cube", color=WOOD, scale=(.035, .34, .05),
                   y=sign * .26, rotation_x=-sign * 14)
            Entity(parent=self, model="cube", color=DARK_WOOD, scale=(.028, .3, .04),
                   y=sign * .56, z=.06, rotation_x=-sign * 32)
        Entity(parent=self, model="cube", color=color.rgb32(225, 225, 210), unlit=True,
               scale=(.006, 1.3, .006), z=-.03)
        # nocked arrow: shaft, head and fletching
        self.arrow = Entity(parent=self, z=.1)
        Entity(parent=self.arrow, model="cube", color=WOOD, scale=(.014, .014, .75))
        Entity(parent=self.arrow, model="cube", color=STEEL, scale=(.03, .03, .07), z=.4, rotation_z=45)
        Entity(parent=self.arrow, model="cube", color=color.rgb32(200, 50, 50), scale=(.045, .012, .08), z=-.3)
        Entity(parent=self.arrow, model="cube", color=color.rgb32(200, 50, 50), scale=(.012, .045, .08), z=-.3)

    def perform_attack(self, shooter):
        hit = self._fire_ray(camera.forward, self.damage, shooter)
        end = hit.world_point if hit.hit else camera.world_position + camera.forward * self.range
        self._launch_arrow(end)
        return [hit]

    def _launch_arrow(self, end):
        start = self.arrow.world_position
        arrow = Entity(model="cube", color=WOOD, scale=(.03, .03, .75), position=start)
        Entity(parent=arrow, model="cube", color=STEEL, scale=(2, 2, .09), z=.5)
        arrow.look_at(end)
        duration = max(.04, distance(start, end) / self.ARROW_SPEED)
        arrow.animate_position(end, duration=duration, curve=curve.linear)
        destroy(arrow, delay=duration)

    def animate_attack(self):
        # the arrow disappears while it flies and a new one is nocked on reload
        self.arrow.enabled = False
        invoke(setattr, self.arrow, "enabled", True, delay=.9)
        self.animate_rotation(self.rest_rotation + Vec3(-6, 0, 0), duration=.05)
        self.animate_rotation(self.rest_rotation, duration=.25, delay=.06, curve=curve.out_quad)
