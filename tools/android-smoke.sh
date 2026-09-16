#!/usr/bin/env bash
set -euo pipefail
mkdir -p artifacts
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -W -n com.marketbrew.edge/.MainActivity
sleep 8
adb shell pidof com.marketbrew.edge > artifacts/android-process.txt
adb shell uiautomator dump /sdcard/edge-window.xml
adb pull /sdcard/edge-window.xml artifacts/android-window.xml
adb exec-out screencap -p > artifacts/android-onboarding.png
adb logcat -d -s Capacitor/Console AndroidRuntime > artifacts/android-runtime.log
if grep -q 'FATAL EXCEPTION' artifacts/android-runtime.log; then exit 1; fi
test -s artifacts/android-process.txt
