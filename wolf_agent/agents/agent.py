from __future__ import annotations

from .llm import LLMClient
from .personality import PERSONALITY_TEMPLATES

ROLE_NAMES = {
    "werewolf": "狼人",
    "seer": "预言家",
    "witch": "女巫",
    "villager": "村民",
}


class Agent:
    """A wolf-agent player with SBTI personality, backed by LLM."""

    def __init__(self, player_id: int, role: str, personality: str, llm: LLMClient,
                 memories: list | None = None):
        self.player_id = player_id
        self.role = role
        self.personality = personality
        self.alive = True
        self.llm = llm
        self.memories = memories or []
        self._build_prompt()

    def _build_prompt(self):
        tpl = PERSONALITY_TEMPLATES[self.personality]
        lines = [
            f"你是 {self.player_id} 号玩家，身份为【{ROLE_NAMES[self.role]}】。",
            f"你的性格是【{self.personality}】（{tpl['title']}）：{tpl['description']}",
            f"发言风格：{tpl['style']}",
            f"策略倾向：{tpl['strategy']}",
        ]
        if self.memories:
            lines.append("\n你的历史对局记忆（可能会影响你的判断）：")
            for m in self.memories:
                lines.append(f"  - {m['content']}")
        lines.append("禁止说出你是AI或提及游戏外信息。")
        self.system_prompt = "\n".join(lines)

    def build_context(self, game_state: dict) -> str:
        parts = [f"第 {game_state['round_num']} 轮"]
        alive = [p for p in game_state["players"] if p["id"] in game_state["alive"]]
        alive_str = ", ".join(str(p["id"]) + "号" for p in alive)
        parts.append(f"存活玩家: {alive_str}")
        if game_state.get("last_death"):
            parts.append(f"昨晚死亡: {game_state['last_death']}")
        if game_state.get("public_messages"):
            recent = game_state["public_messages"][-10:]
            parts.append("最近发言:")
            for m in recent:
                parts.append(f"  {m['from']}号: {m['content'][:100]}")
        return "\n".join(parts)

    def speak(self, context: str) -> tuple[str, str]:
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    "请输出一段发言（≤200字），格式为JSON：\n"
                    '{"content": "你的发言", "strategy_summary": "策略说明（≤30字）"}'
                ),
            },
        ]
        return self.llm.speak(msgs)

    def vote(self, context: str, candidates: list[int]) -> int:
        candidate_str = ", ".join(f"{c}号" for c in candidates)
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"当前可投票对象: {candidate_str}\n"
                    "你要投票给谁？只输出数字。"
                ),
            },
        ]
        return self.llm.vote(msgs)

    def night_kill(self, context: str, targets: list[int]) -> int:
        tgt_str = ", ".join(f"{t}号" for t in targets)
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    "你是狼人，今晚要和同伴商议杀死谁。\n"
                    f"可选目标: {tgt_str}\n"
                    '输出JSON: {"target": 数字}'
                ),
            },
        ]
        result = self.llm.act(msgs)
        return result.get("target", targets[0] if targets else 0)

    def night_investigate(self, context: str, targets: list[int]) -> int:
        tgt_str = ", ".join(f"{t}号" for t in targets)
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    "你是预言家，今晚可以查验一名玩家身份。\n"
                    f"可选目标: {tgt_str}\n"
                    '输出JSON: {"target": 数字}'
                ),
            },
        ]
        result = self.llm.act(msgs)
        return result.get("target", targets[0] if targets else 0)

    def witch_act(self, context: str, save_target: int | None, has_antidote: bool, has_poison: bool) -> dict:
        antidote_str = "可用" if has_antidote else "已用"
        poison_str = "可用" if has_poison else "已用"
        target_str = f"今晚被刀的是 {save_target} 号。" if save_target else "今晚没人被杀。"
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n你是女巫。{target_str}\n"
                    f"解药{antidote_str}，毒药{poison_str}\n"
                    '输出JSON: {"use_antidote": bool, "poison_target": int|null}'
                ),
            },
        ]
        result = self.llm.act(msgs)
        return {
            "use_antidote": result.get("use_antidote", False),
            "poison_target": result.get("poison_target"),
        }

    def reflect(self, context: str) -> str:
        """Generate a self-review reflection after the game."""
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    "游戏结束了。请回顾你自己的表现：你做了哪些关键决策？"
                    "哪些做得好？哪些下次可以改进？"
                    "请简短总结（≤100字）。"
                ),
            },
        ]
        return self.llm.reflect(msgs)

    def wolf_discuss(self, context: str, packmates: list[int]) -> str:
        pack_str = ", ".join(f"{p}号" for p in packmates)
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"你和狼队友({pack_str})在密道商议今晚杀谁。\n"
                    "请发表意见（≤100字）。"
                ),
            },
        ]
        text, _ = self.llm.speak(msgs)
        return text
