# E-Stats: Enhanced Process Grouping & Memory Tracking

This is an enhanced fork of [Stats](https://github.com/exelban/stats) customized to support comprehensive parent-level process grouping and headless application tracking.

## What Was Modified

### 1. `Modules/RAM/readers.swift` (`ProcessReader`)
- **App Bundle Inspection (`proc_pidpath`)**: Instead of relying solely on `NSRunningApplication` (which returns `nil` for headless instances and background helper processes), the reader now queries `proc_pidpath` from `Darwin.libproc` to identify the parent `.app` bundle directory on disk.
- **Unified Grouping Key**: Process aggregation combines child workers, tabs, GPU processes, and renderer helpers into their canonical application group (`Google Chrome`, `Dia`, `Safari`, `Visual Studio Code`, `WhatsApp`, etc.).
- **PID Icon Resolution**: When grouping subprocesses, the main PID associated with an active window/application icon is preserved so the menu bar popup displays the correct app icon.

### 2. `Modules/CPU/readers.swift` (`ProcessReader`)
- Added `resolveAppName` and `proc_pidpath` bundle resolution to map CPU helper processes to their parent application names.

---

## Building

To build the project into a release `.app` bundle using Xcode:

```bash
cd ~/Documents/projects/E-Stats
xcodebuild -scheme "Stats" -configuration Release -destination 'platform=macOS' build CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO
```

Once built, copy the application to `/Applications`:
```bash
cp -R build/Release/Stats.app /Applications/Stats.app
```
