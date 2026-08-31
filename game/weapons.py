"""Sistema de armas del jugador.

Valores tomados de la tabla ⚔️ del plan (Notion):
    Espada  — slash,  melee 2m,   cadencia alta,  daño medio, penetración baja
    Pistola — pierce, media 15m,  cadencia media, daño medio, penetración media
"""
from pathlib import Path

from ursina import *

import time

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

STEEL = color.rgb32(200, 205, 215)
DARK_STEEL = color.rgb32(60, 62, 70)
GUNMETAL = color.rgb32(45, 45, 52)
WOOD = color.rgb32(110, 75, 45)
LEATHER = color.rgb32(90, 60, 40)


def load_sound(name):
    return Audio(SOUNDS_DIR / name, autoplay=False)


class Weapon(Entity):
    """Clase base: stats + cadencia + ataque por raycast desde la cámara."""

    def __init__(self, name, damage, damage_type, range, fire_rate, armor_pen,
                 attack_sound, rest_position, rest_rotation, **kwargs):
        super().__init__(parent=camera, enabled=False, **kwargs)
        self.weapon_name = name
        self.damage = damage
        self.damage_type = damage_type   # slash | pierce | blunt
        self.range = range               # metros
        self.fire_rate = fire_rate       # ataques por segundo
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
        # animación de desenfundar: sube desde abajo
        self.position = self.rest_position + Vec3(0, -.4, 0)
        self.rotation = self.rest_rotation
        self.animate_position(self.rest_position, duration=.18, curve=curve.out_quad)

    def unequip(self):
        self.enabled = False

    def try_attack(self, shooter):
        """Ataca si la cadencia lo permite. Devuelve el RaycastHitInfo o None."""
        now = time.time()
        if now < self._next_attack_time:
            return None
        self._next_attack_time = now + 1 / self.fire_rate

        self.attack_sound.play()
        self.animate_attack()

        hit = raycast(camera.world_position, camera.forward,
                      distance=self.range, ignore=(shooter,))
        if hit.hit and hasattr(hit.entity, "take_damage"):
            hit.entity.take_damage(self.damage, self.damage_type, self.armor_pen)
            self.hit_sound.play()
        return hit

    def animate_attack(self):
        pass


class Sword(Weapon):
    def __init__(self):
        super().__init__(name="Espada", damage=25, damage_type="slash", range=2,
                         fire_rate=2.5, armor_pen=.10,
                         attack_sound="sword_swing.wav",
                         rest_position=(.55, -.5, 1.1),
                         rest_rotation=(-12, 6, -10))
        # pomo, mango, guarda y hoja
        Entity(parent=self, model="sphere", color=DARK_STEEL, scale=.07, y=-.3)
        Entity(parent=self, model="cube", color=LEATHER, scale=(.045, .22, .045), y=-.18)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.22, .035, .06), y=-.06)
        Entity(parent=self, model="cube", color=STEEL, scale=(.05, .8, .015), y=.35)
        Entity(parent=self, model="cube", color=STEEL.tint(.2), scale=(.018, .8, .017), y=.35)  # filo
        Entity(parent=self, model="cube", color=STEEL, scale=(.05, .07, .015), y=.77,
               rotation_z=45)  # punta

    def animate_attack(self):
        # tajo diagonal y vuelta a la guardia
        self.animate_rotation(Vec3(65, -30, 35), duration=.09, curve=curve.in_out_sine)
        self.animate_rotation(self.rest_rotation, duration=.22, delay=.11, curve=curve.out_quad)


class Pistol(Weapon):
    def __init__(self):
        super().__init__(name="Pistola", damage=25, damage_type="pierce", range=15,
                         fire_rate=1.5, armor_pen=.25,
                         attack_sound="pistol_shot.wav",
                         rest_position=(.45, -.38, .85),
                         rest_rotation=(0, 0, 0))
        # corredera, cañón, mira, empuñadura y guardamonte
        Entity(parent=self, model="cube", color=GUNMETAL, scale=(.085, .085, .4))
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.05, .05, .08), z=.24)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.02, .03, .02), y=.055, z=.16)
        Entity(parent=self, model="cube", color=GUNMETAL.tint(-.1), scale=(.075, .22, .11),
               y=-.13, z=-.13, rotation_x=-18)
        Entity(parent=self, model="cube", color=DARK_STEEL, scale=(.06, .015, .12), y=-.06, z=-.02)
        # fogonazo (se muestra un instante al disparar)
        self.flash = Entity(parent=self, model="quad", color=color.rgb32(255, 220, 120),
                            scale=.22, z=.33, rotation_z=45, enabled=False,
                            unlit=True, billboard=True)

    def animate_attack(self):
        # retroceso
        self.animate_position(self.rest_position + Vec3(0, .03, -.12),
                              duration=.05, curve=curve.out_expo)
        self.animate_position(self.rest_position, duration=.16, delay=.06, curve=curve.out_quad)
        self.animate_rotation(self.rest_rotation + Vec3(-10, 0, 0), duration=.05)
        self.animate_rotation(self.rest_rotation, duration=.16, delay=.06)
        self.flash.enabled = True
        invoke(setattr, self.flash, "enabled", False, delay=.06)
