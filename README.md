# Panopto Offline Captions

Download a Panopto recording, generate subtitles from the full video with
Whisper, and open the result in a normal video player.

## GUI

For non-technical users, start the graphical app and paste the Panopto link into
the window.

Windows:

```text
Double-click run-gui-windows.bat
```

macOS:

```text
Double-click run-gui-macos.command
```

Linux:

```bash
./run-gui-linux.sh
```

The GUI lets users choose the Panopto URL or an existing video file, output
folder, browser login source, and Whisper model. The first run can take a while
because it installs Python dependencies and downloads the model.

## Standalone App

For users who do not have Python installed, build a standalone app on each target
operating system. PyInstaller bundles Python and the application code into
`dist/`.

The build script creates its own `.venv-build` environment, so it does not
install packages into the system Python.

Windows:

```text
Double-click build-app-windows.bat
```

macOS/Linux:

```bash
./build-app-macos-linux.sh
```

Build separately on each platform: Windows apps on Windows, macOS apps on macOS,
and Linux apps on Linux.

## CLI

Linux/macOS:

```bash
python3 panopto-offline-captions.py '<panopto-url>'
```

Windows PowerShell:

```powershell
py panopto-offline-captions.py "https://..."
```

Use a better but slower model:

```bash
python3 panopto-offline-captions.py '<panopto-url>' --model small.en
```

Use an existing downloaded video:

```bash
python3 panopto-offline-captions.py ./lecture.mp4
```

Generate subtitles without opening a player:

```bash
python3 panopto-offline-captions.py '<panopto-url>' --no-play
```

If the Panopto login is in a different browser, pass it explicitly:

```bash
python3 panopto-offline-captions.py '<panopto-url>' --cookies-from-browser chrome
python3 panopto-offline-captions.py '<panopto-url>' --cookies-from-browser edge
python3 panopto-offline-captions.py '<panopto-url>' --cookies-from-browser firefox
python3 panopto-offline-captions.py '<panopto-url>' --cookies-from-browser vivaldi
```

On Windows, the default browser mode is `auto`. It tries common installed
browsers and Firefox profiles until Panopto accepts one:

```powershell
py panopto-offline-captions.py "https://..." --cookies-from-browser auto
```

On Windows, some Firefox/Panopto sessions do not save the actual Panopto login
cookie in Firefox's profile database. If browser cookies are extracted but
Panopto still says the video is only available for registered users, export a
cookies.txt file from the logged-in Panopto tab and pass it explicitly:

```powershell
py panopto-offline-captions.py "https://..." --cookies "C:\path\to\cookies.txt"
```

The GUI also has a "Cookies.txt file" field for the same workaround.
# panopto-captions
