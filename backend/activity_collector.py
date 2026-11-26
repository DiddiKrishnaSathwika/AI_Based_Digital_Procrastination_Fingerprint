import os
import time
import ctypes
import requests
import win32gui
import win32process
import psutil
from datetime import datetime
from winotify import Notification, audio
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

API_URL = os.environ.get(
    "COLLECTOR_API_URL",
    "http://localhost:5050/api/activity"
).strip()

CHECK_INTERVAL = 2
RETRY_INTERVAL_SECONDS = 5
PENDING_ACTIVITY = []
NEXT_RETRY_AT = 0.0


FOCUS_APPS = {
    "Code.exe": "Coding",
    "pycharm64.exe": "Coding",
    "idea64.exe": "Coding",
    "WINWORD.EXE": "Writing",
    "POWERPNT.EXE": "Study",
    "EXCEL.EXE": "Study",
    "AcroRd32.exe": "Research",
}


DISTRACTION_APPS = {
    "chrome.exe": "Browser",
    "msedge.exe": "Browser",
    "firefox.exe": "Browser",
    "WhatsApp.exe": "Communication",
    "Discord.exe": "Communication",
    "Spotify.exe": "Entertainment",
}


def get_active_window():
    """
    Returns:
        application_name,
        process_name,
        window_title
    """

    try:
        hwnd = win32gui.GetForegroundWindow()

        if not hwnd:
            return None, None, None

        window_title = win32gui.GetWindowText(hwnd)

        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        process = psutil.Process(pid)

        process_name = process.name()

        return (
            process_name,
            process_name,
            window_title
        )

    except Exception:
        return None, None, None



def classify_application(process_name, window_title):
    """
    Classifies desktop applications and browser websites.
    Category names match the backend CATEGORIES mapping.
    """

    process = (process_name or "").lower()
    title = (window_title or "").lower()

    # Desktop application categories
    app_categories = {
        # Coding
        "code.exe": "Coding",
        "pycharm64.exe": "Coding",
        "idea64.exe": "Coding",
        "devenv.exe": "Coding",
        "eclipse.exe": "Coding",
        "studio64.exe": "Coding",
        "postman.exe": "Coding",
        "windowsterminal.exe": "Coding",
        "powershell.exe": "Coding",
        "cmd.exe": "Coding",

        # Study and writing
        "winword.exe": "Writing",
        "onenote.exe": "Study",
        "powerpnt.exe": "Work",
        "excel.exe": "Work",
        "acrord32.exe": "Research",
        "sumatrapdf.exe": "Research",

        # Communication
        "whatsapp.exe": "Communication",
        "whatsapp.root.exe": "Communication",
        "discord.exe": "Communication",
        "telegram.exe": "Communication",
        "slack.exe": "Communication",
        "teams.exe": "Communication",
        "zoom.exe": "Communication",

        # Design
        "figma.exe": "Design",
        "canva.exe": "Design",
        "photoshop.exe": "Design",
        "illustrator.exe": "Design",

        # Entertainment
        "spotify.exe": "Entertainment",
        "steam.exe": "Gaming",
        "epicgameslauncher.exe": "Gaming",
    }

    if process in app_categories:
        category = app_categories[process]
        focus = (
            "Distracted"
            if category in {
                "Communication",
                "Entertainment",
                "Gaming",
            }
            else "Focused"
        )
        return category, focus

    # Browser website classification
    website_categories = {
        # Social media
        "instagram": "Social Media",
        "facebook": "Social Media",
        "twitter": "Social Media",
        "x.com": "Social Media",
        "reddit": "Social Media",
        "tiktok": "Social Media",
        "snapchat": "Social Media",
        "pinterest": "Social Media",
        "threads": "Social Media",

        # Entertainment
        "youtube": "Entertainment",
        "netflix": "Entertainment",
        "prime video": "Entertainment",
        "disney+": "Entertainment",
        "twitch": "Entertainment",

        # Shopping
        "amazon": "Shopping",
        "flipkart": "Shopping",
        "myntra": "Shopping",

        # Communication
        "web.whatsapp": "Communication",
        "web.telegram": "Communication",
        "messenger": "Communication",

        # AI Assistants
"chatgpt": "AI Assistant",
"openai": "AI Assistant",
"claude": "AI Assistant",
"anthropic": "AI Assistant",
"gemini": "AI Assistant",
"perplexity": "AI Assistant",
"microsoft copilot": "AI Assistant",

        # Study
        "khan academy": "Study",
        "coursera": "Study",
        "udemy": "Study",
        "edx": "Study",
        "nptel": "Study",
        "quizlet": "Study",
        "google classroom": "Study",
        "moodle": "Study",
        "google docs": "Study",

        # Research
        "google scholar": "Research",
        "researchgate": "Research",
        "arxiv": "Research",
        "semantic scholar": "Research",
        "ieee": "Research",
        "springer": "Research",
        "overleaf": "Research",
        "mendeley": "Research",

        # Coding
        "github": "Coding",
        "stackoverflow": "Coding",
        "stack overflow": "Coding",
        "google colab": "Coding",
        "replit": "Coding",

        # Writing and productivity
        "notion": "Writing",
        "obsidian": "Writing",
        "grammarly": "Writing",
        "google keep": "Writing",
        "google sheets": "Work",
        "google slides": "Work",
        "trello": "Work",
        "asana": "Work",
        "jira": "Work",

        # Design
        "canva": "Design",
        "figma": "Design",
    }

    for keyword, category in website_categories.items():
        if keyword in title:
            focus = (
                "Distracted"
                if category in {
                    "Social Media",
                    "Entertainment",
                    "Shopping",
                    "Communication",
                }
                else "Focused"
            )
            return category, focus

    # Unidentified browser pages
    browsers = {
        "chrome.exe",
        "msedge.exe",
        "firefox.exe",
    }

    if process in browsers:
        return "Browser", "Focused"

    if process == "explorer.exe":
        return "Work", "Focused"

    return "Other", "Focused"


def get_activity_name(process_name, window_title):
    """
    Returns a readable application or website name.
    """

    title = (window_title or "").lower()
    process = (process_name or "").lower()

    website_names = {
        "instagram": "Instagram",
        "facebook": "Facebook",
        "youtube": "YouTube",
        "twitter": "Twitter / X",
        "x.com": "Twitter / X",
        "youtube": "YouTube",
        "netflix": "Netflix",
        "reddit": "Reddit",
        "tiktok": "TikTok",
        "snapchat": "Snapchat",
        "pinterest": "Pinterest",
        "threads": "Threads",
        "prime video": "Amazon Prime Video",
        "disney+": "Disney+",
        "twitch": "Twitch",
        "khan academy": "Khan Academy",
        "coursera": "Coursera",
        "udemy": "Udemy",
        "edx": "edX",
        "nptel": "NPTEL",
        "quizlet": "Quizlet",
        "google classroom": "Google Classroom",
        "google docs": "Google Docs",
        "google scholar": "Google Scholar",
        "researchgate": "ResearchGate",
        "arxiv": "arXiv",
        "semantic scholar": "Semantic Scholar",
        "overleaf": "Overleaf",
        "github": "GitHub",
        "stackoverflow": "Stack Overflow",
        "google colab": "Google Colab",
        "notion": "Notion",
        "obsidian": "Obsidian",
        "grammarly": "Grammarly",
        "canva": "Canva",
        "figma": "Figma",
        "web.whatsapp": "WhatsApp Web",
        "web.telegram": "Telegram Web",
        "flipkart": "Flipkart",
        "myntra": "Myntra",
    }

    for keyword, name in website_names.items():
        if keyword in title:
            return name

    app_names = {
        "code.exe": "VS Code",
        "pycharm64.exe": "PyCharm",
        "idea64.exe": "IntelliJ IDEA",
        "devenv.exe": "Visual Studio",
        "eclipse.exe": "Eclipse",
        "studio64.exe": "Android Studio",
        "winword.exe": "Microsoft Word",
        "powerpnt.exe": "Microsoft PowerPoint",
        "excel.exe": "Microsoft Excel",
        "onenote.exe": "Microsoft OneNote",
        "acrord32.exe": "Adobe Acrobat Reader",
        "whatsapp.exe": "WhatsApp",
        "whatsapp.root.exe": "WhatsApp",
        "discord.exe": "Discord",
        "telegram.exe": "Telegram",
        "slack.exe": "Slack",
        "teams.exe": "Microsoft Teams",
        "zoom.exe": "Zoom",
        "spotify.exe": "Spotify",
        "steam.exe": "Steam",
        "epicgameslauncher.exe": "Epic Games Launcher",
    }

    return app_names.get(process, process_name or "Unknown")


def show_distraction_alert(application, category):
    """
    Shows a Windows notification when a distracting
    activity continues for the alert threshold.
    """

    try:
        toast = Notification(
            app_id="ProcrastiSense AI",
            title="⚠️ Distraction Detected",
            msg=(
                f"You are currently using {application}. "
                "This may interrupt your focus session. "
                "Consider returning to your task."
            ),
            duration="short"
        )

        toast.set_audio(
            audio.Default,
            loop=False
        )

        toast.show()

        print(
            f"[ALERT] Distraction detected: "
            f"{application} | {category}"
        )

    except Exception as e:
        print(
            f"[WARNING] Could not show notification: {e}"
        )


CURRENT_TASK_TYPE = None
CURRENT_TASK_DIFFICULTY = None
CURRENT_COLLECTOR_TOKEN = None


def get_idle_seconds():
    """Return seconds since the last Windows input event."""
    if os.name != "nt":
        return 0

    from ctypes import wintypes

    class LastInputInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("dwTime", wintypes.DWORD),
        ]

    info = LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0

    elapsed_ms = (
        ctypes.windll.kernel32.GetTickCount() - info.dwTime
    ) & 0xFFFFFFFF
    return elapsed_ms // 1000


def flush_pending_activities():
    """Retry queued activity records without discarding failed submissions."""
    global NEXT_RETRY_AT

    if time.monotonic() < NEXT_RETRY_AT:
        return

    while PENDING_ACTIVITY:
        payload, token = PENDING_ACTIVITY[0]

        try:
            response = requests.post(
                API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=3
            )
        except requests.exceptions.RequestException:
            NEXT_RETRY_AT = time.monotonic() + RETRY_INTERVAL_SECONDS
            print(
                "[WARNING] Activity API is unavailable; "
                f"{len(PENDING_ACTIVITY)} record(s) queued for retry."
            )
            return

        if response.status_code != 201:
            NEXT_RETRY_AT = time.monotonic() + RETRY_INTERVAL_SECONDS
            print(
                "[WARNING] Activity API rejected a record "
                f"(HTTP {response.status_code}); "
                f"{len(PENDING_ACTIVITY)} record(s) retained for retry."
            )
            return

        PENDING_ACTIVITY.pop(0)
        print(
            f"[RECORDED] {payload['application']} | {payload['category']} | "
            f"{payload['focus_level']} | {payload['task_type']} | "
            f"{payload['task_difficulty']}"
        )

    NEXT_RETRY_AT = 0.0


def send_activity(application, category, duration, focus_level, idle_seconds=0):
    """
    Sends one completed activity session to Flask.
    """
    print(
    f"SEND CHECK: app={application}, "
    f"category={category}, "
    f"focus={repr(focus_level)}, "
    f"token_present={bool(CURRENT_COLLECTOR_TOKEN)}, "
    f"task_present={bool(CURRENT_TASK_TYPE)}"
)
    if not CURRENT_COLLECTOR_TOKEN or not CURRENT_TASK_TYPE:
        return
    print(
    f"SENDING RECORD: {application} | "
    f"{category} | {repr(focus_level)}"
)

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "application": application,
        "category": category,
        "duration_min": round(duration / 60, 2),
        "task_type": CURRENT_TASK_TYPE,
        "task_difficulty": CURRENT_TASK_DIFFICULTY,
        "idle_seconds": idle_seconds,
        "notifications": 0,
        "focus_level": focus_level
    }

    PENDING_ACTIVITY.append((payload, CURRENT_COLLECTOR_TOKEN))
    flush_pending_activities()


class CollectorBridgeHandler(BaseHTTPRequestHandler):

    ALLOWED_ORIGINS = {
        "http://127.0.0.1:5050",
        "http://localhost:5050",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        *(
            origin.strip().rstrip("/")
            for origin in os.environ.get("FRONTEND_ORIGIN", "").split(",")
            if origin.strip()
        ),
    }

    def send_cors_headers(self):
        origin = self.headers.get("Origin", "")

        if origin in self.ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")

        self.end_headers()

    def do_POST(self):

        global CURRENT_TASK_TYPE
        global CURRENT_TASK_DIFFICULTY
        global CURRENT_COLLECTOR_TOKEN

        origin = self.headers.get("Origin", "")

        if origin not in self.ALLOWED_ORIGINS:
            self.send_error(403, "Origin not allowed")
            return

        if self.path != "/task":
            self.send_error(404, "Endpoint not found")
            return

        try:
            length = int(self.headers.get("Content-Length", 0))

            if length <= 0 or length > 8192:
                self.send_error(400, "Invalid request size")
                return

            data = json.loads(self.rfile.read(length))

            action = data.get("action")

            if action == "start":

                token = data.get("token")
                task_type = data.get("task_type")
                difficulty = data.get("task_difficulty")

                if not token or not task_type:
                    self.send_error(400, "Missing task or token")
                    return

                if difficulty not in ["Low", "Medium", "High"]:
                    self.send_error(400, "Invalid difficulty")
                    return

                CURRENT_COLLECTOR_TOKEN = token
                CURRENT_TASK_TYPE = task_type
                CURRENT_TASK_DIFFICULTY = difficulty

            elif action == "stop":

                CURRENT_TASK_TYPE = None
                CURRENT_TASK_DIFFICULTY = None
                CURRENT_COLLECTOR_TOKEN = None

            else:
                self.send_error(400, "Invalid action")
                return

            self.send_response(200)
            self.send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                json.dumps({"success": True}).encode("utf-8")
            )

        except Exception as error:
            print("Collector bridge error:", error)
            self.send_error(400, "Invalid request")

    def log_message(self, format, *args):
        pass


def run_collector_bridge():

    server = HTTPServer(
        ("127.0.0.1", 5051),
        CollectorBridgeHandler
    )

    print("[BRIDGE] Local website connection ready on port 5051")

    server.serve_forever()



def main():

    global CURRENT_TASK_TYPE, CURRENT_TASK_DIFFICULTY

    # Task and difficulty will be received from the website.
    CURRENT_TASK_TYPE = None
    CURRENT_TASK_DIFFICULTY = None

    print("=" * 60)
    print("ProcrastiSense REAL-TIME ACTIVITY COLLECTOR")
        # Start the local website-to-collector communication bridge
    bridge_thread = threading.Thread(
        target=run_collector_bridge,
        daemon=True
    )
    bridge_thread.start()
    print("=" * 60)
    print("\nMonitoring your active Windows application...")
    print("Task and difficulty will be managed through the website.")
    print("Distraction alert threshold: 15 seconds.")
    print("Press CTRL+C to stop.\n")

    previous_process = None
    previous_activity = None
    previous_category = None
    previous_focus = None

    session_start = time.time()

    distraction_start = None
    distraction_alert_sent = False

    ALERT_AFTER_SECONDS = 15

    try:
        while True:

            flush_pending_activities()
            idle_seconds = get_idle_seconds()
            now = time.time()

            if idle_seconds >= 60:
                if previous_focus != "Idle":
                    idle_started_at = now - idle_seconds
                    active_duration = max(0, idle_started_at - session_start)

                    if previous_activity is not None and active_duration > 0:
                        send_activity(
                            previous_activity,
                            previous_category,
                            active_duration,
                            previous_focus
                        )

                    previous_process = None
                    previous_activity = "Screen Locked"
                    previous_category = "Other"
                    previous_focus = "Idle"
                    session_start = idle_started_at
                    distraction_start = None
                    distraction_alert_sent = False

                time.sleep(CHECK_INTERVAL)
                continue

            if previous_focus == "Idle":
                idle_duration = max(0, now - session_start)
                if idle_duration > 0:
                    send_activity(
                        previous_activity,
                        previous_category,
                        idle_duration,
                        "Idle",
                        idle_seconds=int(idle_duration)
                    )

                previous_process = None
                previous_activity = None
                previous_category = None
                previous_focus = None
                session_start = now

            process_name, _, window_title = get_active_window()

            if process_name is None:
                flush_pending_activities()
                time.sleep(CHECK_INTERVAL)
                continue

            print("DEBUG:", process_name, "|", window_title)

            activity_name = get_activity_name(
                process_name,
                window_title
            )

            category, focus_level = classify_application(
                process_name,
                window_title
            )
            print(
    f"CLASSIFICATION: {process_name} | "
    f"{activity_name} | {category} | {focus_level}"
)

            if previous_process is None:

                previous_process = process_name
                previous_category = category
                previous_focus = focus_level
                previous_activity = activity_name

                session_start = time.time()

            elif (
                process_name != previous_process
                or activity_name != previous_activity
            ):

                duration = time.time() - session_start

                send_activity(
                    previous_activity,
                    previous_category,
                    duration,
                    previous_focus,
                    idle_seconds=int(duration) if previous_focus == "Idle" else 0
                )

                previous_process = process_name
                previous_category = category
                previous_focus = focus_level
                previous_activity = activity_name

                session_start = time.time()

                distraction_start = None
                distraction_alert_sent = False

            elif (
                category != previous_category
                or focus_level != previous_focus
            ):

                duration = time.time() - session_start

                send_activity(
                    previous_activity,
                    previous_category,
                    duration,
                    previous_focus
                )

                previous_category = category
                previous_focus = focus_level

                session_start = time.time()

            if focus_level == "Distracted":

                if distraction_start is None:
                    distraction_start = time.time()
                    distraction_alert_sent = False

                distraction_duration = (
                    time.time() - distraction_start
                )

                if (
                    distraction_duration >= ALERT_AFTER_SECONDS
                    and not distraction_alert_sent
                ):

                    show_distraction_alert(
                        activity_name,
                        category
                    )

                    distraction_alert_sent = True

            else:
                distraction_start = None
                distraction_alert_sent = False

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:

        print()

        if previous_activity is not None:

            duration = time.time() - session_start

            if duration > 0:
                send_activity(
                    previous_activity,
                    previous_category,
                    duration,
                    previous_focus
                )

        print("Activity collector stopped.")


if __name__ == "__main__":
    main()
