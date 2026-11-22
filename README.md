<div align="center">

# 🌱 Idle Garden

**Step away from your computer — and an ASCII tree slowly grows over your screen.**<br>
Move the mouse or press any key, and it's gone.

<img src="docs/demo.gif" alt="An ASCII tree growing from a sprout until it fills the screen" width="760">

<sub>A 40-minute growth sped up to about 14 seconds. Every tree is different.</sub>

<br><br>

[![Tests](https://github.com/DMgen10/idle-garden/actions/workflows/tests.yml/badge.svg)](https://github.com/DMgen10/idle-garden/actions/workflows/tests.yml)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04%2B-E95420?logo=ubuntu&logoColor=white)](#-requirements)
[![Wayland & X11](https://img.shields.io/badge/Wayland%20%26%20X11-supported-4caf50)](#-how-it-works)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)](#-requirements)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**[Install](#-install) · [Try without installing](#-try-it-first) · [Settings](#%EF%B8%8F-settings) · [Русская версия](README.ru.md)**

</div>

---

Most screensavers just go black. **Idle Garden** turns the time you're away into something to come back to:
a sprout pushes out of a little patch of earth, stretches into a trunk, branches out, gets tangled in ivy —
and, if you stay away long enough, swallows the whole screen in leaves.

## ✨ Features

- 🌳 **A real tree, not a loop.** Trunk, crown, gnarled branches, hanging vines and ivy climbing the trunk —
  generated from scratch every time, so you never see the same tree twice.
- 🐌 **Grows slowly and unevenly**, like a living thing: some branches race ahead, others rest and catch up later,
  growth comes in spurts and lulls. About 40 minutes to overgrow the screen (configurable).
- 🍃 **Stays alive.** Once the screen is covered, fresh bright leaves keep unfolding among the old dark ones.
- 🖱️ **Gone instantly** on any mouse movement, click, scroll or key press. It never locks your session.
- 🎬 **Polite.** Doesn't start while you watch a video or sit in a call.
- 🖥️ **Every monitor** gets its own tree.
- 🪶 **Tiny.** Pure Python, no pip packages — it uses the GTK that already ships with Ubuntu.
- 💻 **Bonus:** grow a tree right in your terminal with `idle-garden --terminal`.

## 👀 Try it first

No installation needed — this only runs it once from the downloaded folder:

```bash
git clone https://github.com/DMgen10/idle-garden.git
cd idle-garden
python3 -m idle_garden --preview -g 2     # a whole tree in 2 minutes, fullscreen
python3 -m idle_garden --terminal -g 2    # …or inside the terminal
```

## 🚀 Install

**Ubuntu / Debian / Mint / Pop!_OS** — like any other program, with apt:

```bash
wget https://github.com/DMgen10/idle-garden/releases/latest/download/idle-garden.deb
sudo apt install ./idle-garden.deb
idle-garden --restart        # start now (otherwise it starts at your next login)
```

**Any other Linux, no sudo** — installs into your home folder only:

```bash
curl -fsSL https://raw.githubusercontent.com/DMgen10/idle-garden/main/install.sh | bash
```

That's it. Leave the computer alone for **2 minutes** and the first sprout appears.
`man idle-garden` and `idle-garden --help` list everything it can do.

## 🎮 Usage

| Command | What it does |
|---|---|
| `idle-garden --preview` | Show the tree right now (move the mouse to close) |
| `idle-garden --preview -g 2` | …growing in 2 minutes instead of 40 |
| `idle-garden --terminal` | Grow a tree in the current terminal |
| `idle-garden --restart` | Restart the background app (after changing settings) |
| `idle-garden --stop` | Stop it until the next login |
| `idle-garden --check` | Check that idle detection works on your desktop |

There is also an **Idle Garden** entry in the app menu that opens a preview.

## ⚙️ Settings

Edit `~/.config/idle-garden/config.ini`, then run `idle-garden --restart`.

| Option | Default | Meaning |
|---|---|---|
| `timeout` | `120` | Seconds without input before the sprout appears |
| `grow_minutes` | `40` | Minutes until the tree fills the whole screen |
| `font` / `font_size` | `Monospace` / `18` | Font of the ASCII art (bigger font = bigger leaves) |
| `background` | `#000000` | Background colour |
| `respect_inhibit` | `true` | Don't start while a video/call keeps the system awake |
| `keep_screen_on` | `false` | Stop Ubuntu from blanking the monitor while the tree is shown |

> 💡 Ubuntu turns the screen off after 5 minutes by default (*Settings → Power → Screen Blank*).
> Make that longer, or set `keep_screen_on = true`, to watch the tree overgrow the screen.

## 🔧 How it works

- **Idle time** comes from GNOME's `org.gnome.Mutter.IdleMonitor` over D-Bus, so it works on both Wayland and X11.
  Other X11 desktops fall back to the XScreenSaver extension or `xprintidle`.
- When you've been idle for `timeout` seconds, a borderless fullscreen GTK window opens on every monitor.
- The tree's shape comes from the **space colonization** algorithm: thousands of points are scattered over
  the screen (some in clumps, so every crown is lopsided its own way) and the branches grow towards them.
  Each branch gets its own vigour and resting periods; vines and ivy are curly random walks on top.
- Every character gets a birth time; the tree is revealed character by character, young leaves bright, old ones dark.
- The moment your idle time drops, the windows close. It is **not** a screen locker.

## ❓ FAQ

**Will it lock my screen or hide my work?** No. It's just a window on top; your session stays exactly as it was.

**Does it start during YouTube / Zoom?** No — apps that keep the system awake also keep Idle Garden away
(turn off with `respect_inhibit = false`).

**KDE / Sway / other Wayland desktops?** Not yet: there is no common way to read idle time there. PRs welcome!

**How do I remove it?** If you installed the `.deb`: `sudo apt remove idle-garden`.
If you used the script: `curl -fsSL https://raw.githubusercontent.com/DMgen10/idle-garden/main/uninstall.sh | bash`
(add `-s -- --purge` to delete settings too).

## 📋 Requirements

- Ubuntu 20.04+ (or another Linux with GNOME, or any X11 desktop)
- Python 3.8+ and GTK 3 bindings — preinstalled on Ubuntu Desktop, otherwise:
  `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0`

## 🤝 Contributing

Ideas, bug reports and PRs are welcome. The tree lives in [`idle_garden/plants.py`](idle_garden/plants.py) —
pure Python with no GUI, so it's easy to play with:

```bash
python3 -m unittest discover -s tests -t .   # tests
python3 -m idle_garden --terminal -g 1       # quick look
python3 tools/make_demo_gif.py               # regenerate docs/demo.gif (needs Pillow)
bash packaging/build_deb.sh                  # build dist/idle-garden.deb
```

Releases are automatic: bump `__version__` in `idle_garden/__init__.py`, add a section on top of `CHANGELOG.md`
and push to `main` — GitHub Actions tags the version, builds the `.deb` and publishes the release.

If you enjoy it, a ⭐ helps other people find it.

## 📄 License

[MIT](LICENSE)
