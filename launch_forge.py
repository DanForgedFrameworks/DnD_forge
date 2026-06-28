#!/usr/bin/env python
"""D&D Character Forge — one-click launcher / control console (Windows).

Double-click `Forge.bat` (or run this with the venv python). It:
  1. picks FREE ports for the engine + page (reclaiming defaults, ROUTING AROUND any
     wedged/unkillable port like a stuck :5000),
  2. starts the engine (Flask bridge) and the page (http.server),
  3. opens your browser straight at the right ports,
then waits:  [R] reforge   [O] open portal   [S] scry status   [Q] rest at the inn.

Quitting (or closing the window) douses both servers cleanly — no orphans.
(The cheese is purely cosmetic; the plumbing is the same.)
"""
from __future__ import annotations

import os
import random
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE_PORTS = [5000, 5001, 5002, 5003]
PAGE_PORTS = [8000, 8001, 8002]
SHEET = "Character%20Forge%20-%20Prototype.dc.html"
LOG_DIR = ROOT / "output"

# ---- cheese & colour ------------------------------------------------------------
try:  # enable ANSI colours on the Windows console
    import ctypes
    _k = ctypes.windll.kernel32
    _k.SetConsoleMode(_k.GetStdHandle(-11), 7)
except Exception:
    pass

C = {
    "copper": "\033[38;5;173m", "gold": "\033[38;5;220m", "ember": "\033[38;5;208m",
    "ash": "\033[38;5;245m", "green": "\033[38;5;77m", "red": "\033[38;5;167m",
    "bold": "\033[1m", "dim": "\033[2m", "off": "\033[0m",
}


def col(s: str, c: str) -> str:
    return f"{C.get(c, '')}{s}{C['off']}"


QUIPS = [
    "A hush falls over the tavern as the forge-master takes their stool...",
    "You rolled a natural 20 on your Ignite-the-Bellows check!",
    "The anvil hums. The dice are restless tonight.",
    "Legend says a great hero was hammered out here, on a Tuesday.",
    "Mind the dragon by the hearth — she's only *mostly* asleep.",
    "Somewhere a goblin sneezes. The bellows wheeze in reply.",
    "The embers whisper of the heroes yet to be forged...",
]

BANNER = r"""
   .=====================================================.
   |        T H E   C H A R A C T E R   F O R G E         |
   |       ~ where heroes are hammered into legend ~      |
   '====================================================='
              |>>>        _.-=========-._
           \  |  /       (_______________)   *clang*  *clang*
            \ | /          |   A N V I L  |
   _________ \|/ ________/=================\___________
"""

_procs: dict[str, subprocess.Popen] = {}
_logs: dict[str, object] = {}
_engine_port = ENGINE_PORTS[0]
_page_port = PAGE_PORTS[0]
_url = ""


def python_exe() -> str:
    for p in (ROOT / ".venv_forge" / "Scripts" / "python.exe", ROOT / ".venv" / "Scripts" / "python.exe"):
        if p.exists():
            return str(p)
    return sys.executable


PY = python_exe()


def port_is_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def free_port(port: int) -> None:
    """Best-effort: banish processes LISTENING on `port` (Windows netstat + taskkill)."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    except Exception:
        return
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[1].endswith(f":{port}") \
                and any(p.upper() == "LISTENING" for p in parts):
            pid = parts[-1]
            if pid.isdigit() and pid != "0":
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)


def pick_port(candidates: list[int], label: str) -> int:
    free_port(candidates[0])
    time.sleep(0.4)
    for p in candidates:
        if port_is_free(p):
            if p != candidates[0]:
                print(col(f"   ! Port {candidates[0]} is cursed by restless spirits — rerouting the {label} to {p}.", "red"))
            return p
    print(col(f"   ! No free {label} port among {candidates}; braving {candidates[0]} anyway...", "red"))
    return candidates[0]


def _spawn(name: str, args: list[str], env: dict | None = None) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / f"launcher-{name}.log", "w", encoding="utf-8")
    _logs[name] = log
    _procs[name] = subprocess.Popen(args, cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)


def start() -> None:
    global _engine_port, _page_port, _url
    print(col("\n   Stoking the forge-fires...", "ember"))
    _engine_port = pick_port(ENGINE_PORTS, "engine")
    _page_port = pick_port(PAGE_PORTS, "gate")
    print(col(f"   Summoning the engine-spirit to port {_engine_port}...", "copper"))
    _spawn("engine", [PY, "-m", "forge.web.app"], env=dict(os.environ, FORGE_PORT=str(_engine_port)))
    print(col(f"   Raising the tavern gates (the page) on port {_page_port}...", "copper"))
    _spawn("page", [PY, "-m", "http.server", str(_page_port), "--directory", "web/frontend"])
    _url = f"http://localhost:{_page_port}/{SHEET}?bridge=http://localhost:{_engine_port}"
    print(col(f"\n   engine  ->  http://localhost:{_engine_port}", "ash"))
    print(col(f"   page    ->  http://localhost:{_page_port}", "ash"))
    print(col(f"   scrolls ->  {LOG_DIR / 'launcher-engine.log'}", "dim"))


def stop() -> None:
    for name in list(_procs):
        p = _procs.pop(name)
        try:
            p.terminate()
            try:
                p.wait(timeout=4)
            except Exception:
                p.kill()
        except Exception:
            pass
    for name in list(_logs):
        try:
            _logs.pop(name).close()
        except Exception:
            pass


def status() -> None:
    print(col("   Scrying the aether...", "gold"))
    for name, port in (("engine", _engine_port), ("page", _page_port)):
        p = _procs.get(name)
        alive = p is not None and p.poll() is None
        mark = col("alive", "green") if alive else col("cold", "red")
        where = f" on :{port} (PID {p.pid})" if alive else ""
        print(f"   {name:7s}: {mark}{where}")


def restart() -> None:
    print(col("\n   *CLANG* The forge is reforged anew!", "ember"))
    stop()
    time.sleep(0.6)
    start()
    time.sleep(1.2)
    webbrowser.open(_url)


def menu() -> None:
    print(col("\n   ~~~ What is thy command, adventurer? ~~~", "gold"))
    print("     " + col("[R]", "ember") + " Reforge      " + col("(restart the servers)", "dim"))
    print("     " + col("[O]", "ember") + " Open portal  " + col("(reopen the browser)", "dim"))
    print("     " + col("[S]", "ember") + " Scry status  " + col("(what's running)", "dim"))
    print("     " + col("[Q]", "ember") + " Rest at inn  " + col("(quit & douse the fires)", "dim"))


def main() -> None:
    print(col(BANNER, "copper"))
    print(col("   " + random.choice(QUIPS), "gold"))
    start()
    time.sleep(1.5)
    print(col("\n   A shimmering portal tears open before you...", "ember"))
    webbrowser.open(_url)
    menu()
    try:
        while True:
            cmd = input(col("\n   forge> ", "copper")).strip().lower()
            if cmd == "q":
                break
            elif cmd == "r":
                restart()
                menu()
            elif cmd == "o":
                print(col("   The portal shimmers anew...", "ember"))
                webbrowser.open(_url)
            elif cmd == "s":
                status()
            elif cmd:
                print(col("   The forge-master tilts an ear, puzzled. (Try R, O, S or Q.)", "ash"))
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        print(col("\n   Dousing the forge-fires and banking the embers...", "ember"))
        stop()
        print(col("   May your dice roll ever high. Safe travels, adventurer. *\n", "gold"))


if __name__ == "__main__":
    main()
