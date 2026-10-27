# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Nemesis Protocol: a first-person wave-survival arena built with the Ursina engine, where an
"AI Director" (a LangGraph workflow calling Claude through `langchain-anthropic`, with a
deterministic rules fallback) adapts enemy
stats between waves to counter the player's dominant weapon. The project is a portfolio/demo piece. The game and the director share Pydantic contracts
in `shared/`. Code and comments are English; test names are Spanish.

Everything the player sees or the console prints goes through `shared/i18n.py`: `t(key, **values)`
and `weapon_name(id)`, driven by `LANGUAGE` (`es` default, `en`). Add new strings to BOTH the
`es` and `en` tables (a test checks the key sets match); never hardcode display text. Weapons,
telemetry keys, `WEAPON_PROFILES` and `COUNTERS` use language-neutral ids (`sword`, `pistol`,
`hammer`, `shotgun`, `bow`), and the graph's internal profile labels are English. Only display
text, rule-based adaptation names/reasons, and the language Claude is asked to write in change
with `LANGUAGE`. `tests/conftest.py` pins `LANGUAGE=es` so a developer's `.env` can't flip
assertions; use `monkeypatch.setenv("LANGUAGE", "en")` to test English.

## Commands

Python 3.12, managed with `uv` (`uv.lock` is committed; `.python-version` pins 3.12).

```
uv sync                                  # install deps (incl. dev group: pytest)
uv run pytest                            # run all tests (pythonpath="." and testpaths=["tests"] set in pyproject)
uv run pytest tests/test_damage.py       # one file
uv run pytest -k anti_pistola            # by name
uv run main.py                           # launch the game (opens an Ursina window; not headless)
```

`pyproject.toml` lists a uv workspace member `PracticeUrsinaEngine` that does not exist in this
repo; ignore it. `chromadb`, `fastapi` and `uvicorn` are declared but unused.

Config comes from `.env` (loaded by `shared/env.py`, never overriding real env vars; see
`.env.example`): `LANGUAGE` picks the display language, `ANTHROPIC_API_KEY`
enables Claude, `NEMESIS_DIRECTOR=rules` forces the local rules, `NEMESIS_DIRECTOR_MODEL` picks
the model, and the `LANGSMITH_*` vars trace each graph run in LangSmith. Decisions are logged
to `telemetry/director_log.jsonl` (gitignored).

To exercise gameplay without a human, exec `game/game.py` with `app.run()` stripped and pump
frames with `direct.task.TaskManagerGlobal.taskMgr.step()`; then drive `wave_manager`, `tracker`
and enemies from the resulting globals. Flush stdout before `os._exit`, and set
`PYTHONIOENCODING=utf-8` on Windows since HUD strings contain accents.

## Architecture

Two sides with one contract between them:

- `shared/models.py` is the contract imported by both the game and the director. It is pure
  Pydantic, no Ursina. Everything in it is frozen.
- `director/` is pure Python (tested). `Director.decide()` invokes the LangGraph graph in
  `director/graph.py`: `analyze` → `propose` (Claude) → `review` → back to `propose` with the
  review's issues (up to `MAX_ATTEMPTS`) or `finalize`; any LLM error routes to `fallback`
  (rules). An auth error rebuilds the graph without an LLM for the rest of the session.
  `decide_async()` runs it on a worker thread and returns a Future.
- `director/llm.py` owns the prompt, the `DirectorDecision` structured-output schema and
  `build_llm()`. Use `with_structured_output(..., method="json_schema")`: the default
  `function_calling` forces `tool_choice`, which current Opus models reject with a 400. Don't
  pass `temperature` either. `review` exists because the model does misread stat scales (it
  proposed `armor +5` on a 0-0.5 stat in a live call).
- `Director(llm=...)` and `build_director_graph(llm)` accept any object with
  `.invoke(messages) -> DirectorDecision`; `tests/test_director_graph.py` uses a scripted fake
  so every graph path is tested offline. Don't make tests call the real API.
- `game/telemetry.py` (`WaveTracker`) and `game/hud.py` text helpers have no Ursina state worth
  mocking; `WaveTracker` is tested. The rest of `game/` is Ursina code and not unit-tested; the modules import `ursina` and some
  (`weapons.py`) must be imported only after `Ursina()` is constructed, which is why
  `game/game.py` imports `waves`/`weapons` after creating `app`. `game.py` also appends the repo
  root to `sys.path` so `shared` resolves; `waves.py`/`enemy.py` import `from shared.models`
  while `game.py` imports `waves`/`weapons`/`enemy` as top-level modules (run from `game/`).

### The three rules the design hinges on

1. **Replace, never accumulate.** `BASE_STATS` is the single immutable base. An adaptation for a
   wave is always `apply_adaptation(BASE_STATS, adaptation)`, never applied on top of the previous
   wave's stats. Tests in `tests/test_adaptation.py` enforce this.
2. **Clamp in the game.** `STAT_LIMITS` in `shared/models.py` is the last line of defense against
   bad LLM output; `clamp_stats` runs on every `apply_adaptation`, and integer stats are rounded.
   `Adaptation` validators reject unknown stat names up front.
3. **Enemies are driven 100% by `EnemyStats`.** `game/enemy.py` reads speed, size, hp,
   detection_range, melee_damage, attack_speed, armor and resistances from its stats object and
   nothing else. To change enemy behavior, change the stats; new tunables belong as fields in
   `EnemyStats` with an entry in `STAT_LIMITS`.

### Damage model

`compute_damage(weapon_damage, damage_type, weapon_armor_pen, stats)`:
`weapon_damage × (1 − resist_<type>) × (1 − max(0, armor − weapon_armor_pen))`.
Damage types are `slash` (Sword), `blunt` (Hammer), `pierce` (Pistol, Shotgun, Bow). Weapon
numbers live in `game/weapons.py` class constructors and are duplicated as literals in
`tests/test_damage.py`; keep them in sync if you retune a weapon.

### Wave loop and telemetry

`game/waves.py: WaveManager` spawns `enemies_for_wave(wave)` enemies (3 on wave 1, +1 per wave,
cap 12) using `self.stats`, tracks deaths, and fires two hooks: `on_wave_start(wave, stats)` and
`on_wave_end(wave, summary)`. `set_stats_for_next_wave(stats)` is the entry point the director
uses. Derived metrics (accuracy, shares,
`dominant_weapon`) are `computed_field`s so the game and director can never disagree on them.

### Director loop in `game/game.py`

Weapons call `tracker.record_attack` through their `on_attack` hook, and `damage_player` records
damage taken. `on_wave_end` builds the telemetry and starts `director.decide_async`. The wave break
passes `director_ready` as `WaveManager(can_start_next_wave=...)`, which holds the break until the
Future resolves, then calls `set_stats_for_next_wave` and updates the `EvolutionPanel`. On game
over `restart_round` drops the pending Future and resets the director history.

Enemy looks are derived from stats in `game/enemy.py` (tint by strongest resistance, plates for
armor, a cannon when `ranged_enabled`, stripes when fast). Ranged enemies fire `Projectile`s.

### Ursina gotchas

- Never store anything in an entity attribute named `ignore`: a truthy `ignore` makes Ursina skip
  that entity's `update()` and input.
- Set `Text.wordwrap` after the text exists, not in the constructor.
- The default font has no glyph for characters like "→"; use ASCII in HUD text.

### Weapons

`game/weapons.py: Weapon(Entity)` does fire-rate gating in `try_attack`, raycasts from the camera
in `_fire_ray`, and calls `hit.entity.take_damage(damage, damage_type, armor_pen)` on anything
exposing that method. Subclasses override `perform_attack` (Shotgun fires 6 pellets, Bow adds a
visual arrow) and `animate_attack`. Keys 1-5 select Sword, Pistol, Hammer, Shotgun, Bow.
