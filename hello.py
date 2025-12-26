# Last update: 2025-12-26 00:24:08 
import random
import sys
import traceback
import atexit
from datetime import datetime
from pathlib import Path

import pygame


CELL = 30
COLS = 10
ROWS = 20
WIDTH = COLS * CELL
HEIGHT = ROWS * CELL
PANEL_W = 280
WINDOW_W = WIDTH + PANEL_W
FPS = 60

BG = (30, 90, 200)
GRID = (36, 36, 40)
TEXT = (230, 230, 235)
REWARD_COLOR = (80, 220, 140)
PENALTY_COLOR = (240, 90, 90)
GHOST = (240, 240, 240)

SHAPES = [
    # I
    [
        "....",
        "####",
        "....",
        "....",
    ],
    # O
    [
        ".##.",
        ".##.",
        "....",
        "....",
    ],
    # T
    [
        ".#..",
        "###.",
        "....",
        "....",
    ],
    # S
    [
        ".##.",
        "##..",
        "....",
        "....",
    ],
    # Z
    [
        "##..",
        ".##.",
        "....",
        "....",
    ],
    # J
    [
        "#...",
        "###.",
        "....",
        "....",
    ],
    # L
    [
        "..#.",
        "###.",
        "....",
        "....",
    ],
]

COLORS = [
    (255, 105, 180),
    (255, 105, 180),
    (255, 105, 180),
    (255, 105, 180),
    (255, 105, 180),
    (255, 105, 180),
    (255, 105, 180),
]

WEIGHTS = {
    "lines": 1.0,
    "aggregate_height": -0.35,
    "holes": -0.7,
    "bumpiness": -0.18,
    "max_height": -0.25,
}


def rotate(shape):
    return ["".join(shape[3 - c][r] for c in range(4)) for r in range(4)]


def shape_cells(shape, x, y):
    cells = []
    for r in range(4):
        for c in range(4):
            if shape[r][c] == "#":
                cells.append((x + c, y + r))
    return cells


def valid(cells, board):
    for x, y in cells:
        if x < 0 or x >= COLS or y >= ROWS:
            return False
        if y >= 0 and board[y][x] is not None:
            return False
    return True


def clear_lines(board):
    new_board = [row for row in board if any(cell is None for cell in row)]
    cleared = ROWS - len(new_board)
    for _ in range(cleared):
        new_board.insert(0, [None] * COLS)
    return new_board, cleared


def unique_rotations(shape):
    rotations = []
    current = shape
    for _ in range(4):
        if current not in rotations:
            rotations.append(current)
        current = rotate(current)
    return rotations


def drop_y(board, shape, x, y):
    while valid(shape_cells(shape, x, y + 1), board):
        y += 1
    return y


def board_metrics(board):
    heights = [0] * COLS
    holes = 0
    for col in range(COLS):
        block_seen = False
        for row in range(ROWS):
            if board[row][col] is not None:
                if not block_seen:
                    heights[col] = ROWS - row
                    block_seen = True
            elif block_seen:
                holes += 1
    aggregate_height = sum(heights)
    bumpiness = sum(abs(heights[i] - heights[i + 1]) for i in range(COLS - 1))
    max_height = max(heights)
    return aggregate_height, holes, bumpiness, max_height


def place_on_board(board, shape, x, y, color):
    new_board = [row[:] for row in board]
    for cx, cy in shape_cells(shape, x, y):
        if cy >= 0:
            new_board[cy][cx] = color
    return new_board


def evaluate_board(board, lines_cleared):
    aggregate_height, holes, bumpiness, max_height = board_metrics(board)
    score = (
        WEIGHTS["lines"] * lines_cleared
        + WEIGHTS["aggregate_height"] * aggregate_height
        + WEIGHTS["holes"] * holes
        + WEIGHTS["bumpiness"] * bumpiness
        + WEIGHTS["max_height"] * max_height
    )
    reward = lines_cleared * 100
    penalty = aggregate_height + holes * 5 + bumpiness * 2 + max_height * 3
    return {
        "score": score,
        "reward": reward,
        "penalty": penalty,
        "aggregate_height": aggregate_height,
        "holes": holes,
        "bumpiness": bumpiness,
        "max_height": max_height,
    }


def best_move(board, shape, color):
    best = None
    rotations = unique_rotations(shape)
    for rot_index, rot in enumerate(rotations):
        for x in range(-2, COLS):
            if not valid(shape_cells(rot, x, 0), board):
                continue
            y = drop_y(board, rot, x, 0)
            cells = shape_cells(rot, x, y)
            if not valid(cells, board):
                continue
            placed = place_on_board(board, rot, x, y, color)
            cleared_board, cleared = clear_lines(placed)
            metrics = evaluate_board(cleared_board, cleared)
            if best is None or metrics["score"] > best["metrics"]["score"]:
                best = {
                    "x": x,
                    "y": y,
                    "rotation": rot_index,
                    "shape": rot,
                    "cells": cells,
                    "metrics": metrics,
                }
    return best


def setup_logging():
    log_path = Path(__file__).with_name("tetris_log.txt")
    try:
        log_file = log_path.open("w", encoding="utf-8")
    except OSError:
        return None

    sys.stdout = log_file
    sys.stderr = log_file
    print("Tetris log start")
    log_file.flush()

    def _hook(exc_type, exc, tb):
        traceback.print_exception(exc_type, exc, tb)
        try:
            log_file.flush()
        except Exception:
            pass

    sys.excepthook = _hook

    def _close():
        try:
            log_file.flush()
            log_file.close()
        except Exception:
            pass

    atexit.register(_close)
    return log_file


def main():
    log_file = setup_logging()

    # Update the first-line timestamp when the game starts.
    try:
        path = Path(__file__)
        lines = path.read_text().splitlines()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        header = f"# Last update: {stamp}"
        if lines and lines[0].startswith("# Last update:"):
            lines[0] = header
        else:
            lines.insert(0, header)
        path.write_text("\n".join(lines) + "\n")
    except OSError:
        pass

    try:
        pygame.init()
        screen = pygame.display.set_mode((WINDOW_W, HEIGHT))
        pygame.display.set_caption("Tetris")
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("Menlo", 18)
        small = pygame.font.SysFont("Menlo", 14)

        board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        score = 0
        drop_interval = 700
        drop_timer = 0
        ai_enabled = True
        ai_queue = []
        ai_timer = 0
        ai_interval = max(20, 120)
        ai_info = None
        history = []

        current = random.randrange(len(SHAPES))
        shape = SHAPES[current]
        color = COLORS[current]
        x = COLS // 2 - 2
        y = -2

        def spawn():
            nonlocal current, shape, color, x, y
            current = random.randrange(len(SHAPES))
            shape = SHAPES[current]
            color = COLORS[current]
            x = COLS // 2 - 2
            y = -2
            return valid(shape_cells(shape, x, y), board)

        def move_left():
            nonlocal x
            nx = x - 1
            if valid(shape_cells(shape, nx, y), board):
                x = nx

        def move_right():
            nonlocal x
            nx = x + 1
            if valid(shape_cells(shape, nx, y), board):
                x = nx

        def move_down():
            nonlocal y
            ny = y + 1
            if valid(shape_cells(shape, x, ny), board):
                y = ny
                return True
            return False

        def rotate_piece():
            nonlocal shape
            r = rotate(shape)
            if valid(shape_cells(r, x, y), board):
                shape = r

        def hard_drop():
            nonlocal y, drop_timer
            while valid(shape_cells(shape, x, y + 1), board):
                y += 1
            drop_timer = drop_interval

        def plan_ai():
            nonlocal ai_queue, ai_info
            ai_info = best_move(board, shape, color)
            ai_queue = []
            if ai_info is None:
                return
            rotations = unique_rotations(shape)
            target_shape = rotations[ai_info["rotation"]]
            if target_shape != shape:
                current_rotations = unique_rotations(shape)
                current_index = (
                    current_rotations.index(shape)
                    if shape in current_rotations
                    else 0
                )
                rot_steps = (ai_info["rotation"] - current_index) % len(current_rotations)
                ai_queue.extend(["rot"] * rot_steps)
            dx = ai_info["x"] - x
            if dx < 0:
                ai_queue.extend(["left"] * abs(dx))
            elif dx > 0:
                ai_queue.extend(["right"] * dx)
            ai_queue.append("drop")
            metrics = ai_info["metrics"]
            history.append((metrics["reward"], metrics["penalty"]))
            if len(history) > 60:
                history.pop(0)

        running = True
        game_over = False
        while running:
            dt = clock.tick(FPS)
            drop_timer += dt
            ai_timer += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_a and not game_over:
                        ai_enabled = not ai_enabled
                        ai_queue = []
                    elif not ai_enabled:
                        if event.key == pygame.K_LEFT:
                            move_left()
                        elif event.key == pygame.K_RIGHT:
                            move_right()
                        elif event.key == pygame.K_DOWN:
                            move_down()
                        elif event.key == pygame.K_UP:
                            rotate_piece()
                        elif event.key == pygame.K_SPACE:
                            hard_drop()

            if game_over:
                ai_queue = []
                ai_enabled = False
            elif ai_enabled and not ai_queue:
                try:
                    plan_ai()
                except Exception:
                    if log_file is not None:
                        traceback.print_exc()
                        log_file.flush()
                    ai_enabled = False
                    ai_queue = []

            if ai_enabled and ai_queue and ai_timer >= ai_interval and not game_over:
                ai_timer = 0
                action = ai_queue.pop(0)
                if action == "left":
                    move_left()
                elif action == "right":
                    move_right()
                elif action == "rot":
                    rotate_piece()
                elif action == "drop":
                    hard_drop()

            if drop_timer >= drop_interval and not game_over:
                drop_timer = 0
                if move_down():
                    pass
                else:
                    for cx, cy in shape_cells(shape, x, y):
                        if cy >= 0:
                            board[cy][cx] = color
                    board, cleared = clear_lines(board)
                    if cleared:
                        score += (cleared * cleared) * 100
                        drop_interval = max(120, drop_interval - cleared * 20)
                    if not spawn():
                        game_over = True
                    ai_queue = []

            screen.fill(BG)

            for row in range(ROWS):
                for col in range(COLS):
                    rect = pygame.Rect(col * CELL, row * CELL, CELL, CELL)
                    pygame.draw.rect(screen, GRID, rect, 1)
                    cell = board[row][col]
                    if cell is not None:
                        pygame.draw.rect(
                            screen,
                            cell,
                            rect.inflate(-2, -2),
                        )

            for cx, cy in shape_cells(shape, x, y):
                if cy >= 0:
                    rect = pygame.Rect(cx * CELL, cy * CELL, CELL, CELL)
                    pygame.draw.rect(screen, color, rect.inflate(-2, -2))

            if ai_info is not None:
                for cx, cy in ai_info["cells"]:
                    if cy >= 0:
                        rect = pygame.Rect(cx * CELL, cy * CELL, CELL, CELL)
                        pygame.draw.rect(screen, GHOST, rect, 2)

            panel_x = WIDTH + 12
            score_surf = font.render(f"Score: {score}", True, TEXT)
            mode_surf = font.render(f"AI: {'ON' if ai_enabled else 'OFF'}", True, TEXT)
            hint_surf = small.render("A: toggle AI  ESC: quit", True, TEXT)
            screen.blit(score_surf, (panel_x, 10))
            screen.blit(mode_surf, (panel_x, 34))
            screen.blit(hint_surf, (panel_x, 58))
            if game_over:
                over_surf = font.render("GAME OVER", True, PENALTY_COLOR)
                exit_surf = small.render("Press ESC to quit", True, TEXT)
                screen.blit(over_surf, (panel_x, 180))
                screen.blit(exit_surf, (panel_x, 204))

            if ai_info is not None:
                metrics = ai_info["metrics"]
                info_lines = [
                    f"Best X: {ai_info['x']}",
                    f"Rotation: {ai_info['rotation']}",
                    f"Score: {metrics['score']:.2f}",
                    f"Lines: {metrics['reward'] // 100}",
                    f"Holes: {metrics['holes']}",
                    f"Height: {metrics['aggregate_height']}",
                    f"Bump: {metrics['bumpiness']}",
                    f"Max H: {metrics['max_height']}",
                ]
                for i, text in enumerate(info_lines):
                    surf = small.render(text, True, TEXT)
                    screen.blit(surf, (panel_x, 90 + i * 18))

            chart_top = 250
            chart_h = 120
            chart_w = PANEL_W - 24
            pygame.draw.rect(
                screen,
                GRID,
                pygame.Rect(panel_x, chart_top, chart_w, chart_h),
                1,
            )
            if history:
                max_val = max(max(r, p) for r, p in history)
                max_val = max(max_val, 1)
                step = chart_w / max(len(history), 1)
                for i, (reward, penalty) in enumerate(history):
                    x0 = panel_x + i * step
                    r_h = (reward / max_val) * (chart_h - 8)
                    p_h = (penalty / max_val) * (chart_h - 8)
                    pygame.draw.line(
                        screen,
                        REWARD_COLOR,
                        (x0, chart_top + chart_h - 4),
                        (x0, chart_top + chart_h - 4 - r_h),
                        3,
                    )
                    pygame.draw.line(
                        screen,
                        PENALTY_COLOR,
                        (x0 + 3, chart_top + chart_h - 4),
                        (x0 + 3, chart_top + chart_h - 4 - p_h),
                        3,
                    )
                legend_r = small.render("Reward", True, REWARD_COLOR)
                legend_p = small.render("Penalty", True, PENALTY_COLOR)
                screen.blit(legend_r, (panel_x, chart_top + chart_h + 6))
                screen.blit(legend_p, (panel_x + 90, chart_top + chart_h + 6))

            pygame.display.flip()
    except Exception:
        if log_file is not None:
            traceback.print_exc()
            log_file.flush()
        raise
    finally:
        try:
            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
