# Third-party notices — Lombok Holiday v2.1.0

## MonetLoader 3.8.0

This app can optionally package and load MonetLoader, a Lua script loader for GTA: San Andreas / SA-MP on Android.

- Upstream source: https://github.com/xefinity/MonetLoaderOSS
- Pinned source revision used by GitHub Actions: `9fa9fdb305634e6012734e7e10c38bb9bff2a9cd`
- License: GNU General Public License v3.0 (GPL-3.0-only)
- The corresponding source for the exact build is available at: https://github.com/xefinity/MonetLoaderOSS/tree/9fa9fdb305634e6012734e7e10c38bb9bff2a9cd
- A copy of the GPL-3.0 license is included in the app assets as `MonetLoader-GPL-3.0.txt`.

MonetLoader is optional and experimental in this client. GTA-side Lua support is enabled; SA-MP-specific compatibility is not verified across both ABIs. Mod scripts can execute code and should only be installed from trusted sources.

The launcher can copy CLEO Android `.csa` / `.csi` files into a user-visible folder, but this build does **not** include or verify a CLEO runtime. Windows `.dll` files are not Android libraries; Android native plugins must be built as compatible `.so` libraries for the relevant ABI.

## Material Design Icons (Pictogrammers)
Icon navigasi, aksi, dan notifikasi di `client-patch/ui-v21/drawable/ic_*.xml` berasal dari
Material Design Icons (https://github.com/Templarian/MaterialDesign), dilisensikan Apache License 2.0.
