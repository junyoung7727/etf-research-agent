#!/usr/bin/env bash
set -euo pipefail
mkdir -p artifacts
xcodebuild -version > artifacts/ios-xcode.txt
xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath ios-build CODE_SIGNING_ALLOWED=NO build > artifacts/ios-simulator-build.log 2>&1
xcrun simctl list devices available --json > artifacts/ios-devices.json
edge_simulator=$(python3 -c 'import json; x=json.load(open("artifacts/ios-devices.json")); print(next(d["udid"] for ds in x["devices"].values() for d in ds if "iPhone" in d["name"] and d["state"]=="Shutdown"))')
xcrun simctl boot "$edge_simulator"
xcrun simctl bootstatus "$edge_simulator" -b
xcrun simctl install "$edge_simulator" ios-build/Build/Products/Debug-iphonesimulator/App.app
xcrun simctl launch "$edge_simulator" com.marketbrew.edge > artifacts/ios-launch.txt
sleep 8
xcrun simctl io "$edge_simulator" screenshot artifacts/ios-onboarding.png
tar -czf artifacts/edge-ios-simulator.app.tar.gz -C ios-build/Build/Products/Debug-iphonesimulator App.app
