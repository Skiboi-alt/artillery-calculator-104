#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оптимизированный скрипт сборки exe для Artillery Calculator
Поддерживает различные варианты оптимизации размера
"""

import PyInstaller.__main__
import os
import sys
import shutil
from datetime import datetime
import subprocess

# Определяем директорию скрипта
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)  # Изменяем рабочую директорию на директорию скрипта

# Конфигурация
CONFIG = {
    'script': 'Calculator.py',
    'name': 'Артиллерийский калькулятор 104-го ДОБ',
    'icon': 'icon.ico',
    'version': '1.1.0',
    'author': 'SmaleUp',
}

# Варианты оптимизации
OPTIMIZATION_MODES = {
    'standard': {
        'name': 'Стандартная сборка',
        'description': 'Полная функциональность, нормальный размер',
        'options': []
    },
    'small': {
        'name': 'Малый размер (рекомендуется)',
        'description': 'Оптимизирована на размер файла, полная функциональность',
        'options': [
            '--strip',  # Удалить символы отладки
            '--optimize=2',  # Максимальная оптимизация Python
            '--collect-submodules=tkinter',
        ]
    },
    'minimal': {
        'name': 'Минимальный размер',
        'description': 'Максимальная оптимизация, может потребоваться UPX',
        'options': [
            '--strip',
            '--optimize=2',
            '--collect-submodules=tkinter',
            '--noupx',
        ]
    },
}

def clear_previous_builds():
    """Очистка предыдущих сборок"""
    print("🧹 Очистка предыдущих сборок...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__', '.pytest_cache']
    for folder in dirs_to_clean:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)
            print(f"   ✓ Удалена папка: {folder}")
    
    # Удаляем старые .spec файлы
    for spec_file in [f for f in os.listdir('.') if f.endswith('.spec')]:
        os.remove(spec_file)
        print(f"   ✓ Удален файл: {spec_file}")

def display_optimization_options():
    """Показать доступные варианты оптимизации"""
    print("\n" + "="*60)
    print("ВАРИАНТЫ ОПТИМИЗАЦИИ РАЗМЕРА EXE")
    print("="*60)
    
    for idx, (key, opt) in enumerate(OPTIMIZATION_MODES.items(), 1):
        print(f"\n{idx}. {opt['name']}")
        print(f"   Описание: {opt['description']}")
    
    print("\n" + "="*60)

def get_user_choice():
    """Получить выбор пользователя"""
    while True:
        try:
            choice = input("\nВыберите вариант (1-3) или 'q' для выхода: ").strip().lower()
            
            if choice == 'q':
                print("Сборка отменена")
                sys.exit(0)
            
            choice_map = {'1': 'standard', '2': 'small', '3': 'minimal'}
            if choice in choice_map:
                return choice_map[choice]
            
            print("❌ Пожалуйста, выберите корректный вариант")
        except KeyboardInterrupt:
            print("\nСборка отменена")
            sys.exit(0)

def build_exe(mode='small'):
    """Сборка exe файла"""
    
    print(f"\n{'='*60}")
    print(f"🔨 СБОРКА EXE - {OPTIMIZATION_MODES[mode]['name'].upper()}")
    print(f"{'='*60}")
    
    # Очистка предыдущих сборок
    clear_previous_builds()
    
    # Проверка иконки
    if CONFIG['icon'] and not os.path.exists(CONFIG['icon']):
        print(f"\n⚠️  Иконка '{CONFIG['icon']}' не найдена!")
        CONFIG['icon'] = None
    
    # Базовые аргументы
    args = [
        CONFIG['script'],
        f'--name={CONFIG["name"]}',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
    ]
    
    # Добавляем иконку
    if CONFIG['icon']:
        args.append(f'--icon={CONFIG["icon"]}')
        # Иконка ещё и внутрь exe — для заголовка окна программы
        args.append(f'--add-data={CONFIG["icon"]}{os.pathsep}.')
        print(f"✓ Используется иконка: {CONFIG['icon']}")
    
    # Скрытые импорты
    hidden_imports = [
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        'json',
        'math',
        'os',
    ]
    
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')
    
    # Добавляем специфические опции оптимизации
    # (--strip требует утилиту strip из binutils, на Windows её обычно нет)
    for option in OPTIMIZATION_MODES[mode]['options']:
        if option == '--strip' and os.name == 'nt':
            continue
        args.append(option)

    # saves.json в exe не вшиваем: программа хранит его рядом с exe

    print(f"\n📝 Параметры сборки:")
    print(f"   Название: {CONFIG['name']}")
    print(f"   Версия: {CONFIG['version']}")
    print(f"   Иконка: {'Есть' if CONFIG['icon'] else 'Нет'}")
    print(f"   Режим оптимизации: {OPTIMIZATION_MODES[mode]['name']}")
    print(f"   Дата сборки: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    print(f"\n🚀 Начинаю сборку...")
    print("-" * 60)
    
    try:
        # Запуск PyInstaller
        PyInstaller.__main__.run(args)
        
        # Проверка результата
        exe_path = os.path.join('dist', f"{CONFIG['name']}.exe")
        
        if os.path.exists(exe_path):
            size_bytes = os.path.getsize(exe_path)
            size_mb = size_bytes / (1024 * 1024)
            
            print("\n" + "="*60)
            print("✅ СБОРКА УСПЕШНО ЗАВЕРШЕНА!")
            print("="*60)
            print(f"\n📁 Файл: {exe_path}")
            print(f"📊 Размер: {size_mb:.2f} MB ({size_bytes:,} байт)")
            print(f"📅 Время сборки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            print(f"\n💡 Советы:")
            print(f"   • Антивирус может временно блокировать файл")
            print(f"   • При первом запуске может потребоваться время")
            print(f"   • Сохраняйте файл в удобном месте")
            
            # Сравнение размеров
            print(f"\n📈 Информация об оптимизации:")
            if mode == 'standard':
                print(f"   • Используется режим: {OPTIMIZATION_MODES['standard']['name']}")
                print(f"   • Совет: для меньшего размера используйте режим 'small'")
            elif mode == 'small':
                print(f"   • Используется режим: {OPTIMIZATION_MODES['small']['name']}")
                print(f"   • Размер оптимизирован")
                print(f"   • Полная функциональность сохранена")
            else:
                print(f"   • Используется режим: {OPTIMIZATION_MODES['minimal']['name']}")
                print(f"   • Максимальная оптимизация")
            
            # Создание файла информации
            info_file = 'BUILD_INFO.txt'
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write(f"""ИНФОРМАЦИЯ О СБОРКЕ
{'='*60}

Название: {CONFIG['name']}
Версия: {CONFIG['version']}
Дата сборки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Размер файла: {size_mb:.2f} MB
Режим оптимизации: {OPTIMIZATION_MODES[mode]['name']}

{'='*60}

СИСТЕМНЫЕ ТРЕБОВАНИЯ:
• Windows 7/8/10/11 (64-bit рекомендуется)
• .NET Framework не требуется
• ~50-60 MB свободного места на диске

УСТАНОВКА И ИСПОЛЬЗОВАНИЕ:
1. Скопируйте файл {CONFIG['name']}.exe в удобное место
2. Нажмите два раза на файл для запуска
3. При первом запуске может потребоваться время распаковки

ВОЗМОЖНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ:

Проблема: "Файл может быть опасен"
Решение: Это нормально для новых exe файлов. Антивирус проверит
         файл при первом запуске.

Проблема: Медленный запуск в первый раз
Решение: PyInstaller распаковывает файлы в %TEMP% при первом запуске.
         Последующие запуски будут быстрее.

Проблема: "Требуется администратор"
Решение: Это не требуется. Проверьте права доступа к папке.

ВАРИАНТЫ ОПТИМИЗАЦИИ РАЗМЕРА:

1. Standard (стандартная)
   - Полная функциональность
   - Размер: ~70-80 MB

2. Small (малый размер)
   - Удалены символы отладки
   - Применена оптимизация Python
   - Размер: ~50-60 MB
   - РЕКОМЕНДУЕТСЯ

3. Minimal (минимальный)
   - Максимальная оптимизация
   - Может потребоваться UPX
   - Размер: ~30-40 MB

ДОПОЛНИТЕЛЬНЫЕ ОПЦИИ ОПТИМИЗАЦИИ:

Если вам нужен еще меньший размер:

1. Установите UPX (Ultimate Packer for eXecutables)
   pip install upx-python
   pyinstaller ... --upx-dir=/path/to/upx

2. Удалите ненужные модули tkinter
   pyinstaller ... --exclude-module matplotlib

3. Используйте --onefile с --strip

СКРИПТЫ БЫСТРОЙ СБОРКИ:

• python build_optimized.py    - интерактивная сборка
• python build_fast.py         - сборка по умолчанию (малый размер)

КОНТАКТ И ПОДДЕРЖКА:
Автор: {CONFIG['author']}
Версия утилиты сборки: 1.1.0

{'='*60}
""")
            
            print(f"\n📄 Информация сохранена в: {info_file}")
            
            return True
        else:
            print("\n❌ Ошибка: EXE файл не создан")
            return False
    
    except Exception as e:
        print(f"\n❌ Ошибка при сборке: {e}")
        print("\n🔧 Возможные решения:")
        print("   1. Установите PyInstaller: pip install pyinstaller --upgrade")
        print("   2. Проверьте права доступа к папке")
        print("   3. Закройте все Python процессы")
        print("   4. Запустите от имени администратора")
        print("   5. Удалите папки build/ и dist/ вручную")
        return False

def print_size_comparison():
    """Показать примерное сравнение размеров"""
    print("\n" + "="*60)
    print("ПРИМЕРНОЕ СРАВНЕНИЕ РАЗМЕРОВ EXE")
    print("="*60)
    
    sizes = {
        'standard': {'min': 70, 'max': 85},
        'small': {'min': 50, 'max': 65},
        'minimal': {'min': 30, 'max': 45},
    }
    
    for mode, size_range in sizes.items():
        mode_name = OPTIMIZATION_MODES[mode]['name']
        print(f"\n{mode_name}:")
        print(f"  Примерный размер: {size_range['min']}-{size_range['max']} MB")
        
        if mode == 'small':
            print(f"  ⭐ Рекомендуется - оптимальное соотношение размер/функциональность")
        elif mode == 'minimal':
            print(f"  ⚠️  Требует UPX для дополнительного сжатия")

def main():
    """Главная функция"""
    print("\n" + "="*60)
    print("⚙️  АРТИЛЛЕРИЙСКИЙ КАЛЬКУЛЯТОР - СБОРКА EXE")
    print("="*60)
    
    # Показываем варианты оптимизации
    display_optimization_options()
    print_size_comparison()
    
    # Получаем выбор пользователя
    mode = get_user_choice()
    
    # Выполняем сборку
    success = build_exe(mode)
    
    if success:
        print("\n" + "="*60)
        print("Сборка завершена успешно! ✅")
        print("="*60)
    
    input("\nНажмите Enter для завершения...")

if __name__ == "__main__":
    main()
