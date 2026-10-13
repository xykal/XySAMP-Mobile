#pragma once
// ============================================================================
//  lockdown.h — XySAMP Hardened Security & Server-Lock Suite (Dual-ABI 32/64)
//  - XOR Byte-Array Obfuscation (0 plaintext IP/Tag di strings libsamp.so)
//  - Runtime Anti-Tamper / Anti-Frida / Anti-Ptrace / Anti-GameGuardian
//  - Custom RPC 103 (ClientCheck) Challenge-Response Handshake
// ============================================================================

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace XySAMP {

static const uint8_t kEncHost[] = { 0x2A, 0x15, 0xF9, 0xCE, 0xF8, 0x99, 0x7B, 0x5E, 0x30, 0x1E, 0xFB, 0xC7, 0xA1, 0x81, 0x65, 0x4F, 0x2B, 0x10, 0xA6, 0xCA, 0xBF, 0xCB, 0x6D, 0x47, 0x00 };
static const size_t  kEncHostLen = 24;

static const uint8_t kEncTag[] = { 0xFF, 0x9F, 0xB6, 0x45, 0x6E, 0x12, 0x4C, 0xB1, 0xB1, 0x8E, 0x00 };
static const size_t  kEncTagLen = 10;

static const uint16_t kObfPort = 0x445D;
static const uint32_t kHandshakeSecret = (uint32_t)(0x9F4E7C2B);

static inline const char* GetLockedHost() {
    static char s_host[64] = {0};
    if (s_host[0] == '\0') {
        size_t n = (kEncHostLen < sizeof(s_host) - 1) ? kEncHostLen : (sizeof(s_host) - 1);
        for (size_t i = 0; i < n; ++i) {
            s_host[i] = (char)(kEncHost[i] ^ ((0x5A + i * 31) & 0xFF));
        }
        s_host[n] = '\0';
    }
    return s_host;
}

static inline int GetLockedPort() {
    return (int)((kObfPort ^ 0x5A3C) & 0xFFFF);
}

static inline const char* GetClientVersion() {
    static char s_tag[32] = {0};
    if (s_tag[0] == '\0') {
        size_t n = (kEncTagLen < sizeof(s_tag) - 1) ? kEncTagLen : (sizeof(s_tag) - 1);
        for (size_t i = 0; i < n; ++i) {
            s_tag[i] = (char)(kEncTag[i] ^ ((0xA7 + i * 31) & 0xFF));
        }
        s_tag[n] = '\0';
    }
    return s_tag;
}

static inline uint32_t GetHandshakeSecret() {
    return kHandshakeSecret;
}

static inline uint8_t CalcHandshakeResponse(uint32_t challenge, uint16_t offset, uint16_t count) {
    uint32_t x = (challenge ^ kHandshakeSecret) + (((uint32_t)offset << 16) | (uint32_t)count);
    x ^= (x >> 16);
    x *= 0x7FEB352Du;
    x ^= (x >> 15);
    return (uint8_t)(x & 0xFFu);
}

static inline bool IsRuntimeClean() {
    // 1. Cek TracerPid di /proc/self/status (deteksi ptrace / gdb / GameGuardian)
    FILE* fs = fopen("/proc/self/status", "r");
    if (fs) {
        char line[128];
        while (fgets(line, sizeof(line), fs)) {
            if (strncmp(line, "TracerPid:", 10) == 0) {
                int pid = atoi(line + 10);
                if (pid != 0) {
                    fclose(fs);
                    return false;
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
                strstr(line, "edxposed"))
            {
                fclose(fm);
                return false;
            }
        }
        fclose(fm);
    }

    // 3. Cek marker tamper dari verifikasi signature APK di Java
    FILE* ft = fopen("/storage/emulated/0/GTA/SAMP/.tampered", "rb");
    if (ft) {
        fclose(ft);
        return false;
    }

    return true;
}

} // namespace XySAMP
