// ============================================================================
//  gate_client.pwn  -  FILTERSCRIPT / INCLUDE GATE SERVER SA-MP
//  Fungsi: cuma izinin pemain yang pake APK client custom lu (Lapis 1 + 2 + 3).
//
//  Cara pakai (filterscript):
//      1. taruh di folder filterscripts/, compile pake pawno / compiler komunitas
//      2. tambahin di server.cfg:  filterscripts gate_client
//  Cara pakai (include di gamemode): #include "gate_client"
// ============================================================================

#include <a_samp>

#if !defined gpci
    native gpci(playerid, serial[], len);
#endif

#if !defined SendClientCheck
    native SendClientCheck(playerid, type, memAddr, memOffset, bytesCount);
#endif

forward OnClientCheckResponse(playerid, actionid, memaddr, retndata);

#if !defined isnull
    #define isnull(%1) ((!(%1[0])) || (((%1[0]) == '\1') && (!(%1[1]))))
#endif

// --- LAPIS 1: WAJIB sama persis dengan LOCK_CLIENT_TAG di client (maks 25 char)
#define CLIENT_TAG              "XYSAMP-1.0"

// --- LAPIS 2: CI serial (hasil gpci). Kosongin ("") kalau belum mau kunci serial
#define ALLOWED_CI_SERIAL       ""

// --- LAPIS 3: Handshake Challenge-Response (RPC_ClientCheck = 103) -----------
// Set ENABLE_HANDSHAKE 1 untuk wajibin verifikasi kriptografi ringan dari APK lu.
// HANDSHAKE_KEY wajib SAMA PERSIS dengan LOCK_HANDSHAKE_KEY di lockdown.h
#define ENABLE_HANDSHAKE        1
#define HANDSHAKE_ACTION        0x48
#define HANDSHAKE_KEY           0x00000000

// --- pesan tendang & grace period --------------------------------------------
#define KICK_WRONG_CLIENT       "Server ini cuma bisa dimasukin lewat APK client resmi."
#define KICK_NOT_VERIFIED       "Verifikasi APK gagal / timeout. Gunakan APK resmi versi terbaru."
#define VERIFY_TIMEOUT_MS       8000

new bool: g_Verified[MAX_PLAYERS];
new g_VerifyTimer[MAX_PLAYERS];
new g_KickTimer[MAX_PLAYERS];
new g_Challenge[MAX_PLAYERS];

stock Gate_DelayedKick(playerid, const reason[])
{
    SendClientMessage(playerid, 0xFF4444FF, reason);
    if (g_KickTimer[playerid] != 0) KillTimer(g_KickTimer[playerid]);
    g_KickTimer[playerid] = SetTimerEx("OnGateDelayedKick", 250, false, "i", playerid);
}

stock Gate_SendChallenge(playerid)
{
#if ENABLE_HANDSHAKE
    if (g_Challenge[playerid] == 0)
    {
        g_Challenge[playerid] = 0x10000000 + random(0x6FFFFFFF);
    }
    SendClientCheck(playerid, HANDSHAKE_ACTION, g_Challenge[playerid], 0, 4);
#endif
}

public OnFilterScriptInit()
{
    printf("[GATE] Client Gate aktif | Tag='%s' | Handshake=%d", CLIENT_TAG, ENABLE_HANDSHAKE);
    return 1;
}

public OnPlayerConnect(playerid)
{
    g_Verified[playerid] = false;
    g_VerifyTimer[playerid] = 0;
    g_KickTimer[playerid] = 0;
    g_Challenge[playerid] = 0;

    // ---- LAPIS 1: cek tag versi client yang dikirim saat join --------------
    new clientVersion[32];
    GetPlayerVersion(playerid, clientVersion, sizeof clientVersion);

    printf("[GATE] player %d join -> client version: '%s'", playerid, clientVersion);

    if (strlen(clientVersion) == 0 || strcmp(clientVersion, CLIENT_TAG, false) != 0)
    {
        Gate_DelayedKick(playerid, KICK_WRONG_CLIENT);
        return 1;
    }

    // ---- LAPIS 2 (opsional): cek CI serial ---------------------------------
    new ciSerial[41];
    gpci(playerid, ciSerial, sizeof ciSerial);
    printf("[GATE] player %d gpci serial: '%s'", playerid, ciSerial);

    if (!isnull(ALLOWED_CI_SERIAL))
    {
        if (strlen(ciSerial) == 0 || strcmp(ALLOWED_CI_SERIAL, ciSerial, true) != 0)
        {
            Gate_DelayedKick(playerid, "[GATE] Serial client kamu tidak dikenali.");
            return 1;
        }
    }

    // ---- LAPIS 3: Handshake Challenge-Response -----------------------------
#if ENABLE_HANDSHAKE
    Gate_SendChallenge(playerid);
    g_VerifyTimer[playerid] = SetTimerEx("OnVerifyTimeout", VERIFY_TIMEOUT_MS, false, "i", playerid);
#else
    g_Verified[playerid] = true;
#endif

    return 1;
}

public OnPlayerRequestClass(playerid, classid)
{
#if ENABLE_HANDSHAKE
    // Kirim ulang challenge saat class selection kalau paket awal belum nyampe
    if (!g_Verified[playerid] && g_Challenge[playerid] != 0)
    {
        SendClientCheck(playerid, HANDSHAKE_ACTION, g_Challenge[playerid], 0, 4);
    }
#endif
    return 1;
}

public OnClientCheckResponse(playerid, actionid, memaddr, retndata)
{
#if ENABLE_HANDSHAKE
    if (g_Verified[playerid]) return 1;
    if (actionid != HANDSHAKE_ACTION) return 1;

    new expectedAddr = g_Challenge[playerid] ^ HANDSHAKE_KEY;
    new expectedByte = ((expectedAddr ^ (expectedAddr >>> 8) ^ (expectedAddr >>> 16) ^ (expectedAddr >>> 24) ^ actionid) & 0xFF);

    if (memaddr == expectedAddr && (retndata & 0xFF) == expectedByte)
    {
        g_Verified[playerid] = true;
        if (g_VerifyTimer[playerid] != 0)
        {
            KillTimer(g_VerifyTimer[playerid]);
            g_VerifyTimer[playerid] = 0;
        }
        printf("[GATE] player %d LOLOS handshake Lapis 3 (addr=0x%x, crc=0x%x)", playerid, memaddr, retndata & 0xFF);
    }
    else
    {
        printf("[GATE] player %d GAGAL handshake Lapis 3! dapat=(0x%x, 0x%x) harusnya=(0x%x, 0x%x)",
            playerid, memaddr, retndata & 0xFF, expectedAddr, expectedByte);
        Gate_DelayedKick(playerid, KICK_NOT_VERIFIED);
    }
#endif
    return 1;
}

forward OnVerifyTimeout(playerid);
public OnVerifyTimeout(playerid)
{
    g_VerifyTimer[playerid] = 0;
    if (!IsPlayerConnected(playerid)) return 1;

    if (!g_Verified[playerid])
    {
        printf("[GATE] player %d timeout handshake Lapis 3 -> KICK", playerid);
        Gate_DelayedKick(playerid, KICK_NOT_VERIFIED);
    }
    return 1;
}

forward OnGateDelayedKick(playerid);
public OnGateDelayedKick(playerid)
{
    g_KickTimer[playerid] = 0;
    if (IsPlayerConnected(playerid))
    {
        Kick(playerid);
    }
    return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
    if (g_VerifyTimer[playerid] != 0)
    {
        KillTimer(g_VerifyTimer[playerid]);
        g_VerifyTimer[playerid] = 0;
    }
    if (g_KickTimer[playerid] != 0)
    {
        KillTimer(g_KickTimer[playerid]);
        g_KickTimer[playerid] = 0;
    }
    g_Verified[playerid] = false;
    g_Challenge[playerid] = 0;
    return 1;
}

public OnPlayerSpawn(playerid)
{
    if (!g_Verified[playerid])
    {
        Gate_DelayedKick(playerid, KICK_NOT_VERIFIED);
        return 0;
    }
    return 1;
}
