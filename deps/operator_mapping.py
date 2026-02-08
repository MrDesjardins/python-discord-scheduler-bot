"""
Operator classification for Rainbow Six Siege operators.
Maps operator names to their roles (attacker/defender).
"""

from typing import Optional

ATTACKER_OPERATORS = {
    "Sledge",
    "Thatcher",
    "Ash",
    "Thermite",
    "Twitch",
    "Montagne",
    "Glaz",
    "Fuze",
    "Blitz",
    "IQ",
    "Buck",
    "Blackbeard",
    "Capitao",
    "Hibana",
    "Jackal",
    "Ying",
    "Zofia",
    "Dokkaebi",
    "Lion",
    "Finka",
    "Maverick",
    "Nomad",
    "Gridlock",
    "Nokk",
    "Amaru",
    "Kali",
    "Iana",
    "Ace",
    "Zero",
    "Flores",
    "Osa",
    "Sens",
    "Grim",
    "Brava",
    "Ram",
    "Deimos",
    "Striker",
    "Skopos",
}

DEFENDER_OPERATORS = {
    "Smoke",
    "Mute",
    "Castle",
    "Pulse",
    "Doc",
    "Rook",
    "Jager",
    "Bandit",
    "Frost",
    "Valkyrie",
    "Caveira",
    "Echo",
    "Mira",
    "Lesion",
    "Ela",
    "Vigil",
    "Maestro",
    "Alibi",
    "Clash",
    "Kaid",
    "Mozzie",
    "Warden",
    "Goyo",
    "Wamai",
    "Oryx",
    "Melusi",
    "Aruni",
    "Thunderbird",
    "Thorn",
    "Azami",
    "Fenrir",
    "Solis",
    "Tubarao",
}


def get_operator_role(operator_name: str) -> Optional[str]:
    """
    Determine if an operator is an attacker or defender.

    Args:
        operator_name: Name of the operator (case-insensitive)

    Returns:
        'attacker', 'defender', or None if operator not found
    """
    clean = operator_name.strip().title()
    if clean in ATTACKER_OPERATORS:
        return "attacker"
    if clean in DEFENDER_OPERATORS:
        return "defender"
    return None
