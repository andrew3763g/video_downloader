import os
import csv
import datetime
import re
from yt_dlp import YoutubeDL

def check_yt_dlp_version():
    """Проверка и обновление yt-dlp"""
    try:
        import subprocess
        result = subprocess.run(['pip', 'show', 'yt-dlp'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    version = line.split(':')[1].strip()
                    print(f"📦 Версия yt-dlp: {version}")
                    break
        else:
            print("⚠️ yt-dlp не найден")
    except Exception:
        print("⚠️ Не удалось проверить версию yt-dlp")

# Настройки путей
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'Downloads')
LOG_FILE = os.path.join(os.getcwd(), 'downloads_log.csv')


def setup_directories():
    """Создание необходимых папок и файлов"""
    # Создаем папку для загрузок, если её нет
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"📁 Папка загрузок: {DOWNLOAD_DIR}")

    # Создаем файл журнала с заголовками, если его нет
    if not os.path.isfile(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Формат', 'Время загрузки', 'Источник', 'URL', 'Название',
                'Теги', 'Путь к файлу',
                'Плейлист', 'Загрузил', 'Автоудаление',
                'Прокси', 'Заметки'
            ])
        print(f"📋 Создан файл журнала: {LOG_FILE}")
    else:
        print(f"📋 Используется существующий журнал: {LOG_FILE}")


def get_video_source(url):
    """Определение источника видео по URL"""
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'YouTube'
    elif 'tiktok.com' in url_lower:
        return 'TikTok'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'Facebook'
    elif 'instagram.com' in url_lower:
        return 'Instagram'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'Twitter/X'
    elif 'vk.com' in url_lower or 'vk.ru' in url_lower:
        return 'VK'
    else:
        return 'Другое'


def sanitize_filename(filename):
    """Очистка имени файла от недопустимых символов"""
    # Убираем недопустимые символы для имен файлов
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Ограничиваем длину имени файла
    if len(filename) > 200:
        filename = filename[:200]
    return filename.strip()


def log_download(info_dict, output_format, url, file_path, downloaded_by='Andrey',
                 playlist_name='', proxy_used=False, notes=''):
    """Запись информации о скачанном видео в журнал"""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Получаем информацию из словаря
    title = info_dict.get('title', 'Неизвестное название')
    tags = ', '.join(info_dict.get('tags', [])) if info_dict.get('tags') else 'Нет тегов'

    try:
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                output_format,
                timestamp,
                get_video_source(url),
                url,
                title,
                tags,
                file_path,
                playlist_name,
                downloaded_by,
                '',  # Автоудаление (заполняется вручную при необходимости)
                'Да' if proxy_used else 'Нет',
                notes
            ])
        print(f"📝 Запись добавлена в журнал")
        return True
    except Exception as e:
        print(f"❌ Ошибка записи в журнал: {e}")
        return False


def download_video(url, output_format='mp4', downloaded_by='Andrey',
                   playlist_name='', proxy_used=False, notes=''):
    """Основная функция загрузки видео"""

    print(f"🔄 Начинаем загрузку с {get_video_source(url)}...")
    print(f"🔗 URL: {url}")
    print(f"📹 Формат: {output_format}")

    # Настройки для yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best' if output_format == 'mp3' else 'best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': False,  # Показываем прогресс загрузки
        'no_warnings': False,
        'noplaylist': True,  # Скачиваем только одно видео, не весь плейлист
    }

    # Добавляем постобработку для MP3
    if output_format == 'mp3':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with YoutubeDL(ydl_opts) as ydl:
            print("📊 Получаем информацию о видео...")

            # Сначала получаем информацию без загрузки
            info_dict = ydl.extract_info(url, download=False)

            if not info_dict:
                print("❌ Не удалось получить информацию о видео")
                return False

            # Получаем и очищаем название
            original_title = info_dict.get('title', 'Unknown_Video')
            clean_title = sanitize_filename(original_title)

            # Определяем расширение файла
            if output_format == 'mp3':
                ext = 'mp3'
            else:
                ext = info_dict.get('ext', 'mp4')

            # Формируем полный путь к файлу
            filename = f"{clean_title}.{ext}"
            expected_file_path = os.path.join(DOWNLOAD_DIR, filename)

            print(f"📄 Название: {original_title}")
            print(f"💾 Файл будет сохранен как: {filename}")

            # Теперь загружаем видео
            print("⬇️ Загружаем видео...")
            ydl.download([url])

            # Проверяем, что файл действительно скачался
            if os.path.exists(expected_file_path):
                actual_file_path = expected_file_path
                print(f"✅ Файл успешно загружен: {filename}")
            else:
                # Ищем файл в папке загрузок (иногда yt-dlp меняет имя)
                downloaded_files = []
                for file in os.listdir(DOWNLOAD_DIR):
                    file_path = os.path.join(DOWNLOAD_DIR, file)
                    if os.path.isfile(file_path):
                        file_time = os.path.getctime(file_path)
                        downloaded_files.append((file_time, file_path, file))

                if downloaded_files:
                    # Берем самый новый файл
                    downloaded_files.sort(reverse=True)
                    actual_file_path = downloaded_files[0][1]
                    actual_filename = downloaded_files[0][2]
                    print(f"✅ Файл загружен как: {actual_filename}")
                else:
                    print("❌ Не удалось найти загруженный файл")
                    return False

            # Записываем в журнал
            print("📝 Записываем информацию в журнал...")
            log_success = log_download(
                info_dict=info_dict,
                output_format=output_format,
                url=url,
                file_path=actual_file_path,
                downloaded_by=downloaded_by,
                playlist_name=playlist_name,
                proxy_used=proxy_used,
                notes=notes
            )

            if log_success:
                print("🎉 Загрузка завершена успешно!")
                return True
            else:
                print("⚠️ Файл загружен, но не записан в журнал")
                return True

    except Exception as e:
        print(f"❌ Ошибка при загрузке: {e}")
        return False


def main():
    """Главная функция программы"""
    print("🎬 Универсальный загрузчик видео из социальных сетей")
    print("=" * 60)

    # Настройка окружения
    setup_directories()
    print()

    # Проверяем версию yt-dlp
    check_yt_dlp_version()

    try:
        # Получаем данные от пользователя
        url = input("🔗 Введите URL видео: ").strip()

        if not url:
            print("❌ URL не может быть пустым!")
            return

        print("\n📹 Выберите формат:")
        print("1. MP4 (видео)")
        print("2. MP3 (только аудио)")

        format_choice = input("Введите номер (1 или 2): ").strip()

        if format_choice == '2':
            output_format = 'mp3'
        else:
            output_format = 'mp4'

        # Дополнительные параметры (опционально)
        notes = input("📝 Заметки (необязательно): ").strip()

        print("\n" + "=" * 60)

        # Запускаем загрузку
        success = download_video(
            url=url,
            output_format=output_format,
            notes=notes
        )

        if success:
            print("\n🎉 Программа завершена успешно!")
        else:
            print("\n❌ Произошла ошибка при загрузке")

    except KeyboardInterrupt:
        print("\n\n⏹️ Загрузка прервана пользователем")
    except Exception as e:
        print(f"\n❌ Непредвиденная ошибка: {e}")


if __name__ == "__main__":
    main()