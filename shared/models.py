"""Modelos Pydantic compartidos entre el juego y el AI Director.

EnemyStats: TODO lo que el AI Director podrá modificar está aquí.
Valores base según la tabla 👾 del plan (Notion).
BASE_STATS, apply_adaptation() y los clamps llegan en su propio ticket.
"""
from pydantic import BaseModel


class EnemyStats(BaseModel):
    hp: int = 100
    speed: float = 4.0            # m/s
    size: float = 1.0             # escala del modelo (afecta hitbox)
    armor: float = 0.0            # 0-1: reduce % del daño recibido
    armor_pen: float = 0.0        # 0-1: ignora parte de la defensa del jugador
    melee_damage: int = 10
    attack_speed: float = 1.0     # ataques por segundo
    ranged_enabled: bool = False
    ranged_damage: int = 8
    ranged_range: float = 12.0
    resist_slash: float = 0.0     # 0-1: resistencia al daño cortante
    resist_pierce: float = 0.0    # 0-1: resistencia al daño perforante
    resist_blunt: float = 0.0     # 0-1: resistencia al daño contundente
    detection_range: float = 20.0
