"""
ESHAN SIMULATOR
===============
A retro PIXEL-ART platform fighter, Super-Smash-Bros style.

Stage: a university college courtyard with a cheering crowd in the
stands and two floating platforms to jump around on. Knock your
opponent's percent up and launch them clean off the stage to take
their stock!

Fighters
--------
Eshan     - The GOATED bulky powerhouse. Slow, heavy, hits like a truck.
Vishwesh  - Mid-bulk athletic all-rounder.
Karan     - Smart, mid athletic, his Special hits hardest of all.
Abhijit   - Tallest of the group, nerdy, long reach but light-ish.
Ajinkya   - Shortest and weakest, but fast and hard to pin down.

Controls
--------
Player 1:  Arrow Keys = move / Down = shield
           Z = Jump   X = Attack   A = Grab   S = Special
Player 2 (PvP mode only):
           F/H = left/right, T/G = up/down (down = shield)
           R = Jump   Y = Attack   U = Grab   J = Special

ESC = pause / back     ENTER = confirm

Requirements: pip install pygame
Run with:     python eshan_simulator.py
"""

import pygame
import random
import sys
import math
from enum import Enum
from dataclasses import dataclass, field

pygame.init()

# ----------------------------------------------------------------------------
# PIXEL-ART SETUP - draw to a tiny canvas, scale up with NO smoothing.
# ----------------------------------------------------------------------------
PIXEL_SCALE = 4
INTERNAL_W, INTERNAL_H = 320, 180
WINDOW_W, WINDOW_H = INTERNAL_W * PIXEL_SCALE, INTERNAL_H * PIXEL_SCALE
FPS = 60

WHITE = (255, 255, 255)
BLACK = (10, 10, 14)
RED = (216, 48, 60)
GREEN = (56, 158, 82)
BLUE = (52, 118, 220)
YELLOW = (252, 208, 60)
ORANGE = (240, 130, 40)
PURPLE = (150, 70, 190)
PINK = (230, 110, 160)
GRAY = (110, 110, 122)
DARK_GRAY = (48, 48, 58)
LIGHT_GRAY = (196, 196, 206)
SKIN_1 = (160, 110, 76)
SKIN_2 = (200, 150, 105)
HAIR_DARK = (34, 24, 22)
SKY_TOP = (36, 26, 60)
SKY_BOTTOM = (110, 70, 120)
BUILD_STONE = (150, 138, 120)
BUILD_STONE_DK = (110, 100, 88)
BANNER_RED = (160, 40, 45)
GROUND_COLOR = (70, 58, 46)
GROUND_LINE = (100, 84, 64)
PLATFORM_COLOR = (120, 90, 60)

pygame.display.set_caption("Eshan Simulator")
screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
canvas = pygame.Surface((INTERNAL_W, INTERNAL_H))
clock = pygame.time.Clock()

FONT_BIG = pygame.font.SysFont("couriernew", 20, bold=True)
FONT_MED = pygame.font.SysFont("couriernew", 12, bold=True)
FONT_SMALL = pygame.font.SysFont("couriernew", 8, bold=True)


def draw_text(surface, text, font, color, x, y, center=False, shadow=True):
    if shadow:
        sh = font.render(text, False, BLACK)
        r = sh.get_rect()
        if center:
            r.center = (x + 1, y + 1)
        else:
            r.topleft = (x + 1, y + 1)
        surface.blit(sh, r)
    surf = font.render(text, False, color)
    r = surf.get_rect()
    if center:
        r.center = (x, y)
    else:
        r.topleft = (x, y)
    surface.blit(surf, r)
    return r


# ----------------------------------------------------------------------------
# STAGE
# ----------------------------------------------------------------------------
GROUND_Y = INTERNAL_H - 40
PLATFORMS = [
    pygame.Rect(46, 104, 62, 5),
    pygame.Rect(INTERNAL_W - 108, 104, 62, 5),
]
BLAST_LEFT, BLAST_RIGHT = -28, INTERNAL_W + 28
BLAST_TOP, BLAST_BOTTOM = -70, INTERNAL_H + 60
SPAWN_POINTS = [(70, GROUND_Y - 60), (INTERNAL_W - 70, GROUND_Y - 60)]


class GameState(Enum):
    MENU = 0
    CHAR_SELECT = 1
    FIGHTING = 2
    KO_FLASH = 3
    PAUSE = 4
    GAME_OVER = 5


class FState(Enum):
    IDLE = 0
    WALK = 1
    JUMP = 2
    FALL = 3
    ATTACK = 4
    SPECIAL = 5
    GRAB = 6
    GRABBED = 7
    SHIELD = 8
    HIT = 9


@dataclass
class CharacterStats:
    name: str
    shirt: tuple
    skin: tuple
    weight: float      # >1 = heavier, resists knockback
    speed: float
    jump_power: float
    width: int
    height: int
    punch_dmg: int
    special_dmg: int
    grab_dmg: int
    glasses: bool
    build: str          # "fat", "athletic", "tall", "short"
    desc: str


CHARACTERS = [
    CharacterStats("Eshan", (36, 36, 40), SKIN_1, 1.55, 1.05, 6.2, 26, 30,
                    9, 32, 11, False, "fat", "The GOATED bulky powerhouse"),
    CharacterStats("Vishwesh", BLUE, SKIN_2, 1.10, 1.55, 6.6, 16, 36,
                    8, 24, 9, False, "athletic", "Mid-bulk athletic all-rounder"),
    CharacterStats("Karan", GREEN, SKIN_2, 1.00, 1.45, 6.4, 14, 35,
                    7, 30, 8, True, "athletic", "Smart, his Special hits hardest"),
    CharacterStats("Abhijit", ORANGE, SKIN_1, 0.95, 1.35, 6.1, 15, 42,
                    7, 25, 8, True, "tall", "Tallest, nerdy, long reach"),
    CharacterStats("Ajinkya", PURPLE, SKIN_2, 0.75, 2.10, 7.6, 11, 26,
                    5, 18, 6, False, "short", "Shortest and weakest, but fast"),
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
        self.vy += 0.22
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
    def __init__(self, char, p1, ai=False, stocks=3):
        self.char = char
        self.p1 = p1
        self.ai = ai
        idx = 0 if p1 else 1
        self.x, self.y = SPAWN_POINTS[idx]
        self.w, self.h = char.width, char.height
        self.facing_right = p1

        self.vx, self.vy = 0.0, 0.0
        self.on_ground = True
        self.on_platform = None

        self.percent = 0.0
        self.stocks = stocks
        self.invuln = 60

        self.state = FState.IDLE
        self.state_t = 0
        self.atk_cd = 0
        self.grab_cd = 0
        self.special_cd = 0
        self.meter = 0.0
        self.flash = 0
        self.shield_hp = 100

        self.atk_box = None
        self.atk_dmg = 0
        self.atk_kb = 0
        self.grab_target = None
        self.ko_timer = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h), self.w, self.h)

    def respawn(self):
        idx = 0 if self.p1 else 1
        self.x, self.y = SPAWN_POINTS[idx]
        self.vx, self.vy = 0, 0
        self.percent = 0
        self.invuln = 90
        self.state = FState.FALL
        self.on_ground = False

    def apply_knockback(self, dmg, dir_sign, kb_base, launch_angle_deg=52):
        # classic smash-ish knockback: grows with current percent (which already
        # includes this hit's damage), reduced by weight. Low percent = light
        # tap, high percent = a real launch that can send someone off the stage.
        growth = self.percent * 0.035
        kb = (kb_base + growth) / self.char.weight
        kb = max(1.4, kb)
        angle = math.radians(launch_angle_deg)
        self.vx = math.cos(angle) * kb * dir_sign
        self.vy = -math.sin(angle) * kb
        hitstun = min(70, int(kb * 1.6) + 6)
        self.state = FState.HIT
        self.state_t = hitstun
        self.on_ground = False

    def take_hit(self, dmg, dir_sign, kb_base, angle=52):
        if self.invuln > 0:
            return 0, False
        if self.state == FState.SHIELD and self.shield_hp > 0:
            blocked = max(1, int(dmg * 0.15))
            self.shield_hp -= dmg * 2.5
            self.vx = dir_sign * 1.2
            self.flash = 4
            if self.shield_hp <= 0:
                self.shield_hp = 0
                self.state = FState.HIT
                self.state_t = 40
                self.apply_knockback(dmg * 0.3, dir_sign, 2, angle)
            return blocked, True
        self.percent += dmg
        self.flash = 8
        self.meter = min(100, self.meter + dmg * 0.9)
        self.apply_knockback(dmg, dir_sign, kb_base, angle)
        return dmg, False

    def start_attack(self):
        if self.atk_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        self.state = FState.ATTACK
        self.state_t = 10
        self.atk_cd = 16
        d = 1 if self.facing_right else -1
        reach, bw, bh = 16, 14, 12
        bx = self.x + d * (self.w / 2 + reach / 2)
        by = self.y - self.h / 2
        self.atk_box = pygame.Rect(int(bx - bw / 2), int(by - bh / 2), bw, bh)
        self.atk_dmg = self.char.punch_dmg
        self.atk_kb = 2

    def start_special(self):
        if self.meter < 100 or self.special_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        self.meter = 0
        self.special_cd = 100
        self.state = FState.SPECIAL
        self.state_t = 30
        self.vx = 0
        d = 1 if self.facing_right else -1
        bx = self.x + d * 24
        by = self.y - self.h / 2
        self.atk_box = pygame.Rect(int(bx - 24), int(by - 24), 48, 48)
        self.atk_dmg = self.char.special_dmg
        self.atk_kb = 5

    def start_grab(self, opp):
        if self.grab_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        d = 1 if self.facing_right else -1
        reach = 20
        gx = self.x + d * reach
        grab_box = pygame.Rect(int(gx - 10), int(self.y - self.h + 6), 20, self.h - 10)
        self.grab_cd = 40
        self.state = FState.GRAB
        self.state_t = 14
        self.vx = 0
        if grab_box.colliderect(opp.rect) and opp.invuln <= 0 and opp.state not in (FState.GRABBED,):
            self.grab_target = opp
            opp.state = FState.GRABBED
            opp.state_t = 20
            opp.vx = opp.vy = 0

    def resolve_grab_throw(self):
        opp = self.grab_target
        if opp is None:
            return
        d = 1 if self.facing_right else -1
        opp.percent += self.char.grab_dmg
        self.meter = min(100, self.meter + self.char.grab_dmg * 0.9)
        opp.apply_knockback(self.char.grab_dmg, d, 3, 40)
        self.grab_target = None

    def move(self, direction):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        self.vx = direction * self.char.speed
        if self.on_ground:
            self.state = FState.WALK
            self.facing_right = direction > 0 if direction != 0 else self.facing_right

    def jump(self):
        if self.on_ground and self.state not in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            self.vy = -self.char.jump_power
            self.on_ground = False
            self.on_platform = None
            self.state = FState.JUMP

    def shield(self, on):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        if on and self.on_ground:
            self.state = FState.SHIELD
            self.vx = 0
        elif not on and self.state == FState.SHIELD:
            self.state = FState.IDLE
            self.shield_hp = min(100, self.shield_hp + 1)

    def ai_update(self, opp):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        dist = abs(self.x - opp.x)
        if opp.state == FState.ATTACK and dist < 30 and random.random() < 0.4:
            self.shield(True)
            return
        else:
            self.shield(False)
        if self.meter >= 100 and dist < 42 and random.random() < 0.035:
            self.start_special()
            return
        if dist < 18 and random.random() < 0.015:
            self.start_grab(opp)
            return
        if dist < 20:
            if random.random() < 0.06:
                self.start_attack()
        if dist > 16:
            self.move(1 if opp.x > self.x else -1)
        else:
            self.vx = 0
            if self.state == FState.WALK:
                self.state = FState.IDLE
        if self.on_ground and random.random() < 0.006:
            self.jump()
        # avoid blast zone edges
        if self.x < 20 and self.on_ground:
            self.move(1)
        elif self.x > INTERNAL_W - 20 and self.on_ground:
            self.move(-1)

    def update(self, opp):
        if self.atk_cd > 0:
            self.atk_cd -= 1
        if self.grab_cd > 0:
            self.grab_cd -= 1
        if self.special_cd > 0:
            self.special_cd -= 1
        if self.flash > 0:
            self.flash -= 1
        if self.invuln > 0:
            self.invuln -= 1
        if self.state == FState.SHIELD:
            self.shield_hp = min(100, self.shield_hp + 0.15)

        if self.state in (FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            self.state_t -= 1
            if self.state_t <= 0:
                if self.state == FState.GRAB and self.grab_target is opp and opp.state == FState.GRABBED:
                    self.resolve_grab_throw()
                self.state = FState.IDLE
                self.atk_box = None
        elif self.state == FState.HIT:
            self.state_t -= 1
            if self.state_t <= 0 and self.on_ground:
                self.state = FState.IDLE

        # physics
        self.vy += 0.30
        self.x += self.vx
        self.y += self.vy
        if self.on_ground:
            self.vx *= 0.82
            if abs(self.vx) < 0.3:
                self.vx = 0

        # platform / ground collision
        self.on_ground = False
        self.on_platform = None
        if self.vy >= 0:
            for plat in PLATFORMS:
                foot_prev = self.y - self.vy
                if (plat.left - self.w / 2 < self.x < plat.right + self.w / 2
                        and foot_prev <= plat.top + 1 and self.y >= plat.top):
                    self.y = plat.top
                    self.vy = 0
                    self.on_ground = True
                    self.on_platform = plat
                    break
        if self.y >= GROUND_Y:
            self.y = GROUND_Y
            self.vy = 0
            self.on_ground = True

        if self.on_ground and self.state in (FState.JUMP, FState.FALL, FState.HIT) and self.state_t <= 0:
            self.state = FState.IDLE
        if not self.on_ground and self.state in (FState.IDLE, FState.WALK, FState.JUMP):
            self.state = FState.FALL if self.vy > 1 else self.state

        if self.state not in (FState.HIT, FState.GRABBED):
            self.facing_right = opp.x > self.x

        if self.ai:
            self.ai_update(opp)

        # blast zones -> lose a stock
        if self.x < BLAST_LEFT or self.x > BLAST_RIGHT or self.y > BLAST_BOTTOM or self.y < BLAST_TOP:
            self.stocks -= 1
            if self.stocks > 0:
                self.respawn()
            return "ko"
        return None

    def draw(self, surf):
        if self.flash > 0 and self.flash % 2 == 0:
            body_color = WHITE
        else:
            body_color = self.char.shirt
        d = 1 if self.facing_right else -1
        skin = self.char.skin
        build = self.char.build

        belly = 6 if build == "fat" else 0
        leg_h = 12 if build != "tall" else 15
        leg_w = 5 if build != "short" else 4

        # shield bubble
        if self.state == FState.SHIELD:
            radius = int(10 + self.shield_hp / 10)
            s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 200, 255, 90), (radius, radius), radius)
            surf.blit(s, (int(self.x - radius), int(self.y - self.h / 2 - radius)))

        # legs
        if not (self.state == FState.ATTACK and False):
            pygame.draw.rect(surf, HAIR_DARK, (int(self.x - leg_w - 1), int(self.y - leg_h), leg_w, leg_h))
            pygame.draw.rect(surf, HAIR_DARK, (int(self.x + 1), int(self.y - leg_h), leg_w, leg_h))

        # torso
        torso_w = self.w + belly
        torso_rect = pygame.Rect(int(self.x - torso_w / 2), int(self.y - self.h), torso_w, self.h - leg_h)
        pygame.draw.rect(surf, body_color, torso_rect)
        pygame.draw.rect(surf, BLACK, torso_rect, 1)
        if build == "fat":
            pygame.draw.ellipse(surf, body_color, (torso_rect.x - 2, torso_rect.bottom - 14, torso_rect.w + 4, 16))
            pygame.draw.ellipse(surf, BLACK, (torso_rect.x - 2, torso_rect.bottom - 14, torso_rect.w + 4, 16), 1)

        # head
        head_r = 7 if build != "short" else 6
        hx = self.x + d * 2
        hy = torso_rect.top - head_r + 2
        pygame.draw.rect(surf, skin, (int(hx - head_r), int(hy - head_r), head_r * 2, head_r * 2))
        # hair
        pygame.draw.rect(surf, HAIR_DARK, (int(hx - head_r - 1), int(hy - head_r - 3), head_r * 2 + 2, 4))
        if build == "fat":
            for i in range(-2, 3):
                pygame.draw.rect(surf, HAIR_DARK, (int(hx + i * 3 - 1), int(hy - head_r - 4), 3, 3))
        # glasses
        if self.char.glasses:
            gy = int(hy - 1)
            pygame.draw.rect(surf, BLACK, (int(hx - head_r + 1), gy, head_r, 3), 1)
        # eyes
        eye_x = hx + d * 3
        pygame.draw.rect(surf, BLACK, (int(eye_x), int(hy - 1), 2, 2))

        # arms
        if self.state == FState.ATTACK:
            pygame.draw.rect(surf, skin, (int(self.x), int(self.y - self.h + 8), int(d * 16), 5))
        elif self.state == FState.GRAB:
            pygame.draw.rect(surf, skin, (int(self.x), int(self.y - self.h + 10), int(d * 20), 4))
        elif self.state == FState.GRABBED:
            pygame.draw.rect(surf, skin, (int(self.x - 6), int(self.y - self.h + 10), 12, 4))
        elif self.state == FState.SPECIAL:
            pygame.draw.rect(surf, skin, (int(self.x - 10), int(self.y - self.h + 4), 20, 5))
            for _ in range(3):
                ox = random.randint(-16, 16)
                oy = random.randint(-16, 16)
                pygame.draw.rect(surf, YELLOW, (int(self.x + ox), int(self.y - self.h / 2 + oy), 2, 2))
        elif self.state == FState.SHIELD:
            pygame.draw.rect(surf, skin, (int(self.x - 8), int(self.y - self.h + 8), 16, 5))
        else:
            sway = int(math.sin(pygame.time.get_ticks() / 120 + (0 if self.p1 else 2)) * 2)
            pygame.draw.rect(surf, skin, (int(self.x - torso_w / 2 - 4), int(self.y - self.h + 8 + sway), 5, 8))
            pygame.draw.rect(surf, skin, (int(self.x + torso_w / 2 - 1), int(self.y - self.h + 8 - sway), 5, 8))


# ----------------------------------------------------------------------------
# BACKGROUND: college courtyard + cheering crowd + FNF-style bystander girl
# ----------------------------------------------------------------------------
class Background:
    def __init__(self):
        self.crowd = []
        random.seed(7)
        colors = [RED, BLUE, GREEN, YELLOW, ORANGE, PURPLE, PINK, WHITE]
        for row in range(3):
            y = 44 + row * 10
            for i in range(26):
                x = 4 + i * 12 + (row % 2) * 5
                self.crowd.append([x, y, random.choice(colors), random.uniform(0, math.tau)])
        random.seed()

    def draw(self, surf, t):
        for y in range(INTERNAL_H):
            f = y / INTERNAL_H
            c = (
                int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * f),
                int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * f),
                int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * f),
            )
            pygame.draw.line(surf, c, (0, y), (INTERNAL_W, y))

        # college building
        pygame.draw.rect(surf, BUILD_STONE, (0, 20, INTERNAL_W, 40))
        pygame.draw.polygon(surf, BUILD_STONE_DK, [(INTERNAL_W // 2 - 46, 20), (INTERNAL_W // 2, 2), (INTERNAL_W // 2 + 46, 20)])
        for cx in range(6, INTERNAL_W - 5, 14):
            pygame.draw.rect(surf, BUILD_STONE_DK, (cx, 24, 5, 34))
        pygame.draw.rect(surf, BANNER_RED, (INTERNAL_W // 2 - 44, 8, 88, 10))
        draw_text(surf, "STATE UNIVERSITY", FONT_SMALL, YELLOW, INTERNAL_W // 2, 13, center=True, shadow=False)

        # crowd (cheering, bobbing arms)
        for c in self.crowd:
            x, y, col, phase = c
            bob = math.sin(t * 4 + phase) * 2
            pygame.draw.rect(surf, col, (int(x), int(y + bob), 4, 5))
            pygame.draw.rect(surf, SKIN_2, (int(x + 1), int(y - 2 + bob), 2, 2))
            arm_up = math.sin(t * 6 + phase) > 0.2
            if arm_up:
                pygame.draw.rect(surf, col, (int(x - 1), int(y - 3 + bob), 1, 3))
                pygame.draw.rect(surf, col, (int(x + 4), int(y - 3 + bob), 1, 3))

        # FNF-style girl bystander, center background, dancing on a speaker stack
        gx, gy = INTERNAL_W // 2, GROUND_Y - 6
        bob = math.sin(t * 3.2) * 2
        sway = math.sin(t * 3.2) * 3
        pygame.draw.rect(surf, DARK_GRAY, (gx - 12, gy - 10, 24, 10))  # speaker stack
        pygame.draw.rect(surf, BLACK, (gx - 12, gy - 10, 24, 10), 1)
        pygame.draw.circle(surf, DARK_GRAY, (gx - 6, gy - 8), 2)
        pygame.draw.circle(surf, DARK_GRAY, (gx + 6, gy - 8), 2)
        body_y = gy - 10 + bob
        pygame.draw.rect(surf, (24, 22, 28), (int(gx - 5 + sway * 0.3), int(body_y - 16), 10, 16))  # black dress
        pygame.draw.rect(surf, SKIN_2, (int(gx - 3 + sway * 0.3), int(body_y - 21), 6, 6))  # head
        pygame.draw.rect(surf, HAIR_DARK, (int(gx - 4 + sway * 0.3), int(body_y - 23), 8, 4))
        pygame.draw.rect(surf, HAIR_DARK, (int(gx - 5 + sway * 0.3), int(body_y - 19), 2, 6))
        pygame.draw.rect(surf, HAIR_DARK, (int(gx + 3 + sway * 0.3), int(body_y - 19), 2, 6))
        pygame.draw.rect(surf, BLACK, (int(gx - 2 + sway * 0.3), int(body_y - 20), 1, 1))
        pygame.draw.rect(surf, BLACK, (int(gx + sway * 0.3), int(body_y - 20), 1, 1))

        # stage: ground + platforms
        pygame.draw.rect(surf, GROUND_COLOR, (0, GROUND_Y, INTERNAL_W, INTERNAL_H - GROUND_Y))
        pygame.draw.line(surf, GROUND_LINE, (0, GROUND_Y), (INTERNAL_W, GROUND_Y), 2)
        for x in range(0, INTERNAL_W, 16):
            pygame.draw.rect(surf, GROUND_LINE, (x, GROUND_Y + 3, 8, 2))
        for plat in PLATFORMS:
            pygame.draw.rect(surf, PLATFORM_COLOR, plat)
            pygame.draw.rect(surf, GROUND_LINE, plat, 1)


# ----------------------------------------------------------------------------
# GAME
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.running = True
        self.state = GameState.MENU
        self.mode = "pvp"
        self.p1_idx = 0
        self.p2_idx = 1
        self.f1 = None
        self.f2 = None
        self.particles = []
        self.shake = 0
        self.bg = Background()
        self.t = 0.0
        self.winner_msg = ""
        self.ko_flash_timer = 0
        self.sounds = {}
        self._make_sounds()

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

            self.sounds["hit"] = tone(180, 0.09)
            self.sounds["grab"] = tone(130, 0.13)
            self.sounds["shield"] = tone(700, 0.06, fade=False)
            self.sounds["special"] = tone(300, 0.35, sweep=True)
            self.sounds["ko"] = tone(500, 0.35, sweep=True)
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

    def start_match(self):
        c1 = CHARACTERS[self.p1_idx]
        c2 = CHARACTERS[self.p2_idx]
        self.f1 = Fighter(c1, True, False, stocks=3)
        self.f2 = Fighter(c2, False, self.mode == "ai", stocks=3)
        self.particles = []
        self.shake = 0
        self.state = GameState.FIGHTING

    def check_hits(self):
        for a, b in ((self.f1, self.f2), (self.f2, self.f1)):
            if a.atk_box and a.state in (FState.ATTACK, FState.SPECIAL):
                if a.atk_box.colliderect(b.rect):
                    d = 1 if a.facing_right else -1
                    dmg, blocked = b.take_hit(a.atk_dmg, d, a.atk_kb, 52 if a.state == FState.SPECIAL else 40)
                    if dmg:
                        self.spawn_particles(b.x, b.y - b.h / 2, YELLOW if blocked else RED, 10, 4)
                        self.shake = 7 if a.state == FState.SPECIAL else 3
                        self.play("shield" if blocked else ("special" if a.state == FState.SPECIAL else "hit"))
                    a.atk_box = None

    def check_stocks(self):
        for f, name in ((self.f1, "P1"), (self.f2, "P2")):
            if f.stocks <= 0 and self.state == GameState.FIGHTING:
                winner = self.f2.char.name if f is self.f1 else self.f1.char.name
                self.winner_msg = f"{winner} WINS THE MATCH!"
                self.state = GameState.GAME_OVER
                self.play("ko")

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
            if key == pygame.K_LEFT:
                self.p1_idx = (self.p1_idx - 1) % len(CHARACTERS)
            elif key == pygame.K_RIGHT:
                self.p1_idx = (self.p1_idx + 1) % len(CHARACTERS)
            elif key == pygame.K_f:
                self.p2_idx = (self.p2_idx - 1) % len(CHARACTERS)
            elif key == pygame.K_h:
                self.p2_idx = (self.p2_idx + 1) % len(CHARACTERS)
            elif key == pygame.K_RETURN:
                self.start_match()
            elif key == pygame.K_ESCAPE:
                self.state = GameState.MENU

        elif self.state == GameState.FIGHTING:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PAUSE
            elif key == pygame.K_z:
                self.f1.jump()
            elif key == pygame.K_x:
                self.f1.start_attack()
            elif key == pygame.K_a:
                self.f1.start_grab(self.f2)
            elif key == pygame.K_s:
                self.f1.start_special()
            elif self.mode == "pvp":
                if key == pygame.K_r:
                    self.f2.jump()
                elif key == pygame.K_y:
                    self.f2.start_attack()
                elif key == pygame.K_u:
                    self.f2.start_grab(self.f1)
                elif key == pygame.K_j:
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
                self.start_match()
            elif key == pygame.K_ESCAPE:
                self.running = False

    def handle_keyup(self, key):
        if self.state == GameState.FIGHTING:
            if key == pygame.K_DOWN:
                self.f1.shield(False)
            elif self.mode == "pvp" and key == pygame.K_g:
                self.f2.shield(False)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.KEYUP:
                self.handle_keyup(event.key)

    def update(self, dt):
        self.t += dt
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]
        if self.shake > 0:
            self.shake -= 1

        if self.state == GameState.FIGHTING:
            keys = pygame.key.get_pressed()
            if self.f1.state not in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
                if keys[pygame.K_LEFT]:
                    self.f1.move(-1)
                elif keys[pygame.K_RIGHT]:
                    self.f1.move(1)
                elif self.f1.state == FState.WALK:
                    self.f1.state = FState.IDLE
                if keys[pygame.K_DOWN]:
                    self.f1.shield(True)

            if self.mode == "pvp":
                if self.f2.state not in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
                    if keys[pygame.K_f]:
                        self.f2.move(-1)
                    elif keys[pygame.K_h]:
                        self.f2.move(1)
                    elif self.f2.state == FState.WALK:
                        self.f2.state = FState.IDLE
                    if keys[pygame.K_g]:
                        self.f2.shield(True)

            r1 = self.f1.update(self.f2)
            r2 = self.f2.update(self.f1)
            if r1 == "ko":
                self.spawn_particles(self.f1.x, self.f1.y - self.f1.h / 2, WHITE, 16, 6)
                self.shake = 10
            if r2 == "ko":
                self.spawn_particles(self.f2.x, self.f2.y - self.f2.h / 2, WHITE, 16, 6)
                self.shake = 10
            self.check_hits()
            self.check_stocks()

    # -- draw ------------------------------------------------------------------
    def draw_menu(self, surf):
        self.bg.draw(surf, self.t)
        draw_text(surf, "ESHAN SIMULATOR", FONT_BIG, YELLOW, INTERNAL_W // 2, 60, center=True)
        draw_text(surf, "A Pixel Platform Fighter", FONT_SMALL, WHITE, INTERNAL_W // 2, 78, center=True)
        draw_text(surf, "1: Player vs Player", FONT_MED, WHITE, INTERNAL_W // 2, 115, center=True)
        draw_text(surf, "2: Player vs AI", FONT_MED, WHITE, INTERNAL_W // 2, 132, center=True)
        draw_text(surf, "ESC: Quit", FONT_SMALL, LIGHT_GRAY, INTERNAL_W // 2, 155, center=True)
        draw_text(surf, "P1: Arrows move  Z jump  X atk  A grab  S special", FONT_SMALL, LIGHT_GRAY, INTERNAL_W // 2, 168, center=True)

    def draw_char_select(self, surf):
        self.bg.draw(surf, self.t)
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "CHARACTER SELECT", FONT_BIG, YELLOW, INTERNAL_W // 2, 16, center=True)
        box_w = 46
        start_x = INTERNAL_W // 2 - (len(CHARACTERS) * (box_w + 4)) // 2
        for i, c in enumerate(CHARACTERS):
            x = start_x + i * (box_w + 4)
            y = 40
            pygame.draw.rect(surf, c.shirt, (x, y, box_w, box_w))
            border = WHITE if i == self.p1_idx else (RED if i == self.p2_idx else DARK_GRAY)
            pygame.draw.rect(surf, border, (x, y, box_w, box_w), 2 if (i == self.p1_idx or i == self.p2_idx) else 1)
            draw_text(surf, c.name, FONT_SMALL, WHITE, x + box_w // 2, y + box_w + 8, center=True)
        c1 = CHARACTERS[self.p1_idx]
        c2 = CHARACTERS[self.p2_idx]
        draw_text(surf, f"P1: {c1.name} - {c1.desc}", FONT_SMALL, BLUE, INTERNAL_W // 2, 105, center=True)
        label = "AI" if self.mode == "ai" else "P2"
        draw_text(surf, f"{label}: {c2.name} - {c2.desc}", FONT_SMALL, RED, INTERNAL_W // 2, 118, center=True)
        draw_text(surf, "P1: Left/Right   P2: F/H", FONT_SMALL, LIGHT_GRAY, INTERNAL_W // 2, 140, center=True)
        draw_text(surf, "ENTER: Fight!   ESC: Back", FONT_SMALL, WHITE, INTERNAL_W // 2, 155, center=True)

    def draw_hud(self, surf):
        for i, f in enumerate((self.f1, self.f2)):
            x = 6 if i == 0 else INTERNAL_W - 66
            col = BLUE if i == 0 else RED
            draw_text(surf, f.char.name, FONT_SMALL, col, x, 4)
            pct_col = GREEN if f.percent < 60 else (YELLOW if f.percent < 120 else RED)
            draw_text(surf, f"{int(f.percent)}%", FONT_MED, pct_col, x, 12)
            stocks_txt = "\u25CF" * max(0, f.stocks)
            draw_text(surf, stocks_txt if stocks_txt else "-", FONT_SMALL, WHITE, x, 26)
            mpct = f.meter / 100
            bar_x = x if i == 0 else INTERNAL_W - 66
            pygame.draw.rect(surf, DARK_GRAY, (bar_x, 34, 60, 3))
            pygame.draw.rect(surf, (255, 215, 100), (bar_x, 34, int(60 * mpct), 3))

    def draw_fighting(self, surf):
        self.bg.draw(surf, self.t)
        self.f1.draw(surf)
        self.f2.draw(surf)
        for p in self.particles:
            p.draw(surf)
        self.draw_hud(surf)

    def draw_pause(self, surf):
        self.draw_fighting(surf)
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "PAUSED", FONT_BIG, WHITE, INTERNAL_W // 2, 70, center=True)
        draw_text(surf, "ESC: Resume", FONT_MED, LIGHT_GRAY, INTERNAL_W // 2, 100, center=True)
        draw_text(surf, "Q: Quit to Menu", FONT_MED, LIGHT_GRAY, INTERNAL_W // 2, 116, center=True)

    def draw_game_over(self, surf):
        self.bg.draw(surf, self.t)
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "GAME OVER", FONT_BIG, RED, INTERNAL_W // 2, 60, center=True)
        draw_text(surf, self.winner_msg, FONT_MED, YELLOW, INTERNAL_W // 2, 90, center=True)
        draw_text(surf, "ENTER: Menu   R: Rematch   ESC: Quit", FONT_SMALL, WHITE, INTERNAL_W // 2, 120, center=True)

    def draw(self):
        canvas.fill(BLACK)
        if self.state == GameState.MENU:
            self.draw_menu(canvas)
        elif self.state == GameState.CHAR_SELECT:
            self.draw_char_select(canvas)
        elif self.state == GameState.FIGHTING:
            self.draw_fighting(canvas)
        elif self.state == GameState.PAUSE:
            self.draw_pause(canvas)
        elif self.state == GameState.GAME_OVER:
            self.draw_game_over(canvas)

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
