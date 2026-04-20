#!/usr/bin/env python3
"""
Проверка наличия необходимых зависимостей.
"""
import sys

REQUIRED = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "redis",
    "kafka",
    "yaml",
    "prometheus_client",
    "pythonjsonlogger",
]

def check():
    missing = []
    for package in REQUIRED:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        print("Отсутствуют следующие зависимости:")
        for p in missing:
            print(f"  - {p}")
        print("\nУстановите их командой:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    else:
        print("Все зависимости установлены.")
        sys.exit(0)

if __name__ == "__main__":
    check()