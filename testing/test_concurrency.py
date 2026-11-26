from __future__ import annotations

import pytest
import wfwh
import time
import copy

from types import TracebackType
from threading import Event, Lock
from concurrent.futures import ThreadPoolExecutor

class ObservableLock:
    def __init__(self, original_lock: Lock, attempting: Event, acquired: Event, released_event: Event, continue_event: Event | None = None, contended: Event | None = None) -> None:
        self.original_lock = original_lock
        self.attempting = attempting
        self.acquired = acquired
        self.continue_event = continue_event
        self.released = released_event
        self.contended = contended

    def __enter__(self) -> ObservableLock:
        self.attempting.set()
        if not self.original_lock.acquire(blocking=False):
            if self.contended is not None:
                self.contended.set()
            self.original_lock.acquire()
        self.acquired.set()

        if self.continue_event is not None:
            if not self.continue_event.wait(timeout=5):
                self.original_lock.release()
                raise TimeoutError("Timed out while waiting to continue")
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.original_lock.release()
        self.released.set()
        return False

def print_contended(monkeypatch: pytest.MonkeyPatch, webhook_request: dict, other_request: dict | None = None):
    wfwh.init_app()
    app = wfwh.APP
    lock = wfwh.PROCESSING_LOCK
    a_attempting = Event()
    a_acquired = Event()
    a_released = Event()
    allow_a_to_continue = Event()

    b_attempting = Event()
    b_acquired = Event()
    b_released = Event()
    b_contended = Event()

    a_printed = Event()
    b_printed = Event()
    
    printed = []

    def send_request(request):
        client = app.test_client()
        return client.post(
            "/print",
            data=request["body"],
            headers=request["headers"],
            content_type="application/json",
        )

    def fake_write_to_output(receipt):
        printed.append(receipt)
        if not a_printed.is_set():
            a_printed.set()
            return
        b_printed.set()

    monkeypatch.setattr(wfwh, "format_lines_to_print", lambda data: f"Order: {data['code']}")
    monkeypatch.setattr(wfwh, "write_to_output", fake_write_to_output)
    monkeypatch.setattr(wfwh, "verify_webhook_v1_signature", lambda headers, raw_body: True)

    with ThreadPoolExecutor(max_workers=2) as threadpool:
        monkeypatch.setattr(wfwh, 'PROCESSING_LOCK', ObservableLock(lock, a_attempting, a_acquired, a_released, allow_a_to_continue))
        
        a_future = threadpool.submit(send_request, webhook_request)
        assert a_attempting.wait(timeout=5)
        assert a_acquired.wait(timeout=5)
        
        monkeypatch.setattr(wfwh, "PROCESSING_LOCK", ObservableLock(lock, b_attempting, b_acquired, b_released, contended=b_contended))
        contend_with = webhook_request if other_request is None else other_request
        b_future = threadpool.submit(send_request, contend_with)


        assert b_attempting.wait(timeout=5)
        assert b_contended.wait(timeout=5)

        # assert `b` has attempted lock acquisition but does not yet own it.
        assert not b_acquired.is_set()
        assert lock.locked()

        # allow `a` to complete and release the lock.
        allow_a_to_continue.set()

        # allow `a` has completed and released its lock.
        assert a_printed.wait(timeout=5)
        assert a_released.wait(timeout=5)

        # assert `b` has now acquired the lock.
        assert b_acquired.wait(timeout=5)
        if other_request is not None:
            assert b_printed.wait(timeout=5)
        assert b_released.wait(timeout=5)

        assert a_future.result(timeout=5).status_code == 200
        assert b_future.result(timeout=5).status_code == 200
    return printed

class TestPrintEndpointConcurrency:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(wfwh, 'PROCESSED_IDS', set())
        monkeypatch.setattr(wfwh, 'APP', None)

    def test_duplicate_request_one_print(self, monkeypatch: pytest.MonkeyPatch, webhook_request: dict):
        printed = print_contended(monkeypatch, webhook_request)
        assert len(printed) == 1

    def test_different_requests_two_prints(self, monkeypatch: pytest.MonkeyPatch, webhook_request: dict):
        other_request = copy.deepcopy(webhook_request)
        other_request['headers']['webhook-id'] = 'msg321'
        other_request['headers']['webhook-timestamp'] = str(int(time.time()))
        printed = print_contended(monkeypatch, webhook_request, other_request=other_request)
        assert len(printed) == 2

class TestWriteToOutputConcurrency:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        monkeypatch.setattr(wfwh, 'OUTPUT_PATH', (tmp_path / 'output.bin'))

    def test_print_lock(self, monkeypatch: pytest.MonkeyPatch):
        lock = wfwh.OUTPUT_LOCK
        a_attempting = Event()
        a_acquired = Event()
        a_released = Event()
        allow_a_to_continue = Event()

        b_attempting = Event()
        b_acquired = Event()
        b_released = Event()
        b_contended = Event()

        text = 'example-text'
        with ThreadPoolExecutor(max_workers=2) as threadpool:
            monkeypatch.setattr(wfwh, 'OUTPUT_LOCK', ObservableLock(lock, a_attempting, a_acquired, a_released, allow_a_to_continue))
            
            a_future = threadpool.submit(wfwh.write_to_output, text)
            assert a_attempting.wait(timeout=5)
            assert a_acquired.wait(timeout=5)
            
            monkeypatch.setattr(wfwh, "OUTPUT_LOCK", ObservableLock(lock, b_attempting, b_acquired, b_released, contended=b_contended))
            b_future = threadpool.submit(wfwh.write_to_output, text)

            assert b_attempting.wait(timeout=5)
            assert b_contended.wait(timeout=5)

            # assert `b` has attempted lock acquisition but does not yet own it.
            assert not b_acquired.is_set()
            assert lock.locked()

            # allow `a` to complete and release the lock.
            allow_a_to_continue.set()

            # allow `a` has completed and released its lock.
            assert a_released.wait(timeout=5)

            # assert `b` has now acquired the lock.
            assert b_acquired.wait(timeout=5)
            assert b_released.wait(timeout=5)

            a_future.result(timeout=5)
            b_future.result(timeout=5)