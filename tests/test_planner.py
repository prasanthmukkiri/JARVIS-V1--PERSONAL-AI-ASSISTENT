import sys
from pathlib import Path

# ensure repo root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.planner import create_plan


def test_direct_message_plan_is_local():
    plan = create_plan("send a message to John saying hello")
    assert plan["goal"] == "send a message to John saying hello"
    assert len(plan["steps"]) == 1
    step = plan["steps"][0]
    assert step["tool"] == "send_message"
    assert step["parameters"]["receiver"] == "John"
    assert step["parameters"]["message_text"] == "hello"


def test_open_app_plan_is_local():
    plan = create_plan("open chrome")
    assert len(plan["steps"]) == 1
    step = plan["steps"][0]
    assert step["tool"] == "open_app"
    assert step["parameters"]["app_name"].lower() == "chrome"


def test_web_search_plan_is_local():
    plan = create_plan("search for python tutorials")
    assert len(plan["steps"]) == 1
    step = plan["steps"][0]
    assert step["tool"] == "web_search"
    assert "python tutorials" in step["parameters"]["query"].lower()
