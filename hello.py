import random
import sys

import pygame


CELL = 30
COLS = 10
ROWS = 20
WIDTH = COLS * CELL
HEIGHT = ROWS * CELL
FPS = 60

BG = (18, 18, 20)
GRID = (36, 36, 40)
TEXT = (230, 230, 235)

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
    (90, 200, 250),
    (255, 214, 102),
    (178, 102, 255),
    (102, 255, 170),
    (255, 102, 102),
    (102, 170, 255),
    (255, 170, 102),
]


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


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Menlo", 18)

    board = [[None for _ in range(COLS)] for _ in range(ROWS)]
    score = 0
    drop_interval = 700
    drop_timer = 0

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
        if not valid(shape_cells(shape, x, y), board):
            return False
        return True

    running = True
    while running:
        dt = clock.tick(FPS)
        drop_timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    nx = x - 1
                    if valid(shape_cells(shape, nx, y), board):
                        x = nx
                elif event.key == pygame.K_RIGHT:
                    nx = x + 1
                    if valid(shape_cells(shape, nx, y), board):
                        x = nx
                elif event.key == pygame.K_DOWN:
                    ny = y + 1
                    if valid(shape_cells(shape, x, ny), board):
                        y = ny
                elif event.key == pygame.K_UP:
                    r = rotate(shape)
                    if valid(shape_cells(r, x, y), board):
                        shape = r
                elif event.key == pygame.K_SPACE:
                    while valid(shape_cells(shape, x, y + 1), board):
                        y += 1
                    drop_timer = drop_interval

        if drop_timer >= drop_interval:
            drop_timer = 0
            if valid(shape_cells(shape, x, y + 1), board):
                y += 1
            else:
                for cx, cy in shape_cells(shape, x, y):
                    if cy >= 0:
                        board[cy][cx] = color
                board, cleared = clear_lines(board)
                if cleared:
                    score += (cleared * cleared) * 100
                    drop_interval = max(120, drop_interval - cleared * 20)
                if not spawn():
                    running = False

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

        score_surf = font.render(f"Score: {score}", True, TEXT)
        screen.blit(score_surf, (8, 6))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
