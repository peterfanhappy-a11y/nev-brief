"""Prove delivery preflight and unsubscribe serialize on the subscriber row."""

from __future__ import annotations

import sys
import threading
import time

import psycopg
from ai_brief.storage import lock_active_subscriber


def main() -> int:
    database_url, subscriber_id = sys.argv[1:3]
    update_started = threading.Event()
    update_finished = threading.Event()
    worker_error: list[BaseException] = []
    worker_pid: list[int] = []

    def unsubscribe() -> None:
        try:
            with psycopg.connect(database_url) as connection:
                row = connection.execute("SELECT pg_backend_pid()").fetchone()
                if row is None:
                    raise AssertionError("unsubscribe worker has no backend pid")
                worker_pid.append(row[0])
                update_started.set()
                connection.execute(
                    """
                    UPDATE ai_subscribers
                    SET status = 'unsubscribed', unsubscribed_at = NOW()
                    WHERE id = %s
                    """,
                    (subscriber_id,),
                )
        except BaseException as error:  # noqa: BLE001 - propagate thread failure
            worker_error.append(error)
        finally:
            update_finished.set()

    with psycopg.connect(database_url) as delivery_connection:
        if not lock_active_subscriber(
            delivery_connection,
            subscriber_id=subscriber_id,
        ):
            raise AssertionError("delivery preflight did not observe an active subscriber")

        worker = threading.Thread(target=unsubscribe, daemon=True)
        worker.start()
        if not update_started.wait(timeout=2):
            raise AssertionError("unsubscribe worker did not start")
        deadline = time.monotonic() + 2
        observed_lock_wait = False
        with psycopg.connect(database_url) as observer:
            while time.monotonic() < deadline:
                wait = observer.execute(
                    "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                    (worker_pid[0],),
                ).fetchone()
                if wait is not None and wait[0] == "Lock":
                    observed_lock_wait = True
                    break
                if update_finished.wait(timeout=0.02):
                    break
        if not observed_lock_wait:
            raise AssertionError("unsubscribe did not wait on the delivery subscriber lock")
        delivery_connection.commit()

    worker.join(timeout=2)
    if worker.is_alive():
        raise AssertionError("unsubscribe did not complete after delivery commit")
    if worker_error:
        raise worker_error[0]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
