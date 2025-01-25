"""
Integration test to check if the matches information is downloaded correctly
This is an integration test (slow) and perform HTTP requests. The goal is to ensure the system can download
the information from the API.
"""

from datetime import datetime, timezone
from unittest.mock import patch
from deps.data_access_data_class import UserInfo
from deps.browser_context_manager import BrowserContextManager
from deps.models import UserQueueForStats
import deps.log


@patch.object(deps.log, deps.log.print_error_log.__name__)
def test_matches(mock_error_log):
    """Test to check if the matches information is downloaded correctly"""
    mock_error_log.return_value = None

    with BrowserContextManager() as context:
        user = UserInfo(357551747146842124, "Patrick", "noSleep_rb6", "isleep_rb6", None, "east")
        user_queue = UserQueueForStats(user, "1", datetime.now(timezone.utc))
        context.download_full_matches(user_queue)
    assert mock_error_log.call_count == 0
