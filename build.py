"""Сборка exe: python build.py

Перед сборкой прогоняет тесты расчёта — если они не проходят, exe не собирается.
Нужен PyInstaller: pip install pyinstaller
"""

import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "Артиллерийский калькулятор 104-го ДОБ"
ICON = "icon.ico"


def run_tests():
    print("Тесты расчёта…")
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT)
    return result.returncode == 0


def build():
    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        print("Не найден PyInstaller. Установите: pip install pyinstaller")
        return False

    for folder in ("build", "dist"):
        shutil.rmtree(os.path.join(ROOT, folder), ignore_errors=True)

    args = [
        "Calculator.py",
        f"--name={NAME}",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--optimize=2",
        # Не тащим в exe то, что программе не нужно
        "--exclude-module=PIL",
        "--exclude-module=unittest",
        "--exclude-module=pydoc",
    ]
    if os.path.exists(os.path.join(ROOT, ICON)):
        args += [f"--icon={ICON}", f"--add-data={ICON}{os.pathsep}."]  # Иконка exe и окна

    pyinstaller.run(args)

    exe = os.path.join(ROOT, "dist", f"{NAME}.exe")
    if not os.path.exists(exe):
        print("Ошибка: exe не создан")
        return False
    size_mb = os.path.getsize(exe) / (1024 * 1024)
    print(f"\nГотово: {exe}\nРазмер: {size_mb:.1f} МБ\nСобрано: {time.strftime('%Y-%m-%d %H:%M')}")
    print("Сохранения и настройки программа хранит рядом с exe (saves.json, settings.json).")
    return True


def main():
    os.chdir(ROOT)
    if "--skip-tests" not in sys.argv and not run_tests():
        print("\nТесты не прошли — сборка остановлена. (Пропустить: python build.py --skip-tests)")
        sys.exit(1)
    sys.exit(0 if build() else 1)


if __name__ == "__main__":
    main()
