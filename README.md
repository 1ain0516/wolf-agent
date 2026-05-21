# Wolf Agent

AI wolf werewolf game platform. LangGraph state machine + MBTI personality agents + two-channel communication.

## v1 Scope

- Spectate mode (AI vs AI)
- 9-player standard game (3 wolves + 1 seer + 1 witch + 4 villagers)
- Two-channel communication (public board + wolf den)
- Canonical Event Log (append-only JSONL)
- 4 MBTI personality templates (ENTJ/INTP/ESFJ/INFJ)

## Quick Start

```
pip install -r requirements.txt
python -m wolf_agent run_spectate --seed 42
```

## Project Structure

```
src/engine/       # LangGraph state machine + game rules
src/agents/       # MBTI agent wrapper + prompt templates
src/events/       # Canonical Event Log
src/cli/          # CLI entry point
tests/            # Unit tests + e2e
```
