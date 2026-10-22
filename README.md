# Lombok Holiday Mobile Client

Launcher/client SA-MP Mobile berbasis proyek open source SA-MP 2.10, disesuaikan untuk Lombok Holiday. Package name Android: `com.lombokholiday.mobile`.

## Fitur v2.2.0

- APK resmi terpisah untuk `arm64-v8a` dan `armeabi-v7a`, ditandatangani dengan keystore produksi dan R8.
- Dashboard lanskap dengan sidebar rounded, banner carousel otomatis, berita konfigurasi, dan menu Settings/Controls.
- Daftar server lokal: server resmi sudah disediakan, server domain/IPv4 dan port UDP lain dapat ditambahkan/dihapus dari aplikasi.
- Input sentuh hingga empat pointer, serta dukungan input keyboard fisik, mouse, dan gamepad dari fork sebelumnya.
- Preset FPS hemat/seimbang/maksimum dan pengaturan client yang dikenali oleh engine.
- Konfigurasi banner, berita, endpoint server resmi, dan URL data berada di [`data-config.json`](data-config.json).
- MonetLoader 3.8.0 opsional untuk Lua, dibangun dari source GPLv3 yang dipin; folder data disiapkan di `Android/media/com.lombokholiday.mobile/monetloader/`.

## Mod & kompatibilitas

MonetLoader bersifat opsional/eksperimental. Jalur dasar Lua disertakan; kompatibilitas API SA-MP di semua ABI dan script pihak ketiga belum diverifikasi. Instal script hanya dari sumber tepercaya.

Mod Center dapat menyalin CLEO Android `.csa`/`.csi` ke folder `Android/media/com.lombokholiday.mobile/cleo/sa/`, tetapi build ini **tidak menyertakan atau memverifikasi runtime CLEO**. File Windows `.dll` bukan format Android; plugin native Android harus berupa `.so` yang dibuat untuk ABI yang sesuai.

## Server & handshake

Launcher menulis host/port server terpilih ke `SAMP/settings.ini`. Handshake privat RPC 103 dengan secret produksi hanya dijawab untuk hostname/port Lombok Holiday resmi; server tambahan tidak menerima secret tersebut. Server kustom tetap dapat menolak client berdasarkan kebijakan/protokolnya sendiri. Filterscript produksi dibuat oleh `tools/lockdown.py` dari secret owner dan ditempatkan di direktori `dist` lokal/build; file template bertanda placeholder tidak untuk dikompilasi. Workflow rilis menolak build bila secret handshake tidak tersedia.

## Data game

Aplikasi mendukung download ZIP dan ekstraksi ke folder data tanpa OBB. Isi `data_lite.url` dan `data_full.url` di [`data-config.json`](data-config.json) dengan link ZIP langsung (https); nilai saat ini mengarah ke arsip data di Google Drive. URL kosong = tombol download nonaktif di launcher.

## Struktur sumber & build lokal

- `client-patch/ui-v21/` — **source of truth** UI launcher: `MainActivity.java.template`, `main_activity.xml.template`, `drawable/`, dan helper `AppLog.java`, `DataDownloadService.java`, `GameDataFixer.java`, `SidebarLayout.java`. Patch UI dilakukan di sini.
- `tools/lockdown.py` — patcher build: substitusi branding/host/port/cert, injeksi `lockdown.h` (git-ignored), XOR obfuscation, dan generator `dist/gate_client.pwn`. CI menjalankannya sebelum Gradle build; tree `app/` yang ter-commit disinkronkan dengan output pipeline ini (baseline default resmi).
- `server/gate_client.pwn` — template filterscript gate handshake dengan placeholder `__PROD_HANDSHAKE_KEY__` (jangan dikompilasi langsung; versi produksi digenerate ke `dist/` oleh `lockdown.py`).

Build lokal:

1. Pasang JDK 17, Android SDK 34, NDK `26.2.11394342`, dan CMake `3.22.1`.
2. Untuk meniru CI: `python3 tools/lockdown.py --repo . --host <host> --port <port> --key 0x<secret> --app-name "Lombok Holiday" --brand "Lombok Holiday Roleplay" --name Warga_Lombok --package-id com.lombokholiday.mobile --cert-sha256 <sha256>`.
3. `./gradlew assembleDebug` (atau `assembleRelease` dengan env `KEYSTORE_FILE`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD` untuk APK bertanda tangan resmi).

Jangan commit file `.env`/secret — sudah masuk `.gitignore`.

## Build resmi

Build rilis dilakukan lewat GitHub Actions pada repository publik ini. Workflow memverifikasi repository/actor dan keystore resmi, membangun MonetLoader dari revision yang dipin, lalu menandatangani APK ABI-split. Trigger rilis dengan tag `v*` hanya untuk owner `xykal`.

## Notifikasi lisensi

Lihat [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) untuk MonetLoader dan source revision yang dipakai. Proyek ini tidak berafiliasi dengan Rockstar Games, Take-Two Interactive, atau pemegang merek SA-MP.
