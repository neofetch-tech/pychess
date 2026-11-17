# pyfischer

**pyfischer** is the chess engine integrated into the pyChess desktop application. pyChess owns the user interface, clocks, and game archive; pyfischer chooses the engine moves.

## How it works

The engine uses alpha-beta minimax search. Its position score combines piece values with piece-square tables, and it searches captures before quiet moves to improve pruning. Legal chess moves and board state are provided by python-chess.

The GUI currently asks the engine to search to depth 3. This keeps the app responsive while running a pure-Python search. The evaluation is intentionally small and understandable; it is not a replacement for a tournament engine such as Stockfish.

## Source entry points

- get_best_move(board, depth=3) selects a move for the current side.
- minimax(...) searches the game tree with alpha-beta pruning.
- evaluate_board(board) scores material and piece placement.
- order_moves(board, moves) puts captures and promotions first.

Engine source: src/pychess/pyfischer.py. It can be imported by pyChess or used independently with a python-chess Board.