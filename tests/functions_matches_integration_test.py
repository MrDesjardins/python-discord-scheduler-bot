from unittest.mock import patch
from deps.browser_context_manager import BrowserContextManager


class TestMatchStatsDownload:
    """
    Test to get data from the matches using TRN API

    This is an integration test (slow) and perform HTTP requests. The goal is to ensure the system can download
    the information from the API.
    """

    @patch("deps.log.print_error_log")
    def test_matches(self, mock_error_log):
        """Test to check if the matches information is downloaded correctly"""
        mock_error_log.return_value = None

        with BrowserContextManager() as context:
            context.download_matches("isleep_rb6")
        assert mock_error_log.call_count == 0
