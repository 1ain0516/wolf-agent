"""Growth memory system — per-player reflections persist across games."""

from __future__ import annotations

import json
import os
import time


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def save_memory(game_id: str, player_id: int, personality: str, role: str,
                content: str, memory_dir: str):
    """Save a reflection to per-game backup + global index."""
    os.makedirs(memory_dir, exist_ok=True)

    entry = {
        "memory_id": f"mem-{game_id}-{player_id:02d}",
        "player_id": player_id,
        "game_id": game_id,
        "type": "self_review",
        "content": content,
        "strength": 0.7,
        "personality": personality,
        "role": role,
        "created_at": _ts(),
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"

    # Per-game backup
    per_game_path = os.path.join(memory_dir, f"{game_id}.memories.jsonl")
    with open(per_game_path, "a", encoding="utf-8") as f:
        f.write(line)

    # Global index
    index_path = os.path.join(memory_dir, "memories.jsonl")
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(line)


def load_memories(player_id: int, memory_dir: str, limit: int = 3,
                  min_strength: float = 0.5, exclude_game_id: str = "") -> list[dict]:
    """Load the strongest memories for a player from the global index."""
    index_path = os.path.join(memory_dir, "memories.jsonl")
    if not os.path.exists(index_path):
        return []

    memories = []
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                mem = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (mem.get("player_id") == player_id
                    and mem.get("game_id") != exclude_game_id
                    and mem.get("strength", 0) >= min_strength):
                memories.append(mem)

    memories.sort(key=lambda m: m.get("strength", 0), reverse=True)
    return memories[:limit]
