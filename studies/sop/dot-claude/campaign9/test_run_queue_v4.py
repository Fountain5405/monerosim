import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from run_queue_v4 import decide, parse_go


def test_parse_go():
    assert parse_go("2\n") == 2 and parse_go("") == 0 and parse_go("x") == 0 and parse_go(None) == 0


def test_decide():
    assert decide(0, False, 0, 4) == "wait"
    assert decide(2, False, 0, 4) == "start" and decide(2, False, 1, 4) == "start"
    assert decide(2, False, 2, 4) == "wait"
    assert decide(4, True, 1, 4) == "stop" and decide(4, False, 4, 4) == "stop"
