import os
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
from yt_dlp import YoutubeDL

PORT = 8000
DIRECTORY = 'web'

if not os.path.exists(DIRECTORY):
    os.makedirs(DIRECTORY)

class VideoDownloaderHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        url = data.get('url', '').strip()

        if not url:
            self.respond_with_error(400, "يجب توفير عنوان URL")
            return

        if self.path == '/video_info':
            self.handle_video_info(url)
        elif self.path == '/list_formats':
            self.handle_list_formats(url)
        elif self.path == '/download':
            format_option = data.get('format', 'best')
            is_playlist = data.get('isPlaylist', False)
            is_soundcloud = data.get('isSoundCloud', False)
            self.handle_download(url, format_option, is_playlist, is_soundcloud)
        else:
            self.respond_with_error(404, "الصفحة غير موجودة")

    def handle_video_info(self, url):
        options = {'quiet': True}
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    # It's a playlist
                    video_info = {
                        'is_playlist': True,
                        'title': info.get('title', 'قائمة تشغيل'),
                        'thumbnail': info['entries'][0].get('thumbnail', ''),
                        'video_count': len(info['entries']),
                        'view_count': sum(entry.get('view_count', 0) for entry in info['entries']),
                        'last_updated': info.get('modified_date', 'غير معروف')
                    }
                else:
                    # It's a single video
                    video_info = {
                        'is_playlist': False,
                        'title': info.get('title', 'غير معروف'),
                        'thumbnail': info.get('thumbnail', ''),
                        'duration': info.get('duration', 0),
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'upload_date': info.get('upload_date', 'غير معروف')
                    }
                self.respond_with_json({'success': True, 'info': video_info})
        except Exception as e:
            self.respond_with_error(400, f"حدث خطأ أثناء جلب معلومات الفيديو: {str(e)}")

    def handle_list_formats(self, url):
        formats = self.list_formats(url)
        self.respond_with_json(formats)

    def list_formats(self, url):
        options = {'quiet': True, 'youtube_include_dash_manifest': False}
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                total_size = 0
                all_formats = []
                if 'entries' in info:
                    # Playlist, fetch formats for all videos
                    for entry in info['entries']:
                        formats = entry['formats']
                        video_formats = [
                            {
                                'format_id': f['format_id'],
                                'resolution': f.get('resolution', 'غير معروف'),
                                'note': f.get('format_note', 'لا يوجد'),
                                'filesize': f.get('filesize', 0) or 0
                            }
                            for f in formats
                            if f.get('vcodec') != 'none'
                        ]

                        audio_formats = [
                            {
                                'format_id': f['format_id'],
                                'resolution': 'الصوت فقط',
                                'note': f.get('format_note', 'لا يوجد'),
                                'filesize': f.get('filesize', 0) or 0
                            }
                            for f in formats
                            if f.get('acodec') != 'none' and f.get('vcodec') == 'none'
                        ]
                        all_formats.extend(video_formats + audio_formats)
                        total_size += sum(f.get('filesize', 0) or 0 for f in formats)
                else:
                    # Single video, fetch formats as is
                    formats = info['formats']
                    video_formats = [
                        {
                            'format_id': f['format_id'],
                            'resolution': f.get('resolution', 'غير معروف'),
                            'note': f.get('format_note', 'لا يوجد'),
                            'filesize': f.get('filesize', 0) or 0
                        }
                        for f in formats
                        if f.get('vcodec') != 'none'
                    ]

                    audio_formats = [
                        {
                            'format_id': f['format_id'],
                            'resolution': 'الصوت فقط',
                            'note': f.get('format_note', 'لا يوجد'),
                            'filesize': f.get('filesize', 0) or 0
                        }
                        for f in formats
                        if f.get('acodec') != 'none' and f.get('vcodec') == 'none'
                    ]
                    all_formats = sorted(video_formats + audio_formats, key=lambda x: x['filesize'], reverse=True)
                    total_size = sum(f.get('filesize', 0) or 0 for f in formats)

                all_formats = sorted(all_formats, key=lambda x: x['filesize'], reverse=True)
                return {'success': True, 'formats': all_formats, 'total_size': total_size}
        except Exception as e:
            print(f"Error listing formats for {url}: {e}")
            return {'success': False, 'error': f"حدث خطأ أثناء جلب الجودات: {str(e)}"}

    def handle_download(self, url, format_option, is_playlist, is_soundcloud):
        if is_soundcloud:
            result = self.download_soundcloud(url, format_option)
        elif is_playlist:
            result = self.download_playlist(url, format_option)
        else:
            result = self.download_video(url, format_option)
        self.respond_with_json(result)

    def download_playlist(self, url, format_option):
        options = {
            'format': format_option,
            'outtmpl': f'{DIRECTORY}/%(playlist_title)s/%(title)s.%(ext)s',
            'quiet': True,
            'merge_output_format': 'mp4',
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                playlist_title = info.get('title', 'قائمة التشغيل')
                return {'success': True, 'url': f'/{DIRECTORY}/{playlist_title}', 'title': playlist_title}
        except Exception as e:
            print(f"Error downloading playlist {url}: {e}")
            return {'success': False, 'error': f"حدث خطأ أثناء تحميل قائمة التشغيل: {str(e)}"}

    def download_video(self, url, format_option):
        options = {
            'format': format_option,
            'outtmpl': f'{DIRECTORY}/%(title)s.%(ext)s',
            'quiet': True,
            'merge_output_format': 'mp4',
            'noplaylist': True
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return {'success': True, 'url': f'/{filename}', 'title': info.get('title', 'غير معروف')}
        except Exception as e:
            print(f"Error downloading video {url}: {e}")
            return {'success': False, 'error': f"حدث خطأ أثناء التحميل: {str(e)}"}

    def download_soundcloud(self, url, format_option):
        options = {
            'format': format_option,
            'outtmpl': f'{DIRECTORY}/%(title)s.%(ext)s',
            'quiet': True,
            'merge_output_format': 'mp3',  # Assuming you want audio
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return {'success': True, 'url': f'/{filename}', 'title': info.get('title', 'غير معروف')}
        except Exception as e:
            print(f"Error downloading from SoundCloud {url}: {e}")
            return {'success': False, 'error': f"حدث خطأ أثناء التحميل من SoundCloud: {str(e)}"}

    def respond_with_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = json.dumps(data)
        self.wfile.write(response.encode('utf-8'))

    def respond_with_error(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = json.dumps({'success': False, 'error': message})
        self.wfile.write(response.encode('utf-8'))

def main():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, VideoDownloaderHandler)
    print(f"Server running on port {PORT}...")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
