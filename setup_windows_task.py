import os
import subprocess
import sys

from config.settings import AUTO_RUN_TIME


TASK_NAME = "Naukri_Guru_Daily_Auto_Run"


def validate_auto_run_time() -> None:
    parts = AUTO_RUN_TIME.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError('AUTO_RUN_TIME must use 24-hour "HH:MM" format, example "06:00".')
    hour, minute = int(parts[0]), int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('AUTO_RUN_TIME must use 24-hour "HH:MM" format, example "06:00".')


def project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def python_executable() -> str:
    venv_python = os.path.join(project_root(), "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable


def install_task() -> int:
    validate_auto_run_time()
    command = f'"{python_executable()}" "{os.path.join(project_root(), "run_scheduled.py")}"'
    result = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            TASK_NAME,
            "/SC",
            "DAILY",
            "/ST",
            AUTO_RUN_TIME,
            "/TR",
            command,
            "/F",
        ],
        text=True,
        capture_output=True,
    )
    print(result.stdout or result.stderr)
    return result.returncode


def uninstall_task() -> int:
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        text=True,
        capture_output=True,
    )
    print(result.stdout or result.stderr)
    return result.returncode


def main() -> int:
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "install"
    if action == "install":
        return install_task()
    if action in {"uninstall", "remove", "delete"}:
        return uninstall_task()
    print("Usage: python setup_windows_task.py [install|uninstall]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
