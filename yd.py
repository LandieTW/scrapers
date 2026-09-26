import os
import yt_dlp

format_input = "mp4"
url_input = "https://www.youtube.com/playlist?list=PLYx7XA2nY5Gde-6QO98KUJ9iL_WW4rgYf"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def download_playlist(
        url,
        format="mp3",
        output_path=os.path.join(BASE_DIR, "downloads",
            "%(playlist)s", "%(playlist_index)s - %(title)s.%(ext)s")
            ):

    if format == "mp4":
        ydl_opts = {
            "outtmpl": output_path,
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
            "merge_output_format": "mp4",
            "extractor_args": {"youtube": {"player_client": ["default", "-tv_simply"]}},
            # "cookiesfrombrowser": ("edge",)
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    elif format == "mp3":
        ydl_opts = {
            "outtmpl": output_path,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "ignoreerrors": True,
            "download_archive": "downloads/archive.txt",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

if __name__ == "__main__":
    download_playlist(url_input, format_input)

