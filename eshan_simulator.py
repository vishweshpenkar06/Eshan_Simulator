"""
ESHAN SIMULATOR
===============
A retro PIXEL-ART 2D fighting game built with pygame.

Features:
- Player vs Player (2 players, one keyboard) or Player vs AI
- 4 unique characters with different stats
- Punch, kick, block, and a super "Special" move (fills up a meter)
- Health bars, round timer, best-of-3 round system
- True retro look: everything is drawn onto a tiny low-resolution
  canvas and then scaled up with NO smoothing, which is what gives
  it that chunky, old-school pixel-game feel.

Controls
--------
Player 1 (Blue corner):   A / D = move,  W = jump,  S = block
                            F = punch,  G = kick,  H = special
Player 2 (Red corner):    Left/Right = move, Up = jump, Down = block
                            Numpad 1 (or END) = punch
                            Numpad 2 (or PAGE DOWN) = kick
                            Numpad 3 (or PAGE UP) = special
ESC = pause / back        ENTER = confirm

Requirements: pip install pygame
Run with:     python eshan_simulator.py
"""

import pygame
import random
import sys
import math
from enum import Enum
from dataclasses import dataclass

pygame.init()

# ----------------------------------------------------------------------------
# PIXEL-ART SETUP
# Everything is drawn onto a tiny internal canvas (INTERNAL_W x INTERNAL_H).
# That canvas is then scaled up by PIXEL_SCALE with pygame.transform.scale
# (nearest-neighbour, i.e. NOT smoothscale) onto the real window. This is
# the classic trick that gives a game that authentic blocky pixel-art look.
# ----------------------------------------------------------------------------
PIXEL_SCALE = 4
INTERNAL_W, INTERNAL_H = 320, 180
WINDOW_W, WINDOW_H = INTERNAL_W * PIXEL_SCALE, INTERNAL_H * PIXEL_SCALE
FPS = 60

# Colors (kept simple / saturated - classic pixel-game palette)
WHITE = (255, 255, 255)
BLACK = (10, 10, 14)
RED = (216, 48, 60)
GREEN = (56, 158, 82)
BLUE = (52, 118, 220)
YELLOW = (252, 208, 60)
ORANGE = (240, 130, 40)
PURPLE = (150, 70, 190)
GRAY = (100, 100, 110)
DARK_GRAY = (48, 48, 58)
LIGHT_GRAY = (190, 190, 200)
SKIN = (240, 196, 156)
SKY_TOP = (26, 20, 48)
SKY_BOTTOM = (78, 54, 110)
GROUND_COLOR = (34, 26, 40)
GROUND_LINE = (58, 44, 70)

pygame.display.set_caption("Eshan Simulator")
screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
canvas = pygame.Surface((INTERNAL_W, INTERNAL_H))
clock = pygame.time.Clock()

# Small pixel-style fonts (default font at tiny sizes reads as pixel font once scaled)
FONT_BIG = pygame.font.SysFont("couriernew", 20, bold=True)
FONT_MED = pygame.font.SysFont("couriernew", 12, bold=True)
FONT_SMALL = pygame.font.SysFont("couriernew", 8, bold=True)


def draw_text(surface, text, font, color, x, y, center=False, shadow=True):
    if shadow:
        shadow_surf = font.render(text, False, BLACK)
        rect = shadow_surf.get_rect()
        if center:
            rect.center = (x + 1, y + 1)
        else:
            rect.topleft = (x + 1, y + 1)
        surface.blit(shadow_surf, rect)
    surf = font.render(text, False, color)
    rect = surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surface.blit(surf, rect)
    return rect


# ----------------------------------------------------------------------------
# GAME DATA
# ----------------------------------------------------------------------------
class GameState(Enum):
    MENU = 0
    CHAR_SELECT = 1
    FIGHTING = 2
    ROUND_END = 3
    GAME_OVER = 4
    PAUSE = 5


class FState(Enum):
    IDLE = 0
    WALK = 1
    JUMP = 2
    ATTACK = 3
    BLOCK = 4
    HIT = 5
    SPECIAL = 6
    KO = 7


@dataclass
class CharacterStats:
    name: str
    color: tuple
    max_health: int
    speed: float
    jump_power: float
    punch_damage: int
    kick_damage: int
    special_damage: int
    defense: float
    desc: str


CHARACTERS = [
    CharacterStats("Eshan", BLUE, 200, 1.6, 6.6, 10, 16, 34, 0.85, "Balanced lightning warrior"),
    CharacterStats("Titan", RED, 260, 1.1, 5.6, 14, 20, 42, 0.75, "Slow but devastating power"),
    CharacterStats("Swift", GREEN, 160, 2.2, 7.6, 8, 12, 27, 0.90, "Fast and agile fighter"),
    CharacterStats("Blaze", ORANGE, 190, 1.5, 6.1, 11, 17, 37, 0.80, "Fiery, hard-hitting striker"),
]


class Particle:
    __slots__ = ("x", "y", "color", "vx", "vy", "life", "max_life", "size")

    def __init__(self, x, y, color, velocity, life, size):
        self.x, self.y = x, y
        self.color = color
        self.vx, self.vy = velocity
        self.life = life
        self.max_life = life
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.25
        self.life -= 1

    def draw(self, surf):
        if self.life <= 0:
            return
        s = max(1, int(self.size * (self.life / self.max_life)))
        pygame.draw.rect(surf, self.color, (int(self.x) - s // 2, int(self.y) - s // 2, s, s))


# ----------------------------------------------------------------------------
# FIGHTER
# ----------------------------------------------------------------------------
class Fighter:
    def __init__(self, x, y, char, p1, ai=False):
        self.char = char
        self.x, self.y = x, y
        self.w, self.h = 16, 34
        self.p1 = p1
        self.ai = ai
        self.facing_right = p1

        self.max_hp = char.max_health
        self.hp = char.max_health
        self.vx, self.vy = 0.0, 0.0
        self.on_ground = True

        self.state = FState.IDLE
        self.state_t = 0
        self.atk_cd = 0
        self.hit_cd = 0
        self.special_cd = 0
        self.meter = 0.0
        self.combo = 0
        self.combo_t = 0
        self.flash = 0

        self.atk_type = None
        self.atk_box = None
        self.atk_dmg = 0
        self.atk_kb = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h), self.w, self.h)

    def take_hit(self, dmg, kbx, kby):
        if self.state == FState.BLOCK:
            blocked = max(1, int(dmg * 0.2 * self.char.defense))
            self.hp -= blocked
            self.vx = kbx * 0.3
            self.flash = 4
            return blocked, True
        actual = max(1, int(dmg * (1 - (1 - self.char.defense) * 0.5)))
        self.hp -= actual
        self.hp = max(0, self.hp)
        self.state = FState.HIT
        self.state_t = 12
        self.hit_cd = 22
        self.vx, self.vy = kbx, kby
        self.flash = 8
        self.meter = min(100, self.meter + actual * 0.6)
        return actual, False

    def start_attack(self, kind):
        if self.atk_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL):
            return
        specs = {
            "punch": (8, 14, 14, 12, 10, self.char.punch_damage, 1.5),
            "kick": (12, 20, 18, 16, 14, self.char.kick_damage, 2.5),
        }
        dur, cd, reach, bw, bh, dmg, kb = specs[kind]
        self.state = FState.ATTACK
        self.state_t = dur
        self.atk_type = kind
        self.atk_cd = cd
        self.vx = 0
        d = 1 if self.facing_right else -1
        bx = self.x + d * (self.w / 2 + reach / 2)
        by = self.y - self.h / 2 - (6 if kind == "kick" else 0)
        self.atk_box = pygame.Rect(int(bx - bw / 2), int(by - bh / 2), bw, bh)
        self.atk_dmg = dmg
        self.atk_kb = kb

    def start_special(self):
        if self.meter < 100 or self.special_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL):
            return
        self.meter = 0
        self.special_cd = 90
        self.state = FState.SPECIAL
        self.state_t = 34
        self.vx = 0
        d = 1 if self.facing_right else -1
        bx = self.x + d * 22
        by = self.y - self.h / 2
        self.atk_box = pygame.Rect(int(bx - 22), int(by - 22), 44, 44)
        self.atk_type = "special"
        self.atk_dmg = self.char.special_damage
        self.atk_kb = 4.5

    def move(self, direction):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL):
            return
        self.vx = direction * self.char.speed
        if self.on_ground:
            self.state = FState.WALK

    def jump(self):
        if self.on_ground and self.state not in (FState.HIT, FState.ATTACK, FState.SPECIAL):
            self.vy = -self.char.jump_power
            self.on_ground = False
            self.state = FState.JUMP

    def block(self, on):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL):
            return
        if on:
            self.state = FState.BLOCK
            self.vx = 0
        elif self.state == FState.BLOCK:
            self.state = FState.IDLE

    def ai_update(self, opp):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL):
            return
        dist = abs(self.x - opp.x)
        if opp.state == FState.ATTACK and dist < 34 and random.random() < 0.5:
            self.block(True)
            return
        if self.meter >= 100 and dist < 40 and random.random() < 0.04:
            self.start_special()
            return
        if dist < 20:
            if random.random() < 0.05:
                self.start_attack("punch")
            elif random.random() < 0.03:
                self.start_attack("kick")
        if dist > 18:
            self.move(1 if opp.x > self.x else -1)
        else:
            self.vx = 0
            if self.state == FState.WALK:
                self.state = FState.IDLE
        if self.on_ground and random.random() < 0.004:
            self.jump()

    def update(self, opp, ground_y):
        if self.atk_cd > 0:
            self.atk_cd -= 1
        if self.hit_cd > 0:
            self.hit_cd -= 1
        if self.special_cd > 0:
            self.special_cd -= 1
        if self.flash > 0:
            self.flash -= 1
        if self.combo_t > 0:
            self.combo_t -= 1
        else:
            self.combo = 0

        if self.state in (FState.ATTACK, FState.SPECIAL):
            self.state_t -= 1
            if self.state_t <= 0:
                self.state = FState.IDLE
                self.atk_box = None
        elif self.state == FState.HIT:
            self.state_t -= 1
            if self.state_t <= 0 and self.on_ground:
                self.state = FState.IDLE

        self.vy += 0.32
        self.x += self.vx
        self.y += self.vy
        if self.on_ground:
            self.vx *= 0.8
            if abs(self.vx) < 0.3:
                self.vx = 0
        if self.y >= ground_y:
            self.y = ground_y
            self.vy = 0
            if not self.on_ground and self.state == FState.JUMP:
                self.state = FState.IDLE
            self.on_ground = True
        else:
            self.on_ground = False

        self.x = max(self.w / 2, min(INTERNAL_W - self.w / 2, self.x))

        if self.state not in (FState.HIT,):
            self.facing_right = opp.x > self.x

        if self.ai:
            self.ai_update(opp)

    def draw(self, surf):
        body_color = WHITE if self.flash > 0 else self.char.color
        d = 1 if self.facing_right else -1

        # legs
        leg_c = DARK_GRAY
        if not (self.state == FState.ATTACK and self.atk_type == "kick"):
            pygame.draw.rect(surf, leg_c, (int(self.x - 6), int(self.y - 14), 5, 14))
            pygame.draw.rect(surf, leg_c, (int(self.x + 1), int(self.y - 14), 5, 14))
        else:
            pygame.draw.rect(surf, leg_c, (int(self.x - 5), int(self.y - 14), 5, 14))
            pygame.draw.rect(surf, SKIN, (int(self.x), int(self.y - 12), int(d * 22), 6))

        # body
        body_rect = pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h), self.w, self.h - 10)
        if self.state == FState.BLOCK:
            body_rect.y += 3
        pygame.draw.rect(surf, body_color, body_rect)
        pygame.draw.rect(surf, BLACK, body_rect, 1)

        # head
        head_r = 6
        hx = self.x + d * 3
        hy = self.y - self.h - head_r + 3
        pygame.draw.rect(surf, SKIN, (int(hx - head_r), int(hy - head_r), head_r * 2, head_r * 2))
        pygame.draw.rect(surf, self.char.color, (int(hx - head_r - 1), int(hy - head_r - 3), head_r * 2 + 2, 3))
        eye_x = hx + d * 3
        pygame.draw.rect(surf, BLACK, (int(eye_x), int(hy - 1), 2, 2))

        # arms
        if self.state == FState.ATTACK and self.atk_type == "punch":
            pygame.draw.rect(surf, SKIN, (int(self.x), int(self.y - self.h + 8), int(d * 16), 5))
        elif self.state == FState.BLOCK:
            pygame.draw.rect(surf, SKIN, (int(self.x - 8), int(self.y - self.h + 8), 16, 5))
        elif self.state == FState.SPECIAL:
            pygame.draw.rect(surf, SKIN, (int(self.x - 10), int(self.y - self.h + 4), 20, 5))
            for _ in range(3):
                ox = random.randint(-14, 14)
                oy = random.randint(-14, 14)
                pygame.draw.rect(surf, YELLOW, (int(self.x + ox), int(self.y - self.h / 2 + oy), 2, 2))
        else:
            sway = int(math.sin(pygame.time.get_ticks() / 120 + (0 if self.p1 else 2)) * 2)
            pygame.draw.rect(surf, SKIN, (int(self.x - 8), int(self.y - self.h + 8 + sway), 5, 8))
            pygame.draw.rect(surf, SKIN, (int(self.x + 3), int(self.y - self.h + 8 - sway), 5, 8))


# ----------------------------------------------------------------------------
# GAME
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.running = True
        self.state = GameState.MENU
        self.ground_y = INTERNAL_H - 24
        self.mode = "pvp"
        self.p1_idx = 0
        self.p2_idx = 1
        self.round = 1
        self.max_rounds = 3
        self.p1_wins = 0
        self.p2_wins = 0
        self.round_time = 60
        self.timer = self.round_time
        self.tick_accum = 0.0
        self.f1 = None
        self.f2 = None
        self.particles = []
        self.shake = 0
        self.round_end_msg = ""
        self.round_end_timer = 0
        self.winner_msg = ""
        self.sounds = {}
        self._make_sounds()

    # -- sound (best-effort; silently disabled if numpy is missing) ---------
    def _make_sounds(self):
        try:
            import numpy as np
            sr = 22050

            def tone(freq, dur, sweep=False, fade=True):
                t = np.linspace(0, dur, int(sr * dur), False)
                f = np.linspace(freq, freq * 2, len(t)) if sweep else freq
                wave = np.sin(2 * np.pi * f * t)
                if fade:
                    wave *= np.linspace(1, 0, len(t))
                audio = (wave * 22000).astype(np.int16)
                stereo = np.column_stack((audio, audio)).copy()
                return pygame.sndarray.make_sound(stereo)

            self.sounds["punch"] = tone(180, 0.09)
            self.sounds["kick"] = tone(130, 0.13)
            self.sounds["block"] = tone(700, 0.06, fade=False)
            self.sounds["special"] = tone(300, 0.35, sweep=True)
            self.sounds["win"] = tone(500, 0.3, sweep=True)
        except Exception:
            self.sounds = {}

    def play(self, name):
        s = self.sounds.get(name)
        if s:
            try:
                s.play()
            except Exception:
                pass

    def spawn_particles(self, x, y, color, count=8, speed=3):
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            vel = (math.cos(ang) * random.uniform(1, speed), math.sin(ang) * random.uniform(1, speed) - 1.5)
            self.particles.append(Particle(x, y, color, vel, random.randint(10, 20), random.randint(2, 4)))

    def start_fight(self):
        c1 = CHARACTERS[self.p1_idx]
        c2 = CHARACTERS[self.p2_idx]
        self.f1 = Fighter(INTERNAL_W * 0.25, self.ground_y, c1, True, False)
        self.f2 = Fighter(INTERNAL_W * 0.75, self.ground_y, c2, False, self.mode == "ai")
        self.timer = self.round_time
        self.tick_accum = 0.0
        self.particles = []
        self.shake = 0
        self.state = GameState.FIGHTING

    def check_hits(self):
        for a, b in ((self.f1, self.f2), (self.f2, self.f1)):
            if a.atk_box and a.state in (FState.ATTACK, FState.SPECIAL) and b.hit_cd <= 0:
                if a.atk_box.colliderect(b.rect):
                    d = 1 if a.facing_right else -1
                    kbx = d * a.atk_kb
                    kby = -3.5 if a.atk_type == "special" else -1.2
                    dmg, blocked = b.take_hit(a.atk_dmg, kbx, kby)
                    a.meter = min(100, a.meter + dmg * 1.0)
                    self.spawn_particles(b.x, b.y - b.h / 2, YELLOW if blocked else RED, 10, 4)
                    self.shake = 6 if a.atk_type == "special" else 3
                    self.play("block" if blocked else ("special" if a.atk_type == "special" else a.atk_type))
                    if not blocked:
                        a.combo += 1
                        a.combo_t = 45
                    a.atk_box = None

    def check_round_end(self):
        if self.f1.hp <= 0 or self.f2.hp <= 0 or self.timer <= 0:
            if self.f1.hp > self.f2.hp:
                self.p1_wins += 1
                self.winner_msg = f"{self.f1.char.name} WINS ROUND {self.round}"
            elif self.f2.hp > self.f1.hp:
                self.p2_wins += 1
                self.winner_msg = f"{self.f2.char.name} WINS ROUND {self.round}"
            else:
                self.winner_msg = "DRAW ROUND"
            self.play("win")
            self.round += 1
            self.round_end_timer = 90
            self.state = GameState.ROUND_END

    # -- input ---------------------------------------------------------------
    def handle_keydown(self, key):
        if self.state == GameState.MENU:
            if key == pygame.K_1:
                self.mode = "pvp"
                self.state = GameState.CHAR_SELECT
            elif key == pygame.K_2:
                self.mode = "ai"
                self.state = GameState.CHAR_SELECT
            elif key == pygame.K_ESCAPE:
                self.running = False

        elif self.state == GameState.CHAR_SELECT:
            if key == pygame.K_a:
                self.p1_idx = (self.p1_idx - 1) % len(CHARACTERS)
            elif key == pygame.K_d:
                self.p1_idx = (self.p1_idx + 1) % len(CHARACTERS)
            elif key == pygame.K_LEFT:
                self.p2_idx = (self.p2_idx - 1) % len(CHARACTERS)
            elif key == pygame.K_RIGHT:
                self.p2_idx = (self.p2_idx + 1) % len(CHARACTERS)
            elif key == pygame.K_RETURN:
                self.round, self.p1_wins, self.p2_wins = 1, 0, 0
                self.start_fight()
            elif key == pygame.K_ESCAPE:
                self.state = GameState.MENU

        elif self.state == GameState.FIGHTING:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PAUSE
            elif key == pygame.K_f:
                self.f1.start_attack("punch")
            elif key == pygame.K_g:
                self.f1.start_attack("kick")
            elif key == pygame.K_h:
                self.f1.start_special()
            elif self.mode == "pvp":
                if key in (pygame.K_KP1, pygame.K_END):
                    self.f2.start_attack("punch")
                elif key in (pygame.K_KP2, pygame.K_PAGEDOWN):
                    self.f2.start_attack("kick")
                elif key in (pygame.K_KP3, pygame.K_PAGEUP):
                    self.f2.start_special()

        elif self.state == GameState.PAUSE:
            if key == pygame.K_ESCAPE:
                self.state = GameState.FIGHTING
            elif key == pygame.K_q:
                self.state = GameState.MENU

        elif self.state == GameState.GAME_OVER:
            if key == pygame.K_RETURN:
                self.state = GameState.MENU
            elif key == pygame.K_r:
                self.round, self.p1_wins, self.p2_wins = 1, 0, 0
                self.start_fight()
            elif key == pygame.K_ESCAPE:
                self.running = False

    def handle_keyup(self, key):
        if self.state == GameState.FIGHTING:
            if key == pygame.K_s:
                self.f1.block(False)
            elif self.mode == "pvp" and key == pygame.K_DOWN:
                self.f2.block(False)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.KEYUP:
                self.handle_keyup(event.key)

    # -- update ---------------------------------------------------------------
    def update(self, dt):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]
        if self.shake > 0:
            self.shake -= 1

        if self.state == GameState.FIGHTING:
            keys = pygame.key.get_pressed()
            if self.f1.state not in (FState.HIT, FState.ATTACK, FState.SPECIAL):
                if keys[pygame.K_a]:
                    self.f1.move(-1)
                elif keys[pygame.K_d]:
                    self.f1.move(1)
                elif self.f1.state == FState.WALK:
                    self.f1.state = FState.IDLE
                if keys[pygame.K_w]:
                    self.f1.jump()
                if keys[pygame.K_s]:
                    self.f1.block(True)

            if self.mode == "pvp":
                if self.f2.state not in (FState.HIT, FState.ATTACK, FState.SPECIAL):
                    if keys[pygame.K_LEFT]:
                        self.f2.move(-1)
                    elif keys[pygame.K_RIGHT]:
                        self.f2.move(1)
                    elif self.f2.state == FState.WALK:
                        self.f2.state = FState.IDLE
                    if keys[pygame.K_UP]:
                        self.f2.jump()
                    if keys[pygame.K_DOWN]:
                        self.f2.block(True)

            self.f1.update(self.f2, self.ground_y)
            self.f2.update(self.f1, self.ground_y)
            self.check_hits()

            self.tick_accum += dt
            if self.tick_accum >= 1.0:
                self.tick_accum -= 1.0
                self.timer -= 1
            self.check_round_end()

        elif self.state == GameState.ROUND_END:
            self.round_end_timer -= 1
            if self.round_end_timer <= 0:
                if self.p1_wins >= 2 or self.p2_wins >= 2 or self.round > self.max_rounds:
                    if self.p1_wins > self.p2_wins:
                        self.winner_msg = f"{self.f1.char.name} WINS THE MATCH!"
                    elif self.p2_wins > self.p1_wins:
                        self.winner_msg = f"{self.f2.char.name} WINS THE MATCH!"
                    else:
                        self.winner_msg = "IT'S A DRAW!"
                    self.state = GameState.GAME_OVER
                else:
                    self.start_fight()

    # -- draw ------------------------------------------------------------------
    def draw_background(self, surf):
        for y in range(INTERNAL_H):
            t = y / INTERNAL_H
            color = (
                int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * t),
                int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * t),
                int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * t),
            )
            pygame.draw.line(surf, color, (0, y), (INTERNAL_W, y))
        pygame.draw.rect(surf, GROUND_COLOR, (0, self.ground_y, INTERNAL_W, INTERNAL_H - self.ground_y))
        pygame.draw.line(surf, GROUND_LINE, (0, self.ground_y), (INTERNAL_W, self.ground_y), 2)
        for x in range(0, INTERNAL_W, 20):
            pygame.draw.line(surf, GROUND_LINE, (x, self.ground_y + 4), (x - 6, INTERNAL_H), 1)

    def draw_menu(self, surf):
        self.draw_background(surf)
        draw_text(surf, "ESHAN SIMULATOR", FONT_BIG, YELLOW, INTERNAL_W // 2, 40, center=True)
        draw_text(surf, "A Pixel Fighting Game", FONT_SMALL, WHITE, INTERNAL_W // 2, 58, center=True)
        draw_text(surf, "1: Player vs Player", FONT_MED, WHITE, INTERNAL_W // 2, 95, center=True)
        draw_text(surf, "2: Player vs AI", FONT_MED, WHITE, INTERNAL_W // 2, 112, center=True)
        draw_text(surf, "ESC: Quit", FONT_SMALL, LIGHT_GRAY, INTERNAL_W // 2, 135, center=True)
        draw_text(surf, "P1: A/D move  W jump  S block  F/G/H attack", FONT_SMALL, LIGHT_GRAY, INTERNAL_W // 2, 160, center=True)

    def draw_char_select(self, surf):
        self.draw_background(surf)
        draw_text(surf, "CHARACTER SELECT", FONT_BIG, YELLOW, INTERNAL_W // 2, 20, center=True)
        c1 = CHARACTERS[self.p1_idx]
        c2 = CHARACTERS[self.p2_idx]
        # p1 box
        pygame.draw.rect(surf, c1.color, (30, 55, 60, 60))
        pygame.draw.rect(surf, WHITE, (30, 55, 60, 60), 1)
        draw_text(surf, c1.name, FONT_MED, WHITE, 60, 125, center=True)
        draw_text(surf, c1.desc, FONT_SMALL, LIGHT_GRAY, 60, 138, center=True)
        draw_text(surf, "A/D", FONT_SMALL, LIGHT_GRAY, 60, 150, center=True)
        # p2 box
        label = "AI" if self.mode == "ai" else "P2"
        pygame.draw.rect(surf, c2.color, (INTERNAL_W - 90, 55, 60, 60))
        pygame.draw.rect(surf, WHITE, (INTERNAL_W - 90, 55, 60, 60), 1)
        draw_text(surf, c2.name, FONT_MED, WHITE, INTERNAL_W - 60, 125, center=True)
        draw_text(surf, c2.desc, FONT_SMALL, LIGHT_GRAY, INTERNAL_W - 60, 138, center=True)
        draw_text(surf, f"Left/Right ({label})", FONT_SMALL, LIGHT_GRAY, INTERNAL_W - 60, 150, center=True)
        draw_text(surf, "VS", FONT_BIG, RED, INTERNAL_W // 2, 85, center=True)
        draw_text(surf, "ENTER: Fight!   ESC: Back", FONT_SMALL, WHITE, INTERNAL_W // 2, 170, center=True)

    def draw_hud(self, surf):
        # health bars
        for i, f in enumerate((self.f1, self.f2)):
            pct = max(0, f.hp / f.max_hp)
            bar_w = 120
            x = 6 if i == 0 else INTERNAL_W - 6 - bar_w
            pygame.draw.rect(surf, DARK_GRAY, (x, 8, bar_w, 8))
            fill_w = int(bar_w * pct)
            fill_color = GREEN if pct > 0.5 else (YELLOW if pct > 0.25 else RED)
            fill_x = x if i == 0 else x + bar_w - fill_w
            pygame.draw.rect(surf, fill_color, (fill_x, 8, fill_w, 8))
            pygame.draw.rect(surf, WHITE, (x, 8, bar_w, 8), 1)
            name_x = x if i == 0 else x + bar_w
            draw_text(surf, f.char.name, FONT_SMALL, WHITE, name_x, 18, center=False if i == 0 else False)
            # meter
            mpct = f.meter / 100
            mfill_x = x if i == 0 else x + bar_w - int(bar_w * mpct)
            pygame.draw.rect(surf, PURPLE, (x, 18, bar_w, 3))
            pygame.draw.rect(surf, (255, 215, 100), (mfill_x, 18, int(bar_w * mpct), 3))

        draw_text(surf, str(max(0, self.timer)), FONT_BIG, WHITE, INTERNAL_W // 2, 16, center=True)
        # round pips
        for i in range(self.max_rounds - 1):
            col = YELLOW if i < self.p1_wins else DARK_GRAY
            pygame.draw.rect(surf, col, (INTERNAL_W // 2 - 20 + i * 8, 28, 5, 5))
            col2 = YELLOW if i < self.p2_wins else DARK_GRAY
            pygame.draw.rect(surf, col2, (INTERNAL_W // 2 + 15 - i * 8, 28, 5, 5))

    def draw_fighting(self, surf):
        self.draw_background(surf)
        self.f2.draw(surf) if self.f2.x < self.f1.x else self.f1.draw(surf)
        # draw the further-back one first for a touch of depth is overkill here;
        # simplest: just draw both, order doesn't matter much for these sprites.
        self.f1.draw(surf)
        self.f2.draw(surf)
        for p in self.particles:
            p.draw(surf)
        self.draw_hud(surf)

    def draw_round_end(self, surf):
        self.draw_fighting(surf)
        overlay = pygame.Surface((INTERNAL_W, 30), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, INTERNAL_H // 2 - 15))
        draw_text(surf, self.winner_msg, FONT_MED, YELLOW, INTERNAL_W // 2, INTERNAL_H // 2, center=True)

    def draw_pause(self, surf):
        self.draw_fighting(surf)
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "PAUSED", FONT_BIG, WHITE, INTERNAL_W // 2, 70, center=True)
        draw_text(surf, "ESC: Resume", FONT_MED, LIGHT_GRAY, INTERNAL_W // 2, 100, center=True)
        draw_text(surf, "Q: Quit to Menu", FONT_MED, LIGHT_GRAY, INTERNAL_W // 2, 116, center=True)

    def draw_game_over(self, surf):
        self.draw_background(surf)
        draw_text(surf, "GAME OVER", FONT_BIG, RED, INTERNAL_W // 2, 55, center=True)
        draw_text(surf, self.winner_msg, FONT_MED, YELLOW, INTERNAL_W // 2, 85, center=True)
        draw_text(surf, "ENTER: Menu    R: Rematch    ESC: Quit", FONT_SMALL, WHITE, INTERNAL_W // 2, 120, center=True)

    def draw(self):
        canvas.fill(BLACK)
        if self.state == GameState.MENU:
            self.draw_menu(canvas)
        elif self.state == GameState.CHAR_SELECT:
            self.draw_char_select(canvas)
        elif self.state == GameState.FIGHTING:
            self.draw_fighting(canvas)
        elif self.state == GameState.ROUND_END:
            self.draw_round_end(canvas)
        elif self.state == GameState.PAUSE:
            self.draw_pause(canvas)
        elif self.state == GameState.GAME_OVER:
            self.draw_game_over(canvas)

        # screen shake + scale up (pure nearest-neighbour scale -> crisp pixels)
        ox = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        oy = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        scaled = pygame.transform.scale(canvas, (WINDOW_W, WINDOW_H))
        screen.fill(BLACK)
        screen.blit(scaled, (ox * PIXEL_SCALE // 3, oy * PIXEL_SCALE // 3))
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()