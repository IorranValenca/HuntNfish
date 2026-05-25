"""Minimal HUD for Hunt & Fish."""
from ursina import *
from game_utils import solid


class HuntHUD:
    def __init__(self):
        ui = camera.ui

        # Tool indicator (top-left chip — out of the way of the compass)
        self._tool_txt = Text(parent=ui, text='RIFLE', position=(-.78, .46),
                              scale=1.0, color=color.rgb(255, 200, 60), origin=(0, 0))

        # Rifle ammo (bottom right)
        self._ammo_txt = Text(parent=ui, text='5 / 5', position=(.58, -.43),
                              scale=1.55, color=color.white, origin=(0, 0))
        self._ammo_lbl = Text(parent=ui, text='AMMO', position=(.58, -.47),
                              scale=.85, color=color.rgba(200, 200, 200, 160), origin=(0, 0))
        self._bolt_txt = Text(parent=ui, text='', position=(.58, -.51),
                              scale=.90, color=color.rgb(255, 160, 40), origin=(0, 0))

        # Player HP (bottom left)
        self._hp_bg   = Entity(parent=ui, model='quad',
                               color=color.rgba(20, 20, 20, 180),
                               scale=(.30, .024), position=(-.68, -.43))
        self._hp_fill = Entity(parent=ui, model='quad',
                               color=color.rgb(55, 200, 75),
                               scale=(.288, .017), position=(-.833, -.43),
                               origin=(-.5, 0))
        self._hp_lbl  = Text(parent=ui, text='HP', position=(-.86, -.43),
                             scale=.85, color=color.rgba(200, 200, 200, 160), origin=(0, 0))
        self._hp_txt  = Text(parent=ui, text='100', position=(-.68, -.472),
                             scale=.80, color=color.white, origin=(0, 0))
        self._hp_max  = 100
        self._hp_val  = 100

        # Hit flash (white = rifle hit marker, red = player took damage)
        self._hit_flash = Entity(parent=ui, model='quad',
                                 color=color.rgba(255, 255, 255, 0),
                                 scale=(2, 2), z=-1)
        self._hit_t    = 0.0
        self._hit_r    = 255
        self._hit_g    = 255
        self._hit_b    = 255

        # Crosshair (small dot + lines for rifle)
        ch = color.rgba(255, 255, 255, 190)
        self._ch_top   = Entity(parent=ui, model='quad', color=ch, scale=(.003,.016), y= .024)
        self._ch_bot   = Entity(parent=ui, model='quad', color=ch, scale=(.003,.016), y=-.024)
        self._ch_right = Entity(parent=ui, model='quad', color=ch, scale=(.016,.003), x= .024)
        self._ch_left  = Entity(parent=ui, model='quad', color=ch, scale=(.016,.003), x=-.024)
        self._ch_parts = [self._ch_top, self._ch_bot, self._ch_right, self._ch_left]

        # Loot prompt (centre, shown when near lootable animal)
        self._loot_prompt = Text(parent=ui, text='Press  E  to collect',
                                 position=(0, -.08), scale=1.6,
                                 color=color.rgb(255, 230, 80), origin=(0, 0),
                                 enabled=False)

        # Kill / catch log (left side)
        self._log_lines  = []
        self._log_timers = []
        for i in range(5):
            t = Text(parent=ui, text='', position=(-.88, .35 - i * .055),
                     scale=.88, color=color.rgba(255, 255, 255, 0))
            self._log_lines.append(t)
            self._log_timers.append(0.0)

        # Hit marker (white X) — flashes briefly on confirmed body shot
        hm_invis = color.rgba(255, 255, 255, 0)
        self._hm_p1 = Entity(parent=ui, model='quad', color=hm_invis,
                             scale=(.038, .005), rotation_z= 45, z=-.5)
        self._hm_p2 = Entity(parent=ui, model='quad', color=hm_invis,
                             scale=(.038, .005), rotation_z=-45, z=-.5)
        self._hm_t  = 0.0

        # Kill marker (larger gold X) — distinct flash on kill / headshot
        km_invis = color.rgba(255, 200, 60, 0)
        self._km_p1 = Entity(parent=ui, model='quad', color=km_invis,
                             scale=(.075, .008), rotation_z= 45, z=-.5)
        self._km_p2 = Entity(parent=ui, model='quad', color=km_invis,
                             scale=(.075, .008), rotation_z=-45, z=-.5)
        self._km_t  = 0.0
        self._km_color = (255, 200, 60)

        # Kill ribbon (top centre) — "TROPHY BUCK · 187m · HEADSHOT"
        self._kill_ribbon = Text(parent=ui, text='', position=(0, .36),
                                 scale=1.25, color=color.rgba(255, 220, 100, 0),
                                 origin=(0, 0))
        self._kr_t = 0.0

        # Stats panel (above ammo)
        self._stat_shots  = 0
        self._stat_hits   = 0
        self._stat_kills  = 0
        self._stat_best   = 0
        self._stat_streak = 0
        self._stat_txt = Text(parent=ui,
                              text='ACC ---   STRK 0   BEST 0m',
                              position=(.58, -.36), scale=.78,
                              color=color.rgba(200, 200, 200, 180), origin=(0, 0))

        # ── Compass strip (top centre) ──────────────────────────────────────
        self._compass_y = 0.46
        self._compass_labels = []
        for name, ang in [('N', 0), ('NE', 45), ('E', 90), ('SE', 135),
                          ('S', 180), ('SW', 225), ('W', 270), ('NW', 315)]:
            t = Text(parent=ui, text=name, scale=1.0,
                     color=color.rgba(255, 255, 255, 220),
                     position=(0, self._compass_y), origin=(0, 0))
            self._compass_labels.append((t, ang))
        self._compass_marker = Entity(parent=ui, model='quad',
                                      texture=solid(255, 220, 80),
                                      scale=(.006, .020),
                                      position=(0, self._compass_y - .025))

        # ── Mini-map (top-right corner) ─────────────────────────────────────
        self._mm_size  = 0.20
        self._mm_range = 60.0
        self._mm_cx    = 0.78
        self._mm_cy    = 0.30
        Entity(parent=ui, model='quad', texture=solid(70, 95, 115),
               scale=(self._mm_size * 1.06, self._mm_size * 1.06),
               position=(self._mm_cx, self._mm_cy), z=.001)
        self._mm_bg = Entity(parent=ui, model='quad',
                             texture=solid(20, 30, 36),
                             scale=(self._mm_size, self._mm_size),
                             position=(self._mm_cx, self._mm_cy))
        self._mm_lake = Entity(parent=ui, model='quad',
                               texture=solid(38, 95, 155),
                               scale=(0.01, 0.01),
                               position=(self._mm_cx, self._mm_cy),
                               z=-.001, enabled=False)
        # Dot pool — reused each frame
        self._mm_dots = []
        for _ in range(70):
            d = Entity(parent=ui, model='quad',
                       texture=solid(255, 255, 255),
                       scale=(.008, .008),
                       position=(self._mm_cx, self._mm_cy),
                       z=-.002, enabled=False)
            self._mm_dots.append(d)
        # Player marker (rotates with heading)
        self._mm_player = Entity(parent=ui, model='quad',
                                 texture=solid(255, 220, 80),
                                 scale=(.010, .016),
                                 position=(self._mm_cx, self._mm_cy),
                                 z=-.003)
        # 'N' label on map top edge
        Text(parent=ui, text='N',
             position=(self._mm_cx, self._mm_cy + self._mm_size * 0.55),
             scale=.85, color=color.rgba(220, 220, 220, 220), origin=(0, 0))

        # ── Stealth indicator (left side) ───────────────────────────────────
        self._stl_lbl = Text(parent=ui, text='QUIET', position=(-.78, -.36),
                             scale=.85, color=color.rgb(120, 220, 120),
                             origin=(0, 0))
        self._stl_bars = []
        for i in range(3):
            b = Entity(parent=ui, model='quad', texture=solid(120, 220, 120),
                       scale=(.018, .012),
                       position=(-.83 + i * .024, -.39))
            self._stl_bars.append(b)

        # ── Pause menu ──────────────────────────────────────────────────────
        self._pause_bg = Entity(parent=ui, model='quad',
                                texture=solid(0, 0, 0),
                                color=color.rgba(0, 0, 0, 180),
                                scale=(2, 2), z=-0.6, enabled=False)
        self._pause_panel = Entity(parent=ui, model='quad',
                                   texture=solid(20, 28, 38),
                                   scale=(.40, .42),
                                   position=(0, 0), z=-0.65, enabled=False)
        Entity(parent=self._pause_panel, model='quad',
               texture=solid(70, 110, 140),
               scale=(1.04, 1.035), z=.001)
        Entity(parent=self._pause_panel, model='quad',
               texture=solid(20, 28, 38),
               scale=(0.99, 0.99), z=.0001)
        self._pause_title = Text(parent=ui, text='PAUSED',
                                 position=(0, .14), scale=2.6,
                                 color=color.rgb(255, 215, 80),
                                 origin=(0, 0), enabled=False, z=-.7)
        self._pause_lines = []
        for i, (k, label) in enumerate([
            ('R', 'Resume'),
            ('H', 'Controls'),
            ('Q', 'Quit to desktop'),
        ]):
            t = Text(parent=ui,
                     text=f'[{k}]   {label}',
                     position=(0, .04 - i * .065),
                     scale=1.2, color=color.white,
                     origin=(0, 0), enabled=False, z=-.7)
            self._pause_lines.append(t)
        self._pause_hint = Text(parent=ui, text='press ESC again to resume',
                                position=(0, -.17), scale=.85,
                                color=color.rgba(180, 180, 180, 180),
                                origin=(0, 0), enabled=False, z=-.7)

        # ── Controls overlay (toggle with H) ────────────────────────────────
        self._ctl_bg = Entity(parent=ui, model='quad',
                              texture=solid(0, 0, 0),
                              color=color.rgba(0, 0, 0, 200),
                              scale=(2, 2), z=-0.7, enabled=False)
        self._ctl_panel = Entity(parent=ui, model='quad',
                                 texture=solid(18, 22, 30),
                                 scale=(.62, .68),
                                 position=(0, 0), z=-0.75, enabled=False)
        Entity(parent=self._ctl_panel, model='quad',
               texture=solid(70, 110, 140),
               scale=(1.03, 1.025), z=.001)
        Entity(parent=self._ctl_panel, model='quad',
               texture=solid(18, 22, 30),
               scale=(0.992, 0.992), z=.0001)
        self._ctl_title = Text(parent=ui, text='CONTROLS',
                               position=(0, .26), scale=2.0,
                               color=color.rgb(120, 200, 255),
                               origin=(0, 0), enabled=False, z=-.8)
        ctl_lines = [
            'WASD          Move',
            'Shift          Sprint (loud)',
            'Standing      Quiet (animals less alert)',
            'Space         Jump',
            '',
            '1 / 2 / 3     Rifle / Revolver / Rod',
            '4 / 5 / 6     Bow / Shotgun / Binoculars (if owned)',
            'F             Cycle owned weapons',
            '',
            'Left Click    Shoot   |   Charge bow / cast rod',
            'Right Click   Aim down sights / zoom',
            'R             Reload / cycle bolt / reel',
            'E             Collect animal / store fish / enter lodge',
            'TAB           Open tackle box / switch shop tab',
            '',
            "Visit Trader's Lodge to sell carcasses & buy gear.",
            '',
            'ESC           Pause menu',
            'H             Toggle this screen',
        ]
        self._ctl_text = Text(parent=ui, text='\n'.join(ctl_lines),
                              position=(-.26, .19), scale=.95,
                              color=color.rgba(235, 235, 235, 230),
                              enabled=False, z=-.8)
        self._ctl_hint = Text(parent=ui, text='press H to close',
                              position=(0, -.31), scale=.85,
                              color=color.rgba(180, 180, 180, 180),
                              origin=(0, 0), enabled=False, z=-.8)

        self.paused_visible    = False
        self._controls_visible = False

        # ── Money display ────────────────────────────────────────────────
        self._money_txt = Text(parent=ui, text='$0', position=(-.78, .42),
                               scale=1.0, color=color.rgb(120, 220, 120),
                               origin=(0, 0))

        # ── Cabin prompt ─────────────────────────────────────────────────
        self._cabin_prompt = Text(parent=ui, text='Press  E  to trade',
                                  position=(0, -.05), scale=1.5,
                                  color=color.rgb(120, 220, 255),
                                  origin=(0, 0), enabled=False)

        # ── Shop panel ───────────────────────────────────────────────────
        self.shop_visible = False
        self._shop_tab    = 'sell'   # 'sell' | 'buy'

        PANEL_W, PANEL_H = 0.86, 0.86

        # Dim full-screen background
        self._shop_bg = Entity(parent=ui, model='quad', texture=solid(0, 0, 0),
                               color=color.rgba(0, 0, 0, 210),
                               scale=(2, 2), z=-0.80, enabled=False)
        # Golden-wood outer frame
        self._shop_frame = Entity(parent=ui, model='quad',
                                  texture=solid(165, 115, 50),
                                  scale=(PANEL_W + 0.018, PANEL_H + 0.018),
                                  z=-0.81, enabled=False)
        # Inner panel (warm dark wood)
        self._shop_panel = Entity(parent=ui, model='quad',
                                  texture=solid(40, 28, 18),
                                  scale=(PANEL_W, PANEL_H),
                                  z=-0.815, enabled=False)
        # Header banner (darker strip across the top)
        self._shop_header = Entity(parent=ui, model='quad',
                                   texture=solid(26, 16, 8),
                                   scale=(PANEL_W, 0.11),
                                   position=(0, 0.36), z=-0.82, enabled=False)
        # Thin gold divider beneath the header
        self._shop_div = Entity(parent=ui, model='quad',
                                texture=solid(165, 115, 50),
                                scale=(PANEL_W, 0.003),
                                position=(0, 0.30), z=-0.82, enabled=False)
        self._shop_title = Text(parent=ui, text="TRADER'S LODGE",
                                position=(-0.10, 0.36), scale=2.0,
                                color=color.rgb(255, 215, 110),
                                origin=(0, 0), enabled=False, z=-0.83)
        # Money badge (top-right of header)
        self._shop_money_chip = Entity(parent=ui, model='quad',
                                       texture=solid(20, 55, 28),
                                       scale=(0.18, 0.060),
                                       position=(0.32, 0.36),
                                       z=-0.823, enabled=False)
        Entity(parent=self._shop_money_chip, model='quad',
               texture=solid(80, 200, 100),
               scale=(1.03, 1.06), z=.001, enabled=True)
        Entity(parent=self._shop_money_chip, model='quad',
               texture=solid(20, 55, 28),
               scale=(0.985, 0.93), z=.0001, enabled=True)
        self._shop_money = Text(parent=ui, text='$0',
                                position=(0.32, 0.36), scale=1.35,
                                color=color.rgb(150, 250, 150),
                                origin=(0, 0), enabled=False, z=-0.83)

        # Tabs — two boxes with active highlight
        self._shop_tab_sell_bg = Entity(parent=ui, model='quad',
                                        texture=solid(78, 50, 24),
                                        scale=(0.22, 0.058),
                                        position=(-0.16, 0.25),
                                        z=-0.823, enabled=False)
        self._shop_tab_buy_bg  = Entity(parent=ui, model='quad',
                                        texture=solid(45, 30, 16),
                                        scale=(0.22, 0.058),
                                        position=( 0.16, 0.25),
                                        z=-0.823, enabled=False)
        self._shop_tab_sell = Text(parent=ui, text='[1]  SELL',
                                   position=(-0.16, 0.25), scale=1.1,
                                   color=color.rgb(255, 235, 140),
                                   origin=(0, 0), enabled=False, z=-0.83)
        self._shop_tab_buy  = Text(parent=ui, text='[2]  BUY',
                                   position=( 0.16, 0.25), scale=1.1,
                                   color=color.rgba(180, 160, 140, 210),
                                   origin=(0, 0), enabled=False, z=-0.83)

        # Row pool — alternating stripe rows for inventory / catalog
        self._shop_rows = []
        ROW_Y0 = 0.17
        ROW_H  = 0.052
        ROW_W  = PANEL_W - 0.06
        for i in range(9):
            y = ROW_Y0 - i * ROW_H
            stripe_tex = solid(52, 38, 22) if i % 2 == 0 else solid(42, 30, 18)
            bg = Entity(parent=ui, model='quad', texture=stripe_tex,
                        scale=(ROW_W, ROW_H - 0.006),
                        position=(0, y), z=-0.823, enabled=False)
            chip = Entity(parent=ui, model='quad',
                          texture=solid(165, 115, 50),
                          scale=(0.05, 0.038),
                          position=(-0.36, y), z=-0.826, enabled=False)
            key = Text(parent=ui, text='',
                       position=(-0.36, y), scale=0.95,
                       color=color.rgb(30, 18, 8),
                       origin=(0, 0), enabled=False, z=-0.83)
            name = Text(parent=ui, text='',
                        position=(-0.32, y), scale=1.0,
                        color=color.rgb(240, 232, 218),
                        enabled=False, z=-0.83)
            price = Text(parent=ui, text='',
                         position=(0.36, y), scale=1.05,
                         color=color.rgb(150, 245, 150),
                         origin=(0.5, 0), enabled=False, z=-0.83)
            self._shop_rows.append({
                'bg': bg, 'chip': chip, 'key': key,
                'name': name, 'price': price,
            })

        # Footer (hint line)
        self._shop_footer = Text(parent=ui, text='',
                                 position=(0, -0.38), scale=0.88,
                                 color=color.rgba(205, 180, 145, 220),
                                 origin=(0, 0), enabled=False, z=-0.83)

    def set_tool(self, tool):
        names = {
            'rifle':      ('RIFLE',       (255, 200,  60)),
            'revolver':   ('REVOLVER',    (200, 180, 255)),
            'rod':        ('FISHING ROD', ( 60, 200, 255)),
            'bow':        ('BOW',         (180, 240, 140)),
            'shotgun':    ('SHOTGUN',     (255, 150,  90)),
            'binoculars': ('BINOCULARS',  (140, 220, 255)),
        }
        label, rgb = names.get(tool, (tool.upper(), (220, 220, 220)))
        self._tool_txt.text  = label
        self._tool_txt.color = color.rgb(*rgb)

        show_crosshair = tool not in ('rod',)
        for p in self._ch_parts: p.enabled = show_crosshair

        show_ammo = tool in ('rifle', 'revolver', 'shotgun')
        self._ammo_txt.enabled = show_ammo
        self._ammo_lbl.enabled = show_ammo
        self._bolt_txt.enabled = show_ammo
        if not show_ammo:
            self._bolt_txt.text = ''

    def refresh_ammo(self, ammo, state, mag_size=5):
        self._ammo_txt.text = f'{ammo} / {mag_size}'
        if ammo == 0:
            self._ammo_txt.color = color.red
        elif ammo <= 2:
            self._ammo_txt.color = color.yellow
        else:
            self._ammo_txt.color = color.white
        if state == 'needs_bolt':
            self._bolt_txt.text = 'CYCLE BOLT  (tap R)  |  hold R = manual load'
        elif state in ('bolt_back', 'bolt_forward'):
            self._bolt_txt.text = 'cycling...'
        elif state == 'reloading':
            self._bolt_txt.text = 'RELOADING...'
        elif state == 'empty':
            self._bolt_txt.text = 'RELOAD  (R)  |  hold R = manual load'
        elif state == 'loading_open':
            self._bolt_txt.text = 'BOLT OPEN  —  hold R to insert  |  release to close'
        elif state == 'inserting':
            self._bolt_txt.text = 'inserting...'
        elif state == 'bolt_close':
            self._bolt_txt.text = 'closing bolt...'
        elif ammo == 0 and state == 'ready':
            self._bolt_txt.text = 'RELOAD  (R)'
        else:
            self._bolt_txt.text = ''

    def refresh_hp(self, hp):
        self._hp_val = max(0, min(self._hp_max, hp))
        frac = self._hp_val / self._hp_max
        self._hp_fill.scale_x = max(0.001, frac * .288)
        self._hp_txt.text = str(self._hp_val)
        if frac > 0.5:
            self._hp_fill.color = color.rgb(55, 200, 75)
        elif frac > 0.25:
            self._hp_fill.color = color.rgb(220, 185, 20)
        else:
            self._hp_fill.color = color.rgb(210, 45, 30)

    def show_loot_prompt(self, visible):
        self._loot_prompt.enabled = visible

    def show_hit(self, r=255, g=255, b=255):
        self._hit_t = 0.14
        self._hit_r = r
        self._hit_g = g
        self._hit_b = b

    def add_log(self, text):
        for i in range(4, 0, -1):
            self._log_lines[i].text  = self._log_lines[i-1].text
            self._log_timers[i]      = self._log_timers[i-1]
        self._log_lines[0].text  = text
        self._log_timers[0]      = 4.0
        self._log_lines[0].color = color.rgba(255, 255, 200, 230)

    # ── Shot / hit / kill tracking ──────────────────────────────────────
    def register_shot(self):
        self._stat_shots += 1
        self._refresh_stats()

    def register_hit(self, headshot=False):
        self._stat_hits += 1
        self._hm_t = 0.18
        self._refresh_stats()

    def register_miss(self):
        if self._stat_streak > 0:
            self._stat_streak = 0
            self._refresh_stats()

    def register_kill(self, name, distance, headshot=False):
        self._stat_hits   += 1
        self._stat_kills  += 1
        self._stat_streak += 1
        d = int(distance)
        if d > self._stat_best:
            self._stat_best = d
        self._km_t = 0.50
        self._km_color = (255, 90, 90) if headshot else (255, 200, 60)
        parts = [name.upper(), f'{d} m']
        if headshot:
            parts.append('HEADSHOT')
        self._kill_ribbon.text = '   ·   '.join(parts)
        self._kr_t = 2.6
        self._refresh_stats()

    def _refresh_stats(self):
        acc_str = f'{int(self._stat_hits / self._stat_shots * 100)}%' \
                  if self._stat_shots else '---'
        self._stat_txt.text = (
            f'ACC {acc_str}   STRK {self._stat_streak}   BEST {self._stat_best}m'
        )

    # ── Compass / minimap / stealth ─────────────────────────────────────
    def update_compass(self, player_yaw):
        yaw = player_yaw % 360
        WINDOW = 75.0
        SPREAD = 0.32
        for t, ang in self._compass_labels:
            delta = ((ang - yaw + 540) % 360) - 180
            if abs(delta) > WINDOW:
                t.enabled = False
            else:
                t.enabled = True
                t.x = delta / WINDOW * SPREAD
                t.y = self._compass_y
                a = int(220 * (1 - abs(delta) / WINDOW))
                t.color = color.rgba(255, 255, 255, max(80, a))

    def update_minimap(self, player_pos, player_yaw, lake_rect, animal_groups):
        """animal_groups = list of (entity_iterable, color_texture) pairs.
        lake_rect = (x0, x1, z0, z1)."""
        cx, cy = self._mm_cx, self._mm_cy
        scale = (self._mm_size * 0.5) / self._mm_range  # world → screen
        half  = self._mm_size * 0.5

        # Player marker rotates with heading (north-up map)
        import math as _m
        self._mm_player.rotation_z = -player_yaw

        # Lake placement
        lx0, lx1, lz0, lz1 = lake_rect
        lcx = (lx0 + lx1) * 0.5 - player_pos.x
        lcz = (lz0 + lz1) * 0.5 - player_pos.z
        sx, sy = lcx * scale, -lcz * scale
        if abs(sx) < half + 0.05 and abs(sy) < half + 0.05:
            self._mm_lake.enabled = True
            self._mm_lake.x = cx + sx
            self._mm_lake.y = cy + sy
            self._mm_lake.scale_x = (lx1 - lx0) * scale
            self._mm_lake.scale_y = (lz1 - lz0) * scale
        else:
            self._mm_lake.enabled = False

        # Animal dots
        idx = 0
        for entities, tex in animal_groups:
            for a in entities:
                if idx >= len(self._mm_dots):
                    break
                dx = a.x - player_pos.x
                dz = a.z - player_pos.z
                if abs(dx) > self._mm_range or abs(dz) > self._mm_range:
                    continue
                sx, sy = dx * scale, -dz * scale
                dot = self._mm_dots[idx]
                dot.x = cx + sx
                dot.y = cy + sy
                dot.texture = tex
                dot.enabled = True
                idx += 1
        for d in self._mm_dots[idx:]:
            d.enabled = False

    def update_stealth(self, noise_mult):
        if noise_mult <= 0.7:
            level, lit, txt, col = 1, 1, 'QUIET',  (120, 220, 120)
        elif noise_mult <= 1.2:
            level, lit, txt, col = 2, 2, 'WALK',   (220, 200, 80)
        else:
            level, lit, txt, col = 3, 3, 'LOUD',   (240, 90, 70)
        self._stl_lbl.text  = txt
        self._stl_lbl.color = color.rgb(*col)
        for i, bar in enumerate(self._stl_bars):
            if i < lit:
                bar.texture = solid(*col)
                bar.color   = color.white
            else:
                bar.texture = solid(50, 55, 60)
                bar.color   = color.white

    # ── Pause / controls overlays ───────────────────────────────────────
    def show_pause_menu(self):
        self.paused_visible = True
        for e in (self._pause_bg, self._pause_panel, self._pause_title,
                  self._pause_hint):
            e.enabled = True
        for t in self._pause_lines:
            t.enabled = True

    def hide_pause_menu(self):
        self.paused_visible = False
        for e in (self._pause_bg, self._pause_panel, self._pause_title,
                  self._pause_hint):
            e.enabled = False
        for t in self._pause_lines:
            t.enabled = False

    def toggle_controls(self):
        self._controls_visible = not self._controls_visible
        for e in (self._ctl_bg, self._ctl_panel, self._ctl_title,
                  self._ctl_text, self._ctl_hint):
            e.enabled = self._controls_visible

    # ── Money + cabin prompt ────────────────────────────────────────────
    def set_money(self, amount):
        self._money_txt.text = f'${amount}'
        if self.shop_visible:
            self._shop_money.text = f'${amount}'

    def show_cabin_prompt(self, visible):
        self._cabin_prompt.enabled = visible

    # ── Shop panel ──────────────────────────────────────────────────────
    _SHOP_FRAME_ENTITIES = (
        '_shop_bg', '_shop_frame', '_shop_panel', '_shop_header',
        '_shop_div', '_shop_title', '_shop_money_chip', '_shop_money',
        '_shop_tab_sell_bg', '_shop_tab_buy_bg',
        '_shop_tab_sell', '_shop_tab_buy', '_shop_footer',
    )

    def show_shop(self):
        self.shop_visible = True
        self._shop_tab    = 'sell'
        for name in self._SHOP_FRAME_ENTITIES:
            getattr(self, name).enabled = True
        # rows enabled per-call by render_shop()

    def hide_shop(self):
        self.shop_visible = False
        for name in self._SHOP_FRAME_ENTITIES:
            getattr(self, name).enabled = False
        for row in self._shop_rows:
            for e in row.values():
                e.enabled = False

    def set_shop_tab(self, tab):
        self._shop_tab = tab
        if tab == 'sell':
            self._shop_tab_sell_bg.texture = solid(78, 50, 24)
            self._shop_tab_buy_bg.texture  = solid(45, 30, 16)
            self._shop_tab_sell.color      = color.rgb(255, 235, 140)
            self._shop_tab_buy.color       = color.rgba(180, 160, 140, 210)
        else:
            self._shop_tab_sell_bg.texture = solid(45, 30, 16)
            self._shop_tab_buy_bg.texture  = solid(78, 50, 24)
            self._shop_tab_sell.color      = color.rgba(180, 160, 140, 210)
            self._shop_tab_buy.color       = color.rgb(255, 235, 140)

    def _stripe_tex(self, i):
        return solid(52, 38, 22) if i % 2 == 0 else solid(42, 30, 18)

    def _clear_rows(self):
        for row in self._shop_rows:
            for e in row.values():
                e.enabled = False

    def _fill_row(self, idx, key_label, name, price_text, price_rgb,
                  *, sell_all=False, dim_name=False):
        if idx >= len(self._shop_rows):
            return
        r = self._shop_rows[idx]
        if sell_all:
            r['bg'].texture   = solid(28, 60, 32)
            r['chip'].texture = solid(90, 210, 110)
        else:
            r['bg'].texture   = self._stripe_tex(idx)
            r['chip'].texture = solid(165, 115, 50)
        r['bg'].enabled   = True
        r['chip'].enabled = bool(key_label)
        r['key'].text     = key_label
        r['key'].color    = color.rgb(15, 30, 10) if sell_all else color.rgb(30, 18, 8)
        r['key'].enabled  = bool(key_label)
        r['name'].text    = '  ' + name
        if sell_all:
            r['name'].color = color.rgb(170, 255, 180)
        elif dim_name:
            r['name'].color = color.rgba(190, 170, 140, 200)
        else:
            r['name'].color = color.rgb(240, 232, 218)
        r['name'].enabled = True
        r['price'].text   = price_text
        r['price'].color  = color.rgb(*price_rgb)
        r['price'].enabled = True

    def render_shop(self, money, carcasses, weapons):
        """carcasses = [{name,grade,weight,price}, ...]
        weapons   = [{key,name,price,owned,affordable}, ...]"""
        self._shop_money.text = f'${money}'
        self._clear_rows()

        if self._shop_tab == 'sell':
            if not carcasses:
                self._fill_row(0, '', '(no carcasses — go hunt!)',
                               '', (150, 245, 150), dim_name=True)
                self._shop_footer.text = (
                    'TAB switches tab    ·    E or ESC closes'
                )
                return

            # Reserve 1 row for "...and N more" if needed, and 1 for "Sell ALL"
            max_items = 8 if len(carcasses) <= 8 else 7
            shown = 0
            for i, c in enumerate(carcasses[:max_items]):
                self._fill_row(
                    shown, str(i + 1),
                    f"{c['name']}     {c['weight']:.1f} kg",
                    f"+${c['price']}", (150, 245, 150),
                )
                shown += 1

            if len(carcasses) > shown:
                self._fill_row(
                    shown, '',
                    f"...and {len(carcasses) - shown} more",
                    '', (150, 245, 150), dim_name=True,
                )
                shown += 1

            total = sum(c['price'] for c in carcasses)
            self._fill_row(
                shown, 'A', 'Sell ALL',
                f'+${total}', (150, 245, 150), sell_all=True,
            )

            self._shop_footer.text = (
                'number = sell one    ·    A = sell all    ·    TAB / E'
            )
        else:
            for i, w in enumerate(weapons[:9]):
                if w['owned']:
                    price_text = 'OWNED'
                    price_rgb  = (160, 220, 170)
                    dim        = True
                elif w['affordable']:
                    price_text = f"${w['price']}"
                    price_rgb  = (150, 245, 150)
                    dim        = False
                else:
                    price_text = f"${w['price']}"
                    price_rgb  = (225, 105, 95)
                    dim        = False
                self._fill_row(i, w['key'], w['name'],
                               price_text, price_rgb, dim_name=dim)
            self._shop_footer.text = (
                'letter = buy    ·    TAB switches tab    ·    E closes'
            )

    def update(self, dt):
        # Hit flash (damage taken / generic)
        if self._hit_t > 0:
            self._hit_t -= dt
            a = int(min(1, self._hit_t / 0.14) * 100)
            self._hit_flash.color = color.rgba(self._hit_r, self._hit_g, self._hit_b, a)

        # Log fade
        for i, t in enumerate(self._log_timers):
            if t > 0:
                self._log_timers[i] -= dt
                a = min(230, int(self._log_timers[i] / 4.0 * 230))
                self._log_lines[i].color = color.rgba(255, 255, 200, a)
            else:
                self._log_lines[i].text = ''

        # Hit marker (white X)
        if self._hm_t > 0:
            self._hm_t -= dt
            a = int(min(1, self._hm_t / 0.18) * 230)
            c = color.rgba(255, 255, 255, a)
            self._hm_p1.color = c
            self._hm_p2.color = c
        else:
            self._hm_p1.color = color.rgba(0, 0, 0, 0)
            self._hm_p2.color = color.rgba(0, 0, 0, 0)

        # Kill marker (gold/red X — bigger, longer)
        if self._km_t > 0:
            self._km_t -= dt
            a = int(min(1, self._km_t / 0.50) * 255)
            r, g, b = self._km_color
            c = color.rgba(r, g, b, a)
            self._km_p1.color = c
            self._km_p2.color = c
        else:
            self._km_p1.color = color.rgba(0, 0, 0, 0)
            self._km_p2.color = color.rgba(0, 0, 0, 0)

        # Kill ribbon fade
        if self._kr_t > 0:
            self._kr_t -= dt
            a = int(min(1, self._kr_t / 2.6) * 250)
            self._kill_ribbon.color = color.rgba(255, 220, 100, a)
        else:
            self._kill_ribbon.text = ''
