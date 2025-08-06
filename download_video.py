import yt_dlp
import os


def download_video(url, output_dir="downloads"):
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'format': 'best'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


if __name__ == "__main__":
    video_url = input("Введите ссылку на видео (например, из TikTok): ").strip()

    if not video_url:
        print("Ссылка не введена. Завершение работы.")
    else:
        download_video(video_url)
        print("Готово! Видео скачано в папку 'downloads'.")
