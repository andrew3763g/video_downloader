#!/usr/bin/env python3
"""
Универсальный загрузчик видео из социальных сетей.
Поддерживает загрузку отдельных видео и плейлистов с детальным логированием
"""

import csv
import datetime
import re
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    import yaml
except ImportError:
    yaml = None

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError, ExtractorError
except ImportError:
    print("❌ Ошибка: Не установлен yt-dlp. Установите: pip install yt-dlp")
    sys.exit(1)


class OutputFormat(Enum):
    """Поддерживаемые форматы вывода"""
    MP4 = "mp4"
    MP3 = "mp3"
    WEBM = "webm"
    BEST_VIDEO = "best_video"
    BEST_AUDIO = "best_audio"


class VideoSource(Enum):
    """Поддерживаемые источники видео"""
    YOUTUBE = "YouTube"
    TIKTOK = "TikTok"
    FACEBOOK = "Facebook"
    INSTAGRAM = "Instagram"
    TWITTER = "Twitter/X"
    VK = "VK"
    TWITCH = "Twitch"
    REDDIT = "Reddit"
    SOUNDCLOUD = "SoundCloud"
    BANDCAMP = "Bandcamp"
    VIMEO = "Vimeo"
    DAILYMOTION = "Dailymotion"
    SPOTIFY = "Spotify"
    OTHER = "Другое"


@dataclass
class AppConfig:
    """Конфигурация приложения"""
    # Основные настройки
    download_directory: str = "Downloads"
    max_concurrent_downloads: int = 3
    max_file_size_mb: int = 500
    write_subtitles: bool = True
    write_auto_subtitles: bool = False

    # Качество
    max_video_height: int = 1080
    audio_quality: str = "192"
    preferred_video_codec: str = "h264"
    preferred_audio_codec: str = "aac"

    # Плейлисты
    max_playlist_items: int = 100
    create_playlist_folders: bool = True
    download_playlists_by_default: bool = False

    # Сеть
    socket_timeout: int = 30
    http_chunk_size: int = 10485760
    retries: int = 5
    prefer_ipv6: bool = False

    # Логирование
    log_level: str = "INFO"
    max_log_file_size: int = 10
    backup_count: int = 5
    console_output: bool = True


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Загружает конфигурацию из YAML файла"""
    config_file = Path(config_path)

    if not config_file.exists() or not yaml:
        if not yaml:
            print("⚠️ PyYAML не установлен. Используются настройки по умолчанию.")
            print("💡 Для работы с config.yaml установите: pip install pyyaml")
        return AppConfig()

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            return AppConfig()

        # Объединяем настройки из файла с настройками по умолчанию
        config_dict = {}

        # Базовые настройки
        if 'download_settings' in config_data:
            ds = config_data['download_settings']
            config_dict.update({
                'download_directory': ds.get('download_directory', 'Downloads'),
                'max_concurrent_downloads': ds.get('max_concurrent_downloads', 3),
                'max_file_size_mb': ds.get('max_file_size_mb', 500),
                'write_subtitles': ds.get('write_subtitles', True),
                'write_auto_subtitles': ds.get('write_auto_subtitles', False),
            })

        # Качество
        if 'quality_settings' in config_data:
            qs = config_data['quality_settings']
            config_dict.update({
                'max_video_height': qs.get('max_video_height', 1080),
                'audio_quality': str(qs.get('audio_quality', '192')),
                'preferred_video_codec': qs.get('preferred_video_codec', 'h264'),
                'preferred_audio_codec': qs.get('preferred_audio_codec', 'aac'),
            })

        # Плейлисты
        if 'playlist_settings' in config_data:
            ps = config_data['playlist_settings']
            config_dict.update({
                'max_playlist_items': ps.get('max_playlist_items', 100),
                'create_playlist_folders': ps.get('create_playlist_folders', True),
                'download_playlists_by_default': ps.get('download_playlists_by_default', False),
            })

        # Сеть
        if 'network_settings' in config_data:
            ns = config_data['network_settings']
            config_dict.update({
                'socket_timeout': ns.get('socket_timeout', 30),
                'http_chunk_size': ns.get('http_chunk_size', 10485760),
                'retries': ns.get('retries', 5),
                'prefer_ipv6': ns.get('prefer_ipv6', False),
            })

        # Логирование
        if 'logging_settings' in config_data:
            ls = config_data['logging_settings']
            config_dict.update({
                'log_level': ls.get('level', 'INFO'),
                'max_log_file_size': ls.get('max_log_file_size', 10),
                'backup_count': ls.get('backup_count', 5),
                'console_output': ls.get('console_output', True),
            })

        return AppConfig(**{k: v for k, v in config_dict.items()})

    except Exception as e:
        print(f"⚠️ Ошибка чтения config.yaml: {e}")
        print("🔄 Используются настройки по умолчанию")
        return AppConfig()


@dataclass
class DownloadConfig:
    """Конфигурация для загрузки"""
    url: str
    output_format: OutputFormat = OutputFormat.MP4
    downloaded_by: str = "User"
    playlist_name: str = ""
    proxy_used: bool = False
    notes: str = ""
    quality: str = "best"
    download_playlist: bool = False
    max_downloads: int = 50  # Ограничение для плейлистов


class VideoDownloader:
    """Основной класс для загрузки видео"""

    def __init__(self, download_dir: Optional[str] = None, config: Optional[AppConfig] = None):
        """
        Инициализация загрузчика

        Args:
            download_dir: Путь к папке загрузок (переопределяет config)
            config: Конфигурация приложения
        """
        self.config = config or load_config()
        self.download_dir = Path(download_dir) if download_dir else Path.cwd() / self.config.download_directory
        self.log_file = Path.cwd() / 'downloads_log.csv'
        self.logger = self._setup_logging(self.config)
        self._setup_directories()

    @staticmethod
    def _setup_logging(config: Optional[AppConfig] = None) -> logging.Logger:
        """Настройка логирования"""
        if not config:
            config = AppConfig()

        logger = logging.getLogger('VideoDownloader')
        logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

        # Очищаем старые handlers
        logger.handlers = []

        # Создаем handler для файла
        log_dir = Path.cwd() / 'logs'
        log_dir.mkdir(exist_ok=True)

        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_dir / f'downloader_{datetime.datetime.now().strftime("%Y%m%d")}.log',
            maxBytes=config.max_log_file_size * 1024 * 1024,  # MB to bytes
            backupCount=config.backup_count,
            encoding='utf-8'
        )

        # Форматтер
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Создаем handler для консоли если нужно
        if config.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    def _setup_directories(self) -> None:
        """Создание необходимых папок и файлов"""
        try:
            # Создаем папку для загрузок
            self.download_dir.mkdir(exist_ok=True)
            self.logger.info(f"📁 Папка загрузок: {self.download_dir}")

            # Создаем файл журнала с заголовками, если его нет
            if not self.log_file.exists():
                with open(self.log_file, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'ID', 'Формат', 'Время загрузки', 'Источник', 'URL',
                        'Название', 'Теги', 'Путь к файлу', 'Размер файла (MB)',
                        'Длительность', 'Плейлист', 'Позиция в плейлисте',
                        'Загрузил', 'Автоудаление', 'Прокси', 'Качество',
                        'Заметки', 'Статус'
                    ])
                self.logger.info(f"📋 Создан файл журнала: {self.log_file}")
            else:
                self.logger.info(f"📋 Используется существующий журнал: {self.log_file}")

        except Exception as e:
            self.logger.error(f"Ошибка настройки директорий: {e}")
            raise

    @staticmethod
    def get_video_source(url: str) -> VideoSource:
        """
        Определение источника видео по URL

        Args:
            url: URL видео

        Returns:
            VideoSource: Источник видео
        """
        url_lower = url.lower()

        source_mapping = {
            ('youtube.com', 'youtu.be', 'youtube-nocookie.com'): VideoSource.YOUTUBE,
            ('tiktok.com',): VideoSource.TIKTOK,
            ('facebook.com', 'fb.watch', 'fb.com'): VideoSource.FACEBOOK,
            ('instagram.com', 'instagr.am'): VideoSource.INSTAGRAM,
            ('twitter.com', 'x.com', 't.co'): VideoSource.TWITTER,
            ('vk.com', 'vk.ru'): VideoSource.VK,
            ('twitch.tv',): VideoSource.TWITCH,
            ('reddit.com', 'redd.it'): VideoSource.REDDIT,
            ('soundcloud.com',): VideoSource.SOUNDCLOUD,
            ('bandcamp.com',): VideoSource.BANDCAMP,
            ('vimeo.com',): VideoSource.VIMEO,
            ('dailymotion.com',): VideoSource.DAILYMOTION,
            ('spotify.com', 'open.spotify.com'): VideoSource.SPOTIFY,
        }

        for domains, source in source_mapping.items():
            if any(domain in url_lower for domain in domains):
                return source

        return VideoSource.OTHER

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 180) -> str:
        """
        Улучшенная очистка имени файла от недопустимых символов

        Args:
            filename: Исходное имя файла
            max_length: Максимальная длина имени файла

        Returns:
            str: Очищенное имя файла
        """
        if not filename or filename.strip() == "":
            return "Unknown_Video"

        # Убираем HTML теги
        filename = re.sub(r'<[^>]+>', '', filename)

        # Убираем недопустимые символы для имен файлов
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        # Заменяем эмодзи и специальные символы
        filename = re.sub(r'[^\w\s\-_.()\[\]{}]', '', filename)

        # Заменяем множественные пробелы одним
        filename = re.sub(r'\s+', ' ', filename)

        # Убираем пробелы в начале и конце
        filename = filename.strip()

        # Убираем точки в конце (недопустимо в Windows)
        filename = filename.rstrip('.')

        # Ограничиваем длину
        if len(filename) > max_length:
            # Разбиваем на части, чтобы сохранить важную информацию
            words = filename.split()
            result = words[0] if words else "Video"

            for word in words[1:]:
                if len(result + " " + word) <= max_length:
                    result += " " + word
                else:
                    break
            filename = result

        return filename or "Unknown_Video"

    @staticmethod
    def _get_file_size_mb(file_path: Path) -> float:
        """Получение размера файла в мегабайтах"""
        try:
            return round(file_path.stat().st_size / (1024 * 1024), 2)
        except (OSError, AttributeError):
            return 0.0

    @staticmethod
    def _format_duration(duration: Optional[float]) -> str:
        """Форматирование длительности видео"""
        if not duration:
            return "Неизвестно"

        minutes, seconds = divmod(int(duration), 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def _get_unique_filename(self, base_title: str, ext: str, playlist_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Создание уникального имени файла с проверкой дубликатов

        Args:
            base_title: Базовое название
            ext: Расширение файла
            playlist_info: Информация о плейлисте

        Returns:
            str: Уникальное имя файла
        """
        # Получаем дополнительную информацию для уникальности
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Формируем базовое название
        if playlist_info:
            # Для плейлистов добавляем номер
            playlist_index = playlist_info.get('playlist_index', 1)
            base_name = f"{playlist_index:02d} - {base_title}"
        else:
            base_name = base_title

        # Очищаем название
        clean_name = self.sanitize_filename(base_name)

        # Проверяем на дубликаты
        target_dir = self.download_dir
        if playlist_info and playlist_info.get('playlist_title'):
            playlist_dir = self.download_dir / self.sanitize_filename(playlist_info['playlist_title'])
            if playlist_dir.exists():
                target_dir = playlist_dir

        original_name = f"{clean_name}.{ext}"
        final_path = target_dir / original_name

        # Если файл уже существует, добавляем уникальный суффикс
        counter = 1
        while final_path.exists():
            name_with_counter = f"{clean_name}_{timestamp}_{counter:02d}.{ext}"
            final_path = target_dir / name_with_counter
            counter += 1

    def log_download(self, info_dict: Dict[str, Any], config: DownloadConfig,
                     file_path: Path, status: str = "Успешно") -> bool:
        """
        Запись информации о скачанном видео в журнал

        Args:
            info_dict: Информация о видео от yt-dlp
            config: Конфигурация загрузки
            file_path: Путь к скачанному файлу
            status: Статус загрузки

        Returns:
            bool: Успешность записи в журнал
        """
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Генерируем уникальный ID для записи
            record_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(config.url) % 10000:04d}"

            # Извлекаем информацию из словаря
            title = info_dict.get('title', 'Неизвестное название')
            tags = ', '.join(info_dict.get('tags', [])[:10]) if info_dict.get('tags') else 'Нет тегов'
            duration = VideoDownloader._format_duration(info_dict.get('duration'))
            playlist_title = info_dict.get('playlist_title', config.playlist_name)
            playlist_index = info_dict.get('playlist_index', '')

            # Размер файла
            file_size = VideoDownloader._get_file_size_mb(file_path) if file_path.exists() else 0.0

            with open(self.log_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    record_id,
                    config.output_format.value,
                    timestamp,
                    self.get_video_source(config.url).value,
                    config.url,
                    title,
                    tags,
                    str(file_path),
                    file_size,
                    duration,
                    playlist_title,
                    playlist_index,
                    config.downloaded_by,
                    '',  # Автоудаление (заполняется вручную)
                    'Да' if config.proxy_used else 'Нет',
                    config.quality,
                    config.notes,
                    status
                ])

            self.logger.info(f"📝 Запись добавлена в журнал: {title}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Ошибка записи в журнал: {e}")
            return False

    def _get_ydl_opts(self, config: DownloadConfig) -> Dict[str, Any]:
        """
        Получение настроек для yt-dlp

        Args:
            config: Конфигурация загрузки

        Returns:
            Dict[str, Any]: Настройки для yt-dlp
        """
        # Базовые настройки с улучшенной совместимостью
        ydl_opts = {
            'outtmpl': str(self.download_dir / '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,  # Продолжаем при ошибках в плейлистах
            'retries': self.config.retries,
            'fragment_retries': self.config.retries,
            'extractor_retries': 3,
            'file_access_retries': 3,
            'http_chunk_size': self.config.http_chunk_size,

            # Улучшенные настройки для обхода SABR и других ограничений
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',

            # Улучшенные настройки для обхода ограничений всех платформ
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'tv'],
                    'player_skip': ['webpage', 'configs'],
                    'skip': ['dash', 'hls'],
                },
                'instagram': {
                    'api_version': 'v1',
                    'include_stories': False,
                },
                'facebook': {
                    'tab': 'videos',
                    'bypass_age_gate': True,
                    'use_cookies': True,  # Важно для Facebook
                },
                'tiktok': {
                    'webpage_download': False,
                    'api_hostname': 'api.tiktokv.com',
                },
                'soundcloud': {
                    'client_id': None,  # Автоматическое получение
                }
            },

            # Дополнительные заголовки
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                'Keep-Alive': '300',
                'Connection': 'keep-alive',
            },

            # Настройки для стабильности
            'socket_timeout': self.config.socket_timeout,
            'source_address': None,  # Использовать системный IP
        }

        # Настройки плейлиста с улучшенными именами файлов
        if config.download_playlist:
            ydl_opts.update({
                'noplaylist': False,
                'playlistend': config.max_downloads,
                'outtmpl': str(self.download_dir / '%(playlist_title)s' / '%(playlist_index)02d - %(title)s.%(ext)s'),
            })
        else:
            ydl_opts.update({
                'noplaylist': True,
                'outtmpl': str(self.download_dir / '%(uploader)s - %(title)s - %(id)s.%(ext)s'),
            })

        # Настройки формата с учетом конфигурации
        max_height = self.config.max_video_height
        format_mapping = {
            OutputFormat.MP4: f'best[height<={max_height}][ext=mp4]/best[height<=720][ext=mp4]/best[ext=mp4]/best',
            OutputFormat.WEBM: f'best[ext=webm]/best[height<={max_height}]/best',
            OutputFormat.BEST_VIDEO: f'best[height<={max_height}]/best[height<=720]/best',
            OutputFormat.BEST_AUDIO: 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
            OutputFormat.MP3: 'bestaudio[ext=m4a]/bestaudio/best'
        }

        ydl_opts['format'] = format_mapping.get(config.output_format, 'best[height<=1080]')

        # Постобработка для аудио форматов с настройками качества
        if config.output_format == OutputFormat.MP3:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': self.config.audio_quality,
            }]
        elif config.output_format == OutputFormat.BEST_AUDIO:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'best',
            }]

        return ydl_opts

    def _fix_facebook_url(self, url: str) -> str:
        """
        Автоматическое исправление Facebook URL для лучшей совместимости

        Args:
            url: Исходный URL Facebook

        Returns:
            str: Исправленный URL в формате facebook.com/watch/?v=ID
        """
        if 'facebook.com' not in url.lower() and 'fb.watch' not in url.lower():
            return url

        # Паттерны для извлечения ID из разных форматов Facebook URL
        patterns = [
            r'/reel/(\d{15,16})',  # facebook.com/reel/1234567890123456
            r'/watch/\?v=(\d{15,16})',  # facebook.com/watch/?v=1234567890123456 (уже правильный)
            r'/videos/(\d{15,16})',  # facebook.com/user/videos/1234567890123456
            r'fb\.watch/[^/]+.*?(\d{15,16})',  # fb.watch/AbC123/ -> находит ID в параметрах
            r'video_id[=:](\d{15,16})',  # Прямое указание video_id
            r'\b(\d{15,16})\b',  # Любое 15-16-значное число в URL
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                fixed_url = f"https://www.facebook.com/watch/?v={video_id}"

                if fixed_url != url:
                    self.logger.info(f"🔧 Исправлен Facebook URL:")
                    self.logger.info(f"   Исходный: {url}")
                    self.logger.info(f"   Исправленный: {fixed_url}")

                return fixed_url

        self.logger.warning(f"⚠️ Не удалось автоматически исправить Facebook URL: {url}")
        self.logger.info("💡 Попробуйте найти ID вручную и использовать формат: facebook.com/watch/?v=ID")

        return url

    def download_video(self, config: DownloadConfig) -> bool:
        """
        Основная функция загрузки видео

        Args:
            config: Конфигурация загрузки

        Returns:
            bool: Успешность загрузки
        """
        # Автоматическое исправление Facebook URL
        if 'facebook.com' in config.url.lower() or 'fb.watch' in config.url.lower():
            config.url = self._fix_facebook_url(config.url)

        self.logger.info(f"🔄 Начинаем загрузку с {self.get_video_source(config.url).value}")
        self.logger.info(f"🔗 URL: {config.url}")
        self.logger.info(f"📹 Формат: {config.output_format.value}")

        if config.download_playlist:
            self.logger.info(f"📋 Режим плейлиста (макс. {config.max_downloads} видео)")

        ydl_opts = self._get_ydl_opts(config)

        # Проверка версии Python
        import sys
        if sys.version_info < (3, 10):
            self.logger.warning("⚠️ Используется устаревшая версия Python. Рекомендуется обновить до Python 3.10+")

        try:
            with YoutubeDL(ydl_opts) as ydl:
                self.logger.info("📊 Получаем информацию о видео...")

                # Получаем информацию без загрузки
                try:
                    info_dict = ydl.extract_info(config.url, download=False)
                except (DownloadError, ExtractorError, ImportError, ValueError) as e:
                    error_msg = str(e).lower()

                    if ("cannot parse data" in error_msg or
                            "sabr streaming" in error_msg or
                            "formats have been skipped" in error_msg):

                        self.logger.warning("⚠️ Проблемы с платформой. Пробуем альтернативные настройки...")

                        # Специальные настройки для проблемных случаев
                        ydl_opts_fallback = ydl_opts.copy()

                        # Для Facebook - специальные заголовки для обхода блокировок
                        if "facebook" in config.url.lower():
                            ydl_opts_fallback.update({
                                'format': 'best[height<=720]/worst',
                                'extractor_args': {
                                    'facebook': {
                                        'tab': 'videos',
                                        'bypass_age_gate': True,
                                        'use_cookies': True,
                                    }
                                },
                                'http_headers': {
                                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
                                    'Accept-Language': 'en-US,en;q=0.9',
                                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                    'DNT': '1',
                                    'Referer': 'https://www.facebook.com/',
                                }
                            })

                        # Для SoundCloud - специальные настройки
                        elif "soundcloud" in config.url.lower():
                            ydl_opts_fallback.update({
                                'format': 'best',
                                'extractor_args': {
                                    'soundcloud': {
                                        'client_id': None,
                                        'use_oauth': False,
                                    }
                                }
                            })

                        # Для YouTube SABR
                        elif "youtube" in config.url.lower() or "youtu.be" in config.url.lower():
                            ydl_opts_fallback.update({
                                'format': 'best[height<=720]/best[height<=480]/worst',
                                'extractor_args': {
                                    'youtube': {
                                        'player_client': ['android_creator', 'android'],
                                        'player_skip': ['webpage', 'configs', 'js'],
                                        'skip': ['dash', 'hls'],
                                    }
                                }
                            })

                        # Общие fallback настройки
                        else:
                            ydl_opts_fallback.update({
                                'format': 'best[height<=720]/worst',
                                'ignoreerrors': True,
                            })

                        with YoutubeDL(ydl_opts_fallback) as ydl_fallback:
                            info_dict = ydl_fallback.extract_info(config.url, download=False)
                            ydl_opts = ydl_opts_fallback  # Используем fallback настройки для загрузки
                    else:
                        raise

                if not info_dict:
                    self.logger.error("❌ Не удалось получить информацию о видео")
                    return False

                # Обработка плейлиста
                if 'entries' in info_dict:
                    return self._download_playlist(info_dict, config, ydl_opts)
                else:
                    return self._download_single_video(info_dict, config, ydl_opts)

        except KeyboardInterrupt:
            self.logger.info("⏹️ Загрузка прервана пользователем")
            return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка при загрузке: {e}")
            return False

    def _download_single_video(self, info_dict: Dict[str, Any],
                               config: DownloadConfig, ydl_opts: Dict[str, Any]) -> bool:
        """Загрузка одного видео"""
        try:
            original_title = info_dict.get('title', 'Unknown_Video')
            uploader = info_dict.get('uploader', info_dict.get('channel', 'Unknown_Channel'))
            video_id = info_dict.get('id', 'unknown_id')

            # Создаем улучшенное название файла
            if uploader and uploader.lower() not in original_title.lower():
                enhanced_title = f"{uploader} - {original_title} - {video_id}"
            else:
                enhanced_title = f"{original_title} - {video_id}"

            clean_title = self.sanitize_filename(enhanced_title)

            # Определяем расширение файла
            ext = 'mp3' if config.output_format == OutputFormat.MP3 else info_dict.get('ext', 'mp4')

            self.logger.info(f"📄 Название: {original_title}")
            self.logger.info(f"👤 Автор: {uploader}")
            self.logger.info(f"🆔 ID: {video_id}")
            self.logger.info(f"⏱️ Длительность: {VideoDownloader._format_duration(info_dict.get('duration'))}")

            # Проверяем проблемы с разными платформами
            source = self.get_video_source(config.url)

            # Instagram
            if source == VideoSource.INSTAGRAM:
                error_indicators = ['login_required', 'private_account', 'user_not_found']
                info_str = str(info_dict).lower()

                if any(indicator in info_str for indicator in error_indicators) or not info_dict.get('formats'):
                    self.logger.error("❌ Instagram требует авторизации или видео недоступно")
                    self.log_download(info_dict, config, Path(""), "Ошибка: требуется авторизация Instagram")
                    return False

            # Facebook - особая обработка
            elif source == VideoSource.FACEBOOK:
                if not info_dict.get('formats') or not info_dict.get('title'):
                    self.logger.warning("⚠️ Facebook видео может требовать авторизации")
                    self.logger.info("💡 Рекомендация: войдите в Facebook в браузере перед загрузкой")
                    # Не возвращаем False - пытаемся загрузить

            # TikTok
            elif source == VideoSource.TIKTOK:
                if 'private' in str(info_dict).lower() or not info_dict.get('formats'):
                    self.logger.error("❌ TikTok видео приватное или недоступно")
                    self.log_download(info_dict, config, Path(""), "Ошибка: TikTok видео недоступно")
                    return False

            # SoundCloud - обычно стабильно работает
            elif source == VideoSource.SOUNDCLOUD:
                if 'private' in str(info_dict).lower() and not info_dict.get('formats'):
                    self.logger.error("❌ SoundCloud трек приватный")
                    self.log_download(info_dict, config, Path(""), "Ошибка: SoundCloud трек приватный")
                    return False

            # Загружаем видео
            with YoutubeDL(ydl_opts) as ydl:
                self.logger.info("⬇️ Загружаем видео...")
                ydl.download([config.url])

            # Находим загруженный файл
            file_path = self._find_downloaded_file(clean_title, ext, video_id=video_id, uploader=uploader)

            if file_path:
                self.logger.info(f"✅ Файл успешно загружен: {file_path.name}")
                # Записываем в журнал
                self.log_download(info_dict, config, file_path)
                return True
            else:
                self.logger.error("❌ Не удалось найти загруженный файл")
                self.log_download(info_dict, config, Path(""), "Ошибка: файл не найден")
                return False

        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки видео: {e}")
            self.log_download(info_dict, config, Path(""), f"Ошибка: {str(e)}")
            return False

    def _download_playlist(self, info_dict: Dict[str, Any],
                           config: DownloadConfig, ydl_opts: Dict[str, Any]) -> bool:
        """Загрузка плейлиста"""
        playlist_title = info_dict.get('title', 'Unknown_Playlist')
        entries = info_dict.get('entries', [])

        if not entries:
            self.logger.warning("❌ Плейлист пуст или недоступен")
            return False

        self.logger.info(f"📋 Плейлист: {playlist_title}")
        self.logger.info(f"📊 Найдено видео: {len(entries)}")

        # Обновляем конфигурацию для плейлиста
        config.playlist_name = playlist_title

        success_count = 0
        total_count = min(len(entries), config.max_downloads)

        with YoutubeDL(ydl_opts) as ydl:
            for i, entry in enumerate(entries[:config.max_downloads], 1):
                if entry is None:
                    continue

                try:
                    self.logger.info(f"⬇️ Загружаем [{i}/{total_count}]: {entry.get('title', 'Неизвестно')}")

                    # Загружаем видео
                    ydl.download([entry['webpage_url']])

                    # Находим файл и логируем
                    clean_title = self.sanitize_filename(entry.get('title', 'Unknown'))
                    ext = 'mp3' if config.output_format == OutputFormat.MP3 else entry.get('ext', 'mp4')

                    file_path = self._find_downloaded_file(clean_title, ext, in_playlist=True,
                                                           playlist_title=playlist_title)

                    if file_path:
                        # Добавляем информацию о позиции в плейлисте
                        entry['playlist_index'] = i
                        entry['playlist_title'] = playlist_title

                        self.log_download(entry, config, file_path)
                        success_count += 1
                        self.logger.info(f"✅ [{i}/{total_count}] Загружено успешно")
                    else:
                        self.logger.warning(f"⚠️ [{i}/{total_count}] Файл не найден после загрузки")

                except Exception as e:
                    self.logger.error(f"❌ [{i}/{total_count}] Ошибка: {e}")
                    continue

        self.logger.info(f"🎉 Загрузка плейлиста завершена: {success_count}/{total_count} успешно")
        return success_count > 0

    def _find_downloaded_file(self, clean_title: str, ext: str,
                              in_playlist: bool = False, playlist_title: str = "",
                              video_id: str = "", uploader: str = "") -> Optional[Path]:
        """Улучшенный поиск загруженного файла"""
        search_patterns = [
            clean_title,
            video_id,
            uploader if uploader else "",
        ]

        # Поиск в папке плейлиста
        if in_playlist and playlist_title:
            playlist_dir = self.download_dir / self.sanitize_filename(playlist_title)
            if playlist_dir.exists():
                for pattern in search_patterns:
                    if pattern:
                        for file_path in playlist_dir.iterdir():
                            if (file_path.is_file() and
                                    pattern.lower() in file_path.name.lower() and
                                    file_path.suffix.lower() == f'.{ext.lower()}'):
                                return file_path

        # Поиск в основной папке
        for pattern in search_patterns:
            if pattern:
                for file_path in self.download_dir.iterdir():
                    if (file_path.is_file() and
                            pattern.lower() in file_path.name.lower() and
                            file_path.suffix.lower() == f'.{ext.lower()}'):
                        return file_path

        # Поиск самого нового файла с нужным расширением
        recent_files = []
        for file_path in self.download_dir.rglob(f"*.{ext}"):
            if file_path.is_file():
                stat = file_path.stat()
                recent_files.append((stat.st_mtime, file_path))

        if recent_files:
            recent_files.sort(reverse=True)
            # Проверяем, что файл создан в последние 2 минуты
            import time
            if time.time() - recent_files[0][0] < 120:  # 2 минуты
                return recent_files[0][1]

        return None


def check_and_update_dependencies():
    """Проверка и обновление зависимостей"""
    import subprocess
    import sys

    try:
        print("🔍 Проверяем версию yt-dlp...")
        result = subprocess.run([sys.executable, '-m', 'pip', 'show', 'yt-dlp'],
                                capture_output=True, text=True)

        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    current_version = line.split(':', 1)[1].strip()
                    print(f"📦 Текущая версия yt-dlp: {current_version}")
                    break

        # Предложение обновления
        update_choice = input("🔄 Обновить yt-dlp до последней версии? (y/N): ").strip().lower()

        if update_choice in ['y', 'yes', 'да']:
            print("⬇️ Обновляем yt-dlp...")
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
                                    capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ yt-dlp успешно обновлен!")
                print("\n🎵 Поддерживаемые источники музыки:")
                print("• YouTube & YouTube Music - лучший выбор для плейлистов")
                print("• SoundCloud - подкасты и независимые артисты")
                print("• Bandcamp - высокое качество, покупки артистов")
                print("• Vimeo - качественное аудио из видео")
                print("• VK - русскоязычная музыка")
                print("• Spotify - треки (требуется Premium)")
                print("\n📹 Видео: TikTok, Instagram, Facebook, Twitter/X, Twitch, Reddit")

                print("\n💡 Совет: для музыки выбирайте формат MP3 (192kbps)")
                print("💡 Для бега: лучше заранее создать плейлист на YouTube")
                print("\n" + "=" * 70)
            else:
                print(f"❌ Ошибка обновления: {result.stderr}")
                print("\n" + "=" * 70)

        else:
            print("\n" + "=" * 70)

    except Exception as e:
        print(f"⚠️ Не удалось проверить/обновить yt-dlp: {e}")
        print("\n" + "=" * 70)


def main():
    """Главная функция программы"""
    print("🎬 Универсальный загрузчик видео из социальных сетей v2.1")
    print("=" * 70)

    # Проверка версии Python
    if sys.version_info < (3, 10):
        print("⚠️ ВНИМАНИЕ: Используется Python {}.{}.{}".format(*sys.version_info[:3]))
        print("📋 Рекомендуется обновить до Python 3.10+ для лучшей совместимости")
        print("🔗 Инструкции: https://www.python.org/downloads/")

        continue_choice = input("\n❓ Продолжить с текущей версией? (y/N): ").strip().lower()
        if continue_choice not in ['y', 'yes', 'да']:
            print("👋 До свидания!")
            return

    # Проверка и установка PyYAML
    try:
        import yaml
        config_available = True
    except ImportError:
        config_available = False
        print("⚠️ PyYAML не установлен - config.yaml не будет работать")
        install_yaml = input("📦 Установить PyYAML для работы с конфигурацией? (Y/n): ").strip().lower()

        if install_yaml not in ['n', 'no', 'нет']:
            try:
                import subprocess
                print("⬇️ Устанавливаем PyYAML...")
                result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyyaml'],
                                        capture_output=True, text=True)
                if result.returncode == 0:
                    print("✅ PyYAML установлен!")
                    import yaml
                    config_available = True
                else:
                    print(f"❌ Ошибка установки: {result.stderr}")
            except Exception as e:
                print(f"❌ Не удалось установить PyYAML: {e}")

    # Проверка обновлений
    check_choice = input("\n🔄 Проверить обновления yt-dlp? (Y/n): ").strip().lower()
    if check_choice not in ['n', 'no', 'нет']:
        check_and_update_dependencies()

    print("\n" + "=" * 70)

    try:
        # Инициализируем загрузчик с конфигурацией
        if config_available:
            config = load_config()
            print(f"✅ Загружена конфигурация: {config.download_directory}")
            downloader = VideoDownloader(config=config)
        else:
            print("⚠️ Используются настройки по умолчанию")
            downloader = VideoDownloader()

        # Получаем данные от пользователя
        url = input("🔗 Введите URL видео или плейлиста: ").strip()

        if not url:
            print("❌ URL не может быть пустым!")
            return

        # Определяем тип контента и показываем специальные советы
        source = VideoDownloader.get_video_source(url)
        print(f"\n🔍 Определяем источник: {source.value}")

        # Специальные инструкции для Facebook
        if source == VideoSource.FACEBOOK:
            print("\n⚠️ ВНИМАНИЕ: Facebook требует специального формата URL!")
            print("📋 Для успешной загрузки используйте формат:")
            print("   https://www.facebook.com/watch/?v=ВИДЕО_ID")
            print("💡 Программа попытается автоматически исправить URL")
            print("📖 Подробные инструкции в файле FACEBOOK_GUIDE.md")

            continue_fb = input("\n❓ Продолжить попытку загрузки? (Y/n): ").strip().lower()
            if continue_fb in ['n', 'no', 'нет']:
                print("🔄 Попробуйте найти тот же контент на YouTube или SoundCloud")
                return

        # Выбор формата
        print("\n📹 Выберите формат:")
        print("1. MP4 (видео, до 1080p)")
        print("2. MP3 (только аудио, 192kbps)")
        print("3. WEBM (видео)")
        print("4. Лучшее видео")
        print("5. Лучшее аудио")

        format_choice = input("Введите номер (1-5): ").strip()

        format_mapping = {
            '1': OutputFormat.MP4,
            '2': OutputFormat.MP3,
            '3': OutputFormat.WEBM,
            '4': OutputFormat.BEST_VIDEO,
            '5': OutputFormat.BEST_AUDIO
        }

        output_format = format_mapping.get(format_choice, OutputFormat.MP4)

        # Опция плейлиста
        download_playlist = False
        if 'playlist' in url.lower() or 'list=' in url:
            playlist_choice = input("\n📋 Обнаружен плейлист. Скачать весь плейлист? (y/N): ").strip().lower()
            download_playlist = playlist_choice in ['y', 'yes', 'да']

            if download_playlist:
                try:
                    max_downloads = int(input("📊 Максимальное количество видео (по умолчанию 50): ").strip() or "50")
                except ValueError:
                    max_downloads = 50
            else:
                max_downloads = 1
        else:
            max_downloads = 1

        # Дополнительные параметры
        notes = input("📝 Заметки (необязательно): ").strip()

        print("\n" + "=" * 70)

        # Создаем конфигурацию
        config = DownloadConfig(
            url=url,
            output_format=output_format,
            download_playlist=download_playlist,
            max_downloads=max_downloads,
            notes=notes
        )

        # Запускаем загрузку
        success = downloader.download_video(config)

        if success:
            print("\n🎉 Программа завершена успешно!")
            print(f"📁 Файлы сохранены в: {downloader.download_dir}")
            print(f"📋 Журнал доступен: {downloader.log_file}")
        else:
            print("\n❌ Произошла ошибка при загрузке")

    except KeyboardInterrupt:
        print("\n\n⏹️ Программа прервана пользователем")
    except Exception as e:
        print(f"\n❌ Непредвиденная ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()