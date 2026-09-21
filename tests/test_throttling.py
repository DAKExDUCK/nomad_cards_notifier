from modules.bot.throttling import ThrottleManager, rate_limit


def test_rate_limit_decorator_sets_handler_metadata():
    @rate_limit(1.5)
    def handler():
        pass

    assert handler.throttling_rate_limit == 1.5
    assert handler.throttling_key == "test_rate_limit_decorator_sets_handler_metadata.<locals>.handler"


def test_throttle_manager_blocks_calls_inside_rate_window(monkeypatch):
    current_time = iter([100.0, 100.2, 101.1])
    monkeypatch.setattr("modules.bot.throttling.time.time", lambda: next(current_time))
    manager = ThrottleManager()

    assert manager.is_throttled("key", 1.0) is False
    assert manager.is_throttled("key", 1.0) is True
    assert manager.is_throttled("key", 1.0) is False