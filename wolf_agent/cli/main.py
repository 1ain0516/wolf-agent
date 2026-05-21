"""Wolf Agent CLI — run_spectate command."""

from __future__ import annotations

import argparse
import re
import sys
import time

from wolf_agent.engine import create_game


class StubLLM:
    """Deterministic mock LLM for --stub mode (no API key needed)."""

    def __init__(self):
        self.api_key = "stub"
        self.base_url = "http://stub"
        self.model = "stub"
        self._phrases = [
            "我认为需要仔细分析局势。",
            "我怀疑有人行为异常。",
            "大家注意观察投票模式。",
            "我觉得可以再观察一轮。",
        ]
        self._call_count = 0

    def _alive_from_context(self, messages: list[dict]) -> list[int]:
        for m in messages:
            if m["role"] == "user":
                for line in m["content"].split("\n"):
                    for prefix in ("存活:", "存活玩家:", "可投票对象:", "可选目标:"):
                        if prefix in line:
                            nums = re.findall(r"\d+", line)
                            return [int(n) for n in nums]
        return []

    def speak(self, messages):
        self._call_count += 1
        phrase = self._phrases[self._call_count % len(self._phrases)]
        return phrase, f"第{self._call_count}次发言"

    def vote(self, messages):
        alive = self._alive_from_context(messages)
        if not alive:
            return 1
        idx = self._call_count % len(alive)
        self._call_count += 1
        return alive[idx]

    def act(self, messages):
        alive = self._alive_from_context(messages)
        if not alive:
            return {"target": 1, "use_antidote": False, "poison_target": None}
        target = alive[self._call_count % len(alive)]
        self._call_count += 1
        return {"target": target, "use_antidote": False, "poison_target": None}

    def _call(self, messages, temperature, max_tokens):
        return '{"content": "test", "strategy_summary": "test"}'

    def chat(self, messages, temperature=0.7, max_tokens=300):
        return "test"

    def chat_with_strategy(self, messages, temperature=0.7, max_tokens=350):
        return "test", "test"

    def witch_act(self, context, save_target, has_antidote, has_poison):
        return {"use_antidote": False, "poison_target": None}

    def wolf_discuss(self, context, packmates):
        return "我觉得可以杀了目标。"

    def night_kill(self, context, targets):
        return targets[0] if targets else 1

    def night_investigate(self, context, targets):
        return targets[0]


def run_spectate(seed: int = 42, stub: bool = False):
    """Run a complete game with live terminal output."""
    print(f"\n{'='*50}")
    mode = "STUB" if stub else "REAL"
    print(f"  Wolf Agent v1 — 旁观模式 [{mode}]")
    print(f"  Seed: {seed}")
    print(f"{'='*50}\n")

    start = time.time()

    if stub:
        import wolf_agent.engine.game as game
        original = game.LLMClient
        game.LLMClient = StubLLM  # type: ignore
        final_state, _ = create_game(seed)
        game.LLMClient = original
    else:
        final_state, _ = create_game(seed)

    elapsed = time.time() - start

    winner = final_state.get("winner")
    winner_name = "🐺 狼人" if winner == "werewolf" else "👤 好人"
    print(f"\n{'='*50}")
    print(f"  游戏结束！{winner_name} 获胜！")
    print(f"  回合数: {final_state['round_num']}")
    print(f"  用时: {elapsed:.1f}s")
    print(f"  事件日志: {final_state.get('event_log_path', 'N/A')}")
    print(f"{'='*50}\n")

    print("最终状态:")
    for p in final_state["players"]:
        status = "存活" if p["id"] in final_state["alive"] else "死亡"
        role_map = {"werewolf": "狼人", "seer": "预言家", "witch": "女巫", "villager": "村民"}
        role_name = role_map.get(p["role"], p["role"])
        print(f"  {p['id']}号 [{p['mbti']}] ({role_name}) — {status}")

    return final_state


def main():
    parser = argparse.ArgumentParser(description="Wolf Agent v1 — AI vs AI 狼人杀引擎")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    spectate_parser = subparsers.add_parser("run_spectate", help="旁观模式")
    spectate_parser.add_argument("--seed", type=int, default=42, help="随机种子")
    spectate_parser.add_argument("--stub", action="store_true", help="使用确定性 mock（无需 API key）")

    args = parser.parse_args()

    if args.command == "run_spectate":
        run_spectate(seed=args.seed, stub=args.stub)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
