#!/usr/bin/env python3
"""
Скрипт автоматической установки зависимостей для загрузчика видео
"""

import subprocess
import sys
import os
from pathlib import Path


def check_python_version():
    """Проверка версии Python"""
    print("🐍 Проверяем версию Python...")
    print(f"Текущая версия: Python {sys.version}")


    if sys.version_info < (3, 9):
        print("❌ Требуется Python 3.9 или выше!")
        print("📋 Скачайте с https://www.python.org/downloads/")
        return False

    if sys.version_info < (3, 10):
        print("⚠️ Рекомендуется Python 3.10+ для лучшей совместимости")
    else:
        print("✅ Версия Python подходит")

    return True


def install_package(package_name, description=""):
    """Установка пакета через pip"""
    try:
        print(f"⬇️ Устанавливаем {package_name}...")
        if description:
            print(f"   {description}")

        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', '--upgrade', package_name
        ], capture_output=True, text=True, check=True)

        print(f"✅ {package_name} установлен успешно")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки {package_name}: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка при установке {package_name}: {e}")
        return False


def create_config_if_missing():
    """Создание config.yaml если отсутствует"""
    config_path = Path("config.yaml")

    if config_path.exists():
        print("✅ config.yaml уже существует")
        return

    print("📝 Создаем config.yaml...")

    config_content = """# Конфигурационный файл для загрузчика видео
# Основные настройки
download_settings:
  download_directory: "Downloads"
  max_concurrent_downloads: 3
  max_file_size_mb: 500
  write_subtitles: true
  write_auto_subtitles: false

# Настройки качества по умолчанию
quality_settings:
  max_video_height: 1080
  audio_quality: "192"
  preferred_video_codec: "h264"
  preferred_audio_codec: "aac"

# Настройки плейлистов
playlist_settings:
  max_playlist_items: 100
  create_playlist_folders: true
  download_playlists_by_default: false

# Настройки сети
network_settings:
  socket_timeout: 30
  http_chunk_size: 10485760
  retries: 5
  prefer_ipv6: false

# Настройки логирования
logging_settings:
  level: "INFO"
  max_log_file_size: 10
  backup_count: 5
  console_output: true
"""

    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        print("✅ config.yaml создан")
    except Exception as e:
        print(f"❌ Ошибка создания config.yaml: {e}")


def main():
    """Основная функция установки"""
    print("🚀 Установка зависимостей для загрузчика видео")
    print("=" * 60)

    # Проверка Python
    if not check_python_version():
        input("Нажмите Enter для выхода...")
        return

    print("\n📦 Устанавливаем необходимые пакеты...")

    # Список пакетов для установки
    packages = [
        ("pip", "Менеджер пакетов Python"),
        ("yt-dlp", "Загрузчик видео с YouTube и других платформ"),
        ("pyyaml", "Обработка YAML конфигурационных файлов"),
    ]

    success_count = 0

    for package, description in packages:
        if install_package(package, description):
            success_count += 1
        print()

    print("=" * 60)
    print(f"📊 Установлено пакетов: {success_count}/{len(packages)}")

    if success_count == len(packages):
        print("✅ Все пакеты установлены успешно!")

        # Создаем конфигурационный файл
        create_config_if_missing()

        print("\n🎉 Установка завершена!")
        print("📝 Теперь можете запустить: python main.py")

    else:
        print("⚠️ Некоторые пакеты не установились")
        print("🔧 Попробуйте установить вручную:")
        print("   pip install yt-dlp pyyaml")

    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()