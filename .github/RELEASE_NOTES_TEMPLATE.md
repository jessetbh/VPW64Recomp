<!-- Fill in the changelog, delete this comment, then publish the draft. -->
## Changes

- TODO changelog bullets

## Notes

- **No game assets are included.** You must supply your own Virtual Pro Wrestling 64
  (Japan) ROM — SHA1 `F9E9FA2ED819C3A39DB5CB6AFECA186F021DB5ED`. On first launch,
  click **Load ROM** and select it; the launcher validates and remembers it.
- **The game is in Japanese** (Japan-only release); the port's own menus are in
  English. See the README FAQ.
- **Windows SmartScreen**: the exe is unsigned, so Windows may warn on first run.
  Click "More info" → "Run anyway".
- **Saves and settings** live in `%LOCALAPPDATA%\Vpw64Recompiled\`. Save data is
  compatible across releases unless a release note says otherwise. For a portable
  install, create an empty `portable.txt` next to the exe.
- **GPU**: D3D12 by default. If you hit rendering issues, update your GPU drivers
  first, and please attach `%LOCALAPPDATA%\Vpw64Recompiled\Vpw64Recompiled.log`
  to any bug report.
- Known issues are tracked in the README.
