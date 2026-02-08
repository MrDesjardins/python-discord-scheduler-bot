"""
Unit tests for operator_mapping module
"""

import pytest
from deps.operator_mapping import get_operator_role, ATTACKER_OPERATORS, DEFENDER_OPERATORS


def test_get_operator_role_attacker():
    """Test that attacker operators are correctly identified"""
    assert get_operator_role("Sledge") == "attacker"
    assert get_operator_role("Ash") == "attacker"
    assert get_operator_role("Thermite") == "attacker"
    assert get_operator_role("Ace") == "attacker"


def test_get_operator_role_defender():
    """Test that defender operators are correctly identified"""
    assert get_operator_role("Smoke") == "defender"
    assert get_operator_role("Jager") == "defender"
    assert get_operator_role("Mute") == "defender"
    assert get_operator_role("Azami") == "defender"


def test_get_operator_role_case_insensitive():
    """Test that operator role lookup is case-insensitive"""
    assert get_operator_role("sledge") == "attacker"
    assert get_operator_role("SLEDGE") == "attacker"
    assert get_operator_role("SlEdGe") == "attacker"
    assert get_operator_role("smoke") == "defender"
    assert get_operator_role("SMOKE") == "defender"


def test_get_operator_role_with_whitespace():
    """Test that operator role lookup handles whitespace"""
    assert get_operator_role("  Sledge  ") == "attacker"
    assert get_operator_role("  Smoke  ") == "defender"


def test_get_operator_role_unknown():
    """Test that unknown operators return None"""
    assert get_operator_role("UnknownOperator") is None
    assert get_operator_role("") is None
    assert get_operator_role("   ") is None


def test_no_operator_overlap():
    """Test that no operator is in both attacker and defender sets"""
    overlap = ATTACKER_OPERATORS & DEFENDER_OPERATORS
    assert len(overlap) == 0, f"Operators in both sets: {overlap}"


def test_operator_sets_not_empty():
    """Test that both operator sets contain operators"""
    assert len(ATTACKER_OPERATORS) > 0
    assert len(DEFENDER_OPERATORS) > 0
