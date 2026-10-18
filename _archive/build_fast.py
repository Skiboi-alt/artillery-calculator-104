#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Быстрая сборка exe (режим по умолчанию - малый размер)
"""

import PyInstaller.__main__
import os
import shutil
from datetime import datetime

# Определяем директорию скрипта и изменяем рабочую директорию
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

def build_fast():
    """Быстрая сборка с оптимизацией размера"""
    
    print("🚀 Быстрая сборка Artillery Calculator")
    print("=" * 50)
    
    # Конфигурация
    config = {
        'script': 'Calculator.py',
        'name': 'Артиллерийский калькулятор 104-го ДОБ',
        'icon': 'icon.ico' if os.path.exists('icon.ico') else None,
    }
    
    # Очистка предыдущих сборок
    print("🧹 Очистка...")
    for folder in ['build', 'dist', '__pycache__']:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)
    
    # Аргументы для PyInstaller
    args = [
        config['script'],
        f'--name={config["name"]}',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        '--optimize=2',  # Максимальная оптимизация
    ]

    # --strip требует утилиту strip (binutils), на Windows её обычно нет
    if os.name != 'nt':
        args.append('--strip')

    # Добавляем иконку
    if config['icon']:
        args.append(f'--icon={config["icon"]}')
        # Иконка ещё и внутрь exe — для заголовка окна программы
        args.append(f'--add-data={config["icon"]}{os.pathsep}.')
    
    # Скрытые импорты
    for imp in ['tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.simpledialog', 'json', 'math']:
        args.append(f'--hidden-import={imp}')
    
    # saves.json в exe не вшиваем: программа хранит его рядом с exe

    print("🔨 Сборка...")
    print("-" * 50)
    
    try:
        PyInstaller.__main__.run(args)
        
        exe_path = os.path.join('dist', f"{config['name']}.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print("\n" + "=" * 50)
            print("✅ СБОРКА ЗАВЕРШЕНА!")
            print("=" * 50)
            print(f"📁 Файл: {exe_path}")
            print(f"📊 Размер: {size_mb:.2f} MB")
            print("\n💡 Файл готов к использованию!")
        else:
            print("❌ Ошибка: EXE не создан")
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("\nУстановите PyInstaller: pip install pyinstaller --upgrade")

if __name__ == "__main__":
    build_fast()
