import PyInstaller.__main__
import os
import sys
import shutil
from datetime import datetime

# Работаем из папки скрипта, чтобы пути к Calculator.py и icon.ico находились
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def build_exe():
    print("🚀 Arma 3 Artillery Calculator - Сборка EXE")
    print("=" * 50)
    
    # Конфигурация
    CONFIG = {
        'script': 'Calculator.py',
        'name': 'Артиллерийский калькулятор 104-го ДОБ',
        'icon': 'icon.ico' if os.path.exists('icon.ico') else None,
        'version': '1.0.0',
        'author': 'SmaleUp',
    }
    
    # Очистка предыдущих сборок
    print("🧹 Очистка предыдущих сборок...")
    for folder in ['build', 'dist', '__pycache__']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    for spec in [f for f in os.listdir('.') if f.endswith('.spec')]:
        os.remove(spec)
    
    # Аргументы для PyInstaller
    args = [
        CONFIG['script'],
        f'--name={CONFIG["name"]}',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        '--noupx',  # Отключаем UPX для избежания ложных срабатываний антивируса
    ]
    
    # Добавляем иконку, если она есть
    if CONFIG['icon']:
        args.append(f'--icon={CONFIG["icon"]}')
        # Иконка ещё и внутрь exe — для заголовка окна программы
        args.append(f'--add-data={CONFIG["icon"]}{os.pathsep}.')
    
    # Скрытые импорты
    hidden_imports = [
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        'math',
    ]

    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')

    # saves.json в exe не вшиваем: программа хранит его рядом с exe

    print(f"\n⚙️  Параметры сборки:")
    print(f"   Имя приложения: {CONFIG['name']}")
    print(f"   Версия: {CONFIG['version']}")
    print(f"   Иконка: {'Есть' if CONFIG['icon'] else 'Нет'}")
    print(f"   Дата сборки: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    print("\n🔨 Начинаю сборку...")
    print("-" * 50)
    
    try:
        # Запуск PyInstaller
        PyInstaller.__main__.run(args)
        
        # Проверка результата
        exe_path = os.path.join('dist', f"{CONFIG['name']}.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            
            print("\n" + "=" * 50)
            print("✅ СБОРКА УСПЕШНО ЗАВЕРШЕНА!")
            print("=" * 50)
            print(f"\n📁 Файл: {exe_path}")
            print(f"📊 Размер: {size_mb:.1f} MB")
            print(f"\n🎮 Для запуска дважды щелкните по файлу")
            print("\n💡 Советы:")
            print("   - Антивирус может временно блокировать файл")
            print("   - Для первого запуска может потребоваться время")
            print("   - Сохраните файл в удобном месте")
            
            # Создаем README файл
            with open('README_BUILD.txt', 'w', encoding='utf-8') as f:
                f.write(f"""Артиллерийский калькулятор 104-го ДОБ
Версия: {CONFIG['version']}
Дата сборки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Исполняемый файл: {CONFIG['name']}.exe

Инструкция по установке:
1. Скопируйте файл {CONFIG['name']}.exe в любую папку
2. Запустите двойным щелчком

Системные требования:
- Windows 7/8/10/11
- .NET Framework не требуется
- 50 MB свободного места

Примечания:
- При первом запуске антивирус может запросить разрешение
- Установленный Python не требуется
- Сохранения хранятся в файле saves.json рядом с exe

Управление:
- Введите данные в поля
- Выберите режим расчета
- Нажмите "Рассчитать" (или Enter)

Автор: {CONFIG['author']}
""")
            
            print(f"\n📄 Создан файл README_BUILD.txt с инструкциями")
            
        else:
            print("\n❌ Ошибка: EXE файл не создан")
            
    except Exception as e:
        print(f"\n❌ Ошибка при сборке: {e}")
        print("\n🔧 Возможные решения:")
        print("   1. Установите PyInstaller: pip install pyinstaller")
        print("   2. Проверьте права доступа к папке")
        print("   3. Закройте все Python процессы")
        print("   4. Запустите от имени администратора")
    
    print("\nНажмите Enter для выхода...")
    input()

if __name__ == "__main__":
    build_exe()