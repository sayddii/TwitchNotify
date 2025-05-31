import os
import requests
import time
from dotenv import load_dotenv
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_OAUTH_TOKEN = f"oauth:{os.getenv('TWITCH_OAUTH_TOKEN')}"
TWITCH_USER_ID = os.getenv('TWITCH_USER_ID')
CHECK_INTERVAL = 300  # 5 minutes

class StreamNotifier:
    def __init__(self):
        self.streamers_cache = {}
        self.validate_credentials()

    def validate_credentials(self):
        required = {
            'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
            'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
            'TWITCH_CLIENT_ID': TWITCH_CLIENT_ID,
            'TWITCH_OAUTH_TOKEN': TWITCH_OAUTH_TOKEN,
            'TWITCH_USER_ID': TWITCH_USER_ID
        }
        for name, val in required.items():
            if not val:
                raise ValueError(f"Missing environment variable: {name}")

    def get_twitch_headers(self):
        return {
            'Client-ID': TWITCH_CLIENT_ID,
            'Authorization': f'Bearer {TWITCH_OAUTH_TOKEN.replace("oauth:", "")}'
        }

    def get_live_streams(self):
        try:
            # Get followed channels
            url = f'https://api.twitch.tv/helix/streams/followed?user_id={TWITCH_USER_ID}'
            response = requests.get(url, headers=self.get_twitch_headers(), timeout=10)
            response.raise_for_status()
            return response.json().get('data', [])
        except requests.exceptions.RequestException as e:
            print(f"Twitch API Error: {e}")
            return []

    def send_telegram_alert(self, streamer, title, game):
        message = (
            f"🎮 {streamer} is live!\n\n"
            f"📺 {title}\n"
            f"🎯 {game}\n"
            f"🔗 https://twitch.tv/{streamer}"
        )
        try:
            response = requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                json={
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                },
                timeout=10
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"Telegram Error: {e}")
            return False

    def run(self):
        print("🔔 Twitch Stream Notifier Started")
        try:
            while True:
                current_streams = {s['user_id']: s for s in self.get_live_streams()}
                
                # Detect new streams
                for stream_id, stream in current_streams.items():
                    if stream_id not in self.streamers_cache:
                        print(f"New stream: {stream['user_name']}")
                        if self.send_telegram_alert(
                            stream['user_name'],
                            stream['title'],
                            stream['game_name']
                        ):
                            self.streamers_cache[stream_id] = True
                
                # Remove ended streams
                self.streamers_cache = {
                    k: v for k, v in self.streamers_cache.items()
                    if k in current_streams
                }
                
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")

def keep_alive():
    while True:
        try:
            if 'RENDER' in os.environ:
                requests.get(f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}")
            time.sleep(240)
        except:
            pass

if __name__ == '__main__':
    # Health check server for Render
    PORT = int(os.environ.get("PORT", 8080))
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'Bot is running')
    
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    print(f"🌐 Health server running on port {PORT}")
    
    # Start all components
    Thread(target=server.serve_forever, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    
    # Main bot
    notifier = StreamNotifier()
    notifier.run()
