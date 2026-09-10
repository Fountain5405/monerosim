"""Smoke tests for agents.monero_rpc.

Tests the JSON-RPC payload shape, error mapping, and is_ready() boundary.
We mock the underlying ``requests.Session.post`` so no network is touched.
"""
import requests
import pytest

from agents.monero_rpc import BaseRPC, MoneroRPC, RPCError


def _fake_post_response(json_payload, status_code=200):
    """Build a Mock that quacks like requests.Response."""
    class _Resp:
        def __init__(self, payload, code):
            self._payload = payload
            self.status_code = code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    return _Resp(json_payload, status_code)


def test_make_request_builds_jsonrpc_payload(mocker):
    """_make_request POSTs a properly-shaped JSON-RPC 2.0 payload."""
    rpc = BaseRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.return_value = _fake_post_response({"result": {"height": 42}})

    rpc._make_request("get_info", {"foo": "bar"})

    assert post.call_count == 1
    _, kwargs = post.call_args
    payload = kwargs["json"]
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "0"
    assert payload["method"] == "get_info"
    assert payload["params"] == {"foo": "bar"}


def test_make_request_omits_params_when_none(mocker):
    """When params is None, no 'params' key is included in the payload."""
    rpc = BaseRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.return_value = _fake_post_response({"result": {}})

    rpc._make_request("get_version")

    _, kwargs = post.call_args
    payload = kwargs["json"]
    assert "params" not in payload


def test_make_request_raises_on_error_key(mocker):
    """A JSON response containing an "error" key turns into RPCError."""
    rpc = BaseRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.return_value = _fake_post_response(
        {"error": {"code": -1, "message": "method not found"}}
    )

    with pytest.raises(RPCError, match="method not found"):
        rpc._make_request("bogus_method")


def test_make_request_wraps_request_exception(mocker):
    """Network-layer exceptions propagate as RPCError, not raw requests.*."""
    rpc = BaseRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.side_effect = requests.exceptions.ConnectionError("boom")

    with pytest.raises(RPCError, match="boom"):
        rpc._make_request("get_info")


def test_is_ready_true_on_successful_response(mocker):
    """is_ready returns True when get_version succeeds."""
    rpc = BaseRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.return_value = _fake_post_response({"result": {"version": 65555}})

    assert rpc.is_ready() is True


def test_is_ready_false_on_request_exception(mocker):
    """is_ready swallows a transport failure and returns False."""
    rpc = BaseRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.side_effect = requests.exceptions.ConnectionError("connection refused")

    assert rpc.is_ready() is False


def test_start_mining_posts_to_legacy_endpoint(mocker):
    """start_mining POSTs to /start_mining (not /json_rpc) with miner_address
    and threads_count, and returns the flat reply as-is."""
    rpc = MoneroRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.return_value = _fake_post_response({"status": "OK"})

    result = rpc.start_mining("4Axxxaddress", threads=2)

    assert post.call_count == 1
    args, kwargs = post.call_args
    url = args[0] if args else kwargs.get("url")
    assert url.endswith("/start_mining")
    assert not url.endswith("/json_rpc/start_mining")
    payload = kwargs["json"]
    assert payload["miner_address"] == "4Axxxaddress"
    assert payload["threads_count"] == 2
    assert result == {"status": "OK"}


def test_mining_status_posts_empty_body_to_legacy_endpoint(mocker):
    """mining_status POSTs to /mining_status with an empty JSON body."""
    rpc = MoneroRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.return_value = _fake_post_response({"active": True, "speed": 10})

    result = rpc.mining_status()

    assert post.call_count == 1
    args, kwargs = post.call_args
    url = args[0] if args else kwargs.get("url")
    assert url.endswith("/mining_status")
    assert kwargs["json"] == {}
    assert result == {"active": True, "speed": 10}


def test_ensure_mining_never_calls_start_mining(mocker):
    """ensure_mining (generateblocks mode) must never hit start_mining: on a
    stock daemon that launches an unthrottled RandomX loop that stalls
    simulated time under Shadow. It should post exactly one generateblocks
    json_rpc request and nothing to /start_mining."""
    rpc = MoneroRPC("127.0.0.1", 18081)
    # Skip detection so this test isolates ensure_mining's own call, not
    # detect_available_methods' probing.
    rpc.available_methods = {"generateblocks": True}
    post = mocker.patch.object(rpc.session, "post")
    post.return_value = _fake_post_response(
        {"result": {"status": "OK", "height": 11, "blocks": ["deadbeef"]}}
    )

    result = rpc.ensure_mining("4Axxxaddress")

    assert result["method"] == "generateblocks"
    assert post.call_count == 1
    args, kwargs = post.call_args
    url = args[0] if args else kwargs.get("url")
    assert url.endswith("/json_rpc")
    payload = kwargs["json"]
    assert payload["method"] == "generateblocks"
    posted_urls = [c.args[0] if c.args else c.kwargs.get("url") for c in post.call_args_list]
    assert not any(u.endswith("/start_mining") for u in posted_urls)


def test_legacy_request_transport_failure_becomes_rpc_error(mocker):
    """A RequestException from the session on a legacy endpoint becomes RPCError."""
    rpc = MoneroRPC("127.0.0.1", 18081)
    post = mocker.patch.object(rpc.session, "post")
    post.side_effect = requests.exceptions.ConnectionError("connection refused")

    with pytest.raises(RPCError, match="connection refused"):
        rpc.mining_status()
