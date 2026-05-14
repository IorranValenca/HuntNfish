"""
HUD for FPS Combat Zone.
All elements parented to camera.ui.
"""
from ursina import *
import math


class HUD:
    MAX_HP = 100

    def __init__(self):
        ui = camera.ui

        # ── Crosshair ────────────────────────────────────────────────────
        ch_col = color.rgba(255,255,255,210)
        self._ch_top   = Entity(parent=ui, model='quad', color=ch_col, scale=(.003,.018), y= .028)
        self._ch_bot   = Entity(parent=ui, model='quad', color=ch_col, scale=(.003,.018), y=-.028)
        self._ch_right = Entity(parent=ui, model='quad', color=ch_col, scale=(.018,.003), x= .028)
        self._ch_left  = Entity(parent=ui, model='quad', color=ch_col, scale=(.018,.003), x=-.028)
        self._ch_parts = [self._ch_top, self._ch_bot, self._ch_right, self._ch_left]
        self._ch_spread = 0.0

        # Hit marker (X shape, shown briefly on hit)
        hm_col = color.rgba(255,50,50,0)
        self._hm1 = Entity(parent=ui, model='quad', color=hm_col, scale=(.018,.003), rotation_z= 45)
        self._hm2 = Entity(parent=ui, model='quad', color=hm_col, scale=(.018,.003), rotation_z=-45)
        self._hm_alpha = 0.0

        # ── Health bar (bottom-left) ──────────────────────────────────────
        Entity(parent=ui, model='quad', color=color.rgba(0,0,0,140),
               scale=(.38,.032), position=(-.64,-.45))
        self._hp_bar = Entity(parent=ui, model='quad',
                              color=color.rgb(50,210,70),
                              scale=(.355,.022), position=(-.64,-.45),
                              origin=(-.5, 0))
        self._hp_bar.x = -.82
        self._hp_text = Text(parent=ui, text='♥  100', position=(-.87,-.43),
                             scale=1.15, color=color.white)

        # ── Ammo (bottom-right) ───────────────────────────────────────────
        self._ammo_text = Text(parent=ui, text='30 | 150',
                               position=(.55,-.44), scale=1.6,
                               color=color.white, origin=(0,0))
        self._ammo_label = Text(parent=ui, text='AMMO',
                                position=(.55,-.48), scale=.9,
                                color=color.rgba(200,200,200,160), origin=(0,0))

        # ── Kills (top-left) ─────────────────────────────────────────────
        self._kill_text = Text(parent=ui, text='KILLS  0',
                               position=(-.87,.44), scale=1.2,
                               color=color.rgb(255,220,60))

        # ── Wave (top-right) ─────────────────────────────────────────────
        self._wave_text = Text(parent=ui, text='WAVE 1',
                               position=(.62,.44), scale=1.2,
                               color=color.rgb(80,180,255))
        self._enemies_left = Text(parent=ui, text='',
                                  position=(.62,.40), scale=.95,
                                  color=color.rgba(200,200,200,180))

        # ── Compass (top-centre) ─────────────────────────────────────────
        self._compass = Text(parent=ui, text='N', position=(0,.46),
                             scale=1.5, color=color.rgba(255,255,255,200),
                             origin=(0,0))

        # ── Reload bar (centre) ───────────────────────────────────────────
        self._reload_bg = Entity(parent=ui, model='quad',
                                 color=color.rgba(0,0,0,140),
                                 scale=(.28,.028), position=(0,-.12),
                                 enabled=False)
        self._reload_bar = Entity(parent=ui, model='quad',
                                  color=color.rgb(255,200,30),
                                  scale=(.265,.018), position=(-.135,-.12),
                                  origin=(-.5,0), enabled=False)
        self._reload_text = Text(parent=ui, text='RELOADING',
                                 position=(0,-.08), scale=1.4,
                                 color=color.yellow, origin=(0,0),
                                 enabled=False)
        self._reload_t   = 0.0
        self._reload_dur = 2.3

        # ── Damage vignette — border only, centre stays clear ────────────
        _vp = dict(parent=ui, model='quad', color=color.rgba(200,0,0,0), z=-1)
        self._vig_top   = Entity(**_vp, scale=(2.2, 0.52), position=(0,  0.74))
        self._vig_bot   = Entity(**_vp, scale=(2.2, 0.52), position=(0, -0.74))
        self._vig_left  = Entity(**_vp, scale=(0.52, 2.2), position=(-0.74, 0))
        self._vig_right = Entity(**_vp, scale=(0.52, 2.2), position=( 0.74, 0))
        self._vignette_alpha = 0.0
        self._vig_pulse_t    = 0.0   # for low-HP heartbeat pulse

        # ── Kill feed (right side) ────────────────────────────────────────
        self._feed_lines = []
        for i in range(4):
            t = Text(parent=ui, text='',
                     position=(.5, .32 - i * .055), scale=.9,
                     color=color.rgba(255,100,100,0))
            self._feed_lines.append(t)
        self._feed_timers = [0.0] * 4

        # ── Game-state texts ──────────────────────────────────────────────
        self._wave_banner      = Text(parent=ui, text='', position=(0,.1),
                                      scale=3.5, color=color.rgba(255,220,60,0),
                                      origin=(0,0))
        self._wave_banner_t    = 0.0

        self._hp = self.MAX_HP

    # ── Public API ───────────────────────────────────────────────────────

    def refresh_ammo(self, ammo, reserve):
        self._ammo_text.text = f'{ammo} | {reserve}'
        if ammo == 0:
            self._ammo_text.color = color.red
        elif ammo <= 10:
            self._ammo_text.color = color.yellow
        else:
            self._ammo_text.color = color.white

    def refresh_kills(self, kills):
        self._kill_text.text = f'KILLS  {kills}'

    def refresh_wave(self, wave, enemies_left):
        self._wave_text.text   = f'WAVE {wave}'
        self._enemies_left.text = f'{enemies_left} enemies'

    def take_damage(self, amount):
        self._hp = max(0, self._hp - amount)
        self._update_hp_bar()
        self._vignette_alpha = min(200, self._vignette_alpha + 80)
        return self._hp

    def heal(self, amount):
        self._hp = min(self.MAX_HP, self._hp + amount)
        self._update_hp_bar()

    @property
    def hp(self):
        return self._hp

    def show_hit_marker(self):
        self._hm_alpha = 230
        self._ch_spread = max(self._ch_spread, .018)

    def show_reload(self, on, duration=2.3):
        self._reload_bg.enabled   = on
        self._reload_bar.enabled  = on
        self._reload_text.enabled = on
        if on:
            self._reload_dur = duration
            self._reload_t   = duration
            self._reload_bar.scale_x = .265

    def show_wave_banner(self, wave):
        self._wave_banner.text  = f'WAVE {wave}'
        self._wave_banner.color = color.rgba(255,220,60,220)
        self._wave_banner_t     = 2.5

    def add_kill_feed(self, text='ENEMY ELIMINATED'):
        # Shift existing lines down
        for i in range(3, 0, -1):
            self._feed_lines[i].text  = self._feed_lines[i-1].text
            self._feed_lines[i].color = self._feed_lines[i-1].color
            self._feed_timers[i]      = self._feed_timers[i-1]
        self._feed_lines[0].text  = text
        self._feed_lines[0].color = color.rgba(255,100,100,230)
        self._feed_timers[0]      = 2.5

    def update_compass(self, yaw):
        dirs = ['N','NE','E','SE','S','SW','W','NW','N']
        idx  = int((yaw + 22.5) / 45) % 8
        self._compass.text = dirs[idx]

    def show_game_over(self, kills):
        Entity(parent=camera.ui, model='quad', scale=(2,2),
               color=color.rgba(0,0,0,190), z=-.5)
        Text(parent=camera.ui, text='YOU DIED', position=(0,.15),
             scale=5, color=color.red, origin=(0,0))
        Text(parent=camera.ui, text=f'Kills: {kills}', position=(0,-.04),
             scale=2.5, color=color.white, origin=(0,0))
        Text(parent=camera.ui, text='Press  R  to restart',
             position=(0,-.2), scale=1.8,
             color=color.rgba(220,220,220,200), origin=(0,0))

    def show_wave_complete(self, wave, kills):
        banner = Entity(parent=camera.ui, model='quad',
                        color=color.rgba(0,30,0,160),
                        scale=(1.2,.18), position=(0,.05))
        t = Text(parent=camera.ui,
                 text=f'WAVE {wave} COMPLETE  —  {kills} KILLS',
                 position=(0,.05), scale=1.5,
                 color=color.rgb(80,255,80), origin=(0,0))
        destroy(banner, delay=3.5)
        destroy(t, delay=3.5)

    # ── Ursina update ────────────────────────────────────────────────────

    def update(self):
        dt = time.dt

        # Crosshair spread recovery
        self._ch_spread = max(0, self._ch_spread - dt * .08)
        s = .028 + self._ch_spread
        self._ch_top.y    =  s
        self._ch_bot.y    = -s
        self._ch_right.x  =  s
        self._ch_left.x   = -s

        # Hit marker fade
        if self._hm_alpha > 0:
            self._hm_alpha = max(0, self._hm_alpha - dt * 600)
            a = int(self._hm_alpha)
            self._hm1.color = color.rgba(255,50,50,a)
            self._hm2.color = color.rgba(255,50,50,a)

        # Reload bar fill
        if self._reload_t > 0:
            self._reload_t -= dt
            progress = 1 - max(0, self._reload_t) / self._reload_dur
            self._reload_bar.scale_x = progress * .265

        # Damage vignette fade
        if self._vignette_alpha > 0:
            self._vignette_alpha = max(0, self._vignette_alpha - dt * 160)

        # Low-HP heartbeat pulse (below 30 HP)
        base_alpha = self._vignette_alpha
        if self._hp < 30:
            self._vig_pulse_t += dt * 2.5
            pulse = (math.sin(self._vig_pulse_t) * 0.5 + 0.5) * 60
            base_alpha = max(base_alpha, pulse)

        c = color.rgba(200, 0, 0, int(base_alpha))
        self._vig_top.color   = c
        self._vig_bot.color   = c
        self._vig_left.color  = c
        self._vig_right.color = c

        # Kill feed fade
        for i, t in enumerate(self._feed_timers):
            if t > 0:
                self._feed_timers[i] -= dt
                a = min(230, int(self._feed_timers[i] / 2.5 * 230))
                self._feed_lines[i].color = color.rgba(255,100,100,a)
            else:
                self._feed_lines[i].text = ''

        # Wave banner fade
        if self._wave_banner_t > 0:
            self._wave_banner_t -= dt
            a = min(220, int(self._wave_banner_t / 2.5 * 220))
            self._wave_banner.color = color.rgba(255,220,60, a)

    # ── Private ──────────────────────────────────────────────────────────

    def _update_hp_bar(self):
        ratio = max(0, self._hp / self.MAX_HP)
        self._hp_bar.scale_x = ratio * .355
        self._hp_text.text   = f'♥  {self._hp}'
        if self._hp < 30:
            self._hp_bar.color = color.rgb(210, 50, 50)
        elif self._hp < 60:
            self._hp_bar.color = color.rgb(210,180, 50)
        else:
            self._hp_bar.color = color.rgb(50, 210, 70)
