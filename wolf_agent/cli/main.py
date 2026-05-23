"""Wolf Agent CLI — run_spectate / stats commands."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time


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

    def reflect(self, messages):
        return "作为总结，我今天的发挥还算稳定，关键决策没有问题，但可以更主动一些引导局面。"

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


def _patch_stub():
    import wolf_agent.engine.game as game
    game.LLMClient = StubLLM  # type: ignore


def run_spectate(seed: int = 42, stub: bool = False, no_memory: bool = False,
                 memory_dir: str = ""):
    """Run a complete game with live terminal output."""
    mode = "STUB" if stub else "REAL"
    print(f"\n{'='*50}")
    print(f"  Wolf Agent v2 — 旁观模式 [{mode}]")
    print(f"  Seed: {seed}")
    if no_memory:
        print(f"  记忆: 关闭")
    if memory_dir:
        print(f"  记忆目录: {memory_dir}")
    print(f"{'='*50}\n")

    start = time.time()

    if stub:
        _patch_stub()

    from wolf_agent.engine.game import create_game, default_state

    initial = default_state(seed)
    initial["_no_memory"] = no_memory
    if memory_dir:
        initial["_memory_dir"] = memory_dir
    initial["_player_memories"] = {}

    from wolf_agent.engine import _build_and_run
    final_state = _build_and_run(initial)

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
        print(f"  {p['id']}号 [{p['personality']}] ({role_name}) — {status}")

    return final_state


def _compute_stats(summaries: list[dict]) -> dict:
    total = len(summaries)
    if total == 0:
        return {"batch": {"total_games": 0}, "winner_stats": {}, "round_stats": {}}

    wolf_wins = sum(1 for s in summaries if s.get("winner") == "werewolf")
    villager_wins = total - wolf_wins

    rounds = [s.get("rounds", 0) for s in summaries]
    mean_rounds = sum(rounds) / total
    variance = sum((r - mean_rounds) ** 2 for r in rounds) / total

    role_survival: dict[str, list[int]] = {}
    for s in summaries:
        for p in s.get("players", []):
            role = p.get("role", "")
            if role not in role_survival:
                role_survival[role] = []
            role_survival[role].append(s.get("rounds", 0) if p.get("alive") else 1)

    return {
        "winner_stats": {
            "werewolf": {"wins": wolf_wins, "win_rate": round(wolf_wins / total, 4)},
            "villager": {"wins": villager_wins, "win_rate": round(villager_wins / total, 4)},
        },
        "round_stats": {
            "mean": round(mean_rounds, 2),
            "min": min(rounds),
            "max": max(rounds),
            "std": round(math.sqrt(variance), 2),
        },
        "role_survival": {
            role: {"mean": round(sum(vals) / len(vals), 2)}
            for role, vals in role_survival.items()
        },
    }


def _collect_summaries(directory: str) -> list[dict]:
    summaries = []
    if not os.path.isdir(directory):
        print(f"警告: 目录不存在 {directory}", file=sys.stderr)
        return summaries

    for fname in os.listdir(directory):
        if not fname.endswith(".summary.json"):
            continue
        path = os.path.join(directory, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "winner" not in data:
                raise ValueError("missing winner field")
            summaries.append(data)
        except (json.JSONDecodeError, ValueError, OSError) as e:
            print(f"警告: 跳过异常文件 {fname} — {e}", file=sys.stderr)
            continue

    return summaries


def cmd_run_spectate(args: argparse.Namespace):
    no_memory = args.no_memory or args.stub  # --stub implies --no-memory
    if args.batch:
        batch_seed = args.batch_seed or args.seed
        from wolf_agent.engine.game import default_state, _build_and_run

        results = []
        for i in range(args.batch):
            seed = batch_seed + i if batch_seed else 42 + i
            initial = default_state(seed)
            initial["_no_memory"] = no_memory
            if args.memory_dir:
                initial["_memory_dir"] = args.memory_dir
            initial["_player_memories"] = {}

            if args.stub:
                _patch_stub()

            final = _build_and_run(initial)
            results.append(final)
            print(f"  [{i + 1}/{args.batch}] game={final['game_id']} winner={final.get('winner')}")

        summaries = []
        for final in results:
            from wolf_agent.engine.game import _dump_summary
            # Build summary dict from final state
            players_data = [
                {"id": p["id"], "personality": p["personality"],
                 "role": p["role"], "alive": p["id"] in final["alive"]}
                for p in final["players"]
            ]
            summaries.append({
                "game_id": final["game_id"],
                "seed": final["seed"],
                "winner": final["winner"],
                "rounds": final["round_num"],
                "roles": {str(k): v for k, v in final["roles"].items()},
                "players": players_data,
            })

        stats = _compute_stats(summaries)
        batch_seed_val = batch_seed if batch_seed else 42
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        games_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "games")
        os.makedirs(games_dir, exist_ok=True)
        output_path = os.path.join(games_dir, f"stats-batch-{batch_seed_val}-{timestamp}.json")

        stats["batch"] = {
            "total_games": args.batch,
            "seed": batch_seed_val,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "memory_enabled": not no_memory,
            "memory_dir": args.memory_dir or "games/",
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"\n批量统计已保存: {output_path}")
    else:
        run_spectate(seed=args.seed, stub=args.stub,
                     no_memory=no_memory, memory_dir=args.memory_dir or "")


def cmd_stats(args: argparse.Namespace):
    directory = args.dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "games")
    summaries = _collect_summaries(directory)
    stats = _compute_stats(summaries)
    stats["batch"] = {"total_games": len(summaries)}

    output = json.dumps(stats, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
    else:
        print(output)


def cmd_web(args: argparse.Namespace):
    """启动 web 界面"""
    try:
        from wolf_agent.web import app, socketio
    except ImportError:
        print("错误: Flask 未安装。请运行: pip install flask", file=sys.stderr)
        sys.exit(1)

    port = args.port or 5000
    print(f"\n{'='*50}")
    print(f"  Wolf Agent v2 — Web 界面")
    print(f"  访问: http://localhost:{port}")
    print(f"{'='*50}\n")
    socketio.run(app, debug=False, port=port, host='127.0.0.1', allow_unsafe_werkzeug=True)


def main():
    parser = argparse.ArgumentParser(description="Wolf Agent v2 — AI vs AI 狼人杀引擎")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run_spectate
    spectate_parser = subparsers.add_parser("run_spectate", help="旁观模式")
    spectate_parser.add_argument("--seed", type=int, default=42, help="随机种子")
    spectate_parser.add_argument("--stub", action="store_true", help="使用确定性 mock（无需 API key）")
    spectate_parser.add_argument("--no-memory", action="store_true", help="不读写记忆（退化为 v1 行为）")
    spectate_parser.add_argument("--memory-dir", type=str, default="", help="记忆存储目录")
    spectate_parser.add_argument("--batch", type=int, default=0, help="批量跑 N 局")
    spectate_parser.add_argument("--batch-seed", type=int, default=0, help="批量种子")

    # stats
    stats_parser = subparsers.add_parser("stats", help="统计分析已有对局")
    stats_parser.add_argument("--dir", type=str, default="", help="游戏日志目录")
    stats_parser.add_argument("--output", type=str, default="", help="输出文件路径")

    # web
    web_parser = subparsers.add_parser("web", help="启动 web 界面")
    web_parser.add_argument("--port", type=int, default=5000, help="端口号")

    args = parser.parse_args()

    if args.command == "run_spectate":
        cmd_run_spectate(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "web":
        cmd_web(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
