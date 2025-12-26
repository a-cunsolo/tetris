# Last update: 2025-12-26 00:34:53 
import random
import sys
import traceback
import atexit
from datetime import datetime
from pathlib import Path

import pygame


CELL = 28
COLS = 10
ROWS = 20
WIDTH = COLS * CELL
HEIGHT = ROWS * CELL
MARGIN = 18
PANEL_W = 320
PANEL_GAP = 24
WINDOW_W = WIDTH + PANEL_W + MARGIN * 2 + PANEL_GAP
WINDOW_H = HEIGHT + MARGIN * 2
FPS = 60

BG_TOP = (8, 10, 28)
BG_BOTTOM = (28, 80, 150)
BOARD_TINT = (26, 50, 110)
GRID = (90, 200, 255, 70)
TEXT = (230, 255, 245)
MUTED = (160, 210, 200)
REWARD_COLOR = (110, 255, 190)
PENALTY_COLOR = (255, 120, 160)
GHOST = (255, 255, 255, 180)
GLASS = (255, 255, 255, 35)
GLASS_EDGE = (160, 255, 220, 110)
ACCENT = (120, 255, 210)
KEY_FLASH_MS = 180

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
    (80, 255, 255),   # I
    (255, 240, 80),   # O
    (200, 140, 255),  # T
    (120, 255, 140),  # S
    (255, 110, 140),  # Z
    (110, 160, 255),  # J
    (255, 170, 90),   # L
]

WEIGHTS = {
    "lines": 1.0,
    "aggregate_height": -0.35,
    "holes": -0.7,
    "bumpiness": -0.18,
    "max_height": -0.25,
}


def lerp(a, b, t):
    return int(a + (b - a) * t)


def draw_vertical_gradient(surface, top_color, bottom_color):
    for y in range(surface.get_height()):
        t = y / max(surface.get_height() - 1, 1)
        color = (
            lerp(top_color[0], bottom_color[0], t),
            lerp(top_color[1], bottom_color[1], t),
            lerp(top_color[2], bottom_color[2], t),
        )
        pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))


def draw_glass_rect(surface, rect, fill, edge, radius=16, width=1):
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, edge, panel.get_rect(), width, border_radius=radius)
    surface.blit(panel, rect.topleft)


def draw_text(surface, text, font, color, pos, shadow=True):
    if shadow:
        shadow_surf = font.render(text, True, (10, 12, 20))
        surface.blit(shadow_surf, (pos[0] + 1, pos[1] + 1))
    surf = font.render(text, True, color)
    surface.blit(surf, pos)


def draw_scanlines(surface, alpha=28, spacing=3):
    lines = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
    for y in range(0, surface.get_height(), spacing):
        pygame.draw.line(lines, (5, 10, 20, alpha), (0, y), (surface.get_width(), y))
    surface.blit(lines, (0, 0))


def lighten(color, amount):
    return (
        min(color[0] + amount, 255),
        min(color[1] + amount, 255),
        min(color[2] + amount, 255),
    )


def draw_tile(surface, rect, color):
    pygame.draw.rect(surface, color, rect.inflate(-4, -4), border_radius=6)
    pygame.draw.rect(surface, lighten(color, 50), rect.inflate(-8, -8), 2, border_radius=6)

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
    terms = {
        "lines": WEIGHTS["lines"] * lines_cleared,
        "aggregate_height": WEIGHTS["aggregate_height"] * aggregate_height,
        "holes": WEIGHTS["holes"] * holes,
        "bumpiness": WEIGHTS["bumpiness"] * bumpiness,
        "max_height": WEIGHTS["max_height"] * max_height,
    }
    score = sum(terms.values())
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
        "terms": terms,
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
        screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("Tetris")
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("Courier New", 18, bold=True)
        small = pygame.font.SysFont("Courier New", 14)
        tiny = pygame.font.SysFont("Courier New", 12)

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

        board_x = MARGIN
        board_y = MARGIN
        panel_x = board_x + WIDTH + PANEL_GAP
        panel_y = board_y
        key_flash = {}

        next_index = random.randrange(len(SHAPES))
        next_shape = SHAPES[next_index]
        next_color = COLORS[next_index]
        current = None
        shape = None
        color = None
        x = COLS // 2 - 2
        y = -2

        def spawn():
            nonlocal current, shape, color, x, y, next_index, next_shape, next_color
            current = next_index
            shape = SHAPES[current]
            color = COLORS[current]
            next_index = random.randrange(len(SHAPES))
            next_shape = SHAPES[next_index]
            next_color = COLORS[next_index]
            x = COLS // 2 - 2
            y = -2
            return valid(shape_cells(shape, x, y), board)

        def flash(action):
            key_flash[action] = pygame.time.get_ticks()

        def move_left():
            nonlocal x
            flash("LEFT")
            nx = x - 1
            if valid(shape_cells(shape, nx, y), board):
                x = nx

        def move_right():
            nonlocal x
            flash("RIGHT")
            nx = x + 1
            if valid(shape_cells(shape, nx, y), board):
                x = nx

        def move_down(user_action=False):
            nonlocal y
            if user_action:
                flash("DOWN")
            ny = y + 1
            if valid(shape_cells(shape, x, ny), board):
                y = ny
                return True
            return False

        def rotate_piece():
            nonlocal shape
            flash("ROT")
            r = rotate(shape)
            if valid(shape_cells(r, x, y), board):
                shape = r

        def hard_drop():
            nonlocal y, drop_timer
            flash("DROP")
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

        if not spawn():
            return

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
                            move_down(user_action=True)
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

            draw_vertical_gradient(screen, BG_TOP, BG_BOTTOM)
            draw_glass_rect(
                screen,
                pygame.Rect(board_x - 10, board_y - 10, WIDTH + 20, HEIGHT + 20),
                (255, 255, 255, 25),
                GLASS_EDGE,
                radius=20,
            )
            board_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            board_surface.fill((*BOARD_TINT, 140))
            for row in range(ROWS):
                for col in range(COLS):
                    rect = pygame.Rect(col * CELL, row * CELL, CELL, CELL)
                    pygame.draw.rect(board_surface, GRID, rect, 1, border_radius=4)
            screen.blit(board_surface, (board_x, board_y))

            for row in range(ROWS):
                for col in range(COLS):
                    cell = board[row][col]
                    if cell is not None:
                        rect = pygame.Rect(
                            board_x + col * CELL,
                            board_y + row * CELL,
                            CELL,
                            CELL,
                        )
                        draw_tile(screen, rect, cell)

            for cx, cy in shape_cells(shape, x, y):
                if cy >= 0:
                    rect = pygame.Rect(
                        board_x + cx * CELL,
                        board_y + cy * CELL,
                        CELL,
                        CELL,
                    )
                    draw_tile(screen, rect, color)

            if ai_info is not None:
                for cx, cy in ai_info["cells"]:
                    if cy >= 0:
                        rect = pygame.Rect(
                            board_x + cx * CELL,
                            board_y + cy * CELL,
                            CELL,
                            CELL,
                        )
                        pygame.draw.rect(screen, GHOST, rect, 2, border_radius=6)

            panel_rect = pygame.Rect(panel_x, panel_y, PANEL_W, HEIGHT)
            draw_glass_rect(screen, panel_rect, GLASS, GLASS_EDGE, radius=18)

            draw_text(screen, f"Score {score}", font, TEXT, (panel_x + 16, panel_y + 12))
            draw_text(
                screen,
                f"AI {'ON' if ai_enabled else 'OFF'}",
                font,
                ACCENT,
                (panel_x + 16, panel_y + 36),
            )
            draw_text(
                screen,
                "A toggle AI   ESC quit",
                tiny,
                MUTED,
                (panel_x + 16, panel_y + 62),
                shadow=False,
            )
            if game_over:
                draw_text(
                    screen,
                    "GAME OVER",
                    font,
                    PENALTY_COLOR,
                    (panel_x + 16, panel_y + 92),
                )
                draw_text(
                    screen,
                    "Press ESC to quit",
                    small,
                    MUTED,
                    (panel_x + 16, panel_y + 116),
                )

            next_box = pygame.Rect(panel_x + 16, panel_y + 140, 110, 110)
            draw_glass_rect(screen, next_box, (255, 255, 255, 30), GLASS_EDGE, radius=14)
            draw_text(screen, "NEXT", tiny, MUTED, (panel_x + 24, panel_y + 146), shadow=False)
            for r in range(4):
                for c in range(4):
                    if next_shape[r][c] == "#":
                        rect = pygame.Rect(
                            next_box.x + 18 + c * 18,
                            next_box.y + 26 + r * 18,
                            16,
                            16,
                        )
                        draw_tile(screen, rect, next_color)

            key_y = panel_y + 140
            key_x = panel_x + 140
            key_w = 46
            key_h = 28
            key_gap = 8
            now = pygame.time.get_ticks()
            keys = [
                ("LEFT", key_x, key_y),
                ("ROT", key_x + key_w + key_gap, key_y),
                ("RIGHT", key_x + 2 * (key_w + key_gap), key_y),
                ("DOWN", key_x + 0.5 * (key_w + key_gap), key_y + key_h + key_gap),
                ("DROP", key_x + 1.5 * (key_w + key_gap), key_y + key_h + key_gap),
            ]
            draw_text(screen, "KEYS", tiny, MUTED, (key_x, key_y - 16), shadow=False)
            for label, kx, ky in keys:
                active = now - key_flash.get(label, -9999) < KEY_FLASH_MS
                color = (255, 255, 255, 90) if active else (255, 255, 255, 30)
                edge = (255, 255, 255, 140) if active else GLASS_EDGE
                rect = pygame.Rect(int(kx), int(ky), key_w, key_h)
                draw_glass_rect(screen, rect, color, edge, radius=10)
                draw_text(
                    screen,
                    label,
                    tiny,
                    TEXT if active else MUTED,
                    (rect.x + 6, rect.y + 7),
                    shadow=False,
                )

            if ai_info is not None:
                metrics = ai_info["metrics"]
                terms = metrics["terms"]
                info_lines = [
                    f"Target X {ai_info['x']}  Rot {ai_info['rotation']}",
                    f"Drop Y {ai_info['y']}",
                    f"Eval {metrics['score']:.2f}",
                    f"Reward {metrics['reward']}  Pen {metrics['penalty']}",
                    f"Lines {metrics['reward'] // 100}  ({terms['lines']:+.2f})",
                    f"Height {metrics['aggregate_height']}  ({terms['aggregate_height']:+.2f})",
                    f"Holes {metrics['holes']}  ({terms['holes']:+.2f})",
                    f"Bump {metrics['bumpiness']}  ({terms['bumpiness']:+.2f})",
                    f"Max H {metrics['max_height']}  ({terms['max_height']:+.2f})",
                ]
                for i, text in enumerate(info_lines):
                    draw_text(
                        screen,
                        text,
                        tiny,
                        TEXT,
                        (panel_x + 16, panel_y + 270 + i * 16),
                        shadow=False,
                    )

            chart_top = panel_y + 430
            chart_h = 120
            chart_w = PANEL_W - 32
            chart_rect = pygame.Rect(panel_x + 16, chart_top, chart_w, chart_h)
            draw_glass_rect(screen, chart_rect, (255, 255, 255, 25), GLASS_EDGE, radius=14)
            if history:
                max_val = max(max(r, p) for r, p in history)
                max_val = max(max_val, 1)
                step = chart_w / max(len(history), 1)
                for i, (reward, penalty) in enumerate(history):
                    x0 = chart_rect.x + i * step
                    r_h = (reward / max_val) * (chart_h - 14)
                    p_h = (penalty / max_val) * (chart_h - 14)
                    pygame.draw.line(
                        screen,
                        REWARD_COLOR,
                        (x0, chart_rect.y + chart_h - 7),
                        (x0, chart_rect.y + chart_h - 7 - r_h),
                        3,
                    )
                    pygame.draw.line(
                        screen,
                        PENALTY_COLOR,
                        (x0 + 3, chart_rect.y + chart_h - 7),
                        (x0 + 3, chart_rect.y + chart_h - 7 - p_h),
                        3,
                    )
            draw_text(screen, "REWARD", tiny, REWARD_COLOR, (chart_rect.x, chart_rect.y + chart_h + 6), shadow=False)
            draw_text(screen, "PENALTY", tiny, PENALTY_COLOR, (chart_rect.x + 80, chart_rect.y + chart_h + 6), shadow=False)

            draw_scanlines(screen)
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
