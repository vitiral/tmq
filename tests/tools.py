from unittest.mock import MagicMock

from tmq.context import Context

def mock_context():
    m = MagicMock(spec=Context)
    m.sockets = []
    return m

