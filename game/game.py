from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()

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

app.run()
