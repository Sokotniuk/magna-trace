"""Create the demo employee list of the fictional company.

    python -m agent.make_employees

Writes agent/employees.json (scrypt hashes only, safe to commit) and
agent/demo-accounts.local.md (generated passwords, git-ignored; share it inside the team only).
Running it again replaces every password.
"""

import json
import secrets
from pathlib import Path

from .auth import DEFAULT_FILE, hash_password

COMPANY = "Hornád Drive Systems s.r.o. (fictional)"
# Fictional people. Any resemblance to real persons is unintended.
PEOPLE = [
    ("HDS-0142", "lucia.hruba", "Lucia Hrubá", "Test technician", "A"),
    ("HDS-0157", "marek.dlhy", "Marek Dlhý", "Maintenance technician", "A"),
    ("HDS-0163", "tomas.kovacik", "Tomáš Kováčik", "Test technician", "B"),
    ("HDS-0178", "eva.simkova", "Eva Šimková", "Shift lead", "B"),
    ("HDS-0181", "peter.baran", "Peter Baran", "Maintenance technician", "C"),
    ("HDS-0194", "zuzana.mikulova", "Zuzana Mikulová", "Quality engineer", "C"),
]
WORDS = ["axle", "rotor", "gear", "torque", "spindle", "valve", "sensor", "clamp", "bearing", "piston"]


def demo_password() -> str:
    return f"{secrets.choice(WORDS)}-{secrets.choice(WORDS)}-{secrets.randbelow(9000) + 1000}"


def main() -> None:
    employees, lines = [], []
    for employee_id, username, name, role, shift in PEOPLE:
        password, salt = demo_password(), secrets.token_bytes(16)
        employees.append({"employee_id": employee_id, "username": username, "name": name, "role": role,
                          "shift": shift, "salt": salt.hex(), "password_hash": hash_password(password, salt)})
        lines.append(f"| {name} | {role} | {shift} | `{username}` | `{password}` |")
    DEFAULT_FILE.write_text(json.dumps({"company": COMPANY, "employees": employees}, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    local = Path(__file__).with_name("demo-accounts.local.md")
    local.write_text("# Demo accounts — fictional company, team only, do not commit\n\n"
                     "| Name | Role | Shift | Username | Password |\n|---|---|---|---|---|\n"
                     + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {DEFAULT_FILE.name} ({len(employees)} employees) and {local.name}")


if __name__ == "__main__":
    main()
