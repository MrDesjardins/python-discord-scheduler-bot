"""Unit tests for browser exponential backoff"""

import pytest
from deps.browser_context_manager import BrowserContextManager
from deps.browser_config import BrowserConfig


def test_calculate_backoff_exponential_growth():
    """Test backoff grows exponentially"""
    config = BrowserConfig(
        base_backoff_seconds=2.0,
        backoff_multiplier=2.0,
        max_backoff_seconds=60.0,
        jitter_factor=0.0,  # No jitter for predictable testing
    )
    manager = BrowserContextManager(config=config)

    # Attempt 0: 2 * (2^0) = 2 seconds
    backoff0 = manager._calculate_backoff(0, is_fd_exhaustion=False)
    assert backoff0 == pytest.approx(2.0, abs=0.01)

    # Attempt 1: 2 * (2^1) = 4 seconds
    backoff1 = manager._calculate_backoff(1, is_fd_exhaustion=False)
    assert backoff1 == pytest.approx(4.0, abs=0.01)

    # Attempt 2: 2 * (2^2) = 8 seconds
    backoff2 = manager._calculate_backoff(2, is_fd_exhaustion=False)
    assert backoff2 == pytest.approx(8.0, abs=0.01)

    # Attempt 3: 2 * (2^3) = 16 seconds
    backoff3 = manager._calculate_backoff(3, is_fd_exhaustion=False)
    assert backoff3 == pytest.approx(16.0, abs=0.01)


def test_calculate_backoff_capping():
    """Test backoff is capped at max_backoff_seconds"""
    config = BrowserConfig(
        base_backoff_seconds=2.0,
        backoff_multiplier=2.0,
        max_backoff_seconds=10.0,
        jitter_factor=0.0,
    )
    manager = BrowserContextManager(config=config)

    # Attempt 5: 2 * (2^5) = 64 seconds, but capped at 10
    backoff = manager._calculate_backoff(5, is_fd_exhaustion=False)
    assert backoff == pytest.approx(10.0, abs=0.01)

    # Attempt 10: Even larger, still capped at 10
    backoff = manager._calculate_backoff(10, is_fd_exhaustion=False)
    assert backoff == pytest.approx(10.0, abs=0.01)


def test_calculate_backoff_jitter():
    """Test jitter stays within bounds"""
    config = BrowserConfig(
        base_backoff_seconds=10.0,
        backoff_multiplier=2.0,
        max_backoff_seconds=60.0,
        jitter_factor=0.2,  # 20% jitter
    )
    manager = BrowserContextManager(config=config)

    # For attempt 0, base is 10 seconds
    # Jitter range: 10 ± (10 * 0.2) = 10 ± 2 = [8, 12]
    for _ in range(100):  # Test multiple times due to randomness
        backoff = manager._calculate_backoff(0, is_fd_exhaustion=False)
        assert 8.0 <= backoff <= 12.0

    # For attempt 1, base is 20 seconds
    # Jitter range: 20 ± (20 * 0.2) = 20 ± 4 = [16, 24]
    for _ in range(100):
        backoff = manager._calculate_backoff(1, is_fd_exhaustion=False)
        assert 16.0 <= backoff <= 24.0


def test_calculate_backoff_fd_exhaustion():
    """Test FD exhaustion uses special backoff"""
    config = BrowserConfig(
        base_backoff_seconds=2.0,
        backoff_multiplier=2.0,
        max_backoff_seconds=60.0,
        jitter_factor=0.0,
        fd_exhaustion_backoff_seconds=15.0,
    )
    manager = BrowserContextManager(config=config)

    # FD exhaustion should use special backoff regardless of attempt
    backoff0 = manager._calculate_backoff(0, is_fd_exhaustion=True)
    assert backoff0 == pytest.approx(15.0, abs=0.01)

    backoff5 = manager._calculate_backoff(5, is_fd_exhaustion=True)
    assert backoff5 == pytest.approx(15.0, abs=0.01)

    # Normal backoff should be different
    normal_backoff = manager._calculate_backoff(0, is_fd_exhaustion=False)
    assert normal_backoff == pytest.approx(2.0, abs=0.01)


def test_calculate_backoff_minimum():
    """Test backoff never goes below 0.1 seconds"""
    config = BrowserConfig(
        base_backoff_seconds=0.5,
        backoff_multiplier=2.0,
        max_backoff_seconds=60.0,
        jitter_factor=0.9,  # Large jitter could theoretically go negative
    )
    manager = BrowserContextManager(config=config)

    # Even with large jitter, should never be below 0.1
    for _ in range(100):
        backoff = manager._calculate_backoff(0, is_fd_exhaustion=False)
        assert backoff >= 0.1


def test_calculate_backoff_different_multipliers():
    """Test different backoff multipliers"""
    # Test multiplier of 3
    config = BrowserConfig(
        base_backoff_seconds=1.0,
        backoff_multiplier=3.0,
        max_backoff_seconds=100.0,
        jitter_factor=0.0,
    )
    manager = BrowserContextManager(config=config)

    # Attempt 0: 1 * (3^0) = 1
    assert manager._calculate_backoff(0, is_fd_exhaustion=False) == pytest.approx(1.0, abs=0.01)
    # Attempt 1: 1 * (3^1) = 3
    assert manager._calculate_backoff(1, is_fd_exhaustion=False) == pytest.approx(3.0, abs=0.01)
    # Attempt 2: 1 * (3^2) = 9
    assert manager._calculate_backoff(2, is_fd_exhaustion=False) == pytest.approx(9.0, abs=0.01)
    # Attempt 3: 1 * (3^3) = 27
    assert manager._calculate_backoff(3, is_fd_exhaustion=False) == pytest.approx(27.0, abs=0.01)


def test_calculate_backoff_jitter_distribution():
    """Test jitter produces reasonable distribution"""
    config = BrowserConfig(
        base_backoff_seconds=10.0,
        backoff_multiplier=2.0,
        max_backoff_seconds=60.0,
        jitter_factor=0.1,  # 10% jitter
    )
    manager = BrowserContextManager(config=config)

    # Collect many samples
    samples = [manager._calculate_backoff(0, is_fd_exhaustion=False) for _ in range(1000)]

    # Expected range: 10 ± 1 = [9, 11]
    assert all(9.0 <= s <= 11.0 for s in samples)

    # Mean should be close to 10 (within 5% due to jitter)
    mean = sum(samples) / len(samples)
    assert 9.5 <= mean <= 10.5

    # Should have some variation (not all the same)
    assert len(set(samples)) > 10  # At least 10 different values
