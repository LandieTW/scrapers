#!/usr/bin/env python3


"""
This script aims to able download of videos / audios from Youtube


INPUTS

    format_input: you must set it according to your needs
        mp4 - for downloading videos
        mp3 - for downloading audios
    
    url_input: you must set the link from the video / playlist you want to download

NOTE
    It's strongly recommended that you export your browser cookies into a .txt
    file and move it to the same folder where this script will be running
    (By doing this you handle possible Youtube 'blocks')
    I suggest to use 'Get cookies.txt LOCALLY' extension for chrome based browsers
"""


import os
import yt_dlp


format_input = "mp4"
url_input = "https://www.youtube.com/playlist?list=PLo4jXE-LdDTRLGDL59SkkLPBHVmYphuqI"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cookies_path = os.path.join(BASE_DIR, "cookies.txt")
ARCHIVE_PATH = os.path.join(BASE_DIR, "downloads/archive.txt")


def download_playlist(
    url,
    format="mp3",
    output_path=os.path.join(BASE_DIR, "downloads",
        "%(playlist)s", "%(playlist_index)s - %(title)s.%(ext)s")
        ):

    common_opts = {
        "outtmpl": output_path,
        "ignoreerrors": True,
        "download_archive": ARCHIVE_PATH,
    }

    if os.path.isfile(cookies_path):
        common_opts['cookiefile'] = cookies_path
    else:
        common_opts['cookiesfrombrowser'] = ("edge",)

    if format == "mp4":
        ydl_opts = {
            **common_opts,
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
            "merge_output_format": "mp4",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    elif format == "mp3":
        ydl_opts = {
            **common_opts,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

if __name__ == "__main__":
    download_playlist(url_input, format_input)

