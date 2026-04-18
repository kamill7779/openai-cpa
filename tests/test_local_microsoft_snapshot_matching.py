import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

fake_requests_module = types.SimpleNamespace(post=None, get=None)
sys.modules.setdefault("curl_cffi", types.SimpleNamespace(requests=fake_requests_module))
sys.modules.setdefault(
    "utils.integrations.ai_service",
    types.SimpleNamespace(AIService=object),
)
sys.modules.setdefault(
    "utils.email_providers.gmail_service",
    types.SimpleNamespace(get_gmail_otp_via_oauth=lambda *args, **kwargs: ""),
)
sys.modules.setdefault(
    "utils.email_providers.duckmail_service",
    types.SimpleNamespace(DuckMailService=object),
)

from utils.email_providers.local_microsoft_service import LocalMicrosoftService


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class LocalMicrosoftSnapshotMatchingTests(unittest.TestCase):
    def test_graph_snapshot_matches_aliases_found_only_in_message_body(self):
        service = LocalMicrosoftService()
        mailbox = {
            "email": "user+freshalias@hotmail.com",
            "master_email": "user@hotmail.com",
        }
        captured = {}

        def fake_exchange(current_mailbox):
            current_mailbox["token_type"] = "graph_full"
            return "access-token"

        def fake_get(url, params=None, headers=None, **kwargs):
            captured["params"] = params
            return _FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "old-msg",
                            "toRecipients": [
                                {"emailAddress": {"address": "user@hotmail.com"}}
                            ],
                            "subject": "Your ChatGPT code is 123456",
                            "body": {
                                "content": "To: user+freshalias@hotmail.com"
                            },
                        }
                    ]
                },
            )

        with patch.object(service, "_exchange_refresh_token", side_effect=fake_exchange):
            with patch(
                "utils.email_providers.local_microsoft_service.cffi_requests.get",
                side_effect=fake_get,
            ):
                with redirect_stdout(io.StringIO()):
                    snapshot = service.get_snapshot_ids(
                        mailbox,
                        "user+freshalias@hotmail.com",
                    )

        self.assertEqual({"old-msg"}, snapshot)
        self.assertIn("body", captured["params"]["$select"])
        self.assertEqual(20, captured["params"]["$top"])


if __name__ == "__main__":
    unittest.main()
