import httpx
import pytest
from fastapi.testclient import TestClient

from app import Settings, create_app

H = {"X-API-Key": "secret-1"}


def make(handler, **kw):
    s = Settings(bot_token="123:TOKEN", chat_ids=kw.pop("chats", ["-100111"]),
                 api_keys={"dev1": "secret-1"}, cache_ttl=kw.pop("ttl", 45),
                 rate_limit_per_min=kw.pop("rate", 60))
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TestClient(create_app(s, client))


def tg(status=None, ok=True, desc=None, **extra):
    if not ok:
        return httpx.Response(400, json={"ok": False, "description": desc})
    return httpx.Response(200, json={"ok": True, "result": {"status": status, **extra}})


def test_member_true():
    c = make(lambda r: tg("member"))
    assert c.get("/check", params={"telegram_id": 5}, headers=H).json() == {"telegram_id": 5, "in_course": True}


@pytest.mark.parametrize("st", ["left", "kicked"])
def test_not_member(st):
    c = make(lambda r: tg(st))
    assert c.get("/check", params={"telegram_id": 5}, headers=H).json()["in_course"] is False


def test_restricted_still_member_or_not():
    assert make(lambda r: tg("restricted", is_member=True)).get("/check", params={"telegram_id": 5}, headers=H).json()["in_course"] is True
    assert make(lambda r: tg("restricted", is_member=False)).get("/check", params={"telegram_id": 5}, headers=H).json()["in_course"] is False


def test_unknown_user_is_false():
    c = make(lambda r: tg(ok=False, desc="Bad Request: user not found"))
    assert c.get("/check", params={"telegram_id": 5}, headers=H).json()["in_course"] is False


def test_config_error_is_502_not_false():
    c = make(lambda r: tg(ok=False, desc="Bad Request: chat not found"))
    assert c.get("/check", params={"telegram_id": 5}, headers=H).status_code == 502


def test_network_error_is_502():
    def boom(r):
        raise httpx.ConnectError("down")
    assert make(boom).get("/check", params={"telegram_id": 5}, headers=H).status_code == 502


def test_auth():
    c = make(lambda r: tg("member"))
    assert c.get("/check", params={"telegram_id": 5}).status_code == 401
    assert c.get("/check", params={"telegram_id": 5}, headers={"X-API-Key": "bad"}).status_code == 401


def test_validation():
    c = make(lambda r: tg("member"))
    assert c.get("/check", params={"telegram_id": "abc"}, headers=H).status_code == 422
    assert c.get("/check", params={"telegram_id": -1}, headers=H).status_code == 422


def test_cache_limits_telegram_calls():
    calls = []
    def h(r):
        calls.append(1)
        return tg("member")
    c = make(h)
    for _ in range(5):
        c.get("/check", params={"telegram_id": 7}, headers=H)
    assert len(calls) == 1


def test_errors_not_cached():
    seq = [tg(ok=False, desc="Bad Request: chat not found"), tg("member")]
    c = make(lambda r: seq.pop(0))
    assert c.get("/check", params={"telegram_id": 9}, headers=H).status_code == 502
    assert c.get("/check", params={"telegram_id": 9}, headers=H).json()["in_course"] is True


def test_multiple_chats_any():
    def h(r):
        return tg("member") if r.url.params["chat_id"] == "-100222" else tg("left")
    c = make(h, chats=["-100111", "-100222"])
    assert c.get("/check", params={"telegram_id": 5}, headers=H).json()["in_course"] is True


def test_rate_limit():
    c = make(lambda r: tg("member"), rate=3)
    codes = [c.get("/check", params={"telegram_id": i + 1}, headers=H).status_code for i in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_token_not_leaked_in_responses():
    c = make(lambda r: tg(ok=False, desc="Unauthorized"))
    r = c.get("/check", params={"telegram_id": 5}, headers=H)
    assert "TOKEN" not in r.text
