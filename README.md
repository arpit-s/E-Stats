# E-Stats — Enhanced macOS System Monitor

<p align="center">
  <img src="Stats/Supporting%20Files/Assets.xcassets/AppIcon.appiconset/icon_256x256.png" width="120" alt="E-Stats Icon">
</p>

<p align="center">
  <strong>Open-source macOS menu bar monitor with kernel-level process tree grouping, headless application tracking, and accurate multi-process RAM aggregation.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Platform-macOS%2012%2B-lightgrey.svg" alt="Platform: macOS">
  <img src="https://img.shields.io/badge/Swift-6.0-orange.svg" alt="Language: Swift">
  <a href="https://github.com/exelban/stats"><img src="https://img.shields.io/badge/Forked%20From-exelban%2Fstats-brightgreen.svg" alt="Forked From: exelban/stats"></a>
</p>

---

> [!IMPORTANT]
> ### Upstream Credit & Attribution
> **E-Stats** is an enhanced, open-source fork of [Stats](https://github.com/exelban/stats) created and maintained by **[Serhiy Mytrovtsiy (@exelban)](https://github.com/exelban)**. All core monitoring architecture, UI design, and telemetry modules are copyright &copy; Serhiy Mytrovtsiy and distributed under the [MIT License](LICENSE).
> 
> We express our immense gratitude to Serhiy and all upstream contributors for building the foundation of this macOS system monitor.

---

## Overview

Modern web browsers (Google Chrome, Arc, Dia, Safari, Brave) and Electron applications distribute their workload across **30 to 50+ isolated child processes** (renderer tabs, GPU acceleration helpers, utility workers, and network services), each consuming 25 MB to 100 MB.

In standard system monitors, these small subprocesses fail to meet single-process thresholds and get pushed out of the top list by single-process daemons (like `WindowServer` or `Mail`). As a result, heavy 2GB+ browser sessions are often completely hidden.

**E-Stats solves this** by introducing low-level kernel inspection via `Darwin.libproc` (`proc_pidpath`), rolling up all child workers, background tabs, and headless instances into a single unified parent application entry with full-tree memory and CPU calculations.

---

## Key Enhancements in E-Stats

### 1. Kernel-Level Executable Inspection (`proc_pidpath`)
- **Limitation in upstream app**: Relies on `NSRunningApplication`, which returns `nil` for headless processes (e.g. Chrome headless, DevTools MCP automation, Puppeteer) and detached background workers.
- **E-Stats Solution**: Queries `proc_pidpath` directly from the kernel to discover the root `.app` bundle directory on disk (`Google Chrome.app`, `Dia.app`, `Safari.app`, `Visual Studio Code.app`, `Slack.app`, etc.), accurately identifying applications regardless of how they were launched.

### 2. Full Multi-Process RAM & CPU Tree Aggregation
- Automatically sums memory footprints and CPU utilization across all child tabs, GPU processes, and helper daemons before ranking.
- Accurately reports the true total resource consumption of multi-process applications in your menu bar popup.

### 3. Smart App Icon & Active PID Preservation
- When combining dozens of subprocesses, E-Stats dynamically preserves the principal PID with an active window and application icon, preventing apps from reverting to generic binary placeholders.

### 4. Crash-Resilient Architecture & Asset Preloading
- Replaced all forced unwraps (`!`) across device model lookups (`SystemKit.swift`), view controllers, and configuration loaders with safe optional bindings and fallback symbols.
- Added runtime asset preloading in `AppDelegate.main` to register all bundled Apple Silicon / Intel device illustrations (`macbookAir`, `macbookPro`, `imacPro`, `macMini`, `macStudio`, etc.) into `NSImage`'s runtime cache upon launch.

### 5. Zero-Dependency Standalone Build Pipeline
- Includes [`build_and_package.py`](build_and_package.py), allowing developers and users to build, link all 10 hardware modules, compile `.icns` icons, set `Info.plist` metadata, and codesign `Stats.app` directly with Apple Command Line Tools (**no full 12 GB Xcode.app required**).

---

## Hardware Metrics Monitored

E-Stats provides real-time telemetry directly from your menu bar:

- **CPU**: Per-core load, frequency, cluster distribution (Efficiency vs. Performance), and top active processes.
- **RAM**: Memory pressure level, app memory, wired kernel data, compressed cache, swap activity, and grouped process rankings.
- **GPU**: Core utilization, integrated/discrete graphics activity, and render engine load.
- **Disk**: Volume space, I/O read/write speeds, and SMART health telemetry.
- **Network**: Real-time upload/download throughput, Wi-Fi details, public/local IP, and per-process network usage.
- **Battery**: State of charge, health/cycle count, power draw, temperature, and time remaining.
- **Sensors**: Thermal zones, voltage, wattage, and fan speeds (via SMC).
- **Bluetooth**: Connected peripherals and battery levels (AirPods, keyboards, mice, trackpads).
- **Clock**: Multiple time zone clock widgets with calendar integration.

---

## Installation Guide

### Option 1: Quick Build & Install (Recommended)

Make sure you have Apple Command Line Tools installed (`xcode-select --install`):

```bash
# 1. Clone the repository
git clone https://github.com/arpit-s/E-Stats.git
cd E-Stats

# 2. Build and package the application
python3 build_and_package.py

# 3. Install to Applications and launch
rm -rf /Applications/Stats.app
cp -R build/Stats.app /Applications/Stats.app
open /Applications/Stats.app
```

### Option 2: Xcode Build

If you have full Xcode installed, open the project in Xcode:

```bash
open Stats.xcodeproj
```
Select the **Stats** scheme and press **Cmd + R** to build and run.

---

## Uninstallation Guide

To completely remove E-Stats and its associated preferences from your Mac:

```bash
# 1. Quit the application
killall Stats 2>/dev/null

# 2. Remove the application bundle
rm -rf /Applications/Stats.app

# 3. Remove user preferences, cache, and application support
rm -rf ~/Library/Application\ Support/Stats
rm -rf ~/Library/Preferences/eu.exelban.Stats.plist
rm -rf ~/Library/Caches/eu.exelban.Stats
rm -rf ~/Library/Saved\ Application\ State/eu.exelban.Stats.savedState
```

---

## Frequently Asked Questions (FAQ)

### Why didn't Google Chrome show up in my top RAM list previously?
Google Chrome divides its workload across dozens of small processes (each ~30 MB). Standard monitors only look at single-process memory, so individual Chrome tabs fell below the top process threshold. E-Stats inspects all running processes via kernel paths and rolls up all 30+ tabs into a single unified Google Chrome entry with full total memory.

### Does E-Stats collect any telemetry or personal data?
**No.** E-Stats runs 100% locally on your Mac. It contains zero analytics, tracking scripts, or telemetry collection.

### How do I configure process grouping in E-Stats?
1. Click the **Stats** menu bar icon and select **Preferences** (gear icon).
2. Navigate to the **RAM** section.
3. Toggle **Combined processes** ON to group child tabs under their parent applications.

### How do I reorder menu bar items?
Hold the **⌘ (Command)** key on your keyboard and drag any menu bar icon to your preferred position.

---

## License & Credits

- **License**: Distributed under the permissive [MIT License](LICENSE).
- **Original Project**: [Stats](https://github.com/exelban/stats) by [Serhiy Mytrovtsiy (@exelban)](https://github.com/exelban).
- **Enhanced Fork**: Maintained by [Arpit (@arpit-s)](https://github.com/arpit-s).
