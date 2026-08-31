import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # para importar /shared

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

from shared.models import EnemyStats

app = Ursina()

from enemy import Enemy  # noqa: E402
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


# --- Vida del jugador ---
PLAYER_MAX_HP = 100
player.hp = PLAYER_MAX_HP

kill_sound = load_sound("kill.wav")
hurt_sound = load_sound("player_hurt.wav")

hp_bar_bg = Entity(parent=camera.ui, model="quad", color=color.rgb32(35, 35, 35),
                   scale=(.3, .03), position=window.bottom_left + Vec2(.19, .1))
hp_bar = Entity(parent=hp_bar_bg, model="quad", color=color.rgb32(90, 200, 90),
                origin_x=-.5, x=-.5, z=-.01)
hp_label = Text(text="HP", origin=(.5, 0), position=hp_bar_bg.position + Vec2(-.17, 0), scale=.9)
damage_overlay = Entity(parent=camera.ui, model="quad", scale=2,
                        color=color.rgba32(255, 40, 40, 0))
game_over_text = Text(text="GAME OVER", origin=(0, 0), scale=3,
                      color=color.rgb32(230, 60, 60), enabled=False)


def damage_player(amount):
    if player.hp <= 0:
        return
    player.hp = max(0, player.hp - amount)
    hp_bar.scale_x = player.hp / PLAYER_MAX_HP
    hurt_sound.play()
    damage_overlay.color = color.rgba32(255, 40, 40, 100)
    damage_overlay.animate_color(color.rgba32(255, 40, 40, 0), duration=.4)
    if player.hp <= 0:
        game_over()


def game_over():
    game_over_text.enabled = True
    invoke(restart_round, delay=2.5)


def restart_round():
    game_over_text.enabled = False
    player.hp = PLAYER_MAX_HP
    hp_bar.scale_x = 1
    player.position = Vec3(0, 2, 0)
    for e in enemies:
        e.respawn()


# --- Enemigos ---
def handle_enemy_death(enemy):
    kill_sound.play()
    invoke(enemy.respawn, delay=4)  # provisional: el sistema de oleadas lo reemplazará


# Tres builds distintas para demostrar que TODO sale de EnemyStats
enemies = [
    Enemy(player, x=0, z=12,
          on_attack_player=damage_player, on_death=handle_enemy_death),  # base
    Enemy(player, EnemyStats(hp=60, speed=6.0, size=.8, attack_speed=1.5), x=-20, z=-12,
          on_attack_player=damage_player, on_death=handle_enemy_death),  # explorador rápido
    Enemy(player, EnemyStats(hp=200, speed=2.5, size=1.4, melee_damage=20, attack_speed=.6),
          x=20, z=15,
          on_attack_player=damage_player, on_death=handle_enemy_death),  # tanque lento
]


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
