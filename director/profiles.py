"""What the director knows about each player weapon (mirrors game/weapons.py).

Keys are language-neutral weapon ids (the same ones the game records in the
telemetry); display names come from shared/i18n.py.
counter_stats: enemy stats that actually counter that weapon. The LangGraph
review step requires a specialist player's evolution to touch at least one.
"""

WEAPON_PROFILES: dict[str, dict] = {
    "sword": {"damage_type": "slash", "range_m": 2, "style": "fast melee",
              "counter_stats": ["resist_slash", "ranged_enabled", "ranged_range", "armor"]},
    "hammer": {"damage_type": "blunt", "range_m": 2.5, "style": "slow heavy melee, high armor penetration",
               "counter_stats": ["resist_blunt", "speed", "attack_speed", "ranged_enabled"]},
    "pistol": {"damage_type": "pierce", "range_m": 15, "style": "medium range",
               "counter_stats": ["resist_pierce", "armor", "speed", "size"]},
    "shotgun": {"damage_type": "pierce", "range_m": 6, "style": "short range burst damage",
                "counter_stats": ["resist_pierce", "ranged_enabled", "ranged_range"]},
    "bow": {"damage_type": "pierce", "range_m": 30, "style": "long range, high armor penetration",
            "counter_stats": ["resist_pierce", "speed", "size", "detection_range"]},
}
