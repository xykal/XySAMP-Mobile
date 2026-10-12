# XySAMP Mobile — Private SA-MP Android Client & Server Gate (All-in-One)

Repository ini berisi source code lengkap **XySAMP Mobile** (basis `GTA-2.11` ARM64, 16KB page size support) yang sudah dimodifikasi khusus menjadi **client eksklusif satu server** lengkap dengan **filterscript Gate Server (`server/gate_client.pwn`)** dan **GitHub Actions Auto-Builder**.

---

## Fitur Utama yang Sudah Terpasang

1. **Lapis 1 — Hardcoded Server Lock & Tag (`app/src/main/cpp/samp/lockdown.h` & `settings.cpp`)**
   - Host/IP, Port, dan Client Version Tag (`XYSAMP-1.0`) dikunci langsung di level binary C++ (`libsamp.so`).
   - Walaupun pemain mengedit `/storage/emulated/0/GTA/SAMP/settings.ini`, client tetap memaksa koneksi ke server resmi dan mengirim tag resmi.
2. **Lapis 2 — Auto-Generate `settings.ini` (`Lockdown_EnsureDefaultIni`)**
   - Jika folder `/storage/emulated/0/GTA/SAMP/settings.ini` belum ada di HP pemain, client otomatis membuatnya saat pertama kali jalan (tidak crash seperti fork bawaan).
3. **Lapis 3 — Handshake Anti-Cloner (`RPC_ClientCheck` ID 103)**
   - Saat pemain join, server (`server/gate_client.pwn`) mengirim *challenge* 32-bit acak lewat `SendClientCheck`.
   - Client (`app/src/main/cpp/samp/net/netrpc.cpp`) otomatis membalas dengan `challenge ^ LOCK_HANDSHAKE_KEY` beserta *checksum byte*.
   - Client SA-MP lain (meskipun memalsukan tag versi) tidak bisa menjawab handshake ini dan akan otomatis di-kick dalam 8 detik.
4. **Input Nickname Langsung di Launcher (`MainActivity.java` & `main_activity.xml`)**
   - Pemain bisa langsung mengetik `Nama_Roleplay` di layar utama launcher sebelum menekan **START!**.
   - Otomatis mengubah spasi menjadi underscore (`_`), menyimpan ke `settings.ini`, dan seluruh pesan launcher sudah berbahasa Indonesia (tanpa telemetri Firebase pihak ketiga).
5. **Auto-Build & Auto-Sign via GitHub Actions (`.github/workflows/build-apk.yml`)**
   - Setiap push atau klik **Run workflow**, GitHub Actions otomatis meng-compile C++ NDK (`26.2.11394342`), menandatangani APK (`XySAMP-Mobile-release.apk`), dan membundelnya bersama `gate_client.pwn` yang sudah tersinkron.

---

## Cara Download APK & Gate Server dari GitHub Actions

1. Buka tab **[Actions](../../actions)** di repository ini.
2. Klik workflow run paling atas yang berstatus centang hijau (**Build SA-MP Mobile Private APK**).
3. Scroll ke bagian bawah (**Artifacts**), lalu download **`Paket-SAMP-Mobile-Client-dan-Server-Gate`**.
4. Di dalam zip tersebut sudah tersedia:
   - `XySAMP-Mobile-release.apk` — APK rilis yang **sudah di-sign**, siap dibagikan ke pemain.
   - `XySAMP-Mobile-debug.apk` — APK debug untuk testing.
   - `gate_client.pwn` — Script gate server SA-MP yang `CLIENT_TAG` dan `HANDSHAKE_KEY`-nya sudah sama persis dengan APK tersebut.
   - `release.keystore` & `release.keystore.base64.txt` — Kunci signature APK (simpan jika ingin dipakai permanen di GitHub Secrets `KEYSTORE_BASE64`).

---

## Cara Ganti IP / Domain / Port / Nama Server Tanpa Ngoding (Lewat Web GitHub)

Kamu bisa langsung mengganti IP server, Port, Tag, atau Nama Aplikasi langsung dari browser:

1. Buka tab **[Actions](../../actions)** → klik workflow **Build SA-MP Mobile Private APK** di panel kiri.
2. Klik tombol **Run workflow** (di sebelah kanan).
3. Isi kolom yang tersedia:
   - **IP / Domain Server SA-MP**: contoh `play.xyverse.my.id` atau IP VPS `103.xxx.xxx.xxx`
   - **Port UDP Server SA-MP**: contoh `7777`
   - **Tag Versi Client**: contoh `XYSAMP-1.0` (maks 25 karakter)
   - **Nickname default**: contoh `Warga_XyVerse`
   - **Kunci Handshake Lapis 3**: contoh `0x5A3C9E71`
   - **Nama Aplikasi di HP**: contoh `XySAMP Mobile`
   - **Nama Brand / Server di Launcher**: contoh `XyVerse Roleplay`
4. Klik tombol hijau **Run workflow**.
5. Tunggu ±10–15 menit sampai selesai, lalu download **Artifact**-nya. Baik `XySAMP-Mobile-release.apk` maupun `gate_client.pwn` di dalam artifact sudah otomatis memakai konfigurasi baru tersebut!

---

## Cara Pasang `gate_client.pwn` di Server SA-MP

1. Ambil file `server/gate_client.pwn` (dari repo ini atau dari zip Artifact hasil build).
2. Masukkan ke folder `filterscripts/gate_client.pwn` di server SA-MP kamu.
3. Compile menggunakan Pawno / `pawncc` menjadi `filterscripts/gate_client.amx`.
4. Tambahkan `gate_client` pada baris `filterscripts` di `server.cfg`:
   ```ini
   filterscripts gate_client
   ```
5. Restart server SA-MP kamu. Semua pemain yang masuk tanpa APK resmi **XySAMP Mobile** akan otomatis ditolak.
