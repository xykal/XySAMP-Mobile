#pragma once
// ============================================================================
//  LOCKDOWN.H  -  konfigurasi client khusus (dikompilasi langsung ke binary)
//  Semua nilai di file ini nempel di APK. Pemain TIDAK bisa ganti lewat
//  settings.ini selama LOCK_ALLOW_INI_OVERRIDE = 0.
// ============================================================================

#include <sys/stat.h>
#include <cstdio>
#include <cstring>

// --- server tujuan (hardcoded) ----------------------------------------------
#define LOCK_SERVER_HOST        "play.xyverse.my.id"
#define LOCK_SERVER_PORT        7777
#define LOCK_PORT_STR           "7777"

// --- identitas client (Lapis 1) ---------------------------------------------
// LOCK_CLIENT_TAG dikirim ke server di paket join, server baca pake
// GetPlayerVersion(playerid, ...). MAKSIMAL 25 karakter.
#define LOCK_CLIENT_TAG         "XYSAMP-1.0"

// Nickname default kalau pemain belum pernah set nick sendiri di launcher.
// Jangan pakai spasi (SA-MP hanya izinkan A-Z, a-z, 0-9, _).
#define LOCK_CLIENT_NAME        "Warga_XyVerse"

// --- Handshake challenge-response (Lapis 3 - RPC_ClientCheck ID 103) --------
// WAJIB sama persis dengan HANDSHAKE_KEY di server/gate_client.pwn
#define LOCK_HANDSHAKE_ENABLE   1
#define LOCK_HANDSHAKE_ACTION   0x48
#define LOCK_HANDSHAKE_KEY      0x5A3C9E71

// 0 = host/port/version SELALU ditimpa nilai di atas (rekomendasi)
// 1 = ikutin settings.ini (buat debug doang)
#define LOCK_ALLOW_INI_OVERRIDE   0

// 1 = kalau settings.ini belum ada, client bikin sendiri otomatis
//     (biar APK-nya langsung jalan tanpa setup manual)
#define LOCK_GENERATE_DEFAULT_INI 1

// ============================================================================
//  Helper: sanitasi nickname (ubah spasi jadi underscore biar gak ditolak SA-MP)
// ============================================================================
static inline void Lockdown_SanitizeNick(char* nick, size_t maxLen)
{
    if (!nick || nick[0] == '\0') return;
    for (size_t i = 0; nick[i] != '\0' && i < maxLen; ++i) {
        if (nick[i] == ' ') {
            nick[i] = '_';
        }
    }
}

// ============================================================================
//  Helper: bikin settings.ini default kalau belum ada
// ============================================================================
#if LOCK_GENERATE_DEFAULT_INI
static inline void Lockdown_EnsureDefaultIni(const char* path)
{
    FILE* f = fopen(path, "rb");
    if (f) { fclose(f); return; }   // sudah ada, jangan diutak-atik

    mkdir("/storage/emulated/0/GTA", 0777);
    mkdir("/storage/emulated/0/GTA/SAMP", 0777);

    f = fopen(path, "wb");
    if (!f) { Log("LOCKDOWN: gagal bikin %s", path); return; }

    fputs("[client]\n"
          "name=" LOCK_CLIENT_NAME "\n"
          "host=" LOCK_SERVER_HOST "\n"
          "port=" LOCK_PORT_STR "\n"
          "password=\n"
          "version=" LOCK_CLIENT_TAG "\n"
          "autoaim=false\n"
          "\n[debug]\n"
          "debug=false\n"
          "online=true\n", f);

    fclose(f);
    Log("LOCKDOWN: settings.ini default dibuat (host=%s:%s)", LOCK_SERVER_HOST, LOCK_PORT_STR);
}
#endif
