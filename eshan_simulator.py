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
           Z = Jump (double jump in air!)   X = Attack   A = Grab   S = Special
Player 2 (PvP mode only):
           F/H = left/right, T/G = up/down (down = shield)
           R = Jump   Y = Attack   U = Grab   J = Special

Being grabbed? Mash your Attack/Grab/Special keys to break free early.
ESC = pause / back     ENTER = confirm     F3 = toggle hitbox debug overlay

Optional: drop a "characters.json" file next to this script to override
any character's stats without touching the code (see load_characters()).

Requirements: pip install pygame   (pip install numpy for sound effects)
Run with:     python eshan_simulator.py
"""

import random
import math
import os
import json
import io
import wave
import struct
from enum import Enum
from dataclasses import dataclass, field

import pygame

# ----------------------------------------------------------------------------
# PURE CONSTANTS (no pygame subsystems touched here - safe to import headless)
# ----------------------------------------------------------------------------
PIXEL_SCALE = 4
INTERNAL_W, INTERNAL_H = 320, 180
WINDOW_W, WINDOW_H = INTERNAL_W * PIXEL_SCALE, INTERNAL_H * PIXEL_SCALE
FPS = 60
FPS_BASE = 60.0  # all "per-frame" physics constants below were tuned at 60fps;
                  # every update multiplies its motion by dt * FPS_BASE so the
                  # game behaves the same even if the frame rate dips.

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
DEBUG_HITBOX = (255, 60, 60, 110)
DEBUG_HURTBOX = (60, 255, 100, 90)

FONT_NAMES = ["couriernew", "consolas", "dejavusansmono", "monospace"]

# ---- Control mapping dictionaries (fix: no more hardcoded keys scattered
#      through handle_keydown / update) ----
P1_KEYS = dict(left=pygame.K_LEFT, right=pygame.K_RIGHT, up=pygame.K_UP, down=pygame.K_DOWN,
               jump=pygame.K_z, attack=pygame.K_x, grab=pygame.K_a, special=pygame.K_s)
P2_KEYS = dict(left=pygame.K_f, right=pygame.K_h, up=pygame.K_t, down=pygame.K_g,
               jump=pygame.K_r, attack=pygame.K_y, grab=pygame.K_u, special=pygame.K_j)


def draw_text(surface, text, font, color, x, y, center=False, shadow=True, cache=None):
    """Renders text with a drop shadow. If a `cache` dict is passed, static
    strings (menu labels etc.) are rendered once and reused instead of calling
    font.render() every single frame."""
    key = (text, id(font), color, shadow) if cache is not None else None
    if cache is not None and key in cache:
        shadow_surf, surf = cache[key]
    else:
        shadow_surf = font.render(text, False, BLACK) if shadow else None
        surf = font.render(text, False, color)
        if cache is not None:
            cache[key] = (shadow_surf, surf)
    rect = surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    if shadow_surf is not None:
        srect = shadow_surf.get_rect()
        srect.center = (rect.centerx + 1, rect.centery + 1) if center else (rect.x + 1, rect.y + 1)
        surface.blit(shadow_surf, srect)
    surface.blit(surf, rect)
    return rect


# ----------------------------------------------------------------------------
# STAGE (fix: stage geometry is now a proper object instead of loose globals,
# so adding a second stage later just means constructing another Stage())
# ----------------------------------------------------------------------------
@dataclass
class Stage:
    ground_y: int
    platforms: list
    blast_left: int
    blast_right: int
    blast_top: int
    blast_bottom: int
    spawn_points: list


def make_default_stage() -> Stage:
    ground_y = INTERNAL_H - 40
    return Stage(
        ground_y=ground_y,
        platforms=[
            pygame.Rect(46, 104, 62, 5),
            pygame.Rect(INTERNAL_W - 108, 104, 62, 5),
        ],
        blast_left=-28, blast_right=INTERNAL_W + 28,
        blast_top=-70, blast_bottom=INTERNAL_H + 60,
        spawn_points=[(70, ground_y - 60), (INTERNAL_W - 70, ground_y - 60)],
    )


class GameState(Enum):
    MENU = 0
    CHAR_SELECT = 1
    FIGHTING = 2
    PAUSE = 3
    GAME_OVER = 4


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


class HitEvent(Enum):
    """fix: Fighter.update() used to return the bare string 'ko'; now an Enum."""
    NONE = 0
    KO = 1


# Attack timing windows: (startup, active, recovery) in frames at 60fps.
# The hitbox only exists during the "active" window, not the whole animation.
JAB_FRAMES = (3, 4, 3)        # total 10
GRAB_FRAMES = (4, 3, 7)       # total 14
SPECIAL_FRAMES = (10, 8, 12)  # total 30


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


DEFAULT_CHARACTERS = [
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


def load_characters(path="characters.json"):
    """fix: character stats are tunable without touching code. If a
    characters.json sits next to the script, its entries override the
    matching (by name) built-in stats; anything not overridden keeps the
    default. If the file is missing or malformed, defaults are used as-is."""
    chars = [CharacterStats(**c.__dict__) for c in DEFAULT_CHARACTERS]
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                overrides = json.load(f)
            by_name = {c.name: c for c in chars}
            for entry in overrides:
                name = entry.get("name")
                if name in by_name:
                    for k, v in entry.items():
                        if k in ("shirt", "skin") and isinstance(v, list):
                            v = tuple(v)
                        setattr(by_name[name], k, v)
        except Exception as e:
            print(f"[characters.json] ignored due to error: {e}")
    return chars


CHARACTERS_BY_ID = None  # populated in Game.__init__ (needs no pygame state, but
                          # keeping construction inside Game keeps side effects local)


@dataclass(slots=True)
class Particle:
    x: float
    y: float
    color: tuple
    vx: float
    vy: float
    life: int
    max_life: int
    size: int

    def update(self, dt):
        self.x += self.vx * dt * FPS_BASE
        self.y += self.vy * dt * FPS_BASE
        self.vy += 0.22 * dt * FPS_BASE
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
    MAX_JUMPS = 2  # fix: ground jump + one air jump (double jump for recovery)

    def __init__(self, char, p1, stage, ai=False, stocks=3):
        self.char = char
        self.p1 = p1
        self.ai = ai
        self.stage = stage
        idx = 0 if p1 else 1
        self.x, self.y = stage.spawn_points[idx]
        self.w, self.h = char.width, char.height
        self.facing_right = p1

        self.vx, self.vy = 0.0, 0.0
        self.on_ground = True
        self.on_platform = None
        self.jumps_left = self.MAX_JUMPS

        self.percent = 0.0
        self.stocks = stocks
        self.invuln = 60

        self.state = FState.IDLE
        self.state_t = 0
        self.atk_total = 0
        self.atk_frames = (0, 0, 0)
        self.atk_connected = False
        self.atk_cd = 0
        self.grab_cd = 0
        self.special_cd = 0
        self.meter = 0.0
        self.flash = 0
        self.shield_hp = 100.0

        self.atk_box = None
        self.atk_dmg = 0
        self.atk_kb = 0
        self.atk_angle = 45
        self.grab_target = None

        # reusable alpha surface for the shield bubble (fix: avoid allocating
        # a brand new Surface every single frame the shield is held)
        max_r = 26
        self._shield_surf = pygame.Surface((max_r * 2, max_r * 2), pygame.SRCALPHA)

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h), self.w, self.h)

    def respawn(self):
        idx = 0 if self.p1 else 1
        self.x, self.y = self.stage.spawn_points[idx]
        self.vx, self.vy = 0, 0
        self.percent = 0
        self.invuln = 90
        self.jumps_left = self.MAX_JUMPS
        self.state = FState.FALL
        self.on_ground = False

    def apply_knockback(self, dmg, dir_sign, kb_base, launch_angle_deg=52, di=0):
        # Smash-ish knockback: grows with current percent (already includes
        # this hit's damage), reduced by weight. Low percent = light tap,
        # high percent = a real launch that can send someone off the stage.
        growth = self.percent * 0.035
        kb = (kb_base + growth) / self.char.weight
        kb = max(1.4, kb)
        # Directional Influence: holding away from the hit nudges the angle
        # a little more vertical/survivable; holding toward it flattens the
        # trajectory a little. Kept subtle so tuned kill percents still hold.
        angle = launch_angle_deg + max(-6, min(6, di * -dir_sign * 6))
        angle = math.radians(angle)
        self.vx = math.cos(angle) * kb * dir_sign
        self.vy = -math.sin(angle) * kb
        hitstun = min(70, int(kb * 1.6) + 6)
        self.state = FState.HIT
        self.state_t = hitstun
        self.on_ground = False
        self.atk_box = None  # fix: getting hit cancels your own pending attack box

    def take_hit(self, dmg, dir_sign, kb_base, angle=52, di=0):
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
                self.apply_knockback(dmg * 0.3, dir_sign, 2, angle, di)
            return blocked, True
        self.percent += dmg
        self.flash = 8
        self.meter = min(100, self.meter + dmg * 0.7)
        self.apply_knockback(dmg, dir_sign, kb_base, angle, di)
        return dmg, False

    def _begin_action(self, state, frames, kind):
        self.state = state
        self.atk_frames = frames
        self.atk_total = sum(frames)
        self.state_t = self.atk_total
        self.atk_connected = False
        self.vx = 0
        # any deliberate action cancels spawn invulnerability (fix: you
        # shouldn't get to attack for free while still flashing invincible)
        self.invuln = 0

    def start_attack(self):
        if self.atk_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        self._begin_action(FState.ATTACK, JAB_FRAMES, "punch")
        self.atk_cd = 16
        self.atk_dmg = self.char.punch_dmg
        self.atk_kb = 2
        self.atk_angle = 40

    def start_special(self):
        if self.meter < 100 or self.special_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        self.meter = 0
        self._begin_action(FState.SPECIAL, SPECIAL_FRAMES, "special")
        self.special_cd = 100
        self.atk_dmg = self.char.special_dmg
        self.atk_kb = 5
        self.atk_angle = 52

    def start_grab(self, opp):
        if self.grab_cd > 0 or self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        self._begin_action(FState.GRAB, GRAB_FRAMES, "grab")
        self.grab_cd = 40

    def _make_attack_box(self, kind):
        d = 1 if self.facing_right else -1
        if kind == "punch":
            reach, bw, bh = 16, 14, 12
            bx = self.rect.right + (reach / 2 if d > 0 else -reach / 2) if d > 0 else self.rect.left - reach / 2
            bx = (self.rect.right + reach / 2) if d > 0 else (self.rect.left - reach / 2)
            by = self.y - self.h / 2
            return pygame.Rect(int(bx - bw / 2), int(by - bh / 2), bw, bh)
        elif kind == "grab":
            reach = 20
            gx = (self.rect.right + reach / 2) if d > 0 else (self.rect.left - reach / 2)
            return pygame.Rect(int(gx - 10), int(self.y - self.h + 6), 20, self.h - 10)
        else:  # special
            bx = self.x + d * 24
            by = self.y - self.h / 2
            return pygame.Rect(int(bx - 24), int(by - 24), 48, 48)

    def resolve_grab_throw(self, opp, di=0):
        d = 1 if self.facing_right else -1
        opp.percent += self.char.grab_dmg
        self.meter = min(100, self.meter + self.char.grab_dmg * 0.7)
        opp.apply_knockback(self.char.grab_dmg, d, 3, 40, di)
        self.grab_target = None

    def move(self, direction):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        self.vx = direction * self.char.speed
        if direction != 0:
            self.facing_right = direction > 0
        if self.on_ground:
            self.state = FState.WALK

    def jump(self):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        if self.jumps_left > 0:
            self.vy = -self.char.jump_power
            self.on_ground = False
            self.on_platform = None
            self.jumps_left -= 1
            self.state = FState.JUMP

    def shield(self, on):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        if on and self.on_ground and self.shield_hp > 0:
            self.state = FState.SHIELD
            self.vx = 0
        elif not on and self.state == FState.SHIELD:
            self.state = FState.IDLE

    def mash_out_of_grab(self):
        """fix: grabbed players can button-mash to shorten the grab and
        break free before the throw resolves."""
        if self.state == FState.GRABBED:
            self.state_t = max(0, self.state_t - 3)

    def ai_update(self, opp):
        if self.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
            return
        dist = abs(self.x - opp.x)

        # fix: recover back toward the stage instead of walking into the blast
        # zone when knocked off / standing near an edge.
        if self.x < 34:
            if not self.on_ground and self.jumps_left > 0:
                self.jump()
            self.move(1)
            return
        elif self.x > INTERNAL_W - 34:
            if not self.on_ground and self.jumps_left > 0:
                self.jump()
            self.move(-1)
            return

        # fix: only shield if there's enough shield health to survive it,
        # instead of shielding blindly and popping the shield instantly.
        if opp.state == FState.ATTACK and dist < 30 and self.shield_hp > 35 and random.random() < 0.4:
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

    def update(self, dt, opp):
        scale = dt * FPS_BASE
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

        # fix: shield now actually decays while held, and only regenerates
        # while NOT shielding - infinite turtle-shielding is no longer possible.
        if self.state == FState.SHIELD:
            self.shield_hp -= 0.5 * scale
            if self.shield_hp <= 0:
                self.shield_hp = 0
                self.state = FState.HIT
                self.state_t = 40
        else:
            self.shield_hp = min(100.0, self.shield_hp + 0.15 * scale)

        if self.state in (FState.ATTACK, FState.SPECIAL, FState.GRAB):
            self.state_t -= 1
            elapsed = self.atk_total - self.state_t
            startup, active, recovery = self.atk_frames
            kind = "punch" if self.state == FState.ATTACK else ("special" if self.state == FState.SPECIAL else "grab")
            if startup <= elapsed < startup + active:
                if self.atk_box is None:
                    self.atk_box = self._make_attack_box(kind)
                    self.atk_dmg = self.atk_dmg  # unchanged, just marks box as live
            else:
                self.atk_box = None
            if self.state == FState.GRAB and startup <= elapsed < startup + active and not self.atk_connected:
                grab_box = self._make_attack_box("grab")
                if grab_box.colliderect(opp.rect) and opp.invuln <= 0 and opp.state != FState.GRABBED:
                    self.grab_target = opp
                    opp.state = FState.GRABBED
                    opp.state_t = 24
                    opp.vx = opp.vy = 0
                    self.atk_connected = True
            if self.state_t <= 0:
                if self.state == FState.GRAB:
                    if self.grab_target is opp and opp.state == FState.GRABBED:
                        self.resolve_grab_throw(opp)
                    self.grab_target = None
                self.state = FState.IDLE
                self.atk_box = None
        elif self.state == FState.GRABBED:
            self.state_t -= 1
            if self.state_t <= 0:
                self.state = FState.IDLE
                if opp.grab_target is self:
                    opp.grab_target = None
        elif self.state == FState.HIT:
            self.state_t -= 1
            if self.state_t <= 0 and self.on_ground:
                self.state = FState.IDLE

        # physics (dt-scaled so a dropped frame doesn't change game feel)
        self.vy += 0.30 * scale
        # fix: air drag so knocked-back / jumping fighters don't drift forever
        if not self.on_ground:
            self.vx *= (0.985 ** max(scale, 0.0001))
        else:
            self.vx *= (0.82 ** max(scale, 0.0001))
            if abs(self.vx) < 0.3:
                self.vx = 0

        # fix: substep the position update against high knockback velocities
        # so a hard hit can't tunnel straight through the ground/platforms.
        steps = max(1, min(6, int(math.ceil((abs(self.vy) * scale) / 6))))
        step_vx = self.vx * scale / steps
        step_vy = self.vy * scale / steps
        landed_this_frame = False
        for _ in range(steps):
            prev_y = self.y
            self.x += step_vx
            self.y += step_vy

            self.on_ground = False
            self.on_platform = None
            if self.vy >= 0:
                for plat in self.stage.platforms:
                    if (plat.left - self.w / 2 < self.x < plat.right + self.w / 2
                            and prev_y <= plat.top < self.y):
                        self.y = plat.top
                        self.vy = 0
                        self.on_ground = True
                        self.on_platform = plat
                        landed_this_frame = True
                        break
            if not landed_this_frame and self.y >= self.stage.ground_y:
                self.y = self.stage.ground_y
                self.vy = 0
                self.on_ground = True
                landed_this_frame = True
            if landed_this_frame:
                break

        if self.on_ground:
            self.jumps_left = self.MAX_JUMPS
            if self.state in (FState.JUMP, FState.FALL):
                self.state = FState.IDLE
        elif self.state in (FState.IDLE, FState.WALK, FState.JUMP):
            self.state = FState.FALL if self.vy > 1 else self.state

        # fix: no hard position clamp here - fighters must be free to travel
        # past the visible stage and into the blast zone below, or KOs can
        # never happen. (An earlier version of this clamp accidentally capped
        # position tighter than the blast zone, silently disabling all KOs.)

        # fix: facing is locked during HIT/GRABBED (already correct) - keep it that way
        if self.state not in (FState.HIT, FState.GRABBED):
            self.facing_right = opp.x > self.x

        if self.ai:
            self.ai_update(opp)

        # blast zones -> lose a stock
        if (self.x < self.stage.blast_left or self.x > self.stage.blast_right
                or self.y > self.stage.blast_bottom or self.y < self.stage.blast_top):
            self.stocks -= 1
            if self.stocks > 0:
                self.respawn()
            return HitEvent.KO
        return HitEvent.NONE

    def draw(self, surf, t, debug=False):
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

        if self.state == FState.SHIELD:
            radius = int(10 + self.shield_hp / 10)
            self._shield_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(self._shield_surf, (80, 200, 255, 90), (26, 26), radius)
            surf.blit(self._shield_surf, (int(self.x - 26), int(self.y - self.h / 2 - 26)))

        pygame.draw.rect(surf, HAIR_DARK, (int(self.x - leg_w - 1), int(self.y - leg_h), leg_w, leg_h))
        pygame.draw.rect(surf, HAIR_DARK, (int(self.x + 1), int(self.y - leg_h), leg_w, leg_h))

        torso_w = self.w + belly
        torso_rect = pygame.Rect(int(self.x - torso_w / 2), int(self.y - self.h), torso_w, self.h - leg_h)
        pygame.draw.rect(surf, body_color, torso_rect)
        pygame.draw.rect(surf, BLACK, torso_rect, 1)
        if build == "fat":
            pygame.draw.ellipse(surf, body_color, (torso_rect.x - 2, torso_rect.bottom - 14, torso_rect.w + 4, 16))
            pygame.draw.ellipse(surf, BLACK, (torso_rect.x - 2, torso_rect.bottom - 14, torso_rect.w + 4, 16), 1)

        head_r = 7 if build != "short" else 6
        hx = self.x + d * 2
        hy = torso_rect.top - head_r + 2
        pygame.draw.rect(surf, skin, (int(hx - head_r), int(hy - head_r), head_r * 2, head_r * 2))
        pygame.draw.rect(surf, HAIR_DARK, (int(hx - head_r - 1), int(hy - head_r - 3), head_r * 2 + 2, 4))
        if build == "fat":
            for i in range(-2, 3):
                pygame.draw.rect(surf, HAIR_DARK, (int(hx + i * 3 - 1), int(hy - head_r - 4), 3, 3))
        if self.char.glasses:
            gy = int(hy - 1)
            pygame.draw.rect(surf, BLACK, (int(hx - head_r + 1), gy, head_r, 3), 1)
        eye_x = hx + d * 3
        pygame.draw.rect(surf, BLACK, (int(eye_x), int(hy - 1), 2, 2))

        if self.state == FState.ATTACK:
            pygame.draw.rect(surf, skin, (int(self.x), int(self.y - self.h + 8), int(d * 16), 5))
        elif self.state == FState.GRAB:
            pygame.draw.rect(surf, skin, (int(self.x), int(self.y - self.h + 10), int(d * 20), 4))
        elif self.state == FState.GRABBED:
            pygame.draw.rect(surf, skin, (int(self.x - 6), int(self.y - self.h + 10), 12, 4))
        elif self.state == FState.SPECIAL:
            pygame.draw.rect(surf, skin, (int(self.x - 10), int(self.y - self.h + 4), 20, 5))
        elif self.state == FState.SHIELD:
            pygame.draw.rect(surf, skin, (int(self.x - 8), int(self.y - self.h + 8), 16, 5))
        else:
            sway = int(math.sin(t * 8 + (0 if self.p1 else 2)) * 2)
            pygame.draw.rect(surf, skin, (int(self.x - torso_w / 2 - 4), int(self.y - self.h + 8 + sway), 5, 8))
            pygame.draw.rect(surf, skin, (int(self.x + torso_w / 2 - 1), int(self.y - self.h + 8 - sway), 5, 8))

        if debug:
            r = self.rect
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            s.fill(DEBUG_HURTBOX)
            surf.blit(s, r.topleft)
            pygame.draw.rect(surf, (60, 255, 100), r, 1)
            if self.atk_box:
                s2 = pygame.Surface((self.atk_box.w, self.atk_box.h), pygame.SRCALPHA)
                s2.fill(DEBUG_HITBOX)
                surf.blit(s2, self.atk_box.topleft)
                pygame.draw.rect(surf, (255, 60, 60), self.atk_box, 1)


# ----------------------------------------------------------------------------
# BACKGROUND: college courtyard + cheering crowd + FNF-style bystander girl
# ----------------------------------------------------------------------------
class Background:
    def __init__(self, stage):
        self.stage = stage
        self.crowd = []
        rng = random.Random(7)  # fix: local RNG instead of mutating global random state
        colors = [RED, BLUE, GREEN, YELLOW, ORANGE, PURPLE, PINK, WHITE]
        for row in range(3):
            y = 44 + row * 10
            for i in range(26):
                x = 4 + i * 12 + (row % 2) * 5
                self.crowd.append([x, y, rng.choice(colors), rng.uniform(0, math.tau)])

        # fix: pre-render the sky gradient once instead of a per-frame
        # line-by-line loop; only the crowd/dancer animate each frame.
        self.sky = pygame.Surface((INTERNAL_W, INTERNAL_H))
        for y in range(INTERNAL_H):
            f = y / INTERNAL_H
            c = (
                int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * f),
                int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * f),
                int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * f),
            )
            pygame.draw.line(self.sky, c, (0, y), (INTERNAL_W, y))
        pygame.draw.rect(self.sky, BUILD_STONE, (0, 20, INTERNAL_W, 40))
        pygame.draw.polygon(self.sky, BUILD_STONE_DK,
                             [(INTERNAL_W // 2 - 46, 20), (INTERNAL_W // 2, 2), (INTERNAL_W // 2 + 46, 20)])
        for cx in range(6, INTERNAL_W - 5, 14):
            pygame.draw.rect(self.sky, BUILD_STONE_DK, (cx, 24, 5, 34))
        pygame.draw.rect(self.sky, BANNER_RED, (INTERNAL_W // 2 - 44, 8, 88, 10))

    def draw(self, surf, t, font_small):
        surf.blit(self.sky, (0, 0))
        draw_text(surf, "STATE UNIVERSITY", font_small, YELLOW, INTERNAL_W // 2, 13, center=True, shadow=False)

        for c in self.crowd:
            x, y, col, phase = c
            bob = math.sin(t * 4 + phase) * 2
            pygame.draw.rect(surf, col, (int(x), int(y + bob), 4, 5))
            pygame.draw.rect(surf, SKIN_2, (int(x + 1), int(y - 2 + bob), 2, 2))
            if math.sin(t * 6 + phase) > 0.2:
                pygame.draw.rect(surf, col, (int(x - 1), int(y - 3 + bob), 1, 3))
                pygame.draw.rect(surf, col, (int(x + 4), int(y - 3 + bob), 1, 3))

        gx, gy = INTERNAL_W // 2, self.stage.ground_y - 6
        bob = math.sin(t * 3.2) * 2
        sway = math.sin(t * 3.2) * 3
        pygame.draw.rect(surf, DARK_GRAY, (gx - 12, gy - 10, 24, 10))
        pygame.draw.rect(surf, BLACK, (gx - 12, gy - 10, 24, 10), 1)
        pygame.draw.circle(surf, DARK_GRAY, (gx - 6, gy - 8), 2)
        pygame.draw.circle(surf, DARK_GRAY, (gx + 6, gy - 8), 2)
        body_y = gy - 10 + bob
        pygame.draw.rect(surf, (24, 22, 28), (int(gx - 5 + sway * 0.3), int(body_y - 16), 10, 16))
        pygame.draw.rect(surf, SKIN_2, (int(gx - 3 + sway * 0.3), int(body_y - 21), 6, 6))
        pygame.draw.rect(surf, HAIR_DARK, (int(gx - 4 + sway * 0.3), int(body_y - 23), 8, 4))
        pygame.draw.rect(surf, HAIR_DARK, (int(gx - 5 + sway * 0.3), int(body_y - 19), 2, 6))
        pygame.draw.rect(surf, HAIR_DARK, (int(gx + 3 + sway * 0.3), int(body_y - 19), 2, 6))
        pygame.draw.rect(surf, BLACK, (int(gx - 2 + sway * 0.3), int(body_y - 20), 1, 1))
        pygame.draw.rect(surf, BLACK, (int(gx + sway * 0.3), int(body_y - 20), 1, 1))

        pygame.draw.rect(surf, GROUND_COLOR, (0, self.stage.ground_y, INTERNAL_W, INTERNAL_H - self.stage.ground_y))
        pygame.draw.line(surf, GROUND_LINE, (0, self.stage.ground_y), (INTERNAL_W, self.stage.ground_y), 2)
        for x in range(0, INTERNAL_W, 16):
            pygame.draw.rect(surf, GROUND_LINE, (x, self.stage.ground_y + 3, 8, 2))
        for plat in self.stage.platforms:
            pygame.draw.rect(surf, PLATFORM_COLOR, plat)
            pygame.draw.rect(surf, GROUND_LINE, plat, 1)


# ----------------------------------------------------------------------------
# Simple WAV tone synthesis with an ADSR envelope (fix: avoids the clicky /
# clipped edges a bare linear fade produces) - stdlib `wave` + `struct`, no
# numpy dependency required for sound anymore.
# ----------------------------------------------------------------------------
def synth_tone(freq, duration, sample_rate=22050, sweep_to=None, volume=0.6):
    n = int(sample_rate * duration)
    attack = max(1, int(n * 0.08))
    release = max(1, int(n * 0.35))
    samples = bytearray()
    for i in range(n):
        f = freq if sweep_to is None else freq + (sweep_to - freq) * (i / n)
        t = i / sample_rate
        val = math.sin(2 * math.pi * f * t)
        # ADSR-ish envelope: quick attack, sustain, gentle release
        if i < attack:
            env = i / attack
        elif i > n - release:
            env = max(0.0, (n - i) / release)
        else:
            env = 1.0
        sample = int(max(-1.0, min(1.0, val * env * volume)) * 32000)
        samples += struct.pack("<h", sample)  # mono; duplicated to stereo below
    stereo = bytearray()
    for i in range(0, len(samples), 2):
        stereo += samples[i:i + 2] * 2
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(stereo))
    buf.seek(0)
    return buf


def make_chiptune_loop(sample_rate=22050):
    """A tiny looping chiptune-ish arpeggio for stage ambience."""
    notes = [220, 262, 294, 330, 294, 262]
    beat = 0.16
    samples = bytearray()
    for note in notes:
        n = int(sample_rate * beat)
        for i in range(n):
            t = i / sample_rate
            val = math.sin(2 * math.pi * note * t) * 0.5 + math.sin(2 * math.pi * note * 2 * t) * 0.15
            env = min(1.0, i / (n * 0.1)) * min(1.0, (n - i) / (n * 0.3))
            sample = int(max(-1.0, min(1.0, val * env * 0.35)) * 32000)
            samples += struct.pack("<h", sample)
    stereo = bytearray()
    for i in range(0, len(samples), 2):
        stereo += samples[i:i + 2] * 2
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(stereo))
    buf.seek(0)
    return buf


# ----------------------------------------------------------------------------
# GAME
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        # fix: all pygame subsystem init lives here (inside a class you
        # actually instantiate) instead of running at module import time.
        pygame.init()
        pygame.mixer.init(frequency=22050, size=-16, channels=2)  # fix: explicit format
        pygame.display.set_caption("Eshan Simulator")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.canvas = pygame.Surface((INTERNAL_W, INTERNAL_H))
        self.clock = pygame.time.Clock()

        self.font_big = pygame.font.SysFont(FONT_NAMES, 20, bold=True)
        self.font_med = pygame.font.SysFont(FONT_NAMES, 12, bold=True)
        self.font_small = pygame.font.SysFont(FONT_NAMES, 8, bold=True)
        self.text_cache = {}

        self.running = True
        self.state = GameState.MENU
        self.mode = "pvp"
        self.p1_keys = P1_KEYS
        self.p2_keys = P2_KEYS
        self.characters = load_characters()
        self.p1_idx = 0
        self.p2_idx = 1
        self.stage = make_default_stage()
        self.f1 = None
        self.f2 = None
        self.particles = []
        self.shake = 0
        self.bg = Background(self.stage)
        self.t = 0.0
        self.winner_msg = ""
        self.debug = False

        self.sound_channels = [pygame.mixer.Channel(i) for i in range(6)]  # fix: dedicated channel pool
        self._next_channel = 0
        self.sounds = {}
        self.music_ok = False
        self._make_sounds()
        self._make_music()

    # -- sound ---------------------------------------------------------------
    def _make_sounds(self):
        try:
            self.sounds["hit"] = pygame.mixer.Sound(synth_tone(180, 0.09))
            self.sounds["grab"] = pygame.mixer.Sound(synth_tone(130, 0.13))
            self.sounds["shield"] = pygame.mixer.Sound(synth_tone(700, 0.06, volume=0.4))
            self.sounds["special"] = pygame.mixer.Sound(synth_tone(300, 0.35, sweep_to=600))
            self.sounds["ko"] = pygame.mixer.Sound(synth_tone(500, 0.35, sweep_to=1000))
        except Exception as e:
            # fix: warn instead of silently muting all feedback
            print(f"[audio] sound effects disabled ({e})")
            self.sounds = {}

    def _make_music(self):
        try:
            pygame.mixer.music.load(make_chiptune_loop())
            pygame.mixer.music.set_volume(0.25)
            pygame.mixer.music.play(loops=-1)
            self.music_ok = True
        except Exception as e:
            print(f"[audio] background music disabled ({e})")
            self.music_ok = False

    def play(self, name):
        s = self.sounds.get(name)
        if not s:
            return
        try:
            ch = self.sound_channels[self._next_channel]
            self._next_channel = (self._next_channel + 1) % len(self.sound_channels)
            ch.play(s)
        except Exception:
            pass

    def spawn_particles(self, x, y, color, count=8, speed=3):
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            vel = (math.cos(ang) * random.uniform(1, speed), math.sin(ang) * random.uniform(1, speed) - 1.5)
            self.particles.append(Particle(x, y, color, vel[0], vel[1], random.randint(10, 20), random.randint(10, 20), random.randint(2, 4)))

    def start_match(self):
        c1 = self.characters[self.p1_idx]
        c2 = self.characters[self.p2_idx]
        self.f1 = Fighter(c1, True, self.stage, False, stocks=3)
        self.f2 = Fighter(c2, False, self.stage, self.mode == "ai", stocks=3)
        self.particles = []
        self.shake = 0
        self.change_state(GameState.FIGHTING)

    def change_state(self, new_state):
        """fix: centralize state transitions so we can flush any stale
        buffered key events (e.g. the ENTER that started the match leaking
        into the fight) instead of them firing a frame late."""
        self.state = new_state
        pygame.event.clear()

    def check_hits(self):
        for a, b in ((self.f1, self.f2), (self.f2, self.f1)):
            if a.atk_box and a.state in (FState.ATTACK, FState.SPECIAL):
                if a.atk_box.colliderect(b.rect) and not a.atk_connected:
                    d = 1 if a.facing_right else -1
                    di = self._defender_di(b)
                    dmg, blocked = b.take_hit(a.atk_dmg, d, a.atk_kb, a.atk_angle, di)
                    a.atk_connected = True
                    if dmg:
                        self.spawn_particles(b.x, b.y - b.h / 2, YELLOW if blocked else RED, 10, 4)
                        self.shake = 7 if a.state == FState.SPECIAL else 3
                        self.play("shield" if blocked else ("special" if a.state == FState.SPECIAL else "hit"))
                    a.atk_box = None

    def _defender_di(self, fighter):
        """fix: Directional Influence - reads whichever movement key the
        about-to-be-hit player is holding to nudge their launch trajectory."""
        keys = pygame.key.get_pressed()
        keymap = self.p1_keys if fighter is self.f1 else self.p2_keys
        if keys[keymap["left"]]:
            return -1
        if keys[keymap["right"]]:
            return 1
        return 0

    def check_stocks(self):
        for f in (self.f1, self.f2):
            if f.stocks <= 0 and self.state == GameState.FIGHTING:
                winner = self.f2.char.name if f is self.f1 else self.f1.char.name
                self.winner_msg = f"{winner} WINS THE MATCH!"
                self.change_state(GameState.GAME_OVER)
                self.play("ko")

    # -- input -----------------------------------------------------------------
    def _action_for_key(self, key, keymap):
        for action, k in keymap.items():
            if k == key:
                return action
        return None

    def handle_keydown(self, key):
        if self.state == GameState.MENU:
            if key == pygame.K_1:
                self.mode = "pvp"
                self.change_state(GameState.CHAR_SELECT)
            elif key == pygame.K_2:
                self.mode = "ai"
                self.change_state(GameState.CHAR_SELECT)
            elif key == pygame.K_ESCAPE:
                self.running = False

        elif self.state == GameState.CHAR_SELECT:
            if key == pygame.K_LEFT:
                self.p1_idx = (self.p1_idx - 1) % len(self.characters)
            elif key == pygame.K_RIGHT:
                self.p1_idx = (self.p1_idx + 1) % len(self.characters)
            elif key == pygame.K_f:
                self.p2_idx = (self.p2_idx - 1) % len(self.characters)
            elif key == pygame.K_h:
                self.p2_idx = (self.p2_idx + 1) % len(self.characters)
            elif key == pygame.K_RETURN:
                self.start_match()
            elif key == pygame.K_ESCAPE:
                self.change_state(GameState.MENU)

        elif self.state == GameState.FIGHTING:
            if key == pygame.K_ESCAPE:
                self.change_state(GameState.PAUSE)
                return
            if key == pygame.K_F3:
                self.debug = not self.debug
                return
            for keymap, fighter, opp in self._players():
                action = self._action_for_key(key, keymap)
                if action is None:
                    continue
                if fighter.state == FState.GRABBED:
                    fighter.mash_out_of_grab()
                    continue
                if action == "jump":
                    fighter.jump()
                elif action == "attack":
                    fighter.start_attack()
                elif action == "grab":
                    fighter.start_grab(opp)
                elif action == "special":
                    fighter.start_special()

        elif self.state == GameState.PAUSE:
            if key == pygame.K_ESCAPE:
                self.change_state(GameState.FIGHTING)
            elif key == pygame.K_q:
                self.change_state(GameState.MENU)

        elif self.state == GameState.GAME_OVER:
            if key == pygame.K_RETURN:
                self.change_state(GameState.MENU)
            elif key == pygame.K_r:
                self.start_match()
            elif key == pygame.K_ESCAPE:
                self.running = False

    def _players(self):
        """Yields (keymap, fighter, opponent) for each active human player."""
        yield self.p1_keys, self.f1, self.f2
        if self.mode == "pvp":
            yield self.p2_keys, self.f2, self.f1

    def handle_keyup(self, key):
        if self.state == GameState.FIGHTING:
            for keymap, fighter, _opp in self._players():
                if key == keymap["down"]:
                    fighter.shield(False)

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
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        if self.shake > 0:
            self.shake -= 1

        if self.state == GameState.FIGHTING:
            keys = pygame.key.get_pressed()
            for keymap, fighter, _opp in self._players():
                if fighter.state in (FState.HIT, FState.ATTACK, FState.SPECIAL, FState.GRAB, FState.GRABBED):
                    continue
                if keys[keymap["left"]]:
                    fighter.move(-1)
                elif keys[keymap["right"]]:
                    fighter.move(1)
                elif fighter.state == FState.WALK:
                    fighter.state = FState.IDLE
                if keys[keymap["down"]]:
                    fighter.shield(True)

            # fix: AI decision-making now driven from Game.update rather than
            # buried inside Fighter.update, loosening the Fighter/opponent coupling.
            if self.f1.ai:
                self.f1.ai_update(self.f2)
            if self.f2.ai:
                self.f2.ai_update(self.f1)

            r1 = self.f1.update(dt, self.f2)
            r2 = self.f2.update(dt, self.f1)
            if r1 == HitEvent.KO:
                self.spawn_particles(self.f1.x, self.f1.y - self.f1.h / 2, WHITE, 16, 6)
                self.shake = 10
            if r2 == HitEvent.KO:
                self.spawn_particles(self.f2.x, self.f2.y - self.f2.h / 2, WHITE, 16, 6)
                self.shake = 10

            # continuous special-move sparkle, driven by the particle system
            # instead of Fighter.draw() spawning random particles as a side effect
            for f in (self.f1, self.f2):
                if f.state == FState.SPECIAL and random.random() < 0.6:
                    self.spawn_particles(f.x + random.randint(-14, 14),
                                         f.y - f.h / 2 + random.randint(-14, 14), YELLOW, 1, 1)

            self.check_hits()
            self.check_stocks()

    # -- draw ------------------------------------------------------------------
    def draw_menu(self, surf):
        self.bg.draw(surf, self.t, self.font_small)
        draw_text(surf, "ESHAN SIMULATOR", self.font_big, YELLOW, INTERNAL_W // 2, 60, center=True, cache=self.text_cache)
        draw_text(surf, "A Pixel Platform Fighter", self.font_small, WHITE, INTERNAL_W // 2, 78, center=True, cache=self.text_cache)
        draw_text(surf, "1: Player vs Player", self.font_med, WHITE, INTERNAL_W // 2, 115, center=True, cache=self.text_cache)
        draw_text(surf, "2: Player vs AI", self.font_med, WHITE, INTERNAL_W // 2, 132, center=True, cache=self.text_cache)
        draw_text(surf, "ESC: Quit", self.font_small, LIGHT_GRAY, INTERNAL_W // 2, 155, center=True, cache=self.text_cache)
        draw_text(surf, "P1: Arrows move  Z jump  X atk  A grab  S special", self.font_small, LIGHT_GRAY,
                  INTERNAL_W // 2, 168, center=True, cache=self.text_cache)

    def draw_char_select(self, surf):
        self.bg.draw(surf, self.t, self.font_small)
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "CHARACTER SELECT", self.font_big, YELLOW, INTERNAL_W // 2, 16, center=True, cache=self.text_cache)
        box_w = 46
        start_x = INTERNAL_W // 2 - (len(self.characters) * (box_w + 4)) // 2
        for i, c in enumerate(self.characters):
            x = start_x + i * (box_w + 4)
            y = 40
            pygame.draw.rect(surf, c.shirt, (x, y, box_w, box_w))
            border = WHITE if i == self.p1_idx else (RED if i == self.p2_idx else DARK_GRAY)
            pygame.draw.rect(surf, border, (x, y, box_w, box_w), 2 if (i == self.p1_idx or i == self.p2_idx) else 1)
            draw_text(surf, c.name, self.font_small, WHITE, x + box_w // 2, y + box_w + 8, center=True, cache=self.text_cache)
        c1 = self.characters[self.p1_idx]
        c2 = self.characters[self.p2_idx]
        draw_text(surf, f"P1: {c1.name} - {c1.desc}", self.font_small, BLUE, INTERNAL_W // 2, 105, center=True)
        label = "AI" if self.mode == "ai" else "P2"
        draw_text(surf, f"{label}: {c2.name} - {c2.desc}", self.font_small, RED, INTERNAL_W // 2, 118, center=True)
        draw_text(surf, "P1: Left/Right   P2: F/H", self.font_small, LIGHT_GRAY, INTERNAL_W // 2, 140, center=True, cache=self.text_cache)
        draw_text(surf, "ENTER: Fight!   ESC: Back", self.font_small, WHITE, INTERNAL_W // 2, 155, center=True, cache=self.text_cache)

    def draw_hud(self, surf):
        for i, f in enumerate((self.f1, self.f2)):
            x = 6 if i == 0 else INTERNAL_W - 66
            col = BLUE if i == 0 else RED
            draw_text(surf, f.char.name, self.font_small, col, x, 4)
            pct_col = GREEN if f.percent < 60 else (YELLOW if f.percent < 120 else RED)
            draw_text(surf, f"{int(f.percent)}%", self.font_med, pct_col, x, 12)
            # fix: draw actual circles instead of relying on a unicode glyph
            # that might not exist in every system font.
            for s in range(max(0, f.stocks)):
                cx = x + 4 + s * 8
                pygame.draw.circle(surf, WHITE, (cx, 30), 3)
            mpct = f.meter / 100
            bar_x = x if i == 0 else INTERNAL_W - 66
            pygame.draw.rect(surf, DARK_GRAY, (bar_x, 34, 60, 3))
            pygame.draw.rect(surf, (255, 215, 100), (bar_x, 34, int(60 * mpct), 3))
        if self.debug:
            draw_text(surf, "F3: debug ON", self.font_small, (255, 100, 100), INTERNAL_W // 2, 6, center=True)

    def draw_fighting(self, surf):
        self.bg.draw(surf, self.t, self.font_small)
        self.f1.draw(surf, self.t, self.debug)
        self.f2.draw(surf, self.t, self.debug)
        for p in self.particles:
            p.draw(surf)
        self.draw_hud(surf)

    def draw_pause(self, surf):
        self.draw_fighting(surf)
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "PAUSED", self.font_big, WHITE, INTERNAL_W // 2, 70, center=True, cache=self.text_cache)
        draw_text(surf, "ESC: Resume", self.font_med, LIGHT_GRAY, INTERNAL_W // 2, 100, center=True, cache=self.text_cache)
        draw_text(surf, "Q: Quit to Menu", self.font_med, LIGHT_GRAY, INTERNAL_W // 2, 116, center=True, cache=self.text_cache)

    def draw_game_over(self, surf):
        self.bg.draw(surf, self.t, self.font_small)
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "GAME OVER", self.font_big, RED, INTERNAL_W // 2, 60, center=True, cache=self.text_cache)
        draw_text(surf, self.winner_msg, self.font_med, YELLOW, INTERNAL_W // 2, 90, center=True)
        draw_text(surf, "ENTER: Menu   R: Rematch   ESC: Quit", self.font_small, WHITE, INTERNAL_W // 2, 120, center=True, cache=self.text_cache)

    # fix: dispatch dict instead of a long if/elif chain (lightweight nod to
    # separating "scenes" without a full class-per-scene rewrite)
    def _draw_dispatch(self):
        return {
            GameState.MENU: self.draw_menu,
            GameState.CHAR_SELECT: self.draw_char_select,
            GameState.FIGHTING: self.draw_fighting,
            GameState.PAUSE: self.draw_pause,
            GameState.GAME_OVER: self.draw_game_over,
        }

    def draw(self):
        self.canvas.fill(BLACK)
        self._draw_dispatch()[self.state](self.canvas)

        ox = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        oy = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        # fix: pygame.transform.scale is nearest-neighbour (NOT smoothscale) -
        # that's what keeps the pixel-art look crisp when we blow the canvas up.
        scaled = pygame.transform.scale(self.canvas, (WINDOW_W, WINDOW_H))
        self.screen.fill(BLACK)
        self.screen.blit(scaled, (int(ox * PIXEL_SCALE), int(oy * PIXEL_SCALE)))
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 1.0 / 20.0)  # clamp huge dt spikes (e.g. window drag) so physics don't jump
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()
        # fix: no more sys.exit() after pygame.quit() - just return and let
        # the interpreter shut down normally (plays nicer with IDEs/threads).


if __name__ == "__main__":
    Game().run()
