from __future__ import annotations

import logging
import os
import signal
import socket
import threading

from anthropic import Anthropic

from memory_mcp.distiller.service import DistillerService

log = logging.getLogger(__name__)


def run_loop(service: DistillerService, *, stop_event: threading.Event,
             idle_sleep: float = 2.0, busy_sleep: float = 0.0) -> None:
    """Poll the staging queue until stop_event is set."""
    while not stop_event.is_set():
        try:
            processed = service.distill_once()
        except Exception:  # noqa: BLE001
            log.exception("distill_once raised; backing off")
            stop_event.wait(idle_sleep)
            continue
        stop_event.wait(busy_sleep if processed > 0 else idle_sleep)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
    service = DistillerService(client=client, worker_id=worker_id)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    log.info("distiller worker %s starting", worker_id)
    run_loop(service, stop_event=stop)
    log.info("distiller worker %s exiting", worker_id)


if __name__ == "__main__":
    main()
