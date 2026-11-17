<p align="center">
  <img src="src/pychess/assets/wB.svg" alt="pyChess bishop logo" width="112">
</p>

<h1 align="center">pyChess</h1>

pyChess is a compact desktop chess game with a mouse-driven board, time controls, and saved game reviews. It is powered by the pyfischer chess engine.

## Features

- Play as White or Black against pyfischer.
- Choose a clock or play without a timer.
- Review saved games with move notation and short explanations.
- Lichess Cburnett chess-piece artwork is bundled locally.

## Run from source

~~~powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe run.py
~~~

## Build for Windows

~~~powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm pyChess.spec
~~~

The executable and its bundled files are written to dist\pyChess\.

Finished and abandoned games are saved under %LOCALAPPDATA%\pyChess\games.json.

For engine details, see the [separate pyfischer README](docs/pyfischer/README.md).