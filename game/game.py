import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # so /shared is importable

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()

from director import Director  # noqa: E402
from shared.i18n import describe_language, t  # noqa: E402
from hud import EvolutionPanel, wave_summary_text  # noqa: E402
from telemetry import WaveTracker  # noqa: E402
from waves import WaveManager, enemies_for_wave  # noqa: E402
from weapons import Bow, Hammer, Pistol, Shotgun, Sword, load_sound  # noqa: E402 (needs the app created)

Sky()

# --- Arena ---
ARENA_SIZE = 60        # arena side length (units)
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


# Perimeter walls (north, south, east, west)
half = ARENA_SIZE / 2
walls = [
    make_wall((0, WALL_HEIGHT / 2,  half), (ARENA_SIZE + WALL_THICKNESS, WALL_HEIGHT, WALL_THICKNESS)),
    make_wall((0, WALL_HEIGHT / 2, -half), (ARENA_SIZE + WALL_THICKNESS, WALL_HEIGHT, WALL_THICKNESS)),
    make_wall(( half, WALL_HEIGHT / 2, 0), (WALL_THICKNESS, WALL_HEIGHT, ARENA_SIZE + WALL_THICKNESS)),
    make_wall((-half, WALL_HEIGHT / 2, 0), (WALL_THICKNESS, WALL_HEIGHT, ARENA_SIZE + WALL_THICKNESS)),
]

# Decorative corner pillars, slightly taller than the walls
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


# --- Cover obstacles ---
# Four tall columns forming an inner ring
obstacles = [
    make_column(-15, -15),
    make_column( 15, -15),
    make_column(-15,  15),
    make_column( 15,  15),
]

# Crates of different sizes scattered around the arena
obstacles += [
    make_crate(0, -20, size=3),
    make_crate(-22, 5, size=2.5),
    make_crate(22, 8, size=2.5),
    make_crate(5, 22, size=3),
    make_crate(-6, 0, size=2),
    make_crate(8, -5, size=2),
]

player = FirstPersonController(y=2, origin_y=-.5)


# --- Player health ---
PLAYER_MAX_HP = 100
player.hp = PLAYER_MAX_HP

kill_sound = load_sound("kill.wav")
hurt_sound = load_sound("player_hurt.wav")

hp_bar_bg = Entity(parent=camera.ui, model="quad", color=color.rgb32(35, 35, 35),
                   scale=(.3, .03), position=window.bottom_left + Vec2(.19, .1))
hp_bar = Entity(parent=hp_bar_bg, model="quad", color=color.rgb32(90, 200, 90),
                origin_x=-.5, x=-.5, z=-.01)
hp_label = Text(text=t("hud.hp"), origin=(.5, 0), position=hp_bar_bg.position + Vec2(-.17, 0), scale=.9)
damage_overlay = Entity(parent=camera.ui, model="quad", scale=2,
                        color=color.rgba32(255, 40, 40, 0))
game_over_text = Text(text=t("hud.game_over"), origin=(0, 0), scale=3,
                      color=color.rgb32(230, 60, 60), enabled=False)


def damage_player(amount):
    if player.hp <= 0:
        return
    tracker.record_damage(min(amount, player.hp))
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
    global pending_decision
    pending_decision = None          # a late answer from the previous run is ignored
    director.reset()
    tracker.reset()
    evolution_panel.show_base()
    game_over_text.enabled = False
    player.hp = PLAYER_MAX_HP
    hp_bar.scale_x = 1
    player.position = Vec3(0, 2, 0)
    wave_manager.restart()


# --- AI Director: telemetry → evolution ---
director = Director()
tracker = WaveTracker()
evolution_panel = EvolutionPanel(director.mode)
pending_decision = None   # Future with the director's decision for the next wave
summary_label = Text(text="", origin=(0, 0), position=(0, .1), scale=1.1,
                     color=color.rgb32(230, 230, 230), enabled=False)
print(describe_language())
print(t("log.director_mode",
        mode=t("source.claude_graph" if director.mode == "claude" else "source.rules_local")))


def on_wave_start(wave, stats):
    tracker.reset()
    print(t("log.wave_start", wave=wave, count=enemies_for_wave(wave), stats=stats.model_dump()))


def on_wave_end(wave, summary):
    global pending_decision
    telemetry = tracker.build(wave=wave, duration_s=summary["duration_s"],
                              player_hp_remaining=player.hp)
    print(t("log.wave_cleared", wave=wave, telemetry=telemetry.model_dump_json()))
    summary_label.text = wave_summary_text(telemetry)
    summary_label.enabled = True
    invoke(setattr, summary_label, "enabled", False, delay=4)
    pending_decision = director.decide_async(telemetry)


def director_ready():
    """Called every frame once the break is over; applies the decision when it arrives."""
    global pending_decision
    if pending_decision is None:
        return True
    if not pending_decision.done():
        return False
    decision = pending_decision.result()
    pending_decision = None
    wave_manager.set_stats_for_next_wave(decision.stats)
    evolution_panel.show(decision)
    print(t("log.decision", source=t("source.claude" if decision.source == "claude" else "source.rules"),
            attempts=decision.attempts,
            issues=decision.issues, adaptation=decision.adaptation.model_dump())
          + (t("log.fallback", error=decision.error) if decision.error else ""))
    return True


wave_manager = WaveManager(player, arena_half=half, obstacles=obstacles,
                           on_attack_player=damage_player, kill_sound=kill_sound,
                           on_wave_start=on_wave_start, on_wave_end=on_wave_end,
                           can_start_next_wave=director_ready)
wave_manager.start()


# --- Weapons: keys 1-5 ---
weapons = {"1": Sword(), "2": Pistol(), "3": Hammer(), "4": Shotgun(), "5": Bow()}
for weapon in weapons.values():
    weapon.on_attack = tracker.record_attack
current_weapon = weapons["2"]
current_weapon.equip()

weapon_label = Text(origin=(.5, -.5), position=window.bottom_right + Vec2(-.03, .03), scale=1)
hint_label = Text(text=t("hud.hint"),
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
    # holding the button keeps attacking, limited by the weapon's fire rate
    if held_keys["left mouse"]:
        current_weapon.try_attack(player)


app.run()
