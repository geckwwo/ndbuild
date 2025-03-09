#!/usr/bin/python3
import sys
import pathlib
import json
import subprocess
import os
import time
import glob

ver = 1

def cmd(*x):
    process = subprocess.Popen(x, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(stdout, file=sys.stdout)
        print(stderr, file=sys.stderr)
        print("Exiting.", file=sys.stderr)
        exit(1)

def make_project():
    if os.path.exists("ndbuild.json"):
        print("Project already exists!")
        exit(1)
    print("Project name?")
    projname = input("> ")
    print("Package name?")
    pkg = input("> ")
    print("Keystore password? (6 characters min)")
    keypass = input("> ")
    print("Target Java version? [default: 1.8]")
    javaver = input("> ") or "1.8"
    print("Target Android SDK version? [default: 35]")
    sdkver = input("> ") or "35"
    print("Creating stuff...")
    
    os.makedirs("src/" + pkg.replace(".", "/"), exist_ok=True)
    os.makedirs("res/layout/", exist_ok=True)
    os.makedirs("signing/", exist_ok=True)
    open("AndroidManifest.xml", "w").write(f"""<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{pkg}">
    <application
        android:allowBackup="true"
        android:label="{projname}">

        <activity android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""")
    open("ndbuild.json", "w").write(f"""{{
    "android_sdk_path": "/home/geckwwo/Android/Sdk",
    "java_target": "{javaver}",
    "sdk_target": "{sdkver}",
    "sdk_ver": "{sdkver}.0.0"
}}""")
    open("src/"+ pkg.replace(".", "/") + "/MainActivity.java", "w").write(f"""package {pkg};

import android.app.Activity;
import android.os.Bundle;

public class MainActivity extends Activity {{
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
    }}
}}
""")
    open("res/layout/activity_main.xml", "w").write("""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical">

    <TextView
        android:id="@+id/textView"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Hello, World!" />
</LinearLayout>""")
    print("Generating keystore...")
    os.system(f"keytool -genkeypair -v -keystore signing/keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias mainkey -storepass \"{keypass}\"")

    open("signing/storepass.txt", "w").write(keypass)
    print("Finished.")

def build_proj():
    print(f"ndbuild v{ver}, @geckwwo 2025")
    start_time = time.time()
    if not os.path.exists("ndbuild.json"):
        print("Project does not exist!")
        exit(1)
    cfg = json.loads(open("ndbuild.json").read())
    
    cmd("rm", "-rf", "classes")
    cmd("rm", "-rf", "dexed")
    cmd("rm", "-rf", "build")
    os.makedirs("classes", exist_ok=True)
    os.makedirs("dexed", exist_ok=True)
    os.makedirs("build", exist_ok=True)
    print("Packing resources with aapt...")
    cmd(str((pathlib.Path(cfg["android_sdk_path"]) / "build-tools" / cfg["sdk_ver"] / "aapt").absolute()), "package",
        "-f", "-m", "-J", "src",
        "-M", "AndroidManifest.xml",
        "-S", "res",
        "-I", str((pathlib.Path(cfg["android_sdk_path"]) / "platforms" / f"android-{cfg['sdk_target']}" / "android.jar").absolute()),
        "-F", "build/unsigned.apk")
    print("Compiling with javac...")
    cmd("javac",
        "-source", cfg["java_target"],
        "-target", cfg["java_target"],
        "-bootclasspath", str((pathlib.Path(cfg["android_sdk_path"]) / "platforms" / f"android-{cfg['sdk_target']}" / "android.jar")),
        "-d", "classes",
        *glob.glob("src/**/*.java", recursive=True))
    print("Translating into dex with d8...")
    cmd(str((pathlib.Path(cfg["android_sdk_path"]) / "build-tools" / cfg["sdk_ver"] / "d8").absolute()),
        "--output", "dexed",
        *glob.glob("classes/**/*.class", recursive=True))
    print("Packing into APK with aapt...")
    cmd(str((pathlib.Path(cfg["android_sdk_path"]) / "build-tools" / cfg["sdk_ver"] / "aapt").absolute()), "add",
        "-k",
        "build/unsigned.apk",
        *glob.glob("dexed/**/*.dex", recursive=True))
    print("Signing...")
    cmd(str((pathlib.Path(cfg["android_sdk_path"]) / "build-tools" / cfg["sdk_ver"] / "apksigner").absolute()), "sign",
        "--ks", "signing/keystore.jks",
        "--out", "build/final.apk",
        "--ks-pass", "file:signing/storepass.txt",
        "build/unsigned.apk")
    print("Done! Built in", round(time.time() - start_time, 2), "second(s)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: python3 {sys.argv[0]} [subcommand]")
        print("commands:")
        print("  new - creates new project in current dir")
        print("  build - builds current project")
        print("  checkupdate - checks for ndbuild updates")
        exit(1)
    
    if sys.argv[1] == "new":
        make_project()
    elif sys.argv[1] == "build":
        build_proj()
    elif sys.argv[1] == "checkupdate":
        try:
            import requests
        except ImportError:
            print("Could not import `requests` module to check updates.")
            print("Install it with pip or your system's package manager.")
            exit(1)
        
        try:
            resp = requests.get("https://raw.githubusercontent.com/geckwwo/ndbuild/refs/heads/version/latest-version")
            resp.raise_for_status()
            latest = json.loads(resp.text)
        except Exception as e:
            print("Could not check updates:", e)
            exit(1)
        
        if latest["ver"] > ver:
            print("There is a new update available.")
            print("Changes:")
            for l in latest["changes"].split("\n"):
                print(f"  {l}")
            print("Get ndbuild from GitHub: https://github.com/geckwwo/ndbuild")
        else:
            print("No updates available.")
    else:
        print("Unknown subcommand!")
        exit(1)