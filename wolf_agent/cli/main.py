"""Wolf Agent CLI — run_spectate command."""

from __future__ import annotations

import argparse
import sys
import time

from wolf_agent.engine import create_game


def run_spectate(seed: int = 42):
    """Run a complete game in spectator mode with live terminal output."""
    print(f"\n{'='*50}")
    print(f"  Wolf Agent v1 — 旁观模式")
    print(f"  Seed: {seed}")
    print(f"{'='*50}\n")

    start = time.time()
    final_state, _ = create_game(seed)
    elapsed = time.time() - start

    # Print results
    winner = final_state.get("winner")
    winner_name = "🐺 狼人" if winner == "werewolf" else "👤 好人"
    print(f"\n{'='*50}")
    print(f"  游戏结束！{winner_name} 获胜！")
    print(f"  回合数: {final_state['round_num']}")
    print(f"  用时: {elapsed:.1f}s")
    print(f"  事件日志: {final_state.get('event_log_path', 'N/A')}")
    print(f"{'='*50}\n")

    # Print final state summary
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

    # run_spectate
    spectate_parser = subparsers.add_parser("run_spectate", help="旁观模式")
    spectate_parser.add_argument("--seed", type=int, default=42, help="随机种子")

    args = parser.parse_args()

    if args.command == "run_spectate":
        run_spectate(seed=args.seed)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
