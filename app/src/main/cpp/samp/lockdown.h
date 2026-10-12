#pragma once
// ============================================================================
//  LOCKDOWN.H  -  Security & Server Lock (XOR-Obfuscated + Anti-Tamper)
//  Semua string sensitif (host, tag, default nick) di-encode XOR byte array
//  supaya TIDAK muncul di `strings libsamp.so` atau hex editor (MT Manager).
// ============================================================================

#include <sys/stat.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

// --- server port & handshake config -----------------------------------------
#define LOCK_SERVER_PORT        @PORT@
#define LOCK_PORT_STR           "@PORT@"

// --- Handshake challenge-response (Lapis 3 - RPC_ClientCheck ID 103) --------
#define LOCK_HANDSHAKE_ENABLE   1
#define LOCK_HANDSHAKE_ACTION   0x48
#define LOCK_HANDSHAKE_KEY      @KEY@

// 0 = host/port/version SELALU ditimpa nilai terkunci (rekomendasi)
#define LOCK_ALLOW_INI_OVERRIDE   0
#define LOCK_GENERATE_DEFAULT_INI 1

// --- XOR-Encoded Byte Arrays (Anti-Strings / Anti-HexEdit) ------------------
// Key rolling: plain[i] = enc[i] ^ ((@XOR_SEED@ + i * 37) & 0xFF)
#define LOCK_XOR_SEED           @XOR_SEED@

static const uint8_t kLockEncHost[] = { @ENC_HOST_BYTES@ };
static const size_t  kLockEncHostLen = @ENC_HOST_LEN@;

static const uint8_t kLockEncTag[]  = { @ENC_TAG_BYTES@ };
static const size_t  kLockEncTagLen = @ENC_TAG_LEN@;

static const uint8_t kLockEncName[] = { @ENC_NAME_BYTES@ };
static const size_t  kLockEncNameLen = @ENC_NAME_LEN@;

static inline void Lockdown_XorDecode(const uint8_t* enc, size_t len, char* out, size_t maxOut)
{
    if (!out || maxOut == 0) return;
    size_t n = (len < maxOut - 1) ? len : (maxOut - 1);
    for (size_t i = 0; i < n; ++i) {
        uint8_t mask = (uint8_t)((LOCK_XOR_SEED + i * 37u) & 0xFFu);
        out[i] = (char)(enc[i] ^ mask);
    }
    out[n] = '\0';
}

static inline void Lockdown_DecodeHost(char* out, size_t maxOut)
{
    Lockdown_XorDecode(kLockEncHost, kLockEncHostLen, out, maxOut);
}

static inline void Lockdown_DecodeTag(char* out, size_t maxOut)
{
    Lockdown_XorDecode(kLockEncTag, kLockEncTagLen, out, maxOut);
}

static inline void Lockdown_DecodeName(char* out, size_t maxOut)
{
    Lockdown_XorDecode(kLockEncName, kLockEncNameLen, out, maxOut);
}

// ============================================================================
//  Runtime Anti-Tamper / Anti-Frida / Anti-Ptrace / Anti-GameGuardian
// ============================================================================
static inline bool Lockdown_IsTampered()
{
    // 1. Cek TracerPid di /proc/self/status (deteksi ptrace / gdb / GameGuardian)
    FILE* fs = fopen("/proc/self/status", "r");
    if (fs) {
        char line[128];
        while (fgets(line, sizeof(line), fs)) {
            if (strncmp(line, "TracerPid:", 10) == 0) {
                int pid = atoi(line + 10);
                if (pid != 0) {
                    fclose(fs);
                    return true;
                }
                break;
            }
        }
        fclose(fs);
    }

    // 2. Cek library inject / hook di /proc/self/maps (Frida / Xposed / Substrate)
    FILE* fm = fopen("/proc/self/maps", "r");
    if (fm) {
        char line[512];
        while (fgets(line, sizeof(line), fm)) {
            if (strstr(line, "frida") ||
                strstr(line, "gum-js-loop") ||
                strstr(line, "libsubstrate") ||
                strstr(line, "XposedBridge") ||
                strstr(line, "edxposed") ||
                strstr(line, "lspd"))
            {
                fclose(fm);
                return true;
            }
        }
        fclose(fm);
    }

    // 3. Cek marker tamper dari verifikasi signature APK di Java
    FILE* ft = fopen("/storage/emulated/0/GTA/SAMP/.tampered", "rb");
    if (ft) {
        fclose(ft);
        return true;
    }

    return false;
}

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
//  Helper: bikin settings.ini default kalau belum ada (tanpa bocorin tag)
// ============================================================================
#if LOCK_GENERATE_DEFAULT_INI
static inline void Lockdown_EnsureDefaultIni(const char* path)
{
    FILE* f = fopen(path, "rb");
    if (f) { fclose(f); return; }

    mkdir("/storage/emulated/0/GTA", 0777);
    mkdir("/storage/emulated/0/GTA/SAMP", 0777);

    f = fopen(path, "wb");
    if (!f) return;

    char defNick[32];
    Lockdown_DecodeName(defNick, sizeof(defNick));

    // Jangan tulis host/tag asli ke settings.ini supaya tidak bisa diintip user
    fprintf(f,
            "[client]\n"
            "name=%s\n"
            "host=127.0.0.1\n"
            "port=" LOCK_PORT_STR "\n"
            "password=\n"
            "version=0.3.7\n"
            "autoaim=false\n"
            "\n[debug]\n"
            "debug=false\n"
            "online=true\n",
            defNick);

    fclose(f);
}
#endif
