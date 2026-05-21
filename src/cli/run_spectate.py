"""Spectate mode CLI entry"""

import argparse


def run_spectate(seed: int = 42):
    print(f"Running spectate game with seed={seed}")
    # TODO: v1 implementation


def main():
    parser = argparse.ArgumentParser(description="Wolf Agent - Spectate Mode")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run_spectate(args.seed)


if __name__ == "__main__":
    main()
