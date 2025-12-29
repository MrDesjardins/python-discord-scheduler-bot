"""
Models for team suggestions in custom matches.
"""

from typing import List

import discord


class Team:
    def __init__(self) -> None:
        self.members: List[discord.Member] = []


class TeamSuggestion:
    def __init__(self) -> None:
        self.team1 = Team()
        self.team2 = Team()
        self.logic = ""
        self.explanation = ""
