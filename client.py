import socket
import time
import threading
import requests
import base64
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Config ────────────────────────────────────────────────────────────────────
LIVESPLIT_HOST = "127.0.0.1"
LIVESPLIT_PORT = 16834
SERVER_URL = "http://34.130.30.159:5000"
# ──────────────────────────────────────────────────────────────────────────────

BG = "#1a1a2e"
PANEL = "#16213e"
ACCENT = "#0f3460"
GOLD = "#e94560"
TEXT = "#eaeaea"
DIM = "#888888"
GREEN = "#4ecca3"
RED = "#e94560"

FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_HEAD  = ("Segoe UI", 14, "bold")
FONT_BODY  = ("Segoe UI", 11)
FONT_MONO  = ("Consolas", 11)
FONT_BIG   = ("Consolas", 28, "bold")


# ── LiveSplit helpers ─────────────────────────────────────────────────────────

def send_command(command):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((LIVESPLIT_HOST, LIVESPLIT_PORT))
            s.settimeout(1.0)
            s.sendall((command + "\r\n").encode())
            try:
                return s.recv(4096).decode().strip()
            except socket.timeout:
                return None
    except (ConnectionRefusedError, TimeoutError, OSError):
        return None


def get_phase():        return send_command("gettimerphase")
def get_split_index():
    try:    return int(send_command("getsplitindex"))
    except: return -1
def get_last_split_time(): return send_command("getlastsplittime real")
def get_split_name(i):     return send_command(f"getsplitname {i}")
def get_final_time():      return send_command("getfinalsplittime real")


# ── Server helpers ────────────────────────────────────────────────────────────

def api(method, path, **kwargs):
    try:
        resp = requests.request(method, SERVER_URL + path, timeout=10, **kwargs)
        return resp.json()
    except Exception as e:
        return None


def parse_time_to_seconds(time_str):
    """Convert LiveSplit time string like 1:23:45.67 or 23:45.67 to seconds."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(parts[0])
    except Exception:
        return None


# ── Profile picture helpers ───────────────────────────────────────────────────

def upload_profile_pic(username, filepath):
    """Resize image to 128x128, encode as base64, upload to server."""
    if not PIL_AVAILABLE:
        return False, "Pillow not installed (pip install Pillow)"
    try:
        img = Image.open(filepath).convert("RGBA")
        img = img.resize((128, 128), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        result = api("POST", "/profile/upload", json={"username": username, "image_b64": b64})
        if result and result.get("ok"):
            return True, b64
        return False, str(result)
    except Exception as e:
        return False, str(e)


def fetch_profile_pic(username):
    """Fetch base64 profile pic from server. Returns PhotoImage or None."""
    if not PIL_AVAILABLE:
        return None
    try:
        data = api("GET", f"/profile/get?username={username}")
        if not data or not data.get("image_b64"):
            return None
        raw = base64.b64decode(data["image_b64"])
        img = Image.open(io.BytesIO(raw)).convert("RGBA").resize((96, 96), Image.LANCZOS)
        # Circular crop
        mask = Image.new("L", (96, 96), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 96, 96), fill=255)
        img.putalpha(mask)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def make_placeholder_photo(size=96, color=ACCENT):
    """Create a plain coloured circle as a placeholder avatar."""
    if not PIL_AVAILABLE:
        return None
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    draw.ellipse((0, 0, size, size), fill=(r, g, b, 255))
    return ImageTk.PhotoImage(img)


# ── Main App ──────────────────────────────────────────────────────────────────

class RaceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiveSplit Race Client")
        self.geometry("700x640")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.username = ""
        self.password = ""        # set after successful /auth/login
        self.code = ""
        self.opponent = ""        # set during matchmaking
        self.ghost_opponent = ""  # set when entering a ghost match
        self.max_players = 2      # set when creating/joining a room
        self.ranked = True        # False for FFA (create room) matches
        self.round_num = 1
        self.my_pic_b64 = None   # cached base64 of our own uploaded pic

        self._frame = None
        self.show_frame(LoginFrame)

    def show_frame(self, cls, **kwargs):
        if self._frame:
            self._frame.destroy()
        self._frame = cls(self, **kwargs)
        self._frame.pack(fill="both", expand=True)


# ── Reusable widgets ──────────────────────────────────────────────────────────

def styled_btn(parent, text, command, color=ACCENT, fg=TEXT, width=20):
    btn = tk.Button(parent, text=text, command=command,
                    bg=color, fg=fg, font=FONT_BODY,
                    relief="flat", cursor="hand2",
                    activebackground=GOLD, activeforeground="white",
                    padx=12, pady=8, width=width)
    return btn

def label(parent, text, font=FONT_BODY, fg=TEXT, bg=BG, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, **kw)

def entry(parent, textvariable=None, width=24, show=None):
    e = tk.Entry(parent, textvariable=textvariable, width=width,
                 font=FONT_BODY, bg=PANEL, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightcolor=GOLD,
                 highlightbackground=DIM)
    if show:
        e.config(show=show)
    return e

def separator(parent):
    return tk.Frame(parent, bg=ACCENT, height=2)


# ── Screen: Login / Room Setup ────────────────────────────────────────────────

class LoginFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.master = master
        self._photo = None   # keep reference to avoid GC

        label(self, "LiveSplit Race", font=FONT_TITLE, fg=GOLD).pack(pady=(24, 2))
        label(self, "Best of 5 Match", font=FONT_BODY, fg=DIM).pack(pady=(0, 16))

        # ── Profile picture + username row ────────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack()

        # Avatar canvas (circle)
        self._avatar_canvas = tk.Canvas(top, width=80, height=80, bg=BG,
                                        highlightthickness=0)
        self._avatar_canvas.pack(side="left", padx=(0, 16))
        self._draw_placeholder_avatar()

        right = tk.Frame(top, bg=BG)
        right.pack(side="left")
        label(right, "Username", fg=DIM).pack(anchor="w")
        self.uvar = tk.StringVar()
        entry(right, self.uvar, width=20).pack(pady=(2, 4))
        pw_row = tk.Frame(right, bg=BG)
        pw_row.pack(anchor="w")
        label(pw_row, "Password", fg=DIM, bg=BG).pack(side="left")
        label(pw_row, "  (use a throwaway — not secure storage)",
              fg="#555577", font=("Segoe UI", 8, "italic"), bg=BG).pack(side="left")
        self.pvar = tk.StringVar()
        entry(right, self.pvar, width=20, show="●").pack(pady=(2, 6))
        styled_btn(right, "Upload Profile Pic", self._pick_pic,
                   color=ACCENT, width=18).pack(anchor="w")

        self.pic_status = label(self, "", fg=DIM, font=("Segoe UI", 9))
        self.pic_status.pack()

        # ── Account hint (new / returning) ────────────────────────────────────
        self.account_hint = label(self, "", fg=DIM, font=("Segoe UI", 9, "italic"))
        self.account_hint.pack()

        # ── ELO display ───────────────────────────────────────────────────────
        self.elo_label = label(self, "", fg=GOLD, font=("Consolas", 13, "bold"))
        self.elo_label.pack(pady=(4, 0))

        separator(self).pack(fill="x", padx=60, pady=8)

        # ── Action buttons ────────────────────────────────────────────────────
        styled_btn(self, "Find Match",  self.find_match,  color=GOLD,  fg="white").pack(pady=(4, 6))
        styled_btn(self, "Create Room", self.create_room, color=GREEN, fg=BG).pack(pady=(0, 6))
        styled_btn(self, "Join Room",   self.join_room).pack(pady=(0, 6))
        styled_btn(self, "👻 Ghost Match", self.ghost_match, color="#2a1a4a", fg="#c084fc").pack()

        self.status = label(self, "", fg=RED)
        self.status.pack(pady=6)

        # Check LiveSplit
        threading.Thread(target=self._check_livesplit, daemon=True).start()
        # Fetch ELO + account hint when username is typed (trace)
        self.uvar.trace_add("write", self._on_username_change)
        self._elo_fetch_timer = None

    def _draw_placeholder_avatar(self):
        self._avatar_canvas.delete("all")
        self._avatar_canvas.create_oval(2, 2, 78, 78, fill=ACCENT, outline=DIM, width=2)
        self._avatar_canvas.create_text(40, 40, text="?", font=("Segoe UI", 28, "bold"),
                                        fill=DIM)

    def _draw_avatar_from_b64(self, b64):
        if not PIL_AVAILABLE: return
        try:
            raw = base64.b64decode(b64)
            img = Image.open(io.BytesIO(raw)).convert("RGBA").resize((76, 76), Image.LANCZOS)
            mask = Image.new("L", (76, 76), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 76, 76), fill=255)
            img.putalpha(mask)
            self._photo = ImageTk.PhotoImage(img)
            self._avatar_canvas.delete("all")
            self._avatar_canvas.create_oval(0, 0, 80, 80, outline=GOLD, width=2)
            self._avatar_canvas.create_image(40, 40, image=self._photo)
        except Exception:
            pass

    def _pick_pic(self):
        u = self.uvar.get().strip()
        if not u:
            self.pic_status.config(text="Enter a username first.", fg=RED)
            return
        path = filedialog.askopenfilename(
            title="Choose profile picture",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")]
        )
        if not path: return
        self.pic_status.config(text="Uploading...", fg=DIM)
        threading.Thread(target=self._do_upload_pic, args=(u, path), daemon=True).start()

    def _do_upload_pic(self, u, path):
        ok, result = upload_profile_pic(u, path)
        if ok:
            self.master.my_pic_b64 = result
            self.after(0, lambda: self.pic_status.config(text="Profile picture uploaded!", fg=GREEN))
            self.after(0, lambda: self._draw_avatar_from_b64(result))
        else:
            self.after(0, lambda: self.pic_status.config(text=f"Upload failed: {result}", fg=RED))

    def _check_livesplit(self):
        phase = get_phase()
        if phase is None:
            self.after(0, lambda: self.status.config(
                text="⚠  LiveSplit not connected — open LiveSplit and start TCP Server"))
        else:
            self.after(0, lambda: self.status.config(
                text="✔  LiveSplit connected", fg=GREEN))

    def _on_username_change(self, *_):
        """Debounce: fetch ELO + account hint 600ms after the user stops typing."""
        if self._elo_fetch_timer:
            self.after_cancel(self._elo_fetch_timer)
        self._elo_fetch_timer = self.after(600, self._fetch_elo_and_hint)

    def _fetch_elo_and_hint(self):
        u = self.uvar.get().strip()
        if not u:
            self.elo_label.config(text="")
            self.account_hint.config(text="")
            return
        threading.Thread(target=self._do_fetch_elo_and_hint, args=(u,), daemon=True).start()

    def _do_fetch_elo_and_hint(self, u):
        # Fetch ELO
        elo_data = api("GET", f"/elo?username={u}")
        if elo_data and "elo" in elo_data:
            elo    = elo_data["elo"]
            wins   = elo_data.get("wins", 0)
            losses = elo_data.get("losses", 0)
            self.after(0, lambda: self.elo_label.config(
                text=f"ELO: {elo}   W{wins} / L{losses}", fg=GOLD))
        else:
            self.after(0, lambda: self.elo_label.config(
                text="ELO: 1000  (new player)", fg=DIM))

        # Check if account exists → show hint
        check = api("GET", f"/auth/check?username={u}")
        if check and check.get("exists"):
            self.after(0, lambda: self.account_hint.config(
                text="✔  Returning player — enter your password", fg=GREEN))
        else:
            self.after(0, lambda: self.account_hint.config(
                text="✨  New account — choose a password (min 4 chars)", fg=DIM))

    def _get_credentials(self):
        """Return (username, password) or (None, None) with an error shown."""
        u = self.uvar.get().strip()
        p = self.pvar.get()
        if not u:
            self.status.config(text="Username cannot be empty.", fg=RED)
            return None, None
        if not p:
            self.status.config(text="Password cannot be empty.", fg=RED)
            return None, None
        return u, p

    def _do_auth_then(self, u, p, callback):
        """Call /auth/login, then invoke callback(u, p) on success."""
        result = api("POST", "/auth/login", json={"username": u, "password": p})
        if not result:
            self.after(0, lambda: self.status.config(text="Server unreachable.", fg=RED))
            return
        if "error" in result:
            self.after(0, lambda: self.status.config(
                text=result["error"], fg=RED))
            return
        # Auth OK — store password on master for subsequent calls
        self.master.password = p
        callback(u, p)

    def create_room(self):
        u, p = self._get_credentials()
        if not u: return
        self.status.config(text="Authenticating…", fg=DIM)
        threading.Thread(target=self._do_auth_then, args=(u, p, self._after_auth_create),
                         daemon=True).start()

    def _after_auth_create(self, u, p):
        # Show player-count picker before creating the room
        self.master.username = u
        self.after(0, lambda: self.master.show_frame(CreateRoomOptionsFrame))

    def find_match(self):
        u, p = self._get_credentials()
        if not u: return
        self.status.config(text="Authenticating…", fg=DIM)
        threading.Thread(target=self._do_auth_then, args=(u, p, self._after_auth_find),
                         daemon=True).start()

    def _after_auth_find(self, u, p):
        self.after(0, lambda: self.status.config(text="Joining queue…", fg=DIM))
        data = api("POST", "/queue/join", json={"username": u, "password": p})
        if not data or "error" in data:
            self.after(0, lambda: self.status.config(
                text=f"Error: {data.get('error', 'No response') if data else 'No response'}", fg=RED))
            return
        self.master.username = u
        if data.get("status") == "matched":
            self.master.code = data["code"]
            self.master.opponent = data.get("opponent", "Opponent")
            self.after(0, lambda: self.master.show_frame(MatchIntroFrame))
        else:
            self.after(0, lambda: self.master.show_frame(MatchmakingFrame))

    def join_room(self):
        u, p = self._get_credentials()
        if not u: return
        self.status.config(text="Authenticating…", fg=DIM)
        threading.Thread(target=self._do_auth_then,
                         args=(u, p, lambda _u, _p: self.after(
                             0, lambda: self.master.show_frame(JoinFrame, username=_u))),
                         daemon=True).start()

    def ghost_match(self):
        u, p = self._get_credentials()
        if not u: return
        self.status.config(text="Authenticating…", fg=DIM)
        def _after(u, p):
            self.master.username = u
            self.after(0, lambda: self.master.show_frame(GhostMatchFrame))
        threading.Thread(target=self._do_auth_then, args=(u, p, _after),
                         daemon=True).start()


# ── Screen: Ghost Match — pick opponent ──────────────────────────────────────

class GhostMatchFrame(tk.Frame):
    """Let the player choose a ghost opponent from player_times.json."""

    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.master = master
        self._players = []   # list of dicts from /ghost/players

        label(self, "👻 Ghost Match", font=FONT_TITLE, fg="#c084fc").pack(pady=(20, 2))
        label(self, "Race against a simulated opponent", font=FONT_BODY, fg=DIM).pack(pady=(0, 12))

        # ── Player list ───────────────────────────────────────────────────────
        list_outer = tk.Frame(self, bg=PANEL, bd=0)
        list_outer.pack(fill="both", expand=True, padx=40, pady=(0, 8))

        header_row = tk.Frame(list_outer, bg=ACCENT)
        header_row.pack(fill="x")
        for col, w in [("Player", 18), ("Runs", 5), ("Best", 10), ("Avg", 10)]:
            tk.Label(header_row, text=col, font=("Segoe UI", 10, "bold"),
                     bg=ACCENT, fg=TEXT, width=w, anchor="w").pack(side="left", padx=4, pady=4)

        self._listbox = tk.Listbox(
            list_outer, bg=PANEL, fg=TEXT, font=FONT_MONO,
            selectbackground="#2a1a4a", selectforeground="#c084fc",
            relief="flat", highlightthickness=0, activestyle="none",
            height=10
        )
        self._listbox.pack(fill="both", expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        self._status = label(self, "Loading players…", fg=DIM)
        self._status.pack(pady=4)

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=8)
        self._race_btn = styled_btn(btn_row, "Race Ghost →", self._start_ghost,
                                    color="#2a1a4a", fg="#c084fc", width=18)
        self._race_btn.config(state="disabled")
        self._race_btn.pack(side="left", padx=8)
        styled_btn(btn_row, "Back", lambda: master.show_frame(LoginFrame),
                   color=ACCENT, width=10).pack(side="left", padx=8)

        threading.Thread(target=self._load_players, daemon=True).start()

    def _load_players(self):
        data = api("GET", "/ghost/players")
        if not data:
            self.after(0, lambda: self._status.config(text="Could not load players.", fg=RED))
            return
        self._players = data
        self.after(0, self._populate_list)

    def _populate_list(self):
        self._listbox.delete(0, "end")
        if not self._players:
            self._status.config(text="No players with recorded times yet.", fg=DIM)
            return
        for p in self._players:
            # Skip yourself
            if p["username"] == self.master.username:
                continue
            line = f"  {p['username']:<18}  {p['count']:<5}  {p['best_str']:<10}  {p['avg_str']}"
            self._listbox.insert("end", line)
        self._status.config(text=f"{len(self._players)} ghost(s) available", fg=DIM)

    def _on_select(self, _event=None):
        if self._listbox.curselection():
            self._race_btn.config(state="normal")
        else:
            self._race_btn.config(state="disabled")

    def _get_selected_player(self):
        sel = self._listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        # Rebuild index skipping self
        visible = [p for p in self._players if p["username"] != self.master.username]
        if idx >= len(visible):
            return None
        return visible[idx]

    def _start_ghost(self):
        p = self._get_selected_player()
        if not p:
            return
        self.master.ghost_opponent = p["username"]
        scores = {self.master.username: 0, f"ghost:{p['username']}": 0}
        self.master.show_frame(GhostRaceFrame, round_num=1, scores=scores, rounds={})


# ── Screen: Ghost Race (one round) ───────────────────────────────────────────

class GhostRaceFrame(tk.Frame):
    """Watch LiveSplit for a run, then simulate the ghost's time and show result."""

    def __init__(self, master, round_num, scores, rounds):
        super().__init__(master, bg=BG)
        self.master = master
        self.round_num = round_num
        self.scores = scores          # mutable dict passed between rounds
        self.rounds = rounds          # accumulated round history
        self._running = True
        self.run_started = False
        self.last_phase = None
        self.last_index = -1
        self.split_times = []

        ghost_key = f"ghost:{master.ghost_opponent}"

        # Header
        hdr = tk.Frame(self, bg="#2a1a4a")
        hdr.pack(fill="x")
        label(hdr, f"👻 GHOST ROUND {round_num}  —  Best of 5",
              font=FONT_HEAD, bg="#2a1a4a", fg=TEXT).pack(side="left", padx=16, pady=10)
        label(hdr, f"{master.username}  vs  ghost:{master.ghost_opponent}",
              font=FONT_BODY, bg="#2a1a4a", fg="#c084fc").pack(side="right", padx=16)

        # Score display
        score_row = tk.Frame(self, bg=BG)
        score_row.pack(pady=(10, 0))
        you_score   = scores.get(master.username, 0)
        ghost_score = scores.get(ghost_key, 0)
        label(score_row, f"{master.username}: {you_score}",
              fg=GREEN, font=FONT_HEAD).pack(side="left", padx=20)
        label(score_row, "vs", fg=DIM, font=FONT_BODY).pack(side="left")
        label(score_row, f"ghost:{master.ghost_opponent}: {ghost_score}",
              fg="#c084fc", font=FONT_HEAD).pack(side="left", padx=20)

        self.status_lbl = label(self, "Waiting for run to start…", font=FONT_HEAD, fg=DIM)
        self.status_lbl.pack(pady=(16, 2))

        self.timer_lbl = label(self, "--:--.-", font=FONT_BIG, fg=GOLD)
        self.timer_lbl.pack(pady=2)

        separator(self).pack(fill="x", padx=40, pady=6)

        list_frame = tk.Frame(self, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=40)
        self.splits_box = tk.Text(list_frame, bg=PANEL, fg=TEXT, font=FONT_MONO,
                                  relief="flat", state="disabled", height=11,
                                  highlightthickness=0)
        self.splits_box.pack(fill="both", expand=True)

        threading.Thread(target=self._watch_run, daemon=True).start()

    def _append_split(self, text):
        self.splits_box.config(state="normal")
        self.splits_box.insert("end", text + "\n")
        self.splits_box.see("end")
        self.splits_box.config(state="disabled")

    def _watch_run(self):
        while self._running:
            phase = get_phase()

            if phase == "Running" and not self.run_started:
                self.run_started = True
                self.split_times = []
                self.last_index = -1
                self.after(0, lambda: self.status_lbl.config(text="▶  Run in progress…", fg=GREEN))

            if phase == "Ended" and self.last_phase != "Ended" and self.run_started:
                final = get_final_time()
                self._running = False
                self.after(0, lambda f=final: self._run_finished(f))
                return

            elif phase == "NotRunning" and self.last_phase not in ("NotRunning", None):
                if self.run_started:
                    self.after(0, lambda: self.status_lbl.config(
                        text="↺  Run reset — waiting for new run…", fg=RED))
                self.split_times = []
                self.last_index = -1
                self.run_started = False
                self.after(0, lambda: self.splits_box.config(state="normal"))
                self.after(0, lambda: self.splits_box.delete("1.0", "end"))
                self.after(0, lambda: self.splits_box.config(state="disabled"))

            elif phase == "Running":
                index = get_split_index()
                if index > self.last_index and self.last_index >= 0:
                    split_time = get_last_split_time()
                    split_name = get_split_name(self.last_index) or f"Split {self.last_index + 1}"
                    self.split_times.append((split_name, split_time))
                    n = len(self.split_times)
                    self.after(0, lambda n=n, sn=split_name, st=split_time:
                               self._append_split(f"  {n:>3}.  {sn:<28}  {st}"))
                self.last_index = index

            self.last_phase = phase
            time.sleep(0.1)

    def _run_finished(self, final_time):
        self.status_lbl.config(text="✔  Run complete — simulating ghost…", fg=GREEN)
        self.timer_lbl.config(text=final_time or "--:--.-")
        threading.Thread(target=self._simulate_ghost, args=(final_time,), daemon=True).start()

    def _simulate_ghost(self, my_time_str):
        # Parse my time
        my_seconds = parse_time_to_seconds(my_time_str) if my_time_str else None

        # Ask server to generate ghost time
        ghost_data = api("POST", "/ghost/simulate",
                         json={"ghost_username": self.master.ghost_opponent})

        if not ghost_data or "error" in ghost_data:
            self.after(0, lambda: self.status_lbl.config(
                text=f"Ghost simulation failed: {ghost_data}", fg=RED))
            return

        ghost_seconds = ghost_data["ghost_time_seconds"]
        ghost_time_str = ghost_data["ghost_time"]
        ghost_key = f"ghost:{self.master.ghost_opponent}"

        # Determine round winner
        if my_seconds is not None:
            if my_seconds <= ghost_seconds:
                round_winner = self.master.username
                self.scores[self.master.username] += 1
            else:
                round_winner = ghost_key
                self.scores[ghost_key] += 1
            margin = round(abs(my_seconds - ghost_seconds), 2)
        else:
            # No valid time from player — ghost wins
            round_winner = ghost_key
            self.scores[ghost_key] += 1
            margin = 0.0

        # Record this round
        rnum = str(self.round_num)
        self.rounds[rnum] = {
            self.master.username: {
                "time": my_time_str or "N/A",
                "time_seconds": my_seconds or 0.0,
            },
            ghost_key: {
                "time": ghost_time_str,
                "time_seconds": ghost_seconds,
            },
        }

        result = {
            "round_num":    self.round_num,
            "my_time":      my_time_str or "N/A",
            "my_seconds":   my_seconds or 0.0,
            "ghost_time":   ghost_time_str,
            "ghost_seconds": ghost_seconds,
            "round_winner": round_winner,
            "you_won_round": round_winner == self.master.username,
            "margin":       margin,
            "scores":       dict(self.scores),
            "rounds":       self.rounds,
        }

        self.after(0, lambda r=result: self.master.show_frame(
            GhostRoundResultFrame, result=r))

    def destroy(self):
        self._running = False
        super().destroy()


# ── Screen: Ghost Round Result ────────────────────────────────────────────────

class GhostRoundResultFrame(tk.Frame):
    def __init__(self, master, result):
        super().__init__(master, bg=BG)
        self.master = master
        self.result = result

        round_num    = result["round_num"]
        you_won      = result["you_won_round"]
        round_winner = result["round_winner"]
        scores       = result["scores"]
        rounds       = result["rounds"]
        ghost_key    = f"ghost:{master.ghost_opponent}"

        # Header
        hdr = tk.Frame(self, bg="#2a1a4a")
        hdr.pack(fill="x")
        label(hdr, f"👻 GHOST ROUND {round_num} RESULT",
              font=FONT_HEAD, bg="#2a1a4a", fg=TEXT).pack(side="left", padx=16, pady=10)

        # Round winner banner
        banner_color = GREEN if you_won else "#c084fc"
        banner_text  = f"🏆  You won round {round_num}!" if you_won else f"  {round_winner} won round {round_num}"
        tk.Frame(self, bg=banner_color, height=4).pack(fill="x")
        label(self, banner_text, font=FONT_HEAD, fg=banner_color).pack(pady=(16, 4))
        label(self, f"Margin: {result['margin']}s", fg=DIM).pack()

        separator(self).pack(fill="x", padx=40, pady=12)

        # Times table
        entries = [
            (master.username, result["my_time"],    result["my_seconds"]),
            (ghost_key,       result["ghost_time"],  result["ghost_seconds"]),
        ]
        entries.sort(key=lambda x: x[2])
        for i, (uname, t, _) in enumerate(entries):
            medal = "🥇" if i == 0 else "🥈"
            you   = "  ← you" if uname == master.username else ""
            row = tk.Frame(self, bg=PANEL)
            row.pack(fill="x", padx=40, pady=3)
            label(row, f"  {medal}  {uname}{you}", bg=PANEL, fg=TEXT, font=FONT_BODY).pack(side="left", padx=8, pady=6)
            label(row, t, bg=PANEL, fg=GOLD, font=FONT_MONO).pack(side="right", padx=8)

        separator(self).pack(fill="x", padx=40, pady=12)

        # Score board
        label(self, "Match Score", font=FONT_HEAD, fg=DIM).pack()
        score_row = tk.Frame(self, bg=BG)
        score_row.pack(pady=8)
        for player, score in scores.items():
            you_label = "\n(you)" if player == master.username else ""
            col = tk.Frame(score_row, bg=PANEL, padx=24, pady=10)
            col.pack(side="left", padx=12)
            label(col, f"{player}{you_label}", bg=PANEL, fg=TEXT, font=FONT_BODY).pack()
            label(col, str(score), bg=PANEL,
                  fg=GREEN if player == master.username else "#c084fc",
                  font=("Consolas", 28, "bold")).pack()

        separator(self).pack(fill="x", padx=40, pady=8)

        # Check if match is over (first to ROUNDS_TO_WIN)
        ROUNDS_TO_WIN = 3
        match_winner = None
        for p, s in scores.items():
            if s >= ROUNDS_TO_WIN:
                match_winner = p
                break

        if match_winner:
            styled_btn(self, "See Match Result →",
                       lambda: master.show_frame(GhostMatchCompleteFrame,
                                                 scores=scores, rounds=rounds,
                                                 match_winner=match_winner),
                       color="#2a1a4a", fg="#c084fc", width=24).pack(pady=8)
        else:
            next_round = round_num + 1
            label(self, f"Get ready for Ghost Round {next_round}!", font=FONT_HEAD, fg="#c084fc").pack(pady=4)
            styled_btn(self, f"Start Round {next_round} →",
                       lambda nr=next_round: master.show_frame(
                           GhostRaceFrame, round_num=nr, scores=scores, rounds=rounds),
                       color="#2a1a4a", fg="#c084fc", width=24).pack(pady=8)


# ── Screen: Ghost Match Complete ──────────────────────────────────────────────

class GhostMatchCompleteFrame(tk.Frame):
    def __init__(self, master, scores, rounds, match_winner):
        super().__init__(master, bg=BG)
        self.master = master

        ghost_key  = f"ghost:{master.ghost_opponent}"
        you_won    = match_winner == master.username

        if you_won:
            label(self, "👻 YOU BEAT THE GHOST!", font=FONT_TITLE, fg=GREEN).pack(pady=(28, 2))
        else:
            label(self, f"👻 Ghost {master.ghost_opponent} wins", font=FONT_TITLE, fg="#c084fc").pack(pady=(28, 2))

        label(self, "(Ghost match — no ELO change)", font=FONT_BODY, fg=DIM).pack(pady=(0, 4))

        separator(self).pack(fill="x", padx=40, pady=10)

        label(self, "Final Score", font=FONT_HEAD, fg=DIM).pack()
        score_row = tk.Frame(self, bg=BG)
        score_row.pack(pady=10)
        for player, score in scores.items():
            you_label = "\n(you)" if player == master.username else ""
            col = tk.Frame(score_row, bg=PANEL, padx=30, pady=14)
            col.pack(side="left", padx=16)
            label(col, f"{player}{you_label}", bg=PANEL, fg=TEXT, font=FONT_BODY).pack()
            label(col, str(score), bg=PANEL,
                  fg=GREEN if player == match_winner else "#c084fc",
                  font=("Consolas", 36, "bold")).pack()

        separator(self).pack(fill="x", padx=40, pady=10)

        styled_btn(self, "Play Again", lambda: master.show_frame(LoginFrame),
                   color=ACCENT, width=20).pack(pady=4)
        styled_btn(self, "Quit", master.destroy, color=RED, fg="white", width=20).pack(pady=4)

        # Record match history in background (no ELO)
        threading.Thread(target=self._record, args=(scores, rounds, match_winner), daemon=True).start()

    def _record(self, scores, rounds, match_winner):
        api("POST", "/ghost/record_match", json={
            "player":         self.master.username,
            "ghost_username": self.master.ghost_opponent,
            "scores":         scores,
            "rounds":         rounds,
        })


# ── Screen: Join (enter code) ─────────────────────────────────────────────────

class JoinFrame(tk.Frame):
    def __init__(self, master, username):
        super().__init__(master, bg=BG)
        self.master = master
        self.username = username

        label(self, "Join a Room", font=FONT_TITLE, fg=GOLD).pack(pady=(50, 30))
        label(self, "Room Code", fg=DIM).pack()
        self.cvar = tk.StringVar()
        e = entry(self, self.cvar, width=12)
        e.pack(pady=(4, 20))
        e.focus()

        styled_btn(self, "Join", self.do_join, color=GREEN, fg=BG).pack(pady=4)
        styled_btn(self, "Back", lambda: master.show_frame(LoginFrame)).pack()

        self.status = label(self, "", fg=RED)
        self.status.pack(pady=12)

    def do_join(self):
        code = self.cvar.get().strip().upper()
        if not code:
            self.status.config(text="Enter a room code.", fg=RED)
            return
        self.status.config(text="Joining...", fg=DIM)
        threading.Thread(target=self._do_join, args=(code,), daemon=True).start()

    def _do_join(self, code):
        data = api("POST", "/join_room", json={
            "username": self.username,
            "password": self.master.password,
            "code": code,
        })
        if not data or "error" in data:
            self.after(0, lambda: self.status.config(
                text=f"Error: {data.get('error', data) if data else 'No response'}", fg=RED))
            return
        self.master.username   = self.username
        self.master.code       = code
        self.master.max_players = data.get("max_players", 2)
        self.master.ranked      = data.get("ranked", True)
        self.after(0, lambda: self.master.show_frame(WaitingFrame, host=False))


# ── Screen: Matchmaking (searching for opponent) ──────────────────────────────

class MatchmakingFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.master = master
        self._running = True
        self._start_time = time.time()

        label(self, "Finding a Match", font=FONT_TITLE, fg=GOLD).pack(pady=(50, 4))
        label(self, "Searching for an opponent...", font=FONT_BODY, fg=DIM).pack()

        self.dots_label = label(self, "Searching", fg=GREEN, font=FONT_HEAD)
        self.dots_label.pack(pady=(16, 4))

        self.timer_label = label(self, "0s", fg=DIM, font=FONT_BODY)
        self.timer_label.pack(pady=(0, 8))

        # ELO display while searching
        self.elo_label = label(self, "", fg=GOLD, font=("Consolas", 13, "bold"))
        self.elo_label.pack(pady=(0, 20))

        styled_btn(self, "Cancel", self._cancel, color=RED, fg="white", width=16).pack()

        self.status = label(self, "", fg=RED)
        self.status.pack(pady=12)

        self._animate(0)
        self._tick_timer()
        threading.Thread(target=self._poll_queue, daemon=True).start()
        threading.Thread(target=self._fetch_my_elo, daemon=True).start()

    def _fetch_my_elo(self):
        data = api("GET", f"/elo?username={self.master.username}")
        if data and "elo" in data:
            elo = data["elo"]
            w   = data.get("wins", 0)
            l   = data.get("losses", 0)
            self.after(0, lambda: self.elo_label.config(
                text=f"Your ELO: {elo}   W{w} / L{l}"))
        else:
            self.after(0, lambda: self.elo_label.config(
                text="Your ELO: 1000  (new player)", fg=DIM))

    def _animate(self, n):
        if not self._running: return
        self.dots_label.config(text="Searching" + "." * (n % 4))
        self.after(600, lambda: self._animate(n + 1))

    def _tick_timer(self):
        if not self._running: return
        elapsed = int(time.time() - self._start_time)
        self.timer_label.config(text=f"{elapsed}s elapsed")
        self.after(1000, self._tick_timer)

    def _poll_queue(self):
        while self._running:
            data = api("GET", f"/queue/status?username={self.master.username}")
            if data is None:
                time.sleep(2)
                continue

            status = data.get("status")
            if status == "matched":
                self._running = False
                self.master.code = data["code"]
                self.master.opponent = data.get("opponent", "Opponent")
                self.after(0, lambda: self.master.show_frame(MatchIntroFrame))
                return
            elif status == "not_in_queue":
                self.after(0, lambda: self.status.config(
                    text="Lost queue position. Try again.", fg=RED))
                self._running = False
                return

            time.sleep(2)

    def _cancel(self):
        self._running = False
        threading.Thread(target=lambda: api("POST", "/queue/leave",
                         json={"username": self.master.username}), daemon=True).start()
        self.master.show_frame(LoginFrame)

    def destroy(self):
        self._running = False
        super().destroy()


# ── Screen: Match Intro (cinematic) ──────────────────────────────────────────

class MatchIntroFrame(tk.Frame):
    """Cinematic matchup reveal shown after matchmaking pairs two players."""

    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.master = master
        self._running = True
        self._me_photo  = None   # keep PhotoImage refs alive
        self._opp_photo = None

        W, H = 700, 560
        self.canvas = tk.Canvas(self, width=W, height=H, bg=BG,
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        me  = master.username
        opp = master.opponent

        # ── Static elements drawn once ────────────────────────────────────────
        # "VS" badge in centre
        self._vs = self.canvas.create_text(
            W // 2, H // 2,
            text="VS", font=("Segoe UI", 52, "bold"),
            fill=BG, anchor="center"
        )
        self._vs_bg = self.canvas.create_oval(
            W//2 - 46, H//2 - 46, W//2 + 46, H//2 + 46,
            fill=GOLD, outline=""
        )
        self.canvas.tag_raise(self._vs)

        # Dividing line (hidden initially, revealed later)
        self._line = self.canvas.create_line(
            W//2, 0, W//2, H, fill=GOLD, width=2, dash=(6, 4)
        )
        self.canvas.itemconfig(self._line, state="hidden")

        # Profile picture placeholders — start off-screen, replaced when loaded
        self._me_img_item  = self.canvas.create_image(-300, H // 2 - 80, anchor="center")
        self._opp_img_item = self.canvas.create_image(W + 300, H // 2 - 80, anchor="center")

        # Player name labels — start off-screen
        self._me_text = self.canvas.create_text(
            -300, H // 2 + 30,
            text=me, font=("Segoe UI", 28, "bold"),
            fill=GREEN, anchor="center"
        )
        self._me_sub = self.canvas.create_text(
            -300, H // 2 + 68,
            text="YOU", font=("Segoe UI", 13),
            fill=DIM, anchor="center"
        )

        self._opp_text = self.canvas.create_text(
            W + 300, H // 2 + 30,
            text=opp, font=("Segoe UI", 28, "bold"),
            fill=RED, anchor="center"
        )
        self._opp_sub = self.canvas.create_text(
            W + 300, H // 2 + 68,
            text="OPPONENT", font=("Segoe UI", 13),
            fill=DIM, anchor="center"
        )

        # ELO labels — start off-screen, filled in after fetch
        self._me_elo = self.canvas.create_text(
            -300, H // 2 + 92,
            text="", font=("Consolas", 12, "bold"),
            fill=GOLD, anchor="center"
        )
        self._opp_elo = self.canvas.create_text(
            W + 300, H // 2 + 92,
            text="", font=("Consolas", 12, "bold"),
            fill=GOLD, anchor="center"
        )

        # "MATCH FOUND" header — fades in later
        self._header = self.canvas.create_text(
            W // 2, 60,
            text="MATCH FOUND", font=("Segoe UI", 20, "bold"),
            fill=BG, anchor="center"
        )

        # "Best of 5" subtitle
        self._sub = self.canvas.create_text(
            W // 2, 92,
            text="Best of 5", font=("Segoe UI", 12),
            fill=BG, anchor="center"
        )

        # "Starting soon…" footer
        self._footer = self.canvas.create_text(
            W // 2, H - 40,
            text="", font=("Segoe UI", 11),
            fill=DIM, anchor="center"
        )

        # ── Fetch profile pictures in background, then start animation ────────
        threading.Thread(target=self._load_pics_then_animate, daemon=True).start()

    def _load_pics_then_animate(self):
        """Fetch both profile pics + ELOs from server, then start slide-in."""
        me_photo  = fetch_profile_pic(self.master.username)
        opp_photo = fetch_profile_pic(self.master.opponent)

        # Fetch ELOs
        me_elo_data  = api("GET", f"/elo?username={self.master.username}")
        opp_elo_data = api("GET", f"/elo?username={self.master.opponent}")
        me_elo  = me_elo_data.get("elo",  1000) if me_elo_data  else 1000
        opp_elo = opp_elo_data.get("elo", 1000) if opp_elo_data else 1000

        def apply():
            if not self._running: return
            if me_photo:
                self._me_photo = me_photo
                self.canvas.itemconfig(self._me_img_item, image=self._me_photo)
            else:
                ph = make_placeholder_photo(96, ACCENT)
                if ph:
                    self._me_photo = ph
                    self.canvas.itemconfig(self._me_img_item, image=self._me_photo)

            if opp_photo:
                self._opp_photo = opp_photo
                self.canvas.itemconfig(self._opp_img_item, image=self._opp_photo)
            else:
                ph = make_placeholder_photo(96, RED)
                if ph:
                    self._opp_photo = ph
                    self.canvas.itemconfig(self._opp_img_item, image=self._opp_photo)

            # Set ELO text
            self.canvas.itemconfig(self._me_elo,  text=f"ELO {me_elo}")
            self.canvas.itemconfig(self._opp_elo, text=f"ELO {opp_elo}")

            self.after(100, self._phase_slide_in)

        self.after(0, apply)

    # ── Animation phases ──────────────────────────────────────────────────────

    def _phase_slide_in(self):
        """Slide both names + avatars in from opposite sides over ~600ms."""
        W = 700
        H = 560
        me_target  = W // 4
        opp_target = W * 3 // 4
        steps = 30
        duration = 600  # ms

        me_start  = -300
        opp_start = W + 300

        def step(i):
            if not self._running: return
            t = i / steps
            # Ease-out cubic
            t2 = 1 - (1 - t) ** 3
            me_x  = me_start  + (me_target  - me_start)  * t2
            opp_x = opp_start + (opp_target - opp_start) * t2
            # Move avatars (above the name text)
            self.canvas.coords(self._me_img_item,  me_x,  H // 2 - 80)
            self.canvas.coords(self._opp_img_item, opp_x, H // 2 - 80)
            # Move name text + sub-label + ELO
            self.canvas.coords(self._me_text,  me_x,  H // 2 + 30)
            self.canvas.coords(self._me_sub,   me_x,  H // 2 + 68)
            self.canvas.coords(self._me_elo,   me_x,  H // 2 + 92)
            self.canvas.coords(self._opp_text, opp_x, H // 2 + 30)
            self.canvas.coords(self._opp_sub,  opp_x, H // 2 + 68)
            self.canvas.coords(self._opp_elo,  opp_x, H // 2 + 92)
            if i < steps:
                self.after(duration // steps, lambda: step(i + 1))
            else:
                self.after(80, self._phase_flash)

        step(0)

    def _phase_flash(self):
        """Flash the VS badge and reveal the dividing line."""
        self.canvas.itemconfig(self._line, state="normal")
        self._flash(0)

    def _flash(self, n):
        if not self._running: return
        colors = [GOLD, TEXT, GOLD, TEXT, GOLD]
        if n < len(colors):
            self.canvas.itemconfig(self._vs_bg, fill=colors[n])
            self.after(80, lambda: self._flash(n + 1))
        else:
            self.after(120, self._phase_header)

    def _phase_header(self):
        """Fade in the MATCH FOUND header and subtitle."""
        self._fade_text(self._header, BG, TEXT, steps=20, duration=400,
                        callback=lambda: self._fade_text(
                            self._sub, BG, DIM, steps=15, duration=300,
                            callback=self._phase_footer))

    def _phase_footer(self):
        """Show countdown then transition."""
        self.canvas.itemconfig(self._footer, text="Starting in 3…", fill=DIM)
        self.after(1000, lambda: self.canvas.itemconfig(self._footer, text="Starting in 2…"))
        self.after(2000, lambda: self.canvas.itemconfig(self._footer, text="Starting in 1…"))
        self.after(3000, self._phase_fade_out)

    def _phase_fade_out(self):
        """Fade entire canvas to black then switch to RaceFrame."""
        self._fade_canvas(0)

    def _fade_canvas(self, step):
        if not self._running: return
        steps = 25
        t = step / steps
        # Interpolate all text colours toward BG
        def blend(hex_col):
            # parse hex, blend toward BG
            r1, g1, b1 = int(hex_col[1:3],16), int(hex_col[3:5],16), int(hex_col[5:7],16)
            r2, g2, b2 = int(BG[1:3],16), int(BG[3:5],16), int(BG[5:7],16)
            r = int(r1 + (r2-r1)*t)
            g = int(g1 + (g2-g1)*t)
            b = int(b1 + (b2-b1)*t)
            return f"#{r:02x}{g:02x}{b:02x}"

        self.canvas.itemconfig(self._me_text,  fill=blend(GREEN))
        self.canvas.itemconfig(self._me_sub,   fill=blend(DIM))
        self.canvas.itemconfig(self._me_elo,   fill=blend(GOLD))
        self.canvas.itemconfig(self._opp_text, fill=blend(RED))
        self.canvas.itemconfig(self._opp_sub,  fill=blend(DIM))
        self.canvas.itemconfig(self._opp_elo,  fill=blend(GOLD))
        self.canvas.itemconfig(self._vs,       fill=blend(BG))
        self.canvas.itemconfig(self._vs_bg,    fill=blend(GOLD))
        self.canvas.itemconfig(self._header,   fill=blend(TEXT))
        self.canvas.itemconfig(self._sub,      fill=blend(DIM))
        self.canvas.itemconfig(self._footer,   fill=blend(DIM))
        self.canvas.itemconfig(self._line,     fill=blend(GOLD))
        self.canvas.configure(bg=blend(BG))

        if step < steps:
            self.after(20, lambda: self._fade_canvas(step + 1))
        else:
            if self._running:
                self.after(0, lambda: self.master.show_frame(RaceFrame, round_num=1))

    # ── Helper: fade a single canvas text item between two colours ────────────

    def _fade_text(self, item, from_col, to_col, steps=20, duration=400, callback=None):
        def step(i):
            if not self._running: return
            t = i / steps
            r1,g1,b1 = int(from_col[1:3],16), int(from_col[3:5],16), int(from_col[5:7],16)
            r2,g2,b2 = int(to_col[1:3],16),   int(to_col[3:5],16),   int(to_col[5:7],16)
            r = int(r1 + (r2-r1)*t)
            g = int(g1 + (g2-g1)*t)
            b = int(b1 + (b2-b1)*t)
            self.canvas.itemconfig(item, fill=f"#{r:02x}{g:02x}{b:02x}")
            if i < steps:
                self.after(duration // steps, lambda: step(i + 1))
            elif callback:
                self.after(0, callback)
        step(0)

    def destroy(self):
        self._running = False
        super().destroy()


# ── Screen: Waiting for opponent ──────────────────────────────────────────────

# ── Screen: Create Room — pick player count ───────────────────────────────────

class CreateRoomOptionsFrame(tk.Frame):
    """Let the host choose how many players (2–8) before creating the room."""

    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.master = master

        label(self, "Create Room", font=FONT_TITLE, fg=GREEN).pack(pady=(50, 4))
        label(self, "How many players?", font=FONT_HEAD, fg=DIM).pack(pady=(0, 16))

        spin_frame = tk.Frame(self, bg=BG)
        spin_frame.pack()
        self._spin = tk.Spinbox(
            spin_frame, from_=2, to=8, width=4,
            font=("Consolas", 22, "bold"),
            bg=PANEL, fg=GREEN, buttonbackground=ACCENT,
            relief="flat", justify="center",
        )
        self._spin.pack()
        label(self, "(2 = 1v1 unranked,  3–8 = free-for-all)", fg=DIM,
              font=("Segoe UI", 9, "italic")).pack(pady=(4, 20))

        styled_btn(self, "Create Room →", self._create, color=GREEN, fg=BG, width=20).pack(pady=4)
        styled_btn(self, "Back", lambda: master.show_frame(LoginFrame),
                   color=ACCENT, width=20).pack(pady=4)

        self.status = label(self, "", fg=RED)
        self.status.pack(pady=6)

    def _create(self):
        try:
            n = int(self._spin.get())
        except ValueError:
            n = 2
        n = max(2, min(8, n))
        self.status.config(text="Creating room…", fg=DIM)
        threading.Thread(target=self._do_create, args=(n,), daemon=True).start()

    def _do_create(self, n):
        u = self.master.username
        p = self.master.password
        data = api("POST", "/create_room", json={
            "username":    u,
            "password":    p,
            "max_players": n,
            "ranked":      False,   # create-room is always unranked FFA
        })
        if not data or "error" in data:
            self.after(0, lambda: self.status.config(
                text=f"Error: {data.get('error', data) if data else 'No response'}", fg=RED))
            return
        code = data["code"]
        api("POST", "/join_room", json={"username": u, "password": p, "code": code})
        self.master.code = code
        self.master.max_players = data.get("max_players", n)
        self.master.ranked = False
        self.after(0, lambda: self.master.show_frame(WaitingFrame, host=True))


# ── Screen: Waiting for players ───────────────────────────────────────────────

class WaitingFrame(tk.Frame):
    def __init__(self, master, host=False):
        super().__init__(master, bg=BG)
        self.master = master
        self.host = host
        self._running = True
        max_p = master.max_players

        title = "Waiting for Players" if max_p > 2 else "Waiting for Opponent"
        label(self, title, font=FONT_TITLE, fg=GOLD).pack(pady=(50, 10))

        if host:
            label(self, "Share this code with your players:", fg=DIM).pack()
            label(self, master.code, font=("Consolas", 36, "bold"), fg=GREEN).pack(pady=10)
            if max_p > 2:
                label(self, f"Room size: {max_p} players  |  Unranked FFA",
                      fg=DIM, font=("Segoe UI", 9)).pack()
        else:
            label(self, f"Joined room  {master.code}", font=FONT_HEAD, fg=GREEN).pack(pady=10)

        self.dots_label = label(self, "Waiting", fg=DIM, font=FONT_HEAD)
        self.dots_label.pack(pady=(16, 4))

        self.players_label = label(self, "", fg=DIM, font=("Segoe UI", 10))
        self.players_label.pack(pady=(0, 16))

        self._animate(0)
        threading.Thread(target=self._poll_players, daemon=True).start()

    def _animate(self, n):
        if not self._running: return
        self.dots_label.config(text="Waiting" + "." * (n % 4))
        self.after(500, lambda: self._animate(n + 1))

    def _poll_players(self):
        while self._running:
            data = api("GET", f"/result?code={self.master.code}"
                              f"&username={self.master.username}&round=1")
            if data is None:
                time.sleep(2)
                continue
            status = data.get("status")
            if status == "waiting_for_players":
                joined     = data.get("joined", 0)
                max_p      = data.get("max_players", self.master.max_players)
                players    = data.get("players", [])
                player_str = ", ".join(players) if players else "…"
                self.after(0, lambda j=joined, m=max_p, ps=player_str:
                           self.players_label.config(
                               text=f"{j}/{m} joined: {ps}"))
            else:
                # All players joined — update master state from server response
                max_p  = data.get("max_players", self.master.max_players)
                ranked = data.get("ranked", self.master.ranked)
                self.master.max_players = max_p
                self.master.ranked      = ranked
                self._running = False
                self.after(0, lambda: self.master.show_frame(RaceFrame, round_num=1))
                return
            time.sleep(2)

    def destroy(self):
        self._running = False
        super().destroy()


# ── Screen: Race in progress ──────────────────────────────────────────────────

class RaceFrame(tk.Frame):
    def __init__(self, master, round_num):
        super().__init__(master, bg=BG)
        self.master = master
        self.round_num = round_num
        self._running = True
        self.split_times = []
        self.run_started = False
        self.last_phase = None
        self.last_index = -1

        # Header
        hdr = tk.Frame(self, bg=ACCENT)
        hdr.pack(fill="x")
        label(hdr, f"ROUND {round_num}  —  Best of 5", font=FONT_HEAD, bg=ACCENT, fg=TEXT).pack(side="left", padx=16, pady=10)
        label(hdr, f"Room: {master.code}  |  {master.username}", font=FONT_BODY, bg=ACCENT, fg=DIM).pack(side="right", padx=16)

        # Status
        self.status_lbl = label(self, "Waiting for run to start…", font=FONT_HEAD, fg=DIM)
        self.status_lbl.pack(pady=(16, 2))

        self.timer_lbl = label(self, "--:--.-", font=FONT_BIG, fg=GOLD)
        self.timer_lbl.pack(pady=2)

        # Forfeit button (small, top-right area)
        forfeit_row = tk.Frame(self, bg=BG)
        forfeit_row.pack(fill="x", padx=40)
        self._forfeit_btn = styled_btn(forfeit_row, "Forfeit Round", self._confirm_forfeit,
                                       color="#3a1a1a", fg=RED, width=14)
        self._forfeit_btn.pack(side="right")

        separator(self).pack(fill="x", padx=40, pady=6)

        # Splits list
        list_frame = tk.Frame(self, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=40)

        self.splits_box = tk.Text(list_frame, bg=PANEL, fg=TEXT, font=FONT_MONO,
                                  relief="flat", state="disabled", height=13,
                                  highlightthickness=0)
        self.splits_box.pack(fill="both", expand=True)

        threading.Thread(target=self._watch_run, daemon=True).start()

    def _confirm_forfeit(self):
        if not messagebox.askyesno("Forfeit Round",
                                   f"Forfeit round {self.round_num}?\n"
                                   "Your opponent wins this round."):
            return
        self._forfeit_btn.config(state="disabled", text="Forfeited")
        self._running = False
        threading.Thread(target=self._do_forfeit, daemon=True).start()

    def _do_forfeit(self):
        api("POST", "/forfeit", json={
            "username": self.master.username,
            "password": self.master.password,
            "code": self.master.code,
            "round": self.round_num,
        })
        # Poll for result (opponent may not have submitted yet)
        self.after(0, lambda: self.status_lbl.config(text="Forfeited — waiting for opponent…", fg=RED))
        while True:
            result = api("GET", f"/result?code={self.master.code}"
                                f"&username={self.master.username}&round={self.round_num}")
            if result is None:
                time.sleep(2)
                continue
            status = result.get("status")
            if status in ("round_complete", "match_complete"):
                self.after(0, lambda r=result: self.master.show_frame(
                    RoundResultFrame, result=r, round_num=self.round_num))
                return
            time.sleep(2)

    def _append_split(self, text):
        self.splits_box.config(state="normal")
        self.splits_box.insert("end", text + "\n")
        self.splits_box.see("end")
        self.splits_box.config(state="disabled")

    def _watch_run(self):
        while self._running:
            phase = get_phase()

            if phase == "Running" and not self.run_started:
                self.run_started = True
                self.split_times = []
                self.last_index = -1
                self.after(0, lambda: self.status_lbl.config(text="▶  Run in progress…", fg=GREEN))

            if phase == "Ended" and self.last_phase != "Ended" and self.run_started:
                final = get_final_time()
                self._running = False
                self.after(0, lambda f=final: self._run_finished(f))
                return

            elif phase == "NotRunning" and self.last_phase not in ("NotRunning", None):
                if self.run_started:
                    self.after(0, lambda: self.status_lbl.config(text="↺  Run reset — waiting for new run…", fg=RED))
                self.split_times = []
                self.last_index = -1
                self.run_started = False
                self.after(0, lambda: self.splits_box.config(state="normal"))
                self.after(0, lambda: self.splits_box.delete("1.0", "end"))
                self.after(0, lambda: self.splits_box.config(state="disabled"))

            elif phase == "Running":
                index = get_split_index()
                if index > self.last_index and self.last_index >= 0:
                    split_time = get_last_split_time()
                    split_name = get_split_name(self.last_index) or f"Split {self.last_index + 1}"
                    self.split_times.append((split_name, split_time))
                    n = len(self.split_times)
                    self.after(0, lambda n=n, sn=split_name, st=split_time:
                               self._append_split(f"  {n:>3}.  {sn:<28}  {st}"))
                self.last_index = index

            self.last_phase = phase
            time.sleep(0.1)

    def _run_finished(self, final_time):
        self.status_lbl.config(text="✔  Run complete — uploading…", fg=GREEN)
        self.timer_lbl.config(text=final_time or "--:--.-")
        threading.Thread(target=self._submit_and_wait, args=(final_time,), daemon=True).start()

    def _submit_and_wait(self, final_time):
        data = api("POST", "/submit_time", json={
            "username": self.master.username,
            "password": self.master.password,
            "code": self.master.code,
            "time": final_time,
        })
        if not data or "error" in data:
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to submit time: {data}"))
            return

        self.after(0, lambda: self.status_lbl.config(text="⏳  Waiting for opponent…", fg=DIM))

        # Poll for result
        dots = 0
        while True:
            result = api("GET", f"/result?code={self.master.code}&username={self.master.username}&round={self.round_num}")
            if result is None:
                time.sleep(2)
                continue
            status = result.get("status")
            if status in ("round_complete", "match_complete"):
                self.after(0, lambda r=result: self.master.show_frame(
                    RoundResultFrame, result=r, round_num=self.round_num))
                return
            dots += 1
            time.sleep(2)

    def destroy(self):
        self._running = False
        super().destroy()


# ── Screen: Round Result ──────────────────────────────────────────────────────

class RoundResultFrame(tk.Frame):
    def __init__(self, master, result, round_num):
        super().__init__(master, bg=BG)
        self.master = master
        self.result = result
        self.round_num = round_num
        is_match_done = result["status"] == "match_complete"
        ranked        = result.get("ranked", master.ranked)
        max_p         = result.get("max_players", master.max_players)

        # Sync master state from server response
        master.ranked      = ranked
        master.max_players = max_p

        # Header
        hdr = tk.Frame(self, bg=ACCENT)
        hdr.pack(fill="x")
        mode_tag = "RANKED" if ranked else "FFA"
        label(hdr, f"ROUND {round_num} RESULT  [{mode_tag}]",
              font=FONT_HEAD, bg=ACCENT, fg=TEXT).pack(side="left", padx=16, pady=10)

        # Round winner banner
        rw = result["round_winner"]
        you_won_round = result["you_won_round"]
        banner_color = GREEN if you_won_round else RED
        banner_text  = f"🏆  You won round {round_num}!" if you_won_round else f"  {rw} won round {round_num}"
        tk.Frame(self, bg=banner_color, height=4).pack(fill="x")
        label(self, banner_text, font=FONT_HEAD, fg=banner_color).pack(pady=(16, 4))
        margin_label = "1st–last margin" if max_p > 2 else "Margin"
        label(self, f"{margin_label}: {result['round_margin_seconds']}s", fg=DIM).pack()

        separator(self).pack(fill="x", padx=40, pady=12)

        # Times table — works for any N players
        medals = ["🥇", "🥈", "🥉"] + ["   "] * 10
        for i, p in enumerate(result["round_results"]):
            medal = medals[i] if i < len(medals) else "   "
            you   = "  ← you" if p["username"] == master.username else ""
            row = tk.Frame(self, bg=PANEL)
            row.pack(fill="x", padx=40, pady=2)
            label(row, f"  {medal}  {p['username']}{you}", bg=PANEL, fg=TEXT, font=FONT_BODY).pack(side="left", padx=8, pady=5)
            label(row, p["time"], bg=PANEL, fg=GOLD, font=FONT_MONO).pack(side="right", padx=8)

        separator(self).pack(fill="x", padx=40, pady=10)

        # Score board
        label(self, "Match Score", font=FONT_HEAD, fg=DIM).pack()
        scores = result["scores"]
        score_row = tk.Frame(self, bg=BG)
        score_row.pack(pady=6)
        for player, score in scores.items():
            you = "\n(you)" if player == master.username else ""
            col = tk.Frame(score_row, bg=PANEL, padx=18, pady=8)
            col.pack(side="left", padx=8)
            label(col, f"{player}{you}", bg=PANEL, fg=TEXT, font=FONT_BODY).pack()
            label(col, str(score), bg=PANEL, fg=GREEN if score > 0 else DIM,
                  font=("Consolas", 24, "bold")).pack()

        separator(self).pack(fill="x", padx=40, pady=10)

        if is_match_done:
            styled_btn(self, "See Match Result →", lambda: master.show_frame(
                MatchCompleteFrame, result=result), color=GOLD, fg="white", width=24).pack(pady=8)
        else:
            next_round = result.get("next_round", round_num + 1)
            label(self, f"Get ready for Round {next_round}!", font=FONT_HEAD, fg=GREEN).pack(pady=4)
            styled_btn(self, f"Start Round {next_round} →",
                       lambda nr=next_round: master.show_frame(RaceFrame, round_num=nr),
                       color=GREEN, fg=BG, width=24).pack(pady=8)


# ── Screen: Match Complete ────────────────────────────────────────────────────

class MatchCompleteFrame(tk.Frame):
    def __init__(self, master, result):
        super().__init__(master, bg=BG)
        self.master = master

        match_winner = result["match_winner"]
        you_won      = result["you_won_match"]
        scores       = result["scores"]
        ranked       = result.get("ranked", master.ranked)
        elo_change   = result.get("elo_change")
        new_elo      = result.get("new_elo")

        # Big banner
        if you_won:
            label(self, "YOU WON THE MATCH!", font=FONT_TITLE, fg=GREEN).pack(pady=(28, 2))
        else:
            label(self, f"{match_winner} won the match", font=FONT_TITLE, fg=RED).pack(pady=(28, 2))

        # ELO change badge — only shown for ranked matches
        if ranked and elo_change is not None and new_elo is not None:
            sign  = "+" if elo_change > 0 else ""
            color = GREEN if elo_change > 0 else (RED if elo_change < 0 else DIM)
            label(self, f"ELO  {sign}{elo_change}  →  {new_elo}",
                  font=("Consolas", 16, "bold"), fg=color).pack(pady=(0, 4))
        elif not ranked:
            label(self, "(Unranked — no ELO change)", font=FONT_BODY, fg=DIM).pack(pady=(0, 4))

        separator(self).pack(fill="x", padx=40, pady=10)

        label(self, "Final Score", font=FONT_HEAD, fg=DIM).pack()
        score_row = tk.Frame(self, bg=BG)
        score_row.pack(pady=10)
        for player, score in scores.items():
            you = "\n(you)" if player == master.username else ""
            col = tk.Frame(score_row, bg=PANEL, padx=20, pady=12)
            col.pack(side="left", padx=10)
            label(col, f"{player}{you}", bg=PANEL, fg=TEXT, font=FONT_BODY).pack()
            label(col, str(score), bg=PANEL,
                  fg=GREEN if player == match_winner else DIM,
                  font=("Consolas", 32, "bold")).pack()

        separator(self).pack(fill="x", padx=40, pady=10)

        styled_btn(self, "Play Again", lambda: master.show_frame(LoginFrame),
                   color=ACCENT, width=20).pack(pady=4)
        styled_btn(self, "Quit", master.destroy, color=RED, fg="white", width=20).pack(pady=4)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = RaceApp()
    app.mainloop()
