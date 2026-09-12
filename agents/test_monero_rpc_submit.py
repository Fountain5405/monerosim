from unittest.mock import MagicMock, patch
import pytest
from agents.monero_rpc import MoneroRPC, RPCError


def _mock_response(json_body, status_code=200):
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    resp.status_code = status_code
    return resp


def test_submit_block_sends_positional_list_param():
    rpc = MoneroRPC("10.0.0.5", 28081)
    with patch.object(rpc.session, "post") as post:
        post.return_value = _mock_response({"result": {"status": "OK"}})
        out = rpc.submit_block("deadbeef")
        assert out == {"status": "OK"}
        # The one call's JSON payload must carry params as a LIST [blob].
        _, kwargs = post.call_args
        payload = kwargs["json"]
        assert payload["method"] == "submit_block"
        assert payload["params"] == ["deadbeef"]


def test_submit_block_raises_on_rpc_error():
    rpc = MoneroRPC("10.0.0.5", 28081)
    with patch.object(rpc.session, "post") as post:
        post.return_value = _mock_response({"error": {"code": -7, "message": "Block not accepted"}})
        with pytest.raises(RPCError):
            rpc.submit_block("00")
