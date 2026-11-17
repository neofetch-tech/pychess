"""Small native Tkinter UI for pyChess, powered by pyfischer."""
import base64, queue, threading, time, tkinter as tk, uuid
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
import chess, resvg_py

from .history import GameHistory, explain_move
from .pyfischer import get_best_move


ASSETS = Path(__file__).resolve().parent / "assets"
CLOCKS = {"No clock": (0, 0), "1 + 0": (60, 0), "3 + 2": (180, 2),
          "5 + 0": (300, 0), "10 + 0": (600, 0)}
PIECES = {(c, t): ("w" if c else "b") + chess.piece_symbol(t).upper()
          for c in (chess.WHITE, chess.BLACK) for t in range(1, 7)}

COLORS = {
    "background": "#0D1924",
    "panel": "#142A3A",
    "surface": "#1D3548",
    "surface_alt": "#20394D",
    "blue": "#A9D7F0",
    "text": "#EEF5FA",
    "muted": "#AFC5D6",
    "wine": "#78334D",
    "board_light": "#F6F8FB",
    "board_dark": "#A9C6DE",
    "selected": "#9B4C68",
    "target": "#789FBD",
}
class PyChessApp:
    def __init__(self, root):
        self.root = root
        root.title("pyChess")
        root.configure(bg="#0D1924")
        root.resizable(False, False)
        self.images = {}
        for key, name in PIECES.items():
            path = ASSETS / (name + ".svg")
            if not path.exists():
                raise FileNotFoundError("Missing chess piece asset: " + str(path))
            png = resvg_py.svg_to_bytes(svg_string=path.read_text(encoding="utf-8"), width=68, height=68)
            self.images[key] = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
        self.queue = queue.Queue()
        self.game_id = 0
        self.history = GameHistory()
        self.move_log = []
        self.game_saved = False
        self.menu()
        self.root.after(80, self.poll)

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def menu(self):
        if getattr(self, "active", False) and getattr(self, "move_log", []):
            self.save_game("Abandoned")
        self.active = False
        self.busy = False
        self.clear()
        box = tk.Frame(self.root, bg="#142A3A", padx=26, pady=22)
        box.pack(padx=16, pady=16)
        tk.Label(box, text="pyChess", fg="#A9D7F0", bg="#142A3A",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(box, text="New Game", fg="white", bg="#142A3A",
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(2, 16))
        tk.Label(box, text="Your side", fg="#BED0DE", bg="#142A3A").pack(anchor="w")
        self.color = tk.StringVar(value="white")
        row = tk.Frame(box, bg="#142A3A"); row.pack(fill="x", pady=(5, 14))
        for val, label in (("white", "♔  White"), ("black", "♚  Black")):
            tk.Radiobutton(row, text=label, variable=self.color, value=val,
                indicatoron=False, padx=13, pady=8, relief="flat",
                bg="#1D3548", fg="white", selectcolor="#713048",
                activebackground="#294B61").pack(side="left", padx=(0, 7))
        tk.Label(box, text="Time control", fg="#BED0DE", bg="#142A3A").pack(anchor="w")
        self.clock = tk.StringVar(value="5 + 0")
        menu = tk.OptionMenu(box, self.clock, *CLOCKS)
        menu.config(bg="#1D3548", fg="white", highlightthickness=0, width=21)
        menu["menu"].config(bg="#1D3548", fg="white")
        menu.pack(fill="x", pady=(5, 16))
        tk.Button(box, text="Start Game", command=self.start, bg="#78334D",
            fg="white", relief="flat", padx=12, pady=9,
            font=("Segoe UI", 11, "bold")).pack(fill="x")
        tk.Button(box, text="Game History", command=self.open_history,
            bg=COLORS["surface"], fg=COLORS["text"], relief="flat", pady=8,
        ).pack(fill="x", pady=(7, 0))
        tk.Label(box, text="Engine: pyfischer · Cburnett pieces: Lichess", fg="#8FA9BC",
                 bg="#142A3A", font=("Segoe UI", 8)).pack(anchor="w", pady=(12, 0))

    def start(self):
        self.game_id += 1
        self.human = chess.WHITE if self.color.get() == "white" else chess.BLACK
        secs, self.increment = CLOCKS[self.clock.get()]
        self.left = {chess.WHITE: float(secs), chess.BLACK: float(secs)}
        self.board = chess.Board()
        self.move_log = []
        self.game_id_current = uuid.uuid4().hex
        self.started_at = datetime.now().astimezone().isoformat(timespec="minutes")
        self.time_control = self.clock.get()
        self.game_saved = False
        self.active, self.busy = True, False
        self.selected, self.legal, self.drag = None, [], None
        self.dragging = False
        self.last = time.monotonic()
        self.game_ui()
        self.tick()
        if self.board.turn != self.human:
            self.engine()

    def game_ui(self):
        self.clear()
        outer = tk.Frame(self.root, bg="#0D1924", padx=12, pady=12); outer.pack()
        self.canvas = tk.Canvas(outer, width=560, height=560, highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=2)
        for seq, fn in (("<ButtonPress-1>", self.press), ("<B1-Motion>", self.motion),
                        ("<ButtonRelease-1>", self.release)):
            self.canvas.bind(seq, fn)
        panel = tk.Frame(outer, bg="#142A3A", width=185, height=560, padx=12, pady=13)
        panel.grid(row=0, column=1, sticky="nsew", padx=(11, 0)); panel.grid_propagate(False)
        tk.Label(panel, text="pyChess", fg="#A9D7F0", bg="#142A3A",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(panel, text="Game", fg="white", bg="#142A3A",
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(1, 10))
        tk.Label(panel, text="vs pyfischer", fg="#A9D7F0", bg="#142A3A",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))
        self.wclock = self.clock_ui(panel, "White")
        self.bclock = self.clock_ui(panel, "Black")
        self.status = tk.Label(panel, text="", fg="#eff3ec", bg="#20394D",
            wraplength=154, justify="left", padx=9, pady=9, anchor="w")
        self.status.pack(fill="x", pady=(11, 9))
        self.moves = tk.Label(panel, text="", fg="#B3C9D9", bg="#142A3A",
                              wraplength=150, justify="left")
        self.moves.pack(anchor="w")
        tk.Button(panel, text="Main menu", command=self.menu, bg="#29465C",
                  fg="white", relief="flat", pady=7).pack(fill="x", side="bottom")
        self.paint(); self.labels()

    def clock_ui(self, parent, title):
        f = tk.Frame(parent, bg="#1D3548", padx=9, pady=7); f.pack(fill="x", pady=4)
        tk.Label(f, text=title, fg="#A5C0D2", bg="#1D3548").pack(anchor="w")
        lbl = tk.Label(f, text="--:--", fg="white", bg="#1D3548",
                       font=("Consolas", 17, "bold")); lbl.pack(anchor="w")
        return lbl

    def square(self, x, y):
        col, row = int(x//70), int(y//70)
        if not (0 <= col < 8 and 0 <= row < 8): return None
        f, r = (col, 7-row) if self.human == chess.WHITE else (7-col, row)
        return chess.square(f, r)

    def center(self, sq):
        f, r = chess.square_file(sq), chess.square_rank(sq)
        col, row = (f, 7-r) if self.human == chess.WHITE else (7-f, r)
        return col*70+35, row*70+35

    def paint(self):
        c = self.canvas; c.delete("all")
        for row in range(8):
            for col in range(8):
                f, r = (col, 7-row) if self.human == chess.WHITE else (7-col, row)
                sq = chess.square(f, r); x, y = col*70, row*70
                color = "#F6F8FB" if (f+r)%2 == 0 else "#A9C6DE"
                if sq == self.selected: color = "#9B4C68"
                elif any(m.to_square == sq for m in self.legal): color = "#789FBD"
                c.create_rectangle(x,y,x+70,y+70,fill=color,outline="")
                if col == 0:
                    c.create_text(x+4,y+3,text=str(r+1),anchor="nw",
                        fill="#57778F" if color == "#F6F8FB" else "#EEF5FA",
                        font=("Segoe UI",8,"bold"))
                if row == 7:
                    c.create_text(x+66,y+66,text=chess.FILE_NAMES[f],anchor="se",
                        fill="#57778F" if color == "#F6F8FB" else "#EEF5FA",
                        font=("Segoe UI",8,"bold"))
                p = self.board.piece_at(sq)
                if p and not (self.dragging and sq == self.selected):
                    c.create_image(x+35,y+35,image=self.images[(p.color,p.piece_type)])
        self.moves.config(text= "Last move: "+(self.board.peek().uci() if self.board.move_stack else "—"))

    def press(self, e):
        if not self.active or self.busy or self.board.turn != self.human: return
        sq = self.square(e.x,e.y)
        if sq is None: return
        if self.selected is not None and any(m.to_square == sq for m in self.legal):
            self.move_to(sq); return
        p = self.board.piece_at(sq)
        if p and p.color == self.human:
            self.selected = sq
            self.legal = [m for m in self.board.legal_moves if m.from_square == sq]
            self.dragging = True
            self.paint()
            self.drag = self.canvas.create_image(e.x,e.y,image=self.images[(p.color,p.piece_type)])

    def motion(self,e):
        if self.drag is not None: self.canvas.coords(self.drag,e.x,e.y)

    def release(self,e):
        if self.drag is None: return
        self.canvas.delete(self.drag); self.drag = None; self.dragging = False
        sq = self.square(e.x,e.y)
        if sq is not None and any(m.to_square == sq for m in self.legal): self.move_to(sq)
        else: self.selected,self.legal = None,[]; self.paint()

    def move_to(self,sq):
        choices = [m for m in self.legal if m.to_square == sq]
        if not choices: return
        move = choices[0]
        if move.promotion:
            move = self.pick_promotion(choices)
            if move is None: self.selected,self.legal = None,[]; self.paint(); return
        self.record_and_push(move); self.left[self.human] += self.increment
        self.selected,self.legal = None,[]
        self.last = time.monotonic(); self.paint(); self.labels()
        if self.result(): return
        if self.board.turn != self.human: self.engine()

    def pick_promotion(self, choices):
        win=tk.Toplevel(self.root); win.title("Pawn promotion")
        win.configure(bg="#142A3A"); win.transient(self.root); win.grab_set()
        tk.Label(win,text="Choose a piece",fg="white",bg="#142A3A",
                 padx=10,pady=8).pack()
        result={"move":None}; row=tk.Frame(win,bg="#142A3A"); row.pack(padx=7,pady=(0,8))
        for m in choices:
            tk.Button(row,image=self.images[(self.human,m.promotion)],
                text=chess.piece_name(m.promotion).title(), compound="top",
                command=lambda m=m:(result.update(move=m),win.destroy()),
                bg="#1D3548",relief="flat",padx=4,pady=4).pack(side="left",padx=3)
        self.root.wait_window(win); return result["move"]

    def engine(self):
        if not self.active: return
        self.busy = True; self.labels()
        threading.Thread(target=self.search,args=(self.board.copy(),self.game_id),daemon=True).start()

    def search(self,position,generation):
        try: self.queue.put(("move",get_best_move(position,depth=3),generation))
        except Exception as e: self.queue.put(("error",str(e),generation))

    def poll(self):
        try:
            while True:
                kind,value,generation=self.queue.get_nowait()
                if not self.active or generation != self.game_id: continue
                self.busy=False
                if kind=="move" and value in self.board.legal_moves:
                    self.record_and_push(value); self.left[not self.human]+=self.increment
                    self.last=time.monotonic(); self.paint(); self.labels(); self.result()
                elif kind=="error": messagebox.showerror("Engine error",value)
        except queue.Empty: pass
        self.root.after(80,self.poll)

    def labels(self):
        self.wclock.config(text=self.fmt(self.left[chess.WHITE]))
        self.bclock.config(text=self.fmt(self.left[chess.BLACK]))
        if self.board.is_check():
            text="Check! "+("Your move." if self.board.turn==self.human else "pyfischer to move.")
        else: text="pyfischer is thinking…" if self.busy else ("Your move." if self.board.turn==self.human else "pyfischer to move.")
        self.status.config(text=text)

    def fmt(self,n):
        n=max(0,int(n)); return f"{n//60:02d}:{n%60:02d}"

    def tick(self):
        if not self.active: return
        now=time.monotonic(); elapsed=now-self.last; self.last=now
        if self.left[chess.WHITE] or self.left[chess.BLACK]:
            self.left[self.board.turn]-=elapsed
            if self.left[self.board.turn]<=0:
                loser=self.board.turn; self.left[loser]=0
                self.end("Time out! "+("pyfischer wins." if loser==self.human else "You win."))
                return
        self.labels(); self.root.after(200,self.tick)

    def result(self):
        if self.board.is_checkmate():
            winner="White" if self.board.turn==chess.BLACK else "Black"
            self.end(f"Checkmate! {winner} wins."); return True
        if self.board.is_stalemate() or self.board.is_insufficient_material() or self.board.can_claim_draw():
            self.end("Stalemate! Draw." if self.board.is_stalemate() else "Draw."); return True
        return False

    def end(self,text):
        if not self.active: return
        self.save_game(text)
        self.active=False; self.busy=False
        self.status.config(text=text,fg="#E3A0B5")
        for seq in ("<ButtonPress-1>","<B1-Motion>","<ButtonRelease-1>"): self.canvas.unbind(seq)
        tk.Button(self.root,text="Main menu",command=self.menu,bg="#78334D",fg="white",
                  relief="flat",padx=14,pady=6).pack(pady=(0,9))
        self.root.after(4500,self.menu)


    def record_and_push(self, move):
        before = self.board.copy()
        san = self.board.san(move)
        color = self.board.turn
        self.board.push(move)
        self.move_log.append({
            "number": len(self.move_log) // 2 + 1,
            "color": "White" if color == chess.WHITE else "Black",
            "san": san,
            "uci": move.uci(),
            "explanation": explain_move(before, move, self.board),
        })

    def save_game(self, result):
        if getattr(self, "game_saved", False):
            return
        record = {
            "id": self.game_id_current,
            "started_at": self.started_at,
            "side": "White" if self.human == chess.WHITE else "Black",
            "time_control": self.time_control,
            "result": result,
            "moves": self.move_log,
        }
        try:
            self.history.save(record)
            self.game_saved = True
        except OSError as exc:
            messagebox.showwarning("History could not be saved", str(exc))

    def open_history(self):
        games = self.history.load()
        window = tk.Toplevel(self.root)
        window.title("Game History")
        window.configure(bg=COLORS["panel"])
        window.geometry("680x420")
        tk.Label(window, text="Saved games", fg="white", bg=COLORS["panel"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        listing = tk.Listbox(window, bg=COLORS["surface"], fg=COLORS["text"],
                             selectbackground=COLORS["wine"], font=("Segoe UI", 10),
                             borderwidth=0, highlightthickness=0)
        listing.pack(fill="both", expand=True, padx=16, pady=4)
        for game in games:
            date = game.get("started_at", "Unknown date").replace("T", " ")
            count = len(game.get("moves", []))
            listing.insert("end", f"{date}  ·  {game.get('side', '')}  ·  "
                                  f"{game.get('time_control', '')}  ·  "
                                  f"{game.get('result', '')}  ·  {count} plies")
        if not games:
            listing.insert("end", "No saved games yet. Finish a game to see it here.")

        def review_selected(_event=None):
            selected = listing.curselection()
            if selected and games:
                self.review_game(games[selected[0]])

        listing.bind("<Double-Button-1>", review_selected)
        buttons = tk.Frame(window, bg=COLORS["panel"])
        buttons.pack(fill="x", padx=16, pady=12)
        tk.Button(buttons, text="Review selected", command=review_selected,
                  bg=COLORS["wine"], fg="white", relief="flat", padx=12, pady=7).pack(side="left")
        tk.Button(buttons, text="Close", command=window.destroy,
                  bg=COLORS["surface"], fg="white", relief="flat", padx=12, pady=7).pack(side="right")

    def review_game(self, game):
        window = tk.Toplevel(self.root)
        window.title("Game Review")
        window.configure(bg=COLORS["background"])
        window.geometry("900x650")
        outer = tk.Frame(window, bg=COLORS["background"], padx=14, pady=14)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, width=560, height=560, highlightthickness=0)
        canvas.grid(row=0, column=0, rowspan=2, sticky="n")
        side = tk.Frame(outer, bg=COLORS["panel"], width=280, height=560, padx=12, pady=12)
        side.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        side.grid_propagate(False)
        tk.Label(side, text="Move-by-move review", fg="white", bg=COLORS["panel"],
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(side, text=f"{game.get('started_at', '')}  ·  {game.get('time_control', '')}  ·  "
                            f"{game.get('result', '')}", fg=COLORS["muted"], bg=COLORS["panel"],
                 wraplength=250, justify="left").pack(anchor="w", pady=(5, 10))
        move_list = tk.Listbox(side, bg=COLORS["surface"], fg=COLORS["text"],
                               selectbackground=COLORS["wine"], font=("Consolas", 10),
                               borderwidth=0, highlightthickness=0)
        move_list.pack(fill="both", expand=True)
        moves = game.get("moves", [])
        for item in moves:
            prefix = f"{item.get('number', '')}. " if item.get("color") == "White" \
                     else f"{item.get('number', '')}... "
            move_list.insert("end", prefix + item.get("san", ""))
        explanation = tk.Label(side, text="Select a move for its explanation.",
                               fg=COLORS["text"], bg=COLORS["surface_alt"],
                               wraplength=250, justify="left", anchor="nw",
                               padx=9, pady=9, height=4)
        explanation.pack(fill="x", pady=(9, 0))

        def show_position(index=None):
            board = chess.Board()
            if index is not None:
                for item in moves[:index + 1]:
                    board.push_uci(item["uci"])
            self.draw_review_board(canvas, board, moves[index] if index is not None else None)
            if index is None:
                explanation.config(text="Starting position. Select a move to review.")
            else:
                item = moves[index]
                explanation.config(text=f"{item.get('color')} played {item.get('san')}.\n"
                                        f"{item.get('explanation', 'No explanation saved.')}")
                current = move_list.curselection()
                if not current or current[0] != index:
                    move_list.selection_clear(0, "end")
                    move_list.selection_set(index)
                    move_list.see(index)

        def select_move(_event=None):
            selected = move_list.curselection()
            if selected:
                show_position(selected[0])

        move_list.bind("<<ListboxSelect>>", select_move)
        controls = tk.Frame(side, bg=COLORS["panel"])
        controls.pack(fill="x", pady=(9, 0))
        tk.Button(controls, text="Previous", command=lambda: self.step_review(move_list, show_position, -1),
                  bg=COLORS["surface"], fg="white", relief="flat").pack(side="left")
        tk.Button(controls, text="Next", command=lambda: self.step_review(move_list, show_position, 1),
                  bg=COLORS["surface"], fg="white", relief="flat").pack(side="right")
        show_position(0 if moves else None)

    @staticmethod
    def step_review(move_list, show_position, amount):
        if not move_list.size():
            return
        current = move_list.curselection()
        index = current[0] if current else 0
        show_position(max(0, min(move_list.size() - 1, index + amount)))

    def draw_review_board(self, canvas, board, last_move=None):
        canvas.delete("all")
        last_from = chess.parse_square(last_move["uci"][:2]) if last_move else None
        last_to = chess.parse_square(last_move["uci"][2:4]) if last_move else None
        for row in range(8):
            for column in range(8):
                file_index, rank = column, 7 - row
                square = chess.square(file_index, rank)
                x, y = column * 70, row * 70
                color = COLORS["board_light"] if (file_index + rank) % 2 == 0 else COLORS["board_dark"]
                if square in (last_from, last_to):
                    color = COLORS["selected"]
                canvas.create_rectangle(x, y, x + 70, y + 70, fill=color, outline="")
                if column == 0:
                    canvas.create_text(x + 4, y + 3, text=str(rank + 1), anchor="nw",
                                       fill="#57778F", font=("Segoe UI", 8, "bold"))
                if row == 7:
                    canvas.create_text(x + 66, y + 66, text=chess.FILE_NAMES[file_index],
                                       anchor="se", fill="#57778F", font=("Segoe UI", 8, "bold"))
                piece = board.piece_at(square)
                if piece:
                    canvas.create_image(x + 35, y + 35,
                                        image=self.images[(piece.color, piece.piece_type)])

def main():
    root = tk.Tk()
    PyChessApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
