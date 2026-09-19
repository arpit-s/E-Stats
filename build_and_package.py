#!/usr/bin/env python3
import os
import shutil
import glob
import subprocess
import sys

PROJECT_ROOT = '/Users/arpit/Documents/projects/E-Stats'
BUILD_DIR = os.path.join(PROJECT_ROOT, 'build')
OBJ_DIR = os.path.join(BUILD_DIR, 'obj')
FRAMEWORKS_DIR = os.path.join(BUILD_DIR, 'Frameworks')
APP_DIR = os.path.join(BUILD_DIR, 'Stats.app')
CONTENTS_DIR = os.path.join(APP_DIR, 'Contents')
MACOS_DIR = os.path.join(CONTENTS_DIR, 'MacOS')
RESOURCES_DIR = os.path.join(CONTENTS_DIR, 'Resources')
APP_FRAMEWORKS_DIR = os.path.join(CONTENTS_DIR, 'Frameworks')

def run_cmd(cmd, desc):
    print(f"[*] {desc}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[-] FAILED: {desc}")
        print("STDERR:\n", res.stderr)
        if res.stdout:
            print("STDOUT:\n", res.stdout)
        sys.exit(1)
    return res

def main():
    os.makedirs(OBJ_DIR, exist_ok=True)
    os.makedirs(FRAMEWORKS_DIR, exist_ok=True)
    os.makedirs(MACOS_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)
    os.makedirs(APP_FRAMEWORKS_DIR, exist_ok=True)

    # 1. Compile lldb.m (ObjC++)
    run_cmd([
        'clang', '-x', 'objective-c++', '-stdlib=libc++', '-c',
        os.path.join(PROJECT_ROOT, 'Kit/lldb/lldb.m'),
        f'-I{PROJECT_ROOT}/Kit/lldb/include',
        f'-I{PROJECT_ROOT}/Kit/lldb',
        '-fmodules',
        '-o', os.path.join(OBJ_DIR, 'lldb.o')
    ], "Compiling Kit/lldb.m")

    # 2. Compile Kit
    kit_swifts = glob.glob(f'{PROJECT_ROOT}/Kit/**/*.swift', recursive=True)
    smc_swifts = [
        f'{PROJECT_ROOT}/SMC/smc.swift',
        f'{PROJECT_ROOT}/SMC/Helper/protocol.swift'
    ]
    kit_dylib = os.path.join(FRAMEWORKS_DIR, 'libKit.dylib')
    run_cmd([
        'swiftc',
        '-emit-module',
        '-emit-library',
        '-module-name', 'Kit',
        '-import-objc-header', f'{PROJECT_ROOT}/Kit/Supporting Files/Kit.h',
        f'-I{PROJECT_ROOT}/Kit/lldb',
        '-Xlinker', '-lc++',
        '-Xlinker', '-install_name', '-Xlinker', '@rpath/libKit.dylib',
        os.path.join(OBJ_DIR, 'lldb.o'),
        f'{PROJECT_ROOT}/Kit/lldb/libleveldb.a',
        '-o', kit_dylib
    ] + kit_swifts + smc_swifts, "Compiling Kit framework")

    # Copy Kit.swiftmodule to build dir for swift module resolution
    for ext in ['.swiftmodule', '.swiftdoc', '.swiftsourceinfo']:
        src = os.path.join(PROJECT_ROOT, 'Kit' + ext)
        if os.path.exists(src):
            shutil.move(src, os.path.join(FRAMEWORKS_DIR, 'Kit' + ext))

    # 3. Compile Sensors ObjC helper
    run_cmd([
        'clang', '-c',
        f'{PROJECT_ROOT}/Modules/Sensors/reader.m',
        f'-I{PROJECT_ROOT}/Modules/Sensors',
        '-fmodules',
        '-o', os.path.join(OBJ_DIR, 'sensors_reader.o')
    ], "Compiling Sensors/reader.m")

    # 4. Compile all modules
    modules = [
        ('RAM', None, ['-lKit']),
        ('CPU', f'{PROJECT_ROOT}/Modules/CPU/bridge.h', ['-lKit', '-framework', 'IOKit', '-lIOReport']),
        ('GPU', f'{PROJECT_ROOT}/Modules/GPU/bridge.h', ['-lKit', '-framework', 'IOKit', '-lIOReport']),
        ('Sensors', f'{PROJECT_ROOT}/Modules/Sensors/bridge.h', ['-lKit', '-framework', 'IOKit', '-lIOReport', os.path.join(OBJ_DIR, 'sensors_reader.o')]),
        ('Disk', f'{PROJECT_ROOT}/Modules/Disk/header.h', ['-lKit', '-framework', 'IOKit', '-framework', 'DiskArbitration']),
        ('Net', None, ['-lKit', '-framework', 'SystemConfiguration', '-framework', 'CoreWLAN']),
        ('Battery', None, ['-lKit', '-framework', 'IOKit']),
        ('Bluetooth', None, ['-lKit', '-framework', 'IOBluetooth']),
        ('Clock', None, ['-lKit']),
        ('Remote', None, ['-lKit'])
    ]

    for mod, header, extra_args in modules:
        swifts = glob.glob(f'{PROJECT_ROOT}/Modules/{mod}/*.swift')
        mod_dylib = os.path.join(FRAMEWORKS_DIR, f'lib{mod}.dylib')
        cmd = [
            'swiftc',
            '-emit-module',
            '-emit-library',
            '-module-name', mod,
            f'-I{FRAMEWORKS_DIR}',
            f'-L{FRAMEWORKS_DIR}',
            '-Xlinker', '-install_name', '-Xlinker', f'@rpath/lib{mod}.dylib',
            '-Xlinker', '-rpath', '-Xlinker', '@executable_path/../Frameworks',
            '-Xlinker', '-rpath', '-Xlinker', '@loader_path/../Frameworks',
            '-o', mod_dylib
        ]
        if header:
            cmd.extend(['-import-objc-header', header])
        cmd.extend(extra_args)
        cmd.extend(swifts)
        run_cmd(cmd, f"Compiling {mod} module")

        # Move module files
        for ext in ['.swiftmodule', '.swiftdoc', '.swiftsourceinfo']:
            src = os.path.join(PROJECT_ROOT, mod + ext)
            if os.path.exists(src):
                shutil.move(src, os.path.join(FRAMEWORKS_DIR, mod + ext))

    # 5. Fix dylib linkages with install_name_tool
    for dylib in glob.glob(f'{FRAMEWORKS_DIR}/*.dylib'):
        subprocess.run(['install_name_tool', '-id', f'@rpath/{os.path.basename(dylib)}', dylib], check=False)
        subprocess.run(['install_name_tool', '-change', kit_dylib, '@rpath/libKit.dylib', dylib], check=False)
        # Copy to App Frameworks directory
        shutil.copy2(dylib, APP_FRAMEWORKS_DIR)

    # 6. Compile Main Stats application binary
    stats_swifts = glob.glob(f'{PROJECT_ROOT}/Stats/*.swift') + glob.glob(f'{PROJECT_ROOT}/Stats/Views/*.swift')
    stats_bin = os.path.join(MACOS_DIR, 'Stats')
    run_cmd([
        'swiftc',
        f'-I{FRAMEWORKS_DIR}',
        f'-L{FRAMEWORKS_DIR}',
        '-lKit', '-lRAM', '-lCPU', '-lGPU', '-lDisk', '-lNet', '-lBattery', '-lBluetooth', '-lClock', '-lRemote', '-lSensors',
        '-Xlinker', '-rpath', '-Xlinker', '@executable_path/../Frameworks',
        '-o', stats_bin
    ] + stats_swifts, "Compiling Stats executable")

    # 7. Compile LaunchAtLogin
    launch_app_dir = os.path.join(CONTENTS_DIR, 'Library', 'LoginItems', 'LaunchAtLogin.app', 'Contents', 'MacOS')
    os.makedirs(launch_app_dir, exist_ok=True)
    run_cmd([
        'swiftc',
        f'{PROJECT_ROOT}/LaunchAtLogin/main.swift',
        '-o', os.path.join(launch_app_dir, 'LaunchAtLogin')
    ], "Compiling LaunchAtLogin")
    
    launch_plist = os.path.join(CONTENTS_DIR, 'Library', 'LoginItems', 'LaunchAtLogin.app', 'Contents', 'Info.plist')
    shutil.copy2(f'{PROJECT_ROOT}/LaunchAtLogin/Info.plist', launch_plist)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleName LaunchAtLogin', launch_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleIdentifier eu.exelban.Stats.LaunchAtLogin', launch_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleExecutable LaunchAtLogin', launch_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundlePackageType APPL', launch_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :LSMinimumSystemVersion 12.0', launch_plist], check=False)

    # 8. Copy Resources, Info.plist, configs, localizations
    target_plist = os.path.join(CONTENTS_DIR, 'Info.plist')
    shutil.copy2(f'{PROJECT_ROOT}/Stats/Supporting Files/Info.plist', target_plist)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleName Stats', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleIdentifier eu.exelban.Stats', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleExecutable Stats', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleShortVersionString 3.0.0', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :LSMinimumSystemVersion 12.0', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleDevelopmentRegion en', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Add :CFBundleIconFile string AppIcon', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleIconFile AppIcon', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Add :CFBundleIconName string AppIcon', target_plist], check=False)
    subprocess.run(['/usr/libexec/PlistBuddy', '-c', 'Set :CFBundleIconName AppIcon', target_plist], check=False)

    shutil.copy2(f'{PROJECT_ROOT}/Stats/Supporting Files/background.png', os.path.join(RESOURCES_DIR, 'background.png'))
    
    # Copy module config.plist files into Resources
    for mod_dir in glob.glob(f'{PROJECT_ROOT}/Modules/*'):
        cfg = os.path.join(mod_dir, 'config.plist')
        if os.path.exists(cfg):
            mod_name = os.path.basename(mod_dir)
            target_cfg_dir = os.path.join(RESOURCES_DIR, mod_name)
            os.makedirs(target_cfg_dir, exist_ok=True)
            shutil.copy2(cfg, os.path.join(target_cfg_dir, 'config.plist'))
            shutil.copy2(cfg, os.path.join(RESOURCES_DIR, f'{mod_name}.plist'))

    # Copy localization folders
    for lproj in glob.glob(f'{PROJECT_ROOT}/Stats/Supporting Files/*.lproj'):
        dst = os.path.join(RESOURCES_DIR, os.path.basename(lproj))
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(lproj, dst)

    # Build AppIcon.icns
    iconset_dir = os.path.join(BUILD_DIR, 'AppIcon.iconset')
    os.makedirs(iconset_dir, exist_ok=True)
    src_icon_dir = f'{PROJECT_ROOT}/Stats/Supporting Files/Assets.xcassets/AppIcon.appiconset'
    for f in os.listdir(src_icon_dir):
        if f.endswith('.png'):
            clean_name = f.replace(' 1', '')
            shutil.copy2(os.path.join(src_icon_dir, f), os.path.join(iconset_dir, clean_name))
            if f == 'icon_512x512.png':
                shutil.copy2(os.path.join(src_icon_dir, f), os.path.join(RESOURCES_DIR, 'AppIcon.png'))
    
    icns_path = os.path.join(RESOURCES_DIR, 'AppIcon.icns')
    res_icns = subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', icns_path], capture_output=True)
    if res_icns.returncode == 0:
        print("[+] Generated AppIcon.icns")

    # Copy all device and support image assets under both filename and imageset name
    for dirpath, _, filenames in os.walk(f'{PROJECT_ROOT}/Stats/Supporting Files/Assets.xcassets'):
        if '.imageset' in dirpath:
            imageset_name = os.path.basename(dirpath).replace('.imageset', '')
            for f in filenames:
                if f.endswith('.png'):
                    src_file = os.path.join(dirpath, f)
                    shutil.copy2(src_file, os.path.join(RESOURCES_DIR, f))
                    shutil.copy2(src_file, os.path.join(RESOURCES_DIR, f'{imageset_name}.png'))

    # 9. Codesign bundle
    run_cmd(['codesign', '--force', '--deep', '-s', '-', APP_DIR], "Codesigning Stats.app")

    print("\n[+] BUILD COMPLETED SUCCESSFULLY!")
    print(f"[+] Output: {APP_DIR}")

if __name__ == '__main__':
    main()
