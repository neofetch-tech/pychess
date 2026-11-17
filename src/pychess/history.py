"""Move commentary and persistent game archive for pyChess."""
from __future__ import annotations

import json
import os
from pathlib import Path

import chess


def explain_move(before: chess.Board, move: chess.Move, after: chess.Board) -> str:
    piece = before.piece_at(move.from_square)
    if piece is None:
        return "Move played."

    name = chess.piece_name(piece.piece_type)
    origin = chess.square_name(move.from_square)
    target = chess.square_name(move.to_square)

    if after.is_checkmate():
        return f"{name.title()} moves to {target} and delivers checkmate."
    if before.is_castling(move):
        side = "kingside" if chess.square_file(move.to_square) > chess.square_file(move.from_square) else "queenside"
        return f"Castles {side}, moving the king to safety and bringing the rook toward the center."
    if move.promotion:
        promoted = chess.piece_name(move.promotion)
        note = f"Promotes the pawn on {target} to a {promoted}."
        if after.is_check():
            note += " The promotion gives check."
        return note

    notes = []
    if before.is_capture(move):
        victim = before.piece_at(move.to_square)
        victim_name = chess.piece_name(victim.piece_type) if victim else "pawn"
        notes.append(f"Captures the opponent's {victim_name} on {target}.")
    if after.is_check():
        notes.append("Gives check.")
    if not notes:
        home_rank = 0 if piece.color == chess.WHITE else 7
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(move.from_square) == home_rank:
            notes.append(f"Develops the {name} to {target}, bringing a minor piece into play.")
        elif piece.piece_type == chess.PAWN:
            file_name = chess.FILE_NAMES[chess.square_file(move.to_square)]
            if file_name in "cdef":
                notes.append(f"Advances the {file_name}-pawn toward the center.")
            else:
                notes.append(f"Advances the pawn from {origin} to {target}.")
        else:
            notes.append(f"Repositions the {name} from {origin} to {target}.")
    return " ".join(notes)


class GameHistory:
    """JSON game archive in the current user's application data directory."""

    def __init__(self, path: Path | None = None):
        if path is None:
            app_data = os.environ.get("LOCALAPPDATA")
            path = Path(app_data) / "pyChess" / "games.json" if app_data else Path.home() / ".pychess" / "games.json"
        self.path = Path(path)

    def load(self) -> list[dict]:
        try:
            result = json.loads(self.path.read_text(encoding="utf-8"))
            return result if isinstance(result, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def save(self, game: dict) -> None:
        games = [item for item in self.load() if item.get("id") != game.get("id")]
        games.insert(0, game)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(games[:300], ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)