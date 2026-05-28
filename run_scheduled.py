import os
import sys

from config.settings import AUTO_RUN_ENABLED
from modules.helpers import print_lg

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "scheduled_run.lock")


class RunLock:
    def __enter__(self):
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        try:
            self.fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.fd, str(os.getpid()).encode("utf-8"))
            return self
        except FileExistsError:
            print_lg("Scheduled run skipped because another scheduled run appears to be active.")
            return None

    def __exit__(self, exc_type, exc, tb):
        if getattr(self, "fd", None) is not None:
            os.close(self.fd)
            try:
                os.remove(LOCK_FILE)
            except FileNotFoundError:
                pass


def main() -> int:
    if "--check" in sys.argv:
        print_lg(f"Scheduled runner check OK. AUTO_RUN_ENABLED={AUTO_RUN_ENABLED}.")
        return 0

    if not AUTO_RUN_ENABLED:
        print_lg("Scheduled run skipped because AUTO_RUN_ENABLED is False.")
        return 0

    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    os.environ["NAUKRI_GURU_AUTO_RUN"] = "1"

    with RunLock() as lock:
        if lock is None:
            return 0

        from runAiBot import main as run_bot

        print_lg("Scheduled run accepted. Starting bot.")
        run_bot()
        print_lg("Scheduled run finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
