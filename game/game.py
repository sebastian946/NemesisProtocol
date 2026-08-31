from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()

from weapons import Pistol, Sword, load_sound  # noqa: E402 (necesita la app creada)

Sky()

# --- Arena ---
ARENA_SIZE = 60        # lado de la arena (unidades)
WALL_HEIGHT = 6
WALL_THICKNESS = 1

WALL_COLOR = color.rgb32(120, 110, 100)
FLOOR_COLOR = color.rgb32(90, 160, 90)
CRATE_COLOR = color.rgb32(160, 120, 70)
COLUMN_COLOR = color.rgb32(140, 140, 150)

ground = Entity(model="plane", scale=(ARENA_SIZE, 1, ARENA_SIZE), color=FLOOR_COLOR,
                texture="white_cube", texture_scale=(ARENA_SIZE, ARENA_SIZE), collider="box")


def make_wall(position, scale):
    return Entity(model="cube", position=position, scale=scale,
                  color=WALL_COLOR, texture="brick",
                  texture_scale=(scale[0] + scale[2], scale[1]),
                  collider="box")


# Paredes perimetrales (norte, sur, este, oeste)
half = ARENA_SIZE / 2
walls = [
    make_wall((0, WALL_HEIGHT / 2,  half), (ARENA_SIZE + WALL_THICKNESS, WALL_HEIGHT, WALL_THICKNESS)),
    make_wall((0, WALL_HEIGHT / 2, -half), (ARENA_SIZE + WALL_THICKNESS, WALL_HEIGHT, WALL_THICKNESS)),
    make_wall(( half, WALL_HEIGHT / 2, 0), (WALL_THICKNESS, WALL_HEIGHT, ARENA_SIZE + WALL_THICKNESS)),
    make_wall((-half, WALL_HEIGHT / 2, 0), (WALL_THICKNESS, WALL_HEIGHT, ARENA_SIZE + WALL_THICKNESS)),
]

# Pilares decorativos en las esquinas, un poco más altos que las paredes
for x in (-half, half):
    for z in (-half, half):
        Entity(model="cube", position=(x, (WALL_HEIGHT + 2) / 2, z),
               scale=(WALL_THICKNESS * 2.5, WALL_HEIGHT + 2, WALL_THICKNESS * 2.5),
               color=WALL_COLOR.tint(-.15), texture="brick",
               texture_scale=(2, WALL_HEIGHT + 2), collider="box")


def make_column(x, z, height=7, radius=1.2):
    return Entity(model="cube", position=(x, height / 2, z),
                  scale=(radius * 2, height, radius * 2),
                  color=COLUMN_COLOR, texture="brick",
                  texture_scale=(2, height), collider="box")


def make_crate(x, z, size=2.5):
    return Entity(model="cube", position=(x, size / 2, z),
                  scale=size, color=CRATE_COLOR, texture="white_cube",
                  collider="box")


# --- Obstáculos para cubrirse ---
# Cuatro columnas altas formando un anillo interior
obstacles = [
    make_column(-15, -15),
    make_column( 15, -15),
    make_column(-15,  15),
    make_column( 15,  15),
]

# Cajas de distintos tamaños repartidas por la arena
obstacles += [
    make_crate(0, -20, size=3),
    make_crate(-22, 5, size=2.5),
    make_crate(22, 8, size=2.5),
    make_crate(5, 22, size=3),
    make_crate(-6, 0, size=2),
    make_crate(8, -5, size=2),
]

player = FirstPersonController(y=2, origin_y=-.5)


# --- Dianas de práctica (enemigos de prueba hasta el ticket de la clase Enemy) ---
kill_sound = load_sound("kill.wav")

DUMMY_COLOR = color.rgb32(190, 60, 60)


class TargetDummy(Entity):
    def __init__(self, x, z):
        super().__init__(position=(x, 1, z))
        self.collider = BoxCollider(self, center=Vec3(0, 0, 0), size=Vec3(1, 2, 1))
        self.max_hp = 100
        self.hp = self.max_hp

        self.body = Entity(parent=self, model="cube", color=DUMMY_COLOR,
                           scale=(.6, 1.1, .4), y=-.2)
        self.head = Entity(parent=self, model="sphere", color=DUMMY_COLOR.tint(.1),
                           scale=(.45, .4, .45), y=.55)
        self.bar_bg = Entity(parent=self, model="quad", color=color.rgb32(35, 35, 35),
                             scale=(.9, .08), y=1.2, billboard=True, unlit=True)
        self.bar = Entity(parent=self.bar_bg, model="quad", color=color.rgb32(90, 200, 90),
                          origin_x=-.5, x=-.5, z=-.01, unlit=True)

    def take_damage(self, amount, damage_type, armor_pen):
        # la fórmula completa (resistencias y armadura) llega en su propio ticket
        if self.hp <= 0:
            return
        self.hp = max(0, self.hp - amount)
        self.bar.scale_x = self.hp / self.max_hp
        self.body.blink(color.white, duration=.12)
        if self.hp <= 0:
            self.die()

    def die(self):
        kill_sound.play()
        self.collider = None
        self.animate_scale(Vec3(.01, .01, .01), duration=.25, curve=curve.in_back)
        invoke(self.respawn, delay=3)

    def respawn(self):
        self.hp = self.max_hp
        self.bar.scale_x = 1
        self.scale = Vec3(.01, .01, .01)
        self.animate_scale(Vec3(1, 1, 1), duration=.25, curve=curve.out_back)
        self.collider = BoxCollider(self, center=Vec3(0, 0, 0), size=Vec3(1, 2, 1))


dummies = [TargetDummy(0, 10), TargetDummy(-10, -6), TargetDummy(14, 3)]


# --- Armas: espada (1) y pistola (2) ---
weapons = {"1": Sword(), "2": Pistol()}
current_weapon = weapons["2"]
current_weapon.equip()

weapon_label = Text(origin=(.5, -.5), position=window.bottom_right + Vec2(-.03, .03), scale=1.2)
hint_label = Text(text="Click izquierdo: atacar | Teclas 1-2: cambiar de arma",
                  origin=(-.5, -.5), position=window.bottom_left + Vec2(.03, .03),
                  scale=.8, color=color.rgb32(220, 220, 220))


def update_weapon_label():
    parts = []
    for key, weapon in weapons.items():
        name = f"[{key}] {weapon.weapon_name}"
        parts.append(f"<yellow>{name}<default>" if weapon is current_weapon else name)
    weapon_label.text = "   ".join(parts)


update_weapon_label()


def input(key):
    global current_weapon
    if key in weapons and weapons[key] is not current_weapon:
        current_weapon.unequip()
        current_weapon = weapons[key]
        current_weapon.equip()
        update_weapon_label()


def update():
    # mantener presionado dispara/golpea respetando la cadencia del arma
    if held_keys["left mouse"]:
        current_weapon.try_attack(player)


app.run()
