#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Android Build Automator for Debian 12
Builds APK from modified Telegram source
"""

import os
import sys
import subprocess
import shutil
import argparse
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
DEFAULT_PROJECT_DIR = "/home/lentum/telegram-client/Telegram"
DEFAULT_OUTPUT_DIR = "/home/lentum/telegram-client/output"
DEFAULT_KEYSTORE = "/home/lentum/telegram-client/telegram.keystore"

_ANDROID_SDK_DIR = os.path.expanduser("~/Android/Sdk")

# ============================================================
# COLORS FOR OUTPUT
# ============================================================
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def info(msg):    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")
def success(msg): print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")
def warn(msg):    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")
def error(msg):   print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")
def step(num, msg): print(f"\n{Colors.BOLD}{Colors.CYAN}[{num}/8]{Colors.RESET} {Colors.BOLD}{msg}{Colors.RESET}")

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def run(cmd, cwd=None, check=True, capture=False, input_text=None):
    """Run shell command with live output"""
    info(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

    if capture:
        result = subprocess.run(
            cmd, shell=isinstance(cmd, str), cwd=cwd,
            capture_output=True, text=True, input=input_text
        )
        if check and result.returncode != 0:
            error(f"Command failed: {result.stderr}")
            sys.exit(1)
        return result

    result = subprocess.run(
        cmd, shell=isinstance(cmd, str), cwd=cwd,
        input=input_text, text=True if input_text else None
    )
    if check and result.returncode != 0:
        error("Command failed!")
        sys.exit(1)
    return result

def check_command(cmd):
    """Check if command exists in PATH"""
    return shutil.which(cmd) is not None

# ============================================================
# STEP 1: CHECK PREREQUISITES
# ============================================================
def check_prerequisites():
    step(1, "Checking prerequisites")

    required = {
        "java": "OpenJDK 17",
        "git": "Git",
        "python3": "Python 3",
    }

    missing = []
    for cmd, name in required.items():
        if check_command(cmd):
            success(f"{name} found")
        else:
            missing.append(name)
            error(f"{name} NOT found")

    sdk_dir = _ANDROID_SDK_DIR
    if os.path.isdir(sdk_dir):
        success(f"Android SDK found at {sdk_dir}")
    else:
        warn(f"Android SDK not found at {sdk_dir}")
        alternatives = [
            "/usr/lib/android-sdk",
            "/opt/android-sdk",
            os.path.expanduser("~/android-sdk"),
        ]
        for alt in alternatives:
            if os.path.isdir(alt):
                sdk_dir = alt
                success(f"Found Android SDK at alternative path: {alt}")
                break
        else:
            missing.append("Android SDK")
            error("Android SDK not found.")

    sdkmanager = None
    sdkmanager_paths = [
        os.path.join(sdk_dir, "cmdline-tools", "latest", "bin", "sdkmanager"),
        os.path.join(sdk_dir, "cmdline-tools", "bin", "sdkmanager"),
    ]
    for path in sdkmanager_paths:
        if os.path.isfile(path):
            sdkmanager = path
            success(f"sdkmanager found: {path}")
            break

    if missing:
        error("Missing prerequisites. Install them and retry.")
        sys.exit(1)

    result = run("java -version", capture=True, check=False)
    java_output = result.stderr or result.stdout
    if "17" in java_output or "21" in java_output:
        success(f"Java version OK")
    else:
        warn(f"Java version may be incompatible. Recommended: OpenJDK 17")

    return sdk_dir, sdkmanager

# ============================================================
# STEP 2: ACCEPT ANDROID SDK LICENSES
# ============================================================
def accept_licenses(sdk_dir, sdkmanager):
    step(2, "Accepting Android SDK licenses")

    if sdkmanager and os.path.isfile(sdkmanager):
        info("Accepting licenses via sdkmanager...")
        result = subprocess.run(
            [sdkmanager, "--licenses"],
            input="y\n" * 20,
            text=True,
            capture_output=True
        )
        if result.returncode == 0:
            success("Licenses accepted via sdkmanager")
            return

    licenses_dir = os.path.join(sdk_dir, "licenses")
    os.makedirs(licenses_dir, exist_ok=True)

    licenses = {
        "android-sdk-license": [
            "24333f8a63b6825ea9c5514f83c2829b004d1fee",
            "84831b9409646a918e30573bab4c9c91346d8abd",
            "d56f5187479451eabf01fb78af6dfcb131a6481e",
        ],
        "android-sdk-preview-license": ["84831b9409646a918e30573bab4c9c91346d8abd"],
    }

    for filename, hashes in licenses.items():
        filepath = os.path.join(licenses_dir, filename)
        with open(filepath, "w") as f:
            for h in hashes:
                f.write(h + "\n")
        info(f"Created license file: {filename}")

    success("License files created manually")

# ============================================================
# STEP 3: VERIFY PROJECT STRUCTURE
# ============================================================
def verify_project(project_dir, sdk_dir):
    step(3, "Verifying project structure")

    required_files = [
        "build.gradle",
        "settings.gradle",
        "TMessagesProj/build.gradle",
    ]

    for rel_path in required_files:
        full_path = os.path.join(project_dir, rel_path)
        if os.path.isfile(full_path):
            success(f"Found: {rel_path}")
        else:
            error(f"Missing: {rel_path}")
            sys.exit(1)

    local_props = os.path.join(project_dir, "local.properties")
    if not os.path.isfile(local_props):
        warn("local.properties not found, creating...")
        ndk_dir = os.path.join(sdk_dir, "ndk")
        ndk_version = None
        if os.path.isdir(ndk_dir):
            versions = [d for d in os.listdir(ndk_dir) if os.path.isdir(os.path.join(ndk_dir, d))]
            if versions:
                ndk_version = sorted(versions)[-1]

        with open(local_props, "w") as f:
            f.write(f"sdk.dir={sdk_dir}\n")
            if ndk_version:
                f.write(f"ndk.dir={ndk_dir}/{ndk_version}\n")
        success(f"Created local.properties")
    else:
        success("local.properties exists")

    return local_props

# ============================================================
# STEP 4: CHECK BUILD TOOLS
# ============================================================
def check_build_tools(sdk_dir, sdkmanager):
    step(4, "Checking build tools and NDK")

    gradlew = os.path.join(DEFAULT_PROJECT_DIR, "gradlew")
    if os.path.isfile(gradlew):
        os.chmod(gradlew, 0o755)
        success("gradlew is executable")
    else:
        warn("gradlew not found.")

    ndk_dir = os.path.join(sdk_dir, "ndk")
    if os.path.isdir(ndk_dir):
        versions = [d for d in os.listdir(ndk_dir) if os.path.isdir(os.path.join(ndk_dir, d))]
        if versions:
            success(f"NDK found: {', '.join(versions)}")
        else:
            warn("NDK directory exists but no versions found")
    else:
        warn("NDK not found. Gradle will auto-download it.")

# ============================================================
# STEP 5: CLEAN PREVIOUS BUILDS
# ============================================================
def clean_build(project_dir):
    step(5, "Cleaning previous builds")

    gradlew = os.path.join(project_dir, "gradlew")
    if os.path.isfile(gradlew):
        run([gradlew, "clean"], cwd=project_dir, check=False)
        success("Gradle clean completed")

    build_dirs = [
        os.path.join(project_dir, "TMessagesProj", "build"),
        os.path.join(project_dir, "build"),
    ]
    for d in build_dirs:
        if os.path.isdir(d):
            shutil.rmtree(d)
            info(f"Removed: {d}")

# ============================================================
# STEP 6: BUILD APK
# ============================================================
def build_apk(project_dir, build_type, sdk_dir):
    step(6, f"Building {build_type} APK")

    gradlew = os.path.join(project_dir, "gradlew")
    if not os.path.isfile(gradlew):
        error("gradlew not found!")
        sys.exit(1)

    os.chmod(gradlew, 0o755)

    env = os.environ.copy()
    env["ANDROID_SDK_ROOT"] = sdk_dir
    env["ANDROID_HOME"] = sdk_dir

    gradle_args = [
        gradlew,
        f"assemble{build_type.capitalize()}",
        "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx6g",
        "-Dorg.gradle.parallel=true",
    ]

    if build_type == "release":
        gradle_args.append("-Pandroid.injected.signing.store.file=" + DEFAULT_KEYSTORE)

    info(f"Starting build: {' '.join(gradle_args)}")

    result = subprocess.run(gradle_args, cwd=project_dir, env=env)

    if result.returncode != 0:
        error("Build failed!")
        sys.exit(1)

    success("Build completed successfully!")

# ============================================================
# STEP 7: LOCATE AND COPY OUTPUT APK
# ============================================================
def collect_output(project_dir, output_dir, build_type):
    step(7, "Collecting output APK")

    os.makedirs(output_dir, exist_ok=True)

    # Search ALL possible APK locations in the project
    possible_paths = [
        # Modern AGP paths with flavors
        os.path.join(project_dir, "TMessagesProj_App", "build", "outputs", "apk"),
        os.path.join(project_dir, "TMessagesProj_AppHockeyApp", "build", "outputs", "apk"),
        os.path.join(project_dir, "TMessagesProj_AppStandalone", "build", "outputs", "apk"),
        os.path.join(project_dir, "TMessagesProj_AppHuawei", "build", "outputs", "apk"),
        os.path.join(project_dir, "TMessagesProj_AppTests", "build", "outputs", "apk"),
        # Legacy paths
        os.path.join(project_dir, "TMessagesProj", "build", "outputs", "apk"),
        os.path.join(project_dir, "build", "outputs", "apk"),
    ]

    apks = []
    for base_path in possible_paths:
        if os.path.isdir(base_path):
            for root, dirs, files in os.walk(base_path):
                for f in files:
                    if f.endswith(".apk"):
                        apks.append(os.path.join(root, f))

    if not apks:
        # Also check for AAB files
        aab_paths = [
            os.path.join(project_dir, "TMessagesProj_App", "build", "outputs", "bundle"),
            os.path.join(project_dir, "TMessagesProj", "build", "outputs", "bundle"),
        ]
        aabs = []
        for base_path in aab_paths:
            if os.path.isdir(base_path):
                for root, dirs, files in os.walk(base_path):
                    for f in files:
                        if f.endswith(".aab"):
                            aabs.append(os.path.join(root, f))

        if aabs:
            warn("No APK found, but AAB files exist:")
            for aab in aabs:
                print(f"  {aab}")
            print("\nTo convert AAB to APK, use bundletool:")
            print("  bundletool build-apks --bundle=app.aab --output=app.apks")

        error("No APK files found after build!")
        sys.exit(1)

    # Sort by modification time, take latest
    apks.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collected = []

    for apk_path in apks:
        apk_name = os.path.basename(apk_path)
        name, ext = os.path.splitext(apk_name)
        new_name = f"{name}_{timestamp}{ext}"
        dest = os.path.join(output_dir, new_name)

        shutil.copy2(apk_path, dest)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        success(f"Copied: {apk_name} -> {new_name} ({size_mb:.1f} MB)")
        collected.append(dest)

    return collected

# ============================================================
# STEP 8: VERIFY APK
# ============================================================
def verify_apk(apk_paths, sdk_dir):
    step(8, "Verifying APK")

    for apk_path in apk_paths:
        if not os.path.isfile(apk_path):
            error(f"APK not found: {apk_path}")
            continue

        aapt2 = None
        build_tools = os.path.join(sdk_dir, "build-tools")
        if os.path.isdir(build_tools):
            for root, dirs, files in os.walk(build_tools):
                if "aapt2" in files:
                    aapt2 = os.path.join(root, "aapt2")
                    break

        if aapt2 and os.path.isfile(aapt2):
            result = run([aapt2, "dump", "badging", apk_path], capture=True, check=False)
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                for line in lines[:5]:
                    if line.strip():
                        info(line.strip())
                success("APK verification passed")
            else:
                warn("aapt2 verification failed, but APK exists")
        else:
            warn("aapt2 not found, skipping verification")

        size = os.path.getsize(apk_path)
        info(f"Size: {size / (1024*1024):.2f} MB")
        info(f"Path: {apk_path}")

# ============================================================
# CREATE KEYSTORE
# ============================================================
def create_keystore():
    if os.path.isfile(DEFAULT_KEYSTORE):
        return

    warn(f"Keystore not found at {DEFAULT_KEYSTORE}")
    print(f"\n{Colors.BOLD}Create keystore for release builds?{Colors.RESET}")
    response = input("(y/n): ").lower().strip()

    if response == 'y':
        os.makedirs(os.path.dirname(DEFAULT_KEYSTORE), exist_ok=True)
        cmd = [
            "keytool", "-genkey", "-v",
            "-keystore", DEFAULT_KEYSTORE,
            "-alias", "telegram",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000"
        ]
        run(cmd)
        success(f"Keystore created: {DEFAULT_KEYSTORE}")
    else:
        warn("Release builds will fail without keystore. Use --build-type debug")

# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Build Telegram Android APK from source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Build debug APK with defaults
  %(prog)s --release                # Build signed release APK
  %(prog)s --project /custom/path   # Use different project directory
  %(prog)s --clean                  # Clean before build
        """
    )
    parser.add_argument("--project", "-p", default=DEFAULT_PROJECT_DIR,
                        help=f"Project directory (default: {DEFAULT_PROJECT_DIR})")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_DIR,
                        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--build-type", "-t", choices=["debug", "release"], default="debug",
                        help="Build type: debug or release (default: debug)")
    parser.add_argument("--clean", "-c", action="store_true",
                        help="Clean before build")
    parser.add_argument("--keystore", "-k", default=DEFAULT_KEYSTORE,
                        help=f"Keystore path for release builds (default: {DEFAULT_KEYSTORE})")
    parser.add_argument("--skip-checks", action="store_true",
                        help="Skip prerequisite checks")
    parser.add_argument("--skip-licenses", action="store_true",
                        help="Skip SDK license acceptance")

    args = parser.parse_args()

    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     Telegram Android Build Automator for Debian 12           ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")

    info(f"Project:  {args.project}")
    info(f"Output:   {args.output}")
    info(f"Type:     {args.build_type}")

    if not os.path.isdir(args.project):
        error(f"Project directory does not exist: {args.project}")
        sys.exit(1)

    if not args.skip_checks:
        sdk_dir, sdkmanager = check_prerequisites()
    else:
        sdk_dir = _ANDROID_SDK_DIR
        sdkmanager = None
        warn("Skipping prerequisite checks")

    if not args.skip_licenses:
        accept_licenses(sdk_dir, sdkmanager)
    else:
        warn("Skipping license acceptance")

    verify_project(args.project, sdk_dir)

    if not args.skip_checks:
        check_build_tools(sdk_dir, sdkmanager)

    if args.build_type == "release":
        create_keystore()

    if args.clean:
        clean_build(args.project)

    build_apk(args.project, args.build_type, sdk_dir)

    apks = collect_output(args.project, args.output, args.build_type)

    verify_apk(apks, sdk_dir)

    print(f"\n{Colors.BOLD}{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}  BUILD COMPLETE!{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.RESET}")
    for apk in apks:
        print(f"  📦 {Colors.CYAN}{apk}{Colors.RESET}")
    print(f"\n  Install on device:")
    print(f"    adb install {apks[0]}")
    print()

if __name__ == "__main__":
    main()