"""
Unit tests for AI message splitting at paragraph boundaries
"""

from deps.ai.ai_bot_functions import split_message_at_paragraphs


def test_short_message_no_split() -> None:
    """Test that short messages are not split"""
    message = "This is a short message."
    result = split_message_at_paragraphs(message)
    assert len(result) == 1
    assert result[0] == message


def test_split_at_paragraph_boundary() -> None:
    """Test that messages are split at paragraph boundaries (double newlines)"""
    message = "Paragraph 1 content here.\n\nParagraph 2 content here.\n\nParagraph 3 content here."
    # Each paragraph is short, should all fit in one chunk
    result = split_message_at_paragraphs(message, max_length=200)
    assert len(result) == 1

    # Make paragraphs long enough to require splitting
    para1 = "A" * 1500
    para2 = "B" * 1500
    para3 = "C" * 1500
    message = f"{para1}\n\n{para2}\n\n{para3}"
    result = split_message_at_paragraphs(message, max_length=2000)
    # Should split into 3 chunks, one per paragraph
    assert len(result) == 3
    assert result[0].strip() == para1
    assert result[1].strip() == para2
    assert result[2].strip() == para3


def test_split_long_paragraph_at_line_boundary() -> None:
    """Test that long paragraphs are split at single newlines"""
    # Create a long paragraph with multiple lines
    line1 = "A" * 500
    line2 = "B" * 500
    line3 = "C" * 500
    line4 = "D" * 500
    paragraph = f"{line1}\n{line2}\n{line3}\n{line4}"

    result = split_message_at_paragraphs(paragraph, max_length=1200)
    # Should split into multiple chunks at line boundaries
    assert len(result) >= 2
    # Each chunk should be <= 1200 characters
    for chunk in result:
        assert len(chunk) <= 1200


def test_split_very_long_line_hard_split() -> None:
    """Test that extremely long lines (no newlines) are hard split"""
    # Create a line longer than max_length with no newlines
    long_line = "A" * 2500
    result = split_message_at_paragraphs(long_line, max_length=2000)
    # Should be split into 2 chunks
    assert len(result) == 2
    assert len(result[0]) == 2000
    assert len(result[1]) == 500


def test_realistic_ai_summary() -> None:
    """Test with a realistic AI summary format"""
    # Simulate an AI summary with multiple paragraphs about different users
    summary = """✨**AI summary generated of the last 24 hours**✨

User1 had an exceptional night with 15 kills in their best match on Villa. They maintained a K/D ratio of 2.3 across 5 matches and won 60% of their games. Notable performance includes 2 clutch wins and an ace in the final round.

User2 showed solid defensive play with a headshot percentage of 0.58. Across 4 matches, they achieved 8 kills per game on average. Their best moment was a 1v3 clutch on Coastline that secured the win.

User3 struggled this session with only 3 wins out of 7 matches. However, their individual performance was decent with a K/D of 1.1. They had one team kill incident on Bank that likely cost them the round."""

    result = split_message_at_paragraphs(summary, max_length=2000)

    # With realistic content, this should fit in one or two chunks
    assert len(result) <= 2

    # Verify no paragraphs are broken mid-text
    for chunk in result:
        # Should not end with a partial sentence (no trailing period without newline)
        if not chunk.endswith("\n"):
            # If it doesn't end with newline, it should be the last chunk
            assert chunk == result[-1]

    # Verify all content is preserved
    combined = "".join(result)
    # Remove trailing whitespace differences
    assert combined.strip() == summary.strip()


def test_empty_message() -> None:
    """Test with empty message"""
    result = split_message_at_paragraphs("")
    assert len(result) == 1
    assert result[0] == ""


def test_message_exactly_at_limit() -> None:
    """Test message that is exactly at the character limit"""
    message = "A" * 2000
    result = split_message_at_paragraphs(message, max_length=2000)
    assert len(result) == 1
    assert len(result[0]) == 2000


def test_message_one_char_over_limit() -> None:
    """Test message that is one character over the limit"""
    message = "A" * 2001
    result = split_message_at_paragraphs(message, max_length=2000)
    assert len(result) == 2
    assert len(result[0]) == 2000
    assert len(result[1]) == 1


def test_multiple_paragraphs_with_varying_lengths() -> None:
    """Test with paragraphs of varying lengths"""
    short_para = "Short paragraph."
    medium_para = "B" * 800
    long_para = "C" * 1500

    message = f"{short_para}\n\n{medium_para}\n\n{long_para}"
    result = split_message_at_paragraphs(message, max_length=2000)

    # Short + medium should fit together (< 2000)
    # Long should be in second chunk
    assert len(result) == 2
    assert short_para in result[0]
    assert medium_para in result[0]
    assert long_para.strip() == result[1].strip()


def test_preserves_newline_structure() -> None:
    """Test that the function preserves the newline structure between chunks"""
    para1 = "Paragraph one with some content"
    para2 = "Paragraph two with some content"
    para3 = "Paragraph three with some content"

    message = f"{para1}\n\n{para2}\n\n{para3}"
    result = split_message_at_paragraphs(message, max_length=40)

    # Each paragraph should be in its own chunk
    assert len(result) == 3
    assert result[0].strip() == para1
    assert result[1].strip() == para2
    assert result[2].strip() == para3
