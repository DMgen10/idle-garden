# Changelog

All notable changes to Idle Garden are listed here, newest first.

## 0.5.0 — seasons, wind, birds and butterflies

- 🍂 Seasons, from today's date: fresh greens in spring, deep greens in summer,
  yellow, orange and red leaves that fall and pile up on the ground in autumn
  (early autumn is still mostly green, late autumn half bare), and a half-bare tree with snow on its leaves,
  bullfinches and falling snow in winter. The southern half of the world is detected from the time zone.
  Force one with `season = spring|summer|autumn|winter` or `--season`.
- 🌬️ Wind: gusts roll across the screen, ruffle the leaves and blow falling leaves and snow sideways (`wind = false` to turn off).
- 🐦 Birds fly in, sit on a branch or peck at the ground for a while and fly off; at night they rarely come.
- 🦋 Butterflies flutter about on spring and summer days and sometimes settle on a leaf.
  `animals = false` or `--no-animals` to turn both off.
- 🔎 `--check` also shows which season and hemisphere are used.

## 0.4.0 — light theme and Windows

- 🌗 Light and dark themes. By default the tree follows the system setting (Ubuntu *Appearance → Style*,
  Windows *Colors → App mode*) and picks it up the next time it appears, no restart needed.
  Force one with `theme = dark|light` in the settings or `--theme`.
- 🪟 Windows 10 / 11: `IdleGarden.exe` in every release — run it once and it installs itself for the current user
  (starts at login, Start menu entries, no admin rights). Or `irm …/install.ps1 | iex` in PowerShell.
- 🖥️ Windows: every monitor, sharp on high-DPI screens, stays away while a video keeps the display on.
- 🐛 Colours like `#101010` in `config.ini` were read as comments; they work now.
- ⚙️ `background` is now `dark_background` / `light_background` (the old name still works for the dark theme).

## 0.3.0 — first public release

- 🌳 A tree grows from a small patch of earth in the middle of the screen: a tall trunk first, then a crown.
- 🐌 Slow, uneven growth: every branch has its own pace and rests; growth comes in spurts. ~40 minutes to fill the screen.
- 🌿 Hanging vines, ivy climbing the trunk, creepers on the ground and curly tendrils.
- 🎲 Every tree is different: trunk height and lean, lopsided crowns, gnarled branches.
- 🍃 After the screen is overgrown, new leaves keep unfolding among the old ones.
- 🖥️ Works on GNOME (Wayland and X11) and other X11 desktops, one window per monitor.
- 🎬 Stays away while a video or a call keeps the system awake.
- 💻 Terminal mode: `idle-garden --terminal`.
- 📦 Install with apt (`.deb` in every release) or a one-line script; starts automatically after login; `man idle-garden`.
