from collections import OrderedDict
import random
import pygame
import numpy as np
from pygame import Rect
import sys

# Константы для окна
WINDOW_WIDTH, WINDOW_HEIGHT = 500, 601
GRID_WIDTH, GRID_HEIGHT = 300, 600
TILE_SIZE = 30

# Вероятности выпадения блоков
block_probabilities = {
    "SquareBlock": 1,
    "TBlock": 1,
    "LineBlock": 1,
    "LBlock": 1,
    "ZBlock": 1
}

# Функция для удаления пустых колонок
def remove_empty_columns(arr, _x_offset=0, _keep_counting=True):
    for colid, col in enumerate(arr.T):
        if col.max() == 0:
            if _keep_counting:
                _x_offset += 1
            arr, _x_offset = remove_empty_columns(
                np.delete(arr, colid, 1), _x_offset, _keep_counting)
            break
        else:
            _keep_counting = False
    return arr, _x_offset

# Исключения для обработки границ
class BottomReached(Exception):
    pass

class TopReached(Exception):
    pass

# Класс блока
class Block(pygame.sprite.Sprite):
    @staticmethod
    def collide(block, group):
        for other_block in group:
            if block == other_block:
                continue
            if pygame.sprite.collide_mask(block, other_block) is not None:
                return True
        return False

    def __init__(self):
        super().__init__()
        self.color = random.choice(((200, 200, 200), (215, 133, 133), (30, 145, 255), (0, 170, 0), (180, 0, 140), (200, 200, 0)))
        self.current = True
        self.struct = np.array(self.struct)
        if random.randint(0, 1):
            self.struct = np.rot90(self.struct)
        if random.randint(0, 1):
            self.struct = np.flip(self.struct, 0)
        self._draw()

    def _draw(self, x=4, y=0):
        width = len(self.struct[0]) * TILE_SIZE
        height = len(self.struct) * TILE_SIZE
        self.image = pygame.Surface([width, height])
        self.image.set_colorkey((0, 0, 0))
        self.rect = Rect(0, 0, width, height)
        self._x = x
        self._y = y
        for y, row in enumerate(self.struct):
            for x, col in enumerate(row):
                if col:
                    pygame.draw.rect(
                        self.image,
                        self.color,
                        Rect(x * TILE_SIZE + 1, y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2)
                    )
        self._create_mask()

    def redraw(self):
        self._draw(self._x, self._y)

    def _create_mask(self):
        self.mask = pygame.mask.from_surface(self.image)

    @property
    def group(self):
        return self.groups()[0]

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = value
        self.rect.left = value * TILE_SIZE

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        self._y = value
        self.rect.top = value * TILE_SIZE

    def move_left(self, group):
        self.x -= 1
        if self.x < 0 or Block.collide(self, group):
            self.x += 1

    def move_right(self, group):
        self.x += 1
        if self.rect.right > GRID_WIDTH or Block.collide(self, group):
            self.x -= 1

    def move_down(self, group):
        self.y += 1
        if self.rect.bottom > GRID_HEIGHT or Block.collide(self, group):
            self.y -= 1
            self.current = False
            raise BottomReached

    def rotate(self, group):
        self.image = pygame.transform.rotate(self.image, 90)
        self.rect.width = self.image.get_width()
        self.rect.height = self.image.get_height()
        self._create_mask()
        while self.rect.right > GRID_WIDTH:
            self.x -= 1
        while self.rect.left < 0:
            self.x += 1
        while self.rect.bottom > GRID_HEIGHT:
            self.y -= 1
        while True:
            if not Block.collide(self, group):
                break
            self.y -= 1
        self.struct = np.rot90(self.struct)

    def update(self):
        if self.current:
            self.move_down()

# Определение различных типов блоков
class SquareBlock(Block):
    struct = ((1, 1), (1, 1))

class TBlock(Block):
    struct = ((1, 1, 1), (0, 1, 0))

class LineBlock(Block):
    struct = ((1,), (1,), (1,), (1,))

class LBlock(Block):
    struct = ((1, 1), (1, 0), (1, 0))

class ZBlock(Block):
    struct = ((0, 1), (1, 1), (1, 0))

class BlocksGroup(pygame.sprite.OrderedUpdates):
    @staticmethod
    def get_random_block():
        """
        Возвращает случайный блок на основе вероятностей.
        """
        block_type = random.choices(
            list(block_probabilities.keys()),
            weights=list(block_probabilities.values())
        )[0]
        return globals()[block_type]()  # Создаем блок по имени класса

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self._reset_grid()
        self._ignore_next_stop = False
        self.score = 0
        self.level = 1
        self.next_block = None
        self.completed_lines = 0  # Новый счетчик завершенных линий
        self.stop_moving_current_block()
        self._create_new_block()

    def _check_line_completion(self):
        completed_lines = 0  # Счетчик завершенных линий
        for i, row in enumerate(self.grid[::-1]):
            if all(row):
                completed_lines += 1  # Увеличиваем счетчик завершенных линий

                # Удаляем блоки в завершенной линии
                affected_blocks = list(OrderedDict.fromkeys(self.grid[-1 - i]))

                for block, y_offset in affected_blocks:
                    block.struct = np.delete(block.struct, y_offset, 0)
                    if block.struct.any():
                        block.struct, x_offset = remove_empty_columns(block.struct)
                        block.x += x_offset
                        block.redraw()
                    else:
                        self.remove(block)

        if completed_lines > 0:
            self.score += 5 * completed_lines * self.level  # Увеличиваем очки за завершенные линии
            self.completed_lines += completed_lines  # Увеличиваем количество завершенных линий
            self.update_grid()  # Обновляем состояние сетки

    def _reset_grid(self):
        self.grid = [[0 for _ in range(10)] for _ in range(20)]

    def _create_new_block(self):
        new_block = self.next_block or BlocksGroup.get_random_block()
        if Block.collide(new_block, self):
            raise TopReached  # Если новый блок пересекается с существующими блоками, игра завершается
        self.add(new_block)
        self.next_block = BlocksGroup.get_random_block()

        # Обновляем сетку и проверяем завершенные линии
        self.update_grid()
        self._check_line_completion()

        # Увеличиваем уровень каждые 10 завершенных линий
        if self.completed_lines // 10 > self.level:
            self.level += 1  # Увеличиваем уровень

    def update_grid(self):
        self._reset_grid()
        for block in self:
            for y_offset, row in enumerate(block.struct):
                for x_offset, digit in enumerate(row):
                    if digit == 0:
                        continue
                    rowid = block.y + y_offset
                    colid = block.x + x_offset
                    self.grid[rowid][colid] = (block, y_offset)

    @property
    def current_block(self):
        return self.sprites()[-1]

    def update_current_block(self):
        try:
            self.current_block.move_down(self)
        except BottomReached:
            self.stop_moving_current_block()
            self._create_new_block()
        else:
            self.update_grid()

    def move_current_block(self):
        if self._current_block_movement_heading is None:
            return
        action = {
            pygame.K_DOWN: self.current_block.move_down,
            pygame.K_LEFT: self.current_block.move_left,
            pygame.K_RIGHT: self.current_block.move_right
        }
        try:
            action[self._current_block_movement_heading](self)
        except BottomReached:
            self.stop_moving_current_block()
            self._create_new_block()
        else:
            self.update_grid()

    def start_moving_current_block(self, key):
        if self._current_block_movement_heading is not None:
            self._ignore_next_stop = True
        self._current_block_movement_heading = key

    def stop_moving_current_block(self):
        if self._ignore_next_stop:
            self._ignore_next_stop = False
        else:
            self._current_block_movement_heading = None

    def rotate_current_block(self):
        if not isinstance(self.current_block, SquareBlock):
            self.current_block.rotate(self)
            self.update_grid()

class Scoreboard:
    def __init__(self):
        self.records = []

    def add_record(self, score):
        self.records.append(score)
        self.records.sort(reverse=True)
        if len(self.records) > 5:  # Хранить только 5 лучших результатов
            self.records.pop()

    def display(self, screen):
        font = pygame.font.Font(None, 36)
        title_text = font.render("Таблица рекордов", True, (255, 255, 255))
        screen.blit(title_text, (WINDOW_WIDTH // 2 - title_text.get_width() // 2, 50))
        for i, score in enumerate(self.records):
            score_text = font.render(f"{i + 1}. {score}", True, (255, 255, 255))
            screen.blit(score_text, (WINDOW_WIDTH // 2 - score_text.get_width() // 2, 100 + i * 30))

def draw_grid(background):
    grid_color = 50, 50, 50
    for i in range(11):
        x = TILE_SIZE * i
        pygame.draw.line(background, grid_color, (x, 0), (x, GRID_HEIGHT))
    for i in range(21):
        y = TILE_SIZE * i
        pygame.draw.line(background, grid_color, (0, y), (GRID_WIDTH, y))

def draw_centered_surface(screen, surface, y):
    screen.blit(surface, (400 - surface.get_width() // 2, y))

def draw_menu(screen):
    font = pygame.font.Font(None, 48)
    title_text = font.render("Тетрис", True, (255, 255, 255))
    start_text = font.render("Начать", True, (255, 255, 255))
    controls_text = font.render("Управление", True, (255, 255, 255))
    scores_text = font.render("Рекорды", True, (255, 255, 255))

    start_button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 50, WINDOW_HEIGHT // 2, 100, 50)
    controls_button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 50, WINDOW_HEIGHT // 2 + 60, 100, 50)
    scores_button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 50, WINDOW_HEIGHT // 2 + 120, 100, 50)
    
    screen.fill((0, 0, 0))  # Черный фон
    screen.blit(title_text, (WINDOW_WIDTH // 2 - title_text.get_width() // 2, WINDOW_HEIGHT // 3))
    
    pygame.draw.rect(screen, (100, 100, 100), start_button_rect)  # Кнопка 'Начать'
    screen.blit(start_text, (WINDOW_WIDTH // 2 - start_text.get_width() // 2, WINDOW_HEIGHT // 2 + 10))
    
    pygame.draw.rect(screen, (100, 100, 100), controls_button_rect)  # Кнопка 'Управление'
    screen.blit(controls_text, (WINDOW_WIDTH // 2 - controls_text.get_width() // 2, WINDOW_HEIGHT // 2 + 70))

    pygame.draw.rect(screen, (100, 100, 100), scores_button_rect)  # Кнопка 'Рекорды'
    screen.blit(scores_text, (WINDOW_WIDTH // 2 - scores_text.get_width() // 2, WINDOW_HEIGHT // 2 + 130))
    
    pygame.display.flip()
    return start_button_rect, controls_button_rect, scores_button_rect

def draw_controls(screen):
    font = pygame.font.Font(None, 36)
    instructions = [
        "Управление:",
        "Стрелка влево - Движение влево",
        "Стрелка вправо - Движение вправо",
        "Стрелка вниз - Движение вниз",
        "Стрелка вверх - Поворот",
        "P - Пауза",
        "Нажмите 'Esc' для возврата в меню"
    ]
    
    screen.fill((0, 0, 0))  # Черный фон
    for i, line in enumerate(instructions):
        text_surface = font.render(line, True, (255, 255, 255))
        screen.blit(text_surface, (50, 50 + i * 30))
    pygame.display.flip()

def draw_stats(screen, score, level, completed_lines):
    font = pygame.font.Font(None, 36)
    score_text = font.render(f"Счет: {score}", True, (255, 255, 255))
    level_text = font.render(f"Уровень: {level}", True, (255, 255, 255))
    lines_text = font.render(f"Завершенные линии: {completed_lines}", True, (255, 255, 255))
    
    screen.blit(score_text, (10, 10))
    screen.blit(level_text, (10, 50))
    screen.blit(lines_text, (10, 90))

def draw_scoreboard(screen, scoreboard):
    screen.fill((0, 0, 0))  # Черный фон
    scoreboard.display(screen)
    
    font = pygame.font.Font(None, 36)
    back_text = font.render("Нажмите 'Esc' для возврата в меню", True, (255, 255, 255))
    screen.blit(back_text, (WINDOW_WIDTH // 2 - back_text.get_width() // 2, WINDOW_HEIGHT - 50))
    
    pygame.display.flip()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:  # Возврат в меню при нажатии Esc
                    waiting = False

def main(scoreboard):
    pygame.init()
    pygame.display.set_caption("Тетрис с PyGame")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    run = True
    paused = False
    game_over = False

    # Создание фона
    background = pygame.Surface(screen.get_size())
    bgcolor = (0, 0, 0)
    background.fill(bgcolor)
    draw_grid(background)
    background = background.convert()

    try:
        font = pygame.font.Font("Roboto-Regular.ttf", 20)
    except OSError:
        font = pygame.font.Font(pygame.font.get_default_font(), 20)
    
    next_block_text = font.render("Следующая фигура:", True, (255, 255, 255), bgcolor)
    game_over_text = font.render("Игра окончена!", True, (255, 220, 0), bgcolor)

    MOVEMENT_KEYS = {
        "LEFT": pygame.K_LEFT,
        "RIGHT": pygame.K_RIGHT,
        "DOWN": pygame.K_DOWN,
        "ROTATE": pygame.K_UP
    }

    EVENT_UPDATE_CURRENT_BLOCK = pygame.USEREVENT + 1
    EVENT_MOVE_CURRENT_BLOCK = pygame.USEREVENT + 2
    pygame.time.set_timer(EVENT_UPDATE_CURRENT_BLOCK, 1000)
    pygame.time.set_timer(EVENT_MOVE_CURRENT_BLOCK, 100)

    blocks = BlocksGroup()

    # Основной цикл игры
    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                break
            
            if game_over:
                continue
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    paused = not paused
                if paused:
                    continue
                if event.key == MOVEMENT_KEYS["LEFT"]:
                    blocks.start_moving_current_block(MOVEMENT_KEYS["LEFT"])
                elif event.key == MOVEMENT_KEYS["RIGHT"]:
                    blocks.start_moving_current_block(MOVEMENT_KEYS["RIGHT"])
                elif event.key == MOVEMENT_KEYS["DOWN"]:
                    blocks.start_moving_current_block(MOVEMENT_KEYS["DOWN"])
                elif event.key == MOVEMENT_KEYS["ROTATE"]:
                    blocks.rotate_current_block()

            elif event.type == pygame.KEYUP:
                if not paused:
                    if event.key in MOVEMENT_KEYS.values():
                        blocks.stop_moving_current_block()

            if not paused:
                try:
                    if event.type == EVENT_UPDATE_CURRENT_BLOCK:
                        blocks.update_current_block()
                    elif event.type == EVENT_MOVE_CURRENT_BLOCK:
                        blocks.move_current_block()
                except TopReached:
                    scoreboard.add_record(blocks.score)  # Добавляем рекорд
                    game_over = True

        # Если игра на паузе
        if paused:
            screen.fill((0, 0, 0))
            pause_text = font.render("Пауза (нажмите 'P' для продолжения)", True, (255, 255, 255))
            screen.blit(pause_text, (WINDOW_WIDTH // 2 - pause_text.get_width() // 2, WINDOW_HEIGHT // 2))
        else:
            screen.blit(background, (0, 0))
            blocks.draw(screen)
            draw_centered_surface(screen, next_block_text, 50)
            draw_centered_surface(screen, blocks.next_block.image, 100)
            draw_stats(screen, blocks.score, blocks.level, blocks.completed_lines)  # Отображение статистики
            if game_over:
                draw_centered_surface(screen, game_over_text, 360)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    
    scoreboard = Scoreboard()  # Создаем экземпляр таблицы рекордов
    start_button_rect, controls_button_rect, scores_button_rect = draw_menu(screen)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and start_button_rect.collidepoint(event.pos):
                    main(scoreboard)
                elif event.button == 1 and controls_button_rect.collidepoint(event.pos):
                    draw_controls(screen)
                    waiting = True
                    while waiting:
                        for inner_event in pygame.event.get():
                            if inner_event.type == pygame.QUIT:
                                pygame.quit()
                                sys.exit()
                            if inner_event.type == pygame.KEYDOWN:
                                if inner_event.key == pygame.K_ESCAPE:
                                    waiting = False
                                    start_button_rect, controls_button_rect, scores_button_rect = draw_menu(screen)
                elif event.button == 1 and scores_button_rect.collidepoint(event.pos):
                    draw_scoreboard(screen, scoreboard)  # Отображаем таблицу рекордов
        pygame.display.flip()