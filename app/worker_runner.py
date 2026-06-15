import time

from app.worker import start_worker, stop_worker


def main() -> None:
    """
    Run the OB1 worker as a standalone process.

    This entrypoint prepares OB1 for future horizontally scalable worker
    deployments. It does not change the current local development mode unless
    explicitly used.
    """

    start_worker()

    try:
        while True:
            time.sleep(3600)

    except KeyboardInterrupt:
        stop_worker()


if __name__ == "__main__":
    main()