// ============================================================================
// gate_client.pwn — Filterscript Verifikasi Client Khusus (Lombok Holiday Roleplay)
// ============================================================================
// Taruh di folder `filterscripts/gate_client.pwn`, compile dengan `pawncc`,
// lalu tambahkan `gate_client` ke baris `filterscripts` di `server.cfg`.
// ============================================================================

#include <a_samp>

#define REQUIRED_CLIENT_TAG     "LOMBOKHOLIDAY-2.1"
// Generated production value is injected by tools/lockdown.py; do not publish it.
#define HANDSHAKE_KEY           (__PROD_HANDSHAKE_KEY__)
#define RPC_CLIENT_CHECK        (103)
#define CHECK_TYPE_HANDSHAKE    (0x48)

new bool:g_PlayerVerified[MAX_PLAYERS];
new g_PlayerChallenge[MAX_PLAYERS];
new g_VerifyTimer[MAX_PLAYERS];

forward VerifyClientTimeout(playerid);

stock CalcExpectedHandshake(challenge, offset, count)
{
    new x = (challenge ^ HANDSHAKE_KEY) + ((offset << 16) | count);
    x ^= (x >>> 16);
    x = x * 0x7FEB352D;
    x ^= (x >>> 15);
    return (x & 0xFF);
}

public OnFilterScriptInit()
{
    print("====================================================");
    print(" [Lombok Holiday Roleplay] Client Lockdown Gate Loaded ");
    print(" Required Client Tag : " REQUIRED_CLIENT_TAG);
    print("====================================================");
    return 1;
}

public OnPlayerConnect(playerid)
{
    // Bersihkan timer verifikasi pemain sebelumnya yang masih menggantung di slot ini
    if (g_VerifyTimer[playerid] != 0)
    {
        KillTimer(g_VerifyTimer[playerid]);
        g_VerifyTimer[playerid] = 0;
    }
    g_PlayerVerified[playerid] = false;
    g_PlayerChallenge[playerid] = 0;

    new version[32];
    GetPlayerVersion(playerid, version, sizeof(version));

    if (strcmp(version, REQUIRED_CLIENT_TAG, false) != 0)
    {
        SendClientMessage(playerid, 0xFF3333FF, "[SERVER] Anda wajib menggunakan APK Resmi Lombok Holiday Roleplay!");
        SetTimerEx("DelayedKick", 350, false, "i", playerid);
        return 1;
    }

    new challenge = (random(0x7FFF) << 16) | random(0xFFFF);
    g_PlayerChallenge[playerid] = challenge;

    SendClientCheck(playerid, CHECK_TYPE_HANDSHAKE, challenge, 0x10, 0x04);
    g_VerifyTimer[playerid] = SetTimerEx("VerifyClientTimeout", 6000, false, "i", playerid);
    return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
    if (g_VerifyTimer[playerid] != 0)
    {
        KillTimer(g_VerifyTimer[playerid]);
        g_VerifyTimer[playerid] = 0;
    }
    g_PlayerVerified[playerid] = false;
    g_PlayerChallenge[playerid] = 0;
    return 1;
}

public OnClientCheckResponse(playerid, actionid, memaddr, retndata)
{
    if (actionid == CHECK_TYPE_HANDSHAKE)
    {
        new expectedEcho = g_PlayerChallenge[playerid] ^ HANDSHAKE_KEY;
        new expectedRet  = CalcExpectedHandshake(g_PlayerChallenge[playerid], 0x10, 0x04);

        if (memaddr == expectedEcho && retndata == expectedRet)
        {
            g_PlayerVerified[playerid] = true;
            if (g_VerifyTimer[playerid] != 0)
            {
                KillTimer(g_VerifyTimer[playerid]);
                g_VerifyTimer[playerid] = 0;
            }
            SendClientMessage(playerid, 0x33FF66FF, "[SERVER] Verifikasi APK Resmi Lombok Holiday Roleplay berhasil.");
        }
        else
        {
            SendClientMessage(playerid, 0xFF3333FF, "[SERVER] Verifikasi keamanan APK gagal! Gunakan launcher resmi.");
            SetTimerEx("DelayedKick", 350, false, "i", playerid);
        }
    }
    return 1;
}

public VerifyClientTimeout(playerid)
{
    g_VerifyTimer[playerid] = 0;
    if (IsPlayerConnected(playerid) && !g_PlayerVerified[playerid])
    {
        SendClientMessage(playerid, 0xFF3333FF, "[SERVER] Handshake client timeout! Gunakan APK Resmi Lombok Holiday Roleplay.");
        Kick(playerid);
    }
    return 1;
}

forward DelayedKick(playerid);
public DelayedKick(playerid)
{
    if (IsPlayerConnected(playerid)) Kick(playerid);
    return 1;
}
