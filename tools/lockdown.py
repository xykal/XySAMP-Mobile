#!/usr/bin/env python3
"""
lockdown.py — Hardened Server-Lock & Zero-Blackscreen Patcher untuk XySAMP-Mobile (Dual-ABI: armeabi-v7a + arm64-v8a)
--------------------------------------------------------------------------------------------------------------------
Fitur:
  1. Dual-ABI (armeabi-v7a 32-bit + arm64-v8a 64-bit) berbasis engine GTA-2.10 (libGTASA.so).
  2. Support All Data (Data Lite maupun Data Full, 100% TANPA OBB) dengan Smart Multi-Path Data Auto-Detector:
     - /storage/emulated/0/GTA/
     - /storage/emulated/0/Android/data/com.samp.mobile/files/
     - /storage/emulated/0/Android/data/com.gta.game/files/
     - /storage/emulated/0/Android/data/ro.alyn_sampmobile.game/files/
     - /storage/emulated/0/Android/data/ru.unisamp_mobile.game/files/
     - /storage/emulated/0/Android/data/com.rockstargames.gtasa/files/
  3. Zero-Blackscreen Guarantee:
     - NvFOpen InlineHook dengan Case-Insensitive Path Resolver + SAMP->data fallback + APK assets fallback (NvFOpen_orig).
     - Auto-Detect & Per-File GPU Texture Format Fallback (DXT / ETC / PVR / UNC) untuk semua jenis Data Lite & GPU.
     - Self-Healing Font & Settings Provisioning (otomatis ekstrak arial.ttf & arial_bold.ttf jika belum ada, plus fallback ImGui default font).
     - Penghapusan std::terminate() di settings.cpp & gwpAsanMode di AndroidManifest.xml.
  4. Hardened Security:
     - XOR Byte-Array Obfuscation di libsamp.so (0 plaintext IP/Tag di strings binary & DEX).
     - R8 Code Shrinking & Obfuscation + Native Symbol Stripping.
     - Official Release Keystore SHA-256 Certificate Pinning + Anti-Frida/Ptrace/GameGuardian + RPC_ClientCheck (ID 103).
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "client-patch" / "lockdown.h.template"


def parse_args():
    p = argparse.ArgumentParser(description="Lock SA-MP Mobile client (Dual-ABI + Zero-Blackscreen) to a single server.")
    p.add_argument("--repo", required=True, help="Path ke clone SAMP-Mobile")
    p.add_argument("--host", required=True, help="IP atau hostname server SA-MP")
    p.add_argument("--port", required=True, type=int, help="Port UDP server SA-MP")
    p.add_argument("--tag", default="XYSAMP-1.0", help="Custom client version tag (maks 24 char)")
    p.add_argument("--key", default="0xA55A9F3D", help="32-bit hex key untuk handshake")
    p.add_argument("--app-name", default="XySAMP Mobile", help="Nama aplikasi Android")
    p.add_argument("--server-title", "--brand", dest="server_title", default="XyVerse Roleplay", help="Nama server di tampilan launcher")
    p.add_argument("--default-nick", "--name", dest="default_nick", default="Warga_XyVerse", help="Default nickname jika user belum mengisi")
    p.add_argument("--cert-sha256", default="93fa85c2c42e17125bb66adbeab49fa3ccfcee646429aeb5078bdc322ea9341c",
                   help="SHA-256 fingerprint sertifikat Official Keystore (hex lowercase tanpa titik dua)")
    p.add_argument("--strip-firebase", action="store_true", help="Kompatibilitas flag workflow")
    return p.parse_args()


def encode_xor_bytes(text: str, key: int) -> tuple[str, int]:
    raw = text.encode("utf-8")
    enc = [((b ^ ((key + i * 31) & 0xFF)) & 0xFF) for i, b in enumerate(raw)]
    enc.append(0x00)
    hex_list = ", ".join(f"0x{b:02X}" for b in enc)
    return hex_list, len(raw)


def write_lockdown_header(samp_dir: Path, args):
    tpl_path = TEMPLATE
    if not tpl_path.exists():
        tpl_path = Path(args.repo).resolve() / "client-patch" / "lockdown.h.template"
    content = tpl_path.read_text(encoding="utf-8")

    host_bytes, host_len = encode_xor_bytes(args.host, 0x5A)
    tag_bytes, tag_len = encode_xor_bytes(args.tag, 0xA7)
    port_obf = (int(args.port) ^ 0x5A3C) & 0xFFFF

    content = content.replace("__HOST_XOR_BYTES__", host_bytes)
    content = content.replace("__HOST_LEN__", str(host_len))
    content = content.replace("__PORT_OBF__", f"0x{port_obf:04X}")
    content = content.replace("__TAG_XOR_BYTES__", tag_bytes)
    content = content.replace("__TAG_LEN__", str(tag_len))
    content = content.replace("__HANDSHAKE_SECRET__", args.key)

    out = samp_dir / "lockdown.h"
    out.write_text(content, encoding="utf-8")
    print(f"[+] Wrote XOR-obfuscated {out} (0 plaintext IP/Tag strings)")


def patch_linux_case_sensitivity(samp_dir: Path):
    # 1. gui/gui.h: samp_widgets/playerTabList.h -> samp_widgets/playertablist.h
    gui_h = samp_dir / "gui" / "gui.h"
    if gui_h.exists():
        txt = gui_h.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace("samp_widgets/playerTabList.h", "samp_widgets/playertablist.h")
        gui_h.write_text(txt, encoding="utf-8")

    # 2. game/rgba.cpp: RGBA.h -> rgba.h
    rgba_cpp = samp_dir / "game" / "rgba.cpp"
    if rgba_cpp.exists():
        txt = rgba_cpp.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace('#include "RGBA.h"', '#include "rgba.h"')
        rgba_cpp.write_text(txt, encoding="utf-8")

    # 3. voice_new/Network.h: ../vendor/RakNet/ -> ../vendor/raknet/
    net_h = samp_dir / "voice_new" / "Network.h"
    if net_h.exists():
        txt = net_h.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace("../vendor/RakNet/", "../vendor/raknet/")
        net_h.write_text(txt, encoding="utf-8")

    # 4. main.h: FONT_NAME "arial_bold.ttf" -> "arial.ttf"
    main_h = samp_dir / "main.h"
    if main_h.exists():
        txt = main_h.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace('#define FONT_NAME "arial_bold.ttf"', '#define FONT_NAME "arial.ttf"')
        main_h.write_text(txt, encoding="utf-8")

    print("[+] Fixed Linux header case-sensitivity & FONT_NAME in C++ sources")


def patch_cmake_strip(samp_dir: Path):
    cmake = samp_dir / "CMakeLists.txt"
    if not cmake.exists():
        return
    txt = cmake.read_text(encoding="utf-8", errors="ignore")
    new_txt = txt.replace("-w -s -g -fvisibility=hidden", "-w -s -fvisibility=hidden -fvisibility-inlines-hidden")
    if new_txt != txt:
        cmake.write_text(new_txt, encoding="utf-8")
        print(f"[+] Patched {cmake} (removed -g debug flag, enforced symbol stripping)")


def patch_main_cpp(samp_dir: Path):
    main_cpp = samp_dir / "main.cpp"
    txt = main_cpp.read_text(encoding="utf-8", errors="ignore")

    if '#include "lockdown.h"' not in txt:
        txt = '#include "lockdown.h"\n' + txt

    pattern = re.compile(r'pNetGame\s*=\s*new\s+CNetGame\s*\([^;]+\)\s*;')
    replacement = (
        'pNetGame = new CNetGame(\n'
        '            XySAMP::GetLockedHost(),\n'
        '            XySAMP::GetLockedPort(),\n'
        '            pSettings->Get().szNickName,\n'
        '            pSettings->Get().szPassword);'
    )
    new_txt, count = pattern.subn(replacement, txt)
    if count == 0:
        raise RuntimeError("Gagal menemukan inisialisasi CNetGame di main.cpp")

    main_cpp.write_text(new_txt, encoding="utf-8")
    print(f"[+] Patched {main_cpp} ({count} CNetGame site locked)")


def patch_netgame_cpp(samp_dir: Path):
    netgame_cpp = samp_dir / "net" / "netgame.cpp"
    txt = netgame_cpp.read_text(encoding="utf-8", errors="ignore")

    if '#include "../lockdown.h"' not in txt:
        txt = '#include "../lockdown.h"\n' + txt

    txt = re.sub(
        r'strncpy\s*\(\s*m_szHostOrIp\s*,\s*szHostOrIp\s*,\s*sizeof\s*\(\s*m_szHostOrIp\s*\)\s*\)\s*;',
        'strncpy(m_szHostOrIp, XySAMP::GetLockedHost(), sizeof(m_szHostOrIp));',
        txt,
    )
    txt = re.sub(
        r'm_iPort\s*=\s*iPort\s*;',
        'm_iPort = XySAMP::GetLockedPort();',
        txt,
    )
    txt = re.sub(
        r'bsSend\.Write\s*\(\s*\(char\*\)\s*sampVer\s*,\s*iVersionLen\s*\)\s*;',
        'const char* lockedVer = XySAMP::IsRuntimeClean() ? XySAMP::GetClientVersion() : "TAMPERED";\n'
        '\tuint8_t lockedVerLen = (uint8_t)strlen(lockedVer);\n'
        '\tbsSend.Write(lockedVerLen);\n'
        '\tbsSend.Write((char*)lockedVer, lockedVerLen);',
        txt,
    )
    txt = re.sub(
        r'bsSend\.Write\s*\(\s*iVersionLen\s*\)\s*;\s*\n\s*const char\* lockedVer',
        'const char* lockedVer',
        txt,
    )

    netgame_cpp.write_text(txt, encoding="utf-8")
    print(f"[+] Patched {netgame_cpp} (connect & auth packet locked with runtime integrity check)")


def patch_netrpc_cpp(samp_dir: Path):
    netrpc_cpp = samp_dir / "net" / "netrpc.cpp"
    txt = netrpc_cpp.read_text(encoding="utf-8", errors="ignore")

    if '#include "../lockdown.h"' not in txt:
        txt = '#include "../lockdown.h"\n' + txt

    handler_code = """
// --- XySAMP Custom ClientCheck (RPC 103) Challenge-Response + Anti-Tamper ---
void ClientCheck(RPCParameters *rpcParams)
{
    if (!pNetGame) return;
    unsigned char* Data = reinterpret_cast<unsigned char*>(rpcParams->input);
    int iBitLength = rpcParams->numberOfBitsOfData;
    RakNet::BitStream bsData(Data, (iBitLength / 8) + 1, false);

    uint8_t byteType = 0;
    uint32_t dwAddress = 0;
    uint16_t wOffset = 0, wCount = 0;

    if (!bsData.Read(byteType)) return;
    if (!bsData.Read(dwAddress)) return;
    bsData.Read(wOffset);
    bsData.Read(wCount);

    // Type 0x48 ('H') = Custom XySAMP Handshake Challenge dari Pawn Server
    if (byteType == 0x48) {
        uint8_t byteResponse = XySAMP::CalcHandshakeResponse(dwAddress, wOffset, wCount);
        uint32_t dwEcho = dwAddress ^ XySAMP::GetHandshakeSecret();
        if (!XySAMP::IsRuntimeClean()) {
            byteResponse ^= 0xFF;
            dwEcho ^= 0xDEADDEADu;
        }
        RakNet::BitStream bsSend;
        bsSend.Write((uint8_t)0x48);
        bsSend.Write(dwEcho);
        bsSend.Write(byteResponse);
        int rpc = 103;
        pNetGame->GetRakClient()->RPC(&rId_ClientCheck, &bsSend, HIGH_PRIORITY, RELIABLE, 0, false, UNASSIGNED_NETWORK_ID, NULL);
        return;
    }

    // Default response untuk pengecekan standar (mis. SAMP-Mobile-Checker type 2/70)
    RakNet::BitStream bsSend;
    bsSend.Write(byteType);
    bsSend.Write(dwAddress);
    bsSend.Write((uint8_t)0);
    pNetGame->GetRakClient()->RPC(&rId_ClientCheck, &bsSend, HIGH_PRIORITY, RELIABLE, 0, false, UNASSIGNED_NETWORK_ID, NULL);
}
"""
    handler_code = handler_code.replace("int rpc = 103;\n        ", "").replace("&rId_ClientCheck", "&RPC_ClientCheck")

    if "void ClientCheck(RPCParameters" not in txt:
        txt = txt.replace(
            "void RegisterRPCs(RakClientInterface *pRakClient)",
            handler_code + "\nvoid RegisterRPCs(RakClientInterface *pRakClient)",
        )

    if "pRakClient->RegisterAsRemoteProcedureCall(&RPC_ClientCheck" not in txt:
        txt = txt.replace(
            "pRakClient->RegisterAsRemoteProcedureCall(&RPC_InitGame, InitGame);",
            "pRakClient->RegisterAsRemoteProcedureCall(&RPC_InitGame, InitGame);\n"
            "\tpRakClient->RegisterAsRemoteProcedureCall(&RPC_ClientCheck, ClientCheck);",
        )

    netrpc_cpp.write_text(txt, encoding="utf-8")
    print(f"[+] Patched {netrpc_cpp} (added RPC_ClientCheck ID 103 challenge-response + anti-tamper)")


def patch_settings_cpp(samp_dir: Path, args):
    settings_cpp = samp_dir / "settings.cpp"
    content = f"""#include "main.h"
#include "settings.h"
#include "lockdown.h"
#include "vendor/inih/cpp/INIReader.h"
#include "vendor/SimpleIni/SimpleIni.h"
#include "game/game.h"
#include <sys/stat.h>

extern CGame *pGame;

CSettings::CSettings()
{{
    FLog("Loading settings..");
    memset(&m_Settings, 0, sizeof(m_Settings));

    char buff[256];
    snprintf(buff, sizeof(buff), "%sSAMP/settings.ini", g_pszStorage ? g_pszStorage : "/storage/emulated/0/GTA/");

    INIReader reader(buff);
    bool iniOk = (reader.ParseError() >= 0);

    // Default aman jika settings.ini belum ada (TANPA std::terminate agar tidak pernah blackscreen/crash!)
    char defaultNick[32];
    snprintf(defaultNick, sizeof(defaultNick), "{args.default_nick}_%d", (rand() % 899) + 100);

    std::string nick = iniOk ? reader.Get("client", "name", defaultNick) : std::string(defaultNick);
    if (nick.empty() || nick == "Nick_Name" || nick.find("__android_") == 0) {{
        nick = defaultNick;
    }}
    size_t length = nick.copy(m_Settings.szNickName, 24);
    m_Settings.szNickName[length] = '\\0';

    std::string pass = iniOk ? reader.Get("client", "password", "") : "";
    length = pass.copy(m_Settings.szPassword, MAX_SETTINGS_STRING);
    m_Settings.szPassword[length] = '\\0';

    // Host, Port, dan Version dikunci di memori dari dekripsi XOR runtime
    strncpy(m_Settings.szHost, XySAMP::GetLockedHost(), MAX_SETTINGS_STRING);
    m_Settings.szHost[MAX_SETTINGS_STRING - 1] = '\\0';
    m_Settings.iPort = XySAMP::GetLockedPort();
    strncpy(m_Settings.szVersion, XySAMP::GetClientVersion(), MAX_SETTINGS_STRING);
    m_Settings.szVersion[MAX_SETTINGS_STRING - 1] = '\\0';

    m_Settings.bAutoAim = false;
    m_Settings.bDebug = false;
    m_Settings.bOnline = true;

    std::string fontName = iniOk ? reader.Get("gui", "Font", "arial.ttf") : "arial.ttf";
    if (fontName.empty()) fontName = "arial.ttf";
    length = fontName.copy(m_Settings.szFont, MAX_SETTINGS_STRING);
    m_Settings.szFont[length] = '\\0';

    m_Settings.fFontSize = iniOk ? (float)reader.GetReal("gui", "FontSize", 30.0) : 30.0f;
    m_Settings.iFontOutline = iniOk ? (int)reader.GetInteger("gui", "FontOutline", 2) : 2;

    m_Settings.fChatPosX = iniOk ? (float)reader.GetReal("gui", "ChatPosX", 325.0) : 325.0f;
    m_Settings.fChatPosY = iniOk ? (float)reader.GetReal("gui", "ChatPosY", 25.0) : 25.0f;
    m_Settings.fChatSizeX = iniOk ? (float)reader.GetReal("gui", "ChatSizeX", 1150.0) : 1150.0f;
    m_Settings.fChatSizeY = iniOk ? (float)reader.GetReal("gui", "ChatSizeY", 220.0) : 220.0f;
    m_Settings.iChatMaxMessages = iniOk ? (int)reader.GetInteger("gui", "ChatMaxMessages", 6) : 6;

    m_Settings.fSpawnScreenPosX = iniOk ? (float)reader.GetReal("gui", "SpawnScreenPosX", 660.0) : 660.0f;
    m_Settings.fSpawnScreenPosY = iniOk ? (float)reader.GetReal("gui", "SpawnScreenPosY", 950.0) : 950.0f;
    m_Settings.fSpawnScreenSizeX = iniOk ? (float)reader.GetReal("gui", "SpawnScreenSizeX", 600.0) : 600.0f;
    m_Settings.fSpawnScreenSizeY = iniOk ? (float)reader.GetReal("gui", "SpawnScreenSizeY", 100.0) : 100.0f;

    m_Settings.fHealthBarWidth = iniOk ? (float)reader.GetReal("gui", "HealthBarWidth", 100.0) : 100.0f;
    m_Settings.fHealthBarHeight = iniOk ? (float)reader.GetReal("gui", "HealthBarHeight", 10.0) : 10.0f;

    m_Settings.fScoreBoardSizeX = iniOk ? (float)reader.GetReal("gui", "ScoreBoardSizeX", 846.0) : 846.0f;
    m_Settings.fScoreBoardSizeY = iniOk ? (float)reader.GetReal("gui", "ScoreBoardSizeY", 614.0) : 614.0f;

    m_Settings.bPassengerUseTexture = iniOk ? reader.GetBoolean("gui", "PassengerUseTexture", true) : true;
    m_Settings.fPassengerTextureSize = iniOk ? (float)reader.GetReal("gui", "PassengerTextureSize", 30.0) : 30.0f;
    m_Settings.fPassengerTextureX = iniOk ? (float)reader.GetReal("gui", "PassengerTexturePosX", 120.0) : 120.0f;
    m_Settings.fPassengerTextureY = iniOk ? (float)reader.GetReal("gui", "PassengerTexturePosY", 430.0) : 430.0f;

    m_Settings.iDialog = iniOk ? reader.GetBoolean("gui", "Dialog", true) : true;

    m_Settings.bVoiceChatEnable = iniOk ? reader.GetBoolean("gui", "VoiceChatEnable", true) : true;
    m_Settings.iVoiceChatKey = iniOk ? (int)reader.GetInteger("gui", "VoiceChatKey", 66) : 66;
    m_Settings.fVoiceChatSize = iniOk ? (float)reader.GetReal("gui", "VoiceChatSize", 30.0) : 30.0f;
    m_Settings.fVoiceChatPosX = iniOk ? (float)reader.GetReal("gui", "VoiceChatPosX", 1520.0) : 1520.0f;
    m_Settings.fVoiceChatPosY = iniOk ? (float)reader.GetReal("gui", "VoiceChatPosY", 480.0) : 480.0f;

    m_Settings.iAndroidKeyboard = iniOk ? reader.GetBoolean("gui", "androidkeyboard", false) : false;
    m_Settings.iFirstPerson = iniOk ? reader.GetBoolean("gui", "firstperson", true) : true;
    m_Settings.iCutout = iniOk ? reader.GetBoolean("gui", "cutout", false) : false;
    m_Settings.iFPSCounter = iniOk ? reader.GetBoolean("gui", "fps", false) : false;
    m_Settings.iFPSCount = iniOk ? (int)reader.GetInteger("gui", "FPSLimit", 60) : 60;
    m_Settings.iHPArmourText = iniOk ? reader.GetBoolean("gui", "hparmourtext", false) : false;
    m_Settings.iOutfitGuns = iniOk ? reader.GetBoolean("gui", "outfitguns", false) : false;
    m_Settings.iPCMoney = iniOk ? reader.GetBoolean("gui", "pcmoney", false) : false;
    m_Settings.iRadarRect = iniOk ? reader.GetBoolean("gui", "radarrect", false) : false;
    m_Settings.iSkyBox = iniOk ? reader.GetBoolean("gui", "skybox", false) : false;
    m_Settings.iSnow = iniOk ? reader.GetBoolean("gui", "snow", false) : false;

    if (!iniOk && g_pszStorage) {{
        char sampDir[256];
        snprintf(sampDir, sizeof(sampDir), "%sSAMP", g_pszStorage);
        mkdir(sampDir, 0775);
        FILE* fp = fopen(buff, "w");
        if (fp) {{
            fprintf(fp, "[client]\\nname=%s\\nhost=127.0.0.1\\nport=7777\\nversion=0.3.7\\n\\n[gui]\\nFont=arial.ttf\\nFontSize=30.0\\nFontOutline=2\\nChatMaxMessages=6\\nFPSLimit=60\\n", m_Settings.szNickName);
            fclose(fp);
        }}
    }}

    FLog("Settings loaded.");
}}

const stSettings& CSettings::GetReadOnly()
{{
    return m_Settings;
}}

stSettings& CSettings::GetWrite()
{{
    return m_Settings;
}}
"""
    settings_cpp.write_text(content, encoding="utf-8")
    print(f"[+] Patched {settings_cpp} (removed std::terminate, added safe defaults & zero-leak settings)")


def patch_imgui_and_image_cpp(samp_dir: Path):
    # 1. imguiwrapper.cpp: multi-font fallback + ImGui default embedded font fallback
    imgui_cpp = samp_dir / "gui" / "imguiwrapper.cpp"
    if imgui_cpp.exists():
        txt = imgui_cpp.read_text(encoding="utf-8", errors="ignore")
        old_font_load = """\tImFont* font = io.Fonts->AddFontFromFileTTF(m_fontPath.c_str(),
\t\tUISettings::fontSize(), &fontCfg, ranges);

\tif (font == nullptr)
\t{
\t\tLog::addParameter("font", font);
\t\treturn false;
\t}"""
        new_font_load = """\tImFont* font = nullptr;
\tconst char* base = g_pszStorage ? g_pszStorage : "/storage/emulated/0/GTA/";
\tstd::string candidates[] = {
\t\tm_fontPath,
\t\tstd::string(base) + "SAMP/fonts/arial.ttf",
\t\tstd::string(base) + "SAMP/fonts/Arial.ttf",
\t\tstd::string(base) + "SAMP/fonts/arial_bold.ttf",
\t\t"/system/fonts/Roboto-Medium.ttf",
\t\t"/system/fonts/Roboto-Regular.ttf",
\t\t"/system/fonts/DroidSans.ttf"
\t};
\tfor (const auto& cand : candidates) {
\t\tFILE* tf = fopen(cand.c_str(), "rb");
\t\tif (tf) {
\t\t\tfclose(tf);
\t\t\tfont = io.Fonts->AddFontFromFileTTF(cand.c_str(), UISettings::fontSize(), &fontCfg, ranges);
\t\t\tif (font != nullptr) break;
\t\t}
\t}
\tif (font == nullptr) {
\t\tfont = io.Fonts->AddFontDefault(&fontCfg);
\t}"""
        if old_font_load in txt:
            txt = txt.replace(old_font_load, new_font_load)
            imgui_cpp.write_text(txt, encoding="utf-8")
            print(f"[+] Patched {imgui_cpp} (multi-font + embedded default font fallback)")

    # 2. image.cpp: null-safe raster check
    image_cpp = samp_dir / "gui" / "widgets" / "image.cpp"
    if image_cpp.exists():
        image_cpp.write_text("""#include "../gui.h"
#include "../../game/game.h"

Image::Image(const std::string& arch_name, const std::string& name)
{
    m_texture = (RwTexture*)CUtil::LoadTextureFromDB(arch_name.c_str(), name.c_str());
}

void Image::performLayout()
{
    if (m_texture == nullptr || m_texture->raster == nullptr) return;
    this->setSize(ImVec2(m_texture->raster->width, m_texture->raster->height));
}

void Image::draw(ImGuiRenderer* renderer)
{
    if (m_texture != nullptr && m_texture->raster != nullptr)
        renderer->drawImage(absolutePosition(), absolutePosition() + size(), (ImTextureID)m_texture->raster);
    Widget::draw(renderer);
}
""", encoding="utf-8")
        print(f"[+] Patched {image_cpp} (null-safe raster checks)")


def patch_hooks_cpp(samp_dir: Path):
    hooks_cpp = samp_dir / "game" / "hooks.cpp"
    txt = hooks_cpp.read_text(encoding="utf-8", errors="ignore")

    if "void AutoPatchTextureFormat()" in txt and "NvFOpen_hook" in txt:
        print(f"[+] {hooks_cpp} already patched with NvFOpen_hook & AutoPatchTextureFormat")
        return

    if "#include <dirent.h>" not in txt:
        txt = "#include <dirent.h>\n#include <strings.h>\n#include <cctype>\n" + txt

    # Replace NvUtilInit_hook + NvFOpen block with Smart Multi-Path + Case-Insensitive + Texture-Format-Aware + APK-Asset Fallback
    old_block_pattern = re.compile(
        r"void ReadSettingFile\(\);\s*void ApplyFPSPatch\(uint8_t fps\);\s*void \(\*NvUtilInit\)\(\);.*?bool g_bPlaySAMP = false;",
        re.DOTALL,
    )

    new_block = r"""void ReadSettingFile();
void ApplyFPSPatch(uint8_t fps);
void AutoPatchTextureFormat();
void (*NvUtilInit)();

static bool HasDirCaseInsensitive(const char* rootDir, const char* targetSub)
{
    DIR* d = opendir(rootDir);
    if (!d) return false;
    struct dirent* ent;
    bool found = false;
    while ((ent = readdir(d)) != nullptr) {
        if (strcasecmp(ent->d_name, targetSub) == 0) {
            found = true;
            break;
        }
    }
    closedir(d);
    return found;
}

void NvUtilInit_hook()
{
    FLog("NvUtilInit");

    NvUtilInit();

    g_pszStorage = (char*)(g_libGTASA + (VER_x32 ? 0x6D687C : 0x8B46A8)); // StorageRootBuffer

    // Jika StorageRootBuffer belum memiliki folder texdb/models, auto-scan lokasi data GTA populer (Lite maupun Full, Tanpa OBB!)
    if (!HasDirCaseInsensitive(g_pszStorage, "texdb") && !HasDirCaseInsensitive(g_pszStorage, "models")) {
        const char* candidates[] = {
            "/storage/emulated/0/GTA/",
            "/storage/emulated/0/Android/data/com.samp.mobile/files/",
            "/storage/emulated/0/Android/data/com.gta.game/files/",
            "/storage/emulated/0/Android/data/ro.alyn_sampmobile.game/files/",
            "/storage/emulated/0/Android/data/ru.unisamp_mobile.game/files/",
            "/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/"
        };
        for (const char* cand : candidates) {
            if (HasDirCaseInsensitive(cand, "texdb") || HasDirCaseInsensitive(cand, "models")) {
                strcpy(g_pszStorage, cand);
                FLog("Auto-detected GTA Data directory: %s", g_pszStorage);
                break;
            }
        }
    }

    AutoPatchTextureFormat();

    ReadSettingFile();

    ApplyFPSPatch(120);
}

struct stFile
{
    int isFileExist;
    FILE *f;
};

char lastFile[256];

// Case-insensitive file opener untuk Android (mengatasi perbedaan DATA/ vs data/, SAMP/ vs samp/, dll)
static FILE* FOpenCaseInsensitive(const char* baseDir, const char* relPath)
{
    if (!baseDir || !relPath) return nullptr;
    while (*relPath == '/' || *relPath == '\\') relPath++;

    char fullPath[512];
    snprintf(fullPath, sizeof(fullPath), "%s%s", baseDir, relPath);
    for (char* p = fullPath; *p; ++p) {
        if (*p == '\\') *p = '/';
    }
    FILE* f = fopen(fullPath, "rb");
    if (f) return f;

    // Coba seluruh relPath lowercase (misal DATA/FONTS.DAT -> data/fonts.dat)
    char lowerRel[256];
    size_t i = 0;
    for (; relPath[i] && i < sizeof(lowerRel) - 1; ++i) {
        char c = relPath[i];
        if (c == '\\') c = '/';
        lowerRel[i] = (char)tolower((unsigned char)c);
    }
    lowerRel[i] = '\0';
    snprintf(fullPath, sizeof(fullPath), "%s%s", baseDir, lowerRel);
    f = fopen(fullPath, "rb");
    if (f) return f;

    // Telusuri komponen path satu per satu secara case-insensitive (opendir + strcasecmp)
    char curPath[512];
    snprintf(curPath, sizeof(curPath), "%s", baseDir);
    size_t baseLen = strlen(curPath);
    if (baseLen > 0 && curPath[baseLen - 1] == '/') {
        curPath[baseLen - 1] = '\0';
    }

    char tempRel[256];
    strncpy(tempRel, relPath, sizeof(tempRel) - 1);
    tempRel[sizeof(tempRel) - 1] = '\0';
    for (char* p = tempRel; *p; ++p) {
        if (*p == '\\') *p = '/';
    }

    char* saveptr = nullptr;
    char* token = strtok_r(tempRel, "/", &saveptr);
    while (token != nullptr) {
        DIR* dir = opendir(curPath);
        if (!dir) return nullptr;
        struct dirent* ent;
        char matched[256] = {0};
        while ((ent = readdir(dir)) != nullptr) {
            if (strcasecmp(ent->d_name, token) == 0) {
                strncpy(matched, ent->d_name, sizeof(matched) - 1);
                break;
            }
        }
        closedir(dir);
        if (matched[0] == '\0') return nullptr;
        size_t curLen = strlen(curPath);
        snprintf(curPath + curLen, sizeof(curPath) - curLen, "/%s", matched);
        token = strtok_r(nullptr, "/", &saveptr);
    }

    return fopen(curPath, "rb");
}

// Per-file fallback untuk texdb/<db>/<db>.<ext>.(tmb|toc|dat) agar Data Lite DXT/ETC/PVR selalu terbaca di GPU apa pun
static FILE* TryOpenTexdbAnyFormat(const char* baseDir, const char* relPath)
{
    if (strncasecmp(relPath, "texdb/", 6) != 0) return nullptr;
    const char* exts[] = { ".dxt.", ".etc.", ".pvr.", ".unc." };
    for (const char* srcExt : exts) {
        const char* pos = strcasestr(relPath, srcExt);
        if (pos != nullptr) {
            for (const char* dstExt : exts) {
                char altRel[256];
                size_t prefixLen = (size_t)(pos - relPath);
                if (prefixLen + strlen(pos) >= sizeof(altRel)) continue;
                memcpy(altRel, relPath, prefixLen);
                memcpy(altRel + prefixLen, dstExt, 5);
                strcpy(altRel + prefixLen + 5, pos + 5);
                FILE* f = FOpenCaseInsensitive(baseDir, altRel);
                if (f) return f;
            }
            break;
        }
    }
    return nullptr;
}

stFile* (*NvFOpen_orig)(const char* r0, const char* r1, int r2, int r3) = nullptr;

stFile* NvFOpen_hook(const char* r0, const char* r1, int r2, int r3)
{
    if (!r1) {
        return NvFOpen_orig ? NvFOpen_orig(r0, r1, r2, r3) : nullptr;
    }

    strncpy(lastFile, r1, sizeof(lastFile) - 1);
    lastFile[sizeof(lastFile) - 1] = '\0';

    const char* baseDir = (g_pszStorage && g_pszStorage[0]) ? g_pszStorage : "/storage/emulated/0/GTA/";
    const char* sampOverride = nullptr;

    if (strlen(r1) >= 12 && strncasecmp(r1 + 12, "mainV1.scm", 10) == 0) {
        sampOverride = "SAMP/main.scm";
    } else if (strlen(r1) >= 12 && strncasecmp(r1 + 12, "SCRIPTV1.IMG", 12) == 0) {
        sampOverride = "SAMP/script.img";
    } else if (strncasecmp(r1, "DATA/PEDS.IDE", 13) == 0) {
        sampOverride = "SAMP/peds.ide";
    } else if (strncasecmp(r1, "DATA/VEHICLES.IDE", 17) == 0) {
        sampOverride = "SAMP/vehicles.ide";
    } else if (strncasecmp(r1, "DATA/GTA.DAT", 12) == 0) {
        sampOverride = "SAMP/gta.dat";
    } else if (strncasecmp(r1, "DATA/HANDLING.CFG", 17) == 0) {
        sampOverride = "SAMP/handling.cfg";
    } else if (strncasecmp(r1, "DATA/WEAPON.DAT", 15) == 0) {
        sampOverride = "SAMP/weapon.dat";
    }

    FILE* f = nullptr;
    if (sampOverride) {
        f = FOpenCaseInsensitive(baseDir, sampOverride);
    }
    if (!f) {
        f = FOpenCaseInsensitive(baseDir, r1);
    }
    if (!f) {
        f = TryOpenTexdbAnyFormat(baseDir, r1);
    }

    if (f) {
#if VER_x32
        auto *st = (stFile*)malloc(8);
#else
        auto *st = (stFile*)malloc(0x10);
#endif
        st->isFileExist = 1;
        st->f = f;
        return st;
    }

    // Fallback ke NvFOpen_orig milik libGTASA.so untuk membaca dari APK assets/ (scache.txt, Text/american.gxt, dll)
    if (NvFOpen_orig) {
        stFile* apkSt = NvFOpen_orig(r0, r1, r2, r3);
        if (apkSt) {
            return apkSt;
        }
    }

    FLog("NVFOpen hook | Warning: file not found (%s%s)", baseDir, r1);
    return nullptr;
}

bool g_bPlaySAMP = false;"""

    txt, count = old_block_pattern.subn(new_block, txt, count=1)
    if count == 0:
        raise RuntimeError("Gagal mem-patch blok NvUtilInit_hook / NvFOpen di hooks.cpp")

    # Replace InstallUrezHooks + InstallCRHooks + Redirect NvFOpen with AutoPatchTextureFormat + InlineHook NvFOpen
    old_urez_pattern = re.compile(
        r"void InstallUrezHooks\(\).*?void InstallSpecialHooks\(\)\s*\{.*?CHook::Redirect\(\"_Z7NvFOpenPKcS0_bb\", &NvFOpen\);",
        re.DOTALL,
    )

    new_urez = r"""void AutoPatchTextureFormat()
{
    const char* baseDir = (g_pszStorage && g_pszStorage[0]) ? g_pszStorage : "/storage/emulated/0/GTA/";
    bool hasDXT = (FOpenCaseInsensitive(baseDir, "texdb/gta3/gta3.dxt.dat") != nullptr) ||
                  (FOpenCaseInsensitive(baseDir, "texdb/gta3/gta3.dxt.tmb") != nullptr);
    bool hasETC = (FOpenCaseInsensitive(baseDir, "texdb/gta3/gta3.etc.dat") != nullptr) ||
                  (FOpenCaseInsensitive(baseDir, "texdb/gta3/gta3.etc.tmb") != nullptr);
    bool hasPVR = (FOpenCaseInsensitive(baseDir, "texdb/gta3/gta3.pvr.dat") != nullptr) ||
                  (FOpenCaseInsensitive(baseDir, "texdb/gta3/gta3.pvr.tmb") != nullptr);

    // Tutup handle pengecekan dengan aman lewat helper kecil
    auto checkFile = [&](const char* rel) -> bool {
        FILE* fp = FOpenCaseInsensitive(baseDir, rel);
        if (fp) { fclose(fp); return true; }
        return false;
    };
    hasDXT = checkFile("texdb/gta3/gta3.dxt.dat") || checkFile("texdb/gta3/gta3.dxt.tmb");
    hasETC = checkFile("texdb/gta3/gta3.etc.dat") || checkFile("texdb/gta3/gta3.etc.tmb");
    hasPVR = checkFile("texdb/gta3/gta3.pvr.dat") || checkFile("texdb/gta3/gta3.pvr.tmb");

    const char* fallbackExt = "dxt";
    if (hasDXT) fallbackExt = "dxt";
    else if (hasETC) fallbackExt = "etc";
    else if (hasPVR) fallbackExt = "pvr";

    struct TexSlot {
        uintptr_t x32;
        uintptr_t x64;
        bool exists;
    };

    TexSlot slots[] = {
        { 0x1E87DC, 0x713FC7, hasDXT }, // dxt.tmb
        { 0x1E8C34, 0x71403F, hasDXT }, // dxt
        { 0x1E878C, 0x714017, hasETC }, // etc.tmb
        { 0x1E8BF4, 0x71407F, hasETC }, // etc
        { 0x1E87A0, 0x714003, hasPVR }, // pvr.tmb
        { 0x1E8C04, 0x71406F, hasPVR }, // pvr
        { 0x1E87F0, 0x713FB3, false  }, // unc.tmb -> fallbackExt
    };

    for (const auto& s : slots) {
        if (!s.exists && (hasDXT || hasETC || hasPVR)) {
            uintptr_t addr = g_libGTASA + (VER_x32 ? s.x32 : s.x64);
            CHook::UnFuck(addr);
            char* ext = reinterpret_cast<char*>(addr + 12);
            ext[0] = fallbackExt[0];
            ext[1] = fallbackExt[1];
            ext[2] = fallbackExt[2];
        }
    }
    FLog("AutoPatchTextureFormat: hasDXT=%d hasETC=%d hasPVR=%d fallback=%s", hasDXT, hasETC, hasPVR, fallbackExt);
}

void InstallSpecialHooks()
{
    InjectHooks();

    CHook::Redirect("_ZN5CGame20InitialiseRenderWareEv", &CGame::InitialiseRenderWare);
    CHook::InstallPLT(g_libGTASA + (VER_x32 ? 0x6785FC : 0x84EC20), &StartGameScreen__OnNewGameCheck_hook, &StartGameScreen__OnNewGameCheck);

    CHook::InlineHook("_Z10NvUtilInitv", &NvUtilInit_hook, &NvUtilInit);

    CHook::RET("_ZN12CCutsceneMgr16LoadCutsceneDataEPKc");
    CHook::RET("_ZN12CCutsceneMgr10InitialiseEv");

    CHook::InlineHook("_Z7NvFOpenPKcS0_bb", &NvFOpen_hook, &NvFOpen_orig);"""

    txt, count2 = old_urez_pattern.subn(new_urez, txt, count=1)
    if count2 == 0:
        raise RuntimeError("Gagal mem-patch InstallSpecialHooks di hooks.cpp")

    hooks_cpp.write_text(txt, encoding="utf-8")
    print(f"[+] Patched {hooks_cpp} (InlineHook NvFOpen + Case-Insensitive + AutoPatchTextureFormat + APK Assets fallback)")


def patch_java_and_resources(repo: Path, args):
    app_main = repo / "app" / "src" / "main"
    java_root = app_main / "java"
    res_root = app_main / "res"

    # 1. Hapus class launcher Rusia lama yang tidak terpakai (SplashActivity, UpdateService, Firebase, fragments, adapters)
    launcher_dir = java_root / "com" / "samp" / "mobile" / "launcher"
    for subdir in ("adapters", "fragments", "data", "config"):
        p = launcher_dir / subdir
        if p.exists():
            shutil.rmtree(p)
    for fn in ("SplashActivity.java", "UpdateActivity.java", "UpdateService.java", "Ref.java"):
        p = launcher_dir / fn
        if p.exists():
            p.unlink()
    for fn in ("FirebaseMessageReceiver.java", "SAMPServerInfo.java", "SampQueryAPI.java", "ConfigValidator.java", "SignatureChecker.java"):
        p = launcher_dir / "util" / fn
        if p.exists():
            p.unlink()

    # 2. Bersihkan import @Obfuscate / FirebaseCrashlytics di seluruh file Java yang tersisa
    for jfile in java_root.rglob("*.java"):
        jtxt = jfile.read_text(encoding="utf-8", errors="ignore")
        jtxt = re.sub(r"^\s*import\s+com\.joom\.paranoid\.Obfuscate\s*;\s*\n", "", jtxt, flags=re.MULTILINE)
        jtxt = re.sub(r"^\s*import\s+com\.google\.firebase\.[^\n]+\n", "", jtxt, flags=re.MULTILINE)
        jtxt = re.sub(r"^\s*import\s+com\.samp\.mobile\.launcher\.(config|fragments|adapters|util\.SignatureChecker)[^\n]*\n", "", jtxt, flags=re.MULTILINE)
        jtxt = re.sub(r"^\s*@Obfuscate\s*\n", "", jtxt, flags=re.MULTILINE)
        jtxt = re.sub(r"FirebaseCrashlytics\.getInstance\(\)\.setCrashlyticsCollectionEnabled\(false\);", "", jtxt)
        jfile.write_text(jtxt, encoding="utf-8")

    # 3. Percepat DoResumeEvent di NvEventQueueActivity.java (mSleep(50) bukan 1000ms)
    nvev = java_root / "com" / "nvidia" / "devtech" / "NvEventQueueActivity.java"
    if nvev.exists():
        ntxt = nvev.read_text(encoding="utf-8", errors="ignore")
        ntxt = ntxt.replace("NvEventQueueActivity.this.mSleep(1000);", "NvEventQueueActivity.this.mSleep(50);")
        nvev.write_text(ntxt, encoding="utf-8")

    # 4. Patch GTASA.java: pre-load SCAnd & OpenAL32/64 secara aman, matikan monetloader
    gtasa_java = java_root / "com" / "samp" / "mobile" / "game" / "GTASA.java"
    gtasa_java.write_text("""package com.samp.mobile.game;

import android.content.Intent;
import android.content.res.Configuration;
import android.os.Bundle;
import android.view.KeyEvent;

import com.bytedance.shadowhook.ShadowHook;
import com.wardrumstudios.utils.WarMedia;

public class GTASA extends WarMedia {
    static String vmVersion;
    private boolean once = false;

    static {
        ShadowHook.init(new ShadowHook.ConfigBuilder()
                .setMode(ShadowHook.Mode.UNIQUE)
                .build());

        vmVersion = null;
        try {
            vmVersion = System.getProperty("java.vm.version");
            System.loadLibrary("ImmEmulatorJ");
        } catch (Throwable ignored) {
        }
        try {
            System.loadLibrary("SCAnd");
        } catch (Throwable ignored) {
        }
        try {
            System.loadLibrary("OpenAL64");
        } catch (Throwable t) {
            try {
                System.loadLibrary("OpenAL32");
            } catch (Throwable ignored) {
            }
        }
        System.loadLibrary("GTASA");
        System.loadLibrary("bass");
        System.loadLibrary("samp");
    }

    public static void staticEnterSocialClub() {}
    public static void staticExitSocialClub() {}
    public void AfterDownloadFunction() {}
    public void EnterSocialClub() {}
    public void ExitSocialClub() {}

    public boolean ServiceAppCommand(String str, String str2) {
        return false;
    }

    public int ServiceAppCommandValue(String str, String str2) {
        return 0;
    }

    public native void main();

    @Override
    public void onActivityResult(int i, int i2, Intent intent) {
        super.onActivityResult(i, i2, intent);
    }

    @Override
    public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
    }

    @Override
    public void onCreate(Bundle bundle) {
        if (!once) {
            once = true;
        }
        super.onCreate(bundle);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
    }

    @Override
    public boolean onKeyDown(int i, KeyEvent keyEvent) {
        return super.onKeyDown(i, keyEvent);
    }

    @Override
    public void onPause() {
        super.onPause();
    }

    @Override
    public void onRestart() {
        super.onRestart();
    }

    @Override
    public void onResume() {
        super.onResume();
    }

    @Override
    public void onStart() {
        super.onStart();
    }

    @Override
    public void onStop() {
        super.onStop();
    }

    public native void setCurrentScreenSize(int i, int i2);
}
""", encoding="utf-8")

    # 5. Patch WarMedia.java: gunakan MainActivity.resolveGameDataDir(this) (100% Tanpa OBB, support Data Lite & Full)
    warmedia_java = java_root / "com" / "wardrumstudios" / "utils" / "WarMedia.java"
    wtxt = warmedia_java.read_text(encoding="utf-8", errors="ignore")
    old_get_base = re.compile(
        r"public String GetGameBaseDirectory\(\)\s*\{.*?\n    \}",
        re.DOTALL,
    )
    new_get_base = """public String GetGameBaseDirectory() {
        try {
            String resolved = com.samp.mobile.launcher.MainActivity.resolveGameDataDir(this);
            this.baseDirectoryRoot = Environment.getExternalStorageDirectory().getAbsolutePath();
            return resolved;
        } catch (Exception e) {
            return "/storage/emulated/0/GTA/";
        }
    }"""
    wtxt, _ = old_get_base.subn(new_get_base, wtxt, count=1)
    warmedia_java.write_text(wtxt, encoding="utf-8")

    # 6. Tulis MainActivity.java (Single-Screen XyVerse Roleplay Launcher + Smart Multi-Path Data Auto-Detector + Self-Healing Fonts)
    cert_pin = (args.cert_sha256 or "").strip().lower().replace(":", "")
    main_activity_java = launcher_dir / "MainActivity.java"
    main_activity_java.write_text(f"""package com.samp.mobile.launcher;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.samp.mobile.R;
import com.samp.mobile.game.SAMP;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity {{
    private static final String PREFS_NAME = "samp_launcher_prefs";
    private static final String KEY_NICKNAME = "player_nickname";
    private static final String KEY_DATA_DIR = "active_data_dir";
    private static final String DEFAULT_NICK = "{args.default_nick}";
    private static final int LOCKED_PORT = {args.port};
    // SHA-256 Official Release Keystore Pinning (Anti-Repackage / Anti-Mod APK)
    private static final String EXPECTED_CERT_SHA256 = "{cert_pin}";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private Button startButton;
    private EditText nicknameInput;
    private TextView title1, title2, authorText, bugText;
    private boolean storagePermissionGranted = false;

    private final ActivityResultLauncher<String[]> requestStoragePermissionLauncher =
            registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(), permissions -> {{
                boolean allGranted = true;
                for (Boolean granted : permissions.values()) {{
                    if (!granted) {{
                        allGranted = false;
                        break;
                    }}
                }}

                if (allGranted) {{
                    storagePermissionGranted = true;
                    onPermissionReady();
                }} else {{
                    storagePermissionGranted = false;
                    Toast.makeText(this, "Izin penyimpanan diperlukan untuk membaca data GTA SA", Toast.LENGTH_LONG).show();
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {{
                        requestManageStoragePermission();
                    }}
                }}
            }});

    private final ActivityResultLauncher<Intent> manageStorageLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {{
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {{
                    if (Environment.isExternalStorageManager()) {{
                        storagePermissionGranted = true;
                        onPermissionReady();
                    }} else {{
                        storagePermissionGranted = false;
                        Toast.makeText(this, "Berikan izin 'Akses Semua File' agar game bisa berjalan", Toast.LENGTH_LONG).show();
                    }}
                }}
            }});

    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        try {{
            setFullScreenMode();
            setContentView(R.layout.main_activity);
            initViews();
            if (!verifyOfficialSignature()) {{
                markTampered(true);
                Toast.makeText(this, "PERINGATAN: APK telah dimodifikasi / bukan rilis resmi!", Toast.LENGTH_LONG).show();
                finish();
                return;
            }} else {{
                markTampered(false);
            }}
            setupClickListeners();
            checkAndRequestStoragePermission();
            if (storagePermissionGranted) {{
                onPermissionReady();
            }}
        }} catch (Exception e) {{
            finish();
        }}
    }}

    private void onPermissionReady() {{
        String dir = resolveGameDataDir(this);
        provisionSampDirectory(new File(dir));
        loadSavedNickname();
        updateDataStatusLabel(dir);
    }}

    private void updateDataStatusLabel(String dir) {{
        if (bugText == null) return;
        File d = new File(dir);
        if (hasGtaCache(d)) {{
            bugText.setText("Data Terdeteksi (Lite/Full Tanpa OBB): " + dir);
        }} else {{
            bugText.setText("Taruh folder data GTA (Lite/Full) di: /sdcard/GTA/ atau /Android/data/com.samp.mobile/files/");
        }}
    }}

    public static boolean hasSubdirIgnoreCase(File dir, String name) {{
        if (dir == null || !dir.exists() || !dir.isDirectory()) return false;
        File[] list = dir.listFiles();
        if (list == null) return false;
        for (File f : list) {{
            if (f.isDirectory() && f.getName().equalsIgnoreCase(name)) {{
                return true;
            }}
        }}
        return false;
    }}

    public static boolean hasGtaCache(File dir) {{
        return hasSubdirIgnoreCase(dir, "texdb") || hasSubdirIgnoreCase(dir, "models");
    }}

    public static String resolveGameDataDir(Context ctx) {{
        List<String> candidates = new ArrayList<>();
        candidates.add("/storage/emulated/0/GTA/");
        try {{
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) {{
                String p = ext.getAbsolutePath();
                if (!p.endsWith("/")) p += "/";
                candidates.add(p);
            }}
        }} catch (Exception ignored) {{}}
        candidates.add("/storage/emulated/0/Android/data/com.samp.mobile/files/");
        candidates.add("/storage/emulated/0/Android/data/com.gta.game/files/");
        candidates.add("/storage/emulated/0/Android/data/ro.alyn_sampmobile.game/files/");
        candidates.add("/storage/emulated/0/Android/data/ru.unisamp_mobile.game/files/");
        candidates.add("/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/");

        for (String c : candidates) {{
            File f = new File(c);
            if (hasGtaCache(f)) {{
                return c.endsWith("/") ? c : (c + "/");
            }}
        }}
        return "/storage/emulated/0/GTA/";
    }}

    private void provisionSampDirectory(File baseDir) {{
        try {{
            File sampDir = new File(baseDir, "SAMP");
            File fontsDir = new File(sampDir, "fonts");
            if (!fontsDir.exists()) {{
                fontsDir.mkdirs();
            }}
            // Pastikan arial.ttf & arial_bold.ttf selalu ada agar ImGui tidak pernah gagal / blackscreen
            String[] fontTargets = new String[]{{ "arial.ttf", "Arial.ttf", "arial_bold.ttf" }};
            for (String ft : fontTargets) {{
                File outFont = new File(fontsDir, ft);
                if (!outFont.exists() || outFont.length() < 1024) {{
                    copyBundledFont(outFont);
                }}
            }}
        }} catch (Exception ignored) {{}}
    }}

    private void copyBundledFont(File dest) {{
        try (InputStream is = getResources().openRawResource(R.font.roboto_medium);
             FileOutputStream fos = new FileOutputStream(dest)) {{
            byte[] buf = new byte[4096];
            int n;
            while ((n = is.read(buf)) != -1) {{
                fos.write(buf, 0, n);
            }}
            fos.flush();
        }} catch (Exception e) {{
            try (InputStream is2 = getAssets().open("Fonts/HELVETICANEUELTCOM-MD.TTF");
                 FileOutputStream fos2 = new FileOutputStream(dest)) {{
                byte[] buf = new byte[4096];
                int n;
                while ((n = is2.read(buf)) != -1) {{
                    fos2.write(buf, 0, n);
                }}
                fos2.flush();
            }} catch (Exception ignored) {{}}
        }}
    }}

    private boolean verifyOfficialSignature() {{
        if (EXPECTED_CERT_SHA256 == null || EXPECTED_CERT_SHA256.isEmpty()) {{
            return true;
        }}
        try {{
            PackageInfo pkgInfo = getPackageManager().getPackageInfo(
                    getPackageName(),
                    PackageManager.GET_SIGNING_CERTIFICATES
            );
            SigningInfo signingInfo = pkgInfo.signingInfo;
            if (signingInfo == null) return false;
            Signature[] sigs = signingInfo.hasMultipleSigners()
                    ? signingInfo.getApkContentsSigners()
                    : signingInfo.getSigningCertificateHistory();
            if (sigs == null || sigs.length == 0) return false;

            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(sigs[0].toByteArray());
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {{
                hex.append(String.format("%02x", b & 0xff));
            }}
            return EXPECTED_CERT_SHA256.equalsIgnoreCase(hex.toString());
        }} catch (Exception e) {{
            return false;
        }}
    }}

    private void markTampered(boolean tampered) {{
        try {{
            String dir = resolveGameDataDir(this);
            File f = new File(dir, "SAMP/.tampered");
            if (tampered) {{
                File p = f.getParentFile();
                if (p != null && !p.exists()) p.mkdirs();
                try (FileOutputStream fos = new FileOutputStream(f)) {{
                    fos.write(1);
                }}
            }} else if (f.exists()) {{
                f.delete();
            }}
        }} catch (Exception ignored) {{ }}
    }}

    private void initViews() {{
        title1 = findViewById(R.id.title1);
        title2 = findViewById(R.id.title2);
        authorText = findViewById(R.id.authorText);
        bugText = findViewById(R.id.bugText);
        startButton = findViewById(R.id.startButton);
        nicknameInput = findViewById(R.id.nicknameInput);
    }}

    private String sanitizeNick(String raw) {{
        if (raw == null) return "";
        String s = raw.trim().replace(' ', '_');
        s = s.replaceAll("[^A-Za-z0-9_\\\\[\\\\]$=()@.]", "");
        if (s.length() > 20) s = s.substring(0, 20);
        return s;
    }}

    private void loadSavedNickname() {{
        if (nicknameInput == null) return;
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String saved = prefs.getString(KEY_NICKNAME, "");

        if (saved.isEmpty()) {{
            File ini = new File(resolveGameDataDir(this), "SAMP/settings.ini");
            if (ini.exists()) {{
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {{
                    String line;
                    while ((line = br.readLine()) != null) {{
                        String trimmed = line.trim();
                        if (trimmed.toLowerCase().startsWith("name=")) {{
                            String val = trimmed.substring(5).trim();
                            if (!val.isEmpty() && !val.startsWith("__android_") && !val.equals("Nick_Name")) {{
                                saved = val;
                                break;
                            }}
                        }}
                    }}
                }} catch (Exception ignored) {{ }}
            }}
        }}

        if (!saved.isEmpty() && !saved.equals(DEFAULT_NICK)) {{
            nicknameInput.setText(saved);
        }}
    }}

    private boolean saveNicknameToIni(String nick) {{
        String activeDir = resolveGameDataDir(this);
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit().putString(KEY_NICKNAME, nick).putString(KEY_DATA_DIR, activeDir).apply();

        String[] targetDirs = new String[]{{
                activeDir,
                "/storage/emulated/0/GTA/"
        }};
        boolean ok = false;
        for (String dir : targetDirs) {{
            try {{
                provisionSampDirectory(new File(dir));
                File ini = new File(dir, "SAMP/settings.ini");
                File parent = ini.getParentFile();
                if (parent != null && !parent.exists()) {{
                    parent.mkdirs();
                }}

                if (!ini.exists()) {{
                    String content = "[client]\\n"
                            + "name=" + nick + "\\n"
                            + "host=127.0.0.1\\n"
                            + "port=" + LOCKED_PORT + "\\n"
                            + "password=\\n"
                            + "version=0.3.7\\n"
                            + "autoaim=false\\n\\n"
                            + "[debug]\\n"
                            + "debug=false\\n"
                            + "online=true\\n\\n"
                            + "[gui]\\n"
                            + "Font=arial.ttf\\n"
                            + "FontSize=30.0\\n"
                            + "FontOutline=2\\n"
                            + "ChatMaxMessages=6\\n"
                            + "FPSLimit=60\\n";
                    try (FileOutputStream fos = new FileOutputStream(ini, false)) {{
                        fos.write(content.getBytes(StandardCharsets.UTF_8));
                    }}
                    ok = true;
                    continue;
                }}

                List<String> lines = new ArrayList<>();
                boolean nameUpdated = false;
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {{
                    String line;
                    while ((line = br.readLine()) != null) {{
                        String lower = line.trim().toLowerCase();
                        if (lower.startsWith("name=") || lower.startsWith("name =")) {{
                            lines.add("name=" + nick);
                            nameUpdated = true;
                        }} else if (lower.startsWith("font=") || lower.startsWith("font =")) {{
                            lines.add("Font=arial.ttf");
                        }} else {{
                            lines.add(line);
                        }}
                    }}
                }}

                if (!nameUpdated) {{
                    lines.add(0, "[client]");
                    lines.add(1, "name=" + nick);
                }}

                StringBuilder sb = new StringBuilder();
                for (String l : lines) {{
                    sb.append(l).append("\\n");
                }}
                try (FileOutputStream fos = new FileOutputStream(ini, false)) {{
                    fos.write(sb.toString().getBytes(StandardCharsets.UTF_8));
                }}
                ok = true;
            }} catch (Exception ignored) {{}}
        }}
        return ok;
    }}

    private void checkAndRequestStoragePermission() {{
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {{
            if (Environment.isExternalStorageManager()) {{
                storagePermissionGranted = true;
            }} else {{
                requestManageStoragePermission();
            }}
        }} else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {{
            String[] permissions = new String[]{{
                    android.Manifest.permission.READ_EXTERNAL_STORAGE,
                    android.Manifest.permission.WRITE_EXTERNAL_STORAGE
            }};
            boolean allGranted = true;
            for (String perm : permissions) {{
                if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {{
                    allGranted = false;
                    break;
                }}
            }}
            if (allGranted) {{
                storagePermissionGranted = true;
            }} else {{
                requestStoragePermissionLauncher.launch(permissions);
            }}
        }} else {{
            storagePermissionGranted = true;
        }}
    }}

    private void requestManageStoragePermission() {{
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {{
            try {{
                Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
                intent.setData(Uri.parse("package:" + getPackageName()));
                manageStorageLauncher.launch(intent);
            }} catch (Exception e) {{
                Intent intent = new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION);
                manageStorageLauncher.launch(intent);
            }}
        }}
    }}

    private void setFullScreenMode() {{
        try {{
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            );
            getWindow().setFlags(
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
            );
            getWindow().setStatusBarColor(android.graphics.Color.TRANSPARENT);
            getWindow().setNavigationBarColor(android.graphics.Color.TRANSPARENT);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {{
                WindowManager.LayoutParams params = getWindow().getAttributes();
                params.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
                getWindow().setAttributes(params);
            }}
            if (getSupportActionBar() != null) {{
                getSupportActionBar().hide();
            }}
        }} catch (Exception ignored) {{ }}
    }}

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {{
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {{
            setFullScreenMode();
        }}
    }}

    private void startGame() {{
        if (!verifyOfficialSignature()) {{
            markTampered(true);
            Toast.makeText(this, "APK tidak resmi / telah dimodifikasi!", Toast.LENGTH_LONG).show();
            finish();
            return;
        }}
        String dataDir = resolveGameDataDir(this);
        updateDataStatusLabel(dataDir);
        if (!hasGtaCache(new File(dataDir))) {{
            Toast.makeText(this,
                    "Data GTA SA (Lite / Full) belum ditemukan! Ekstrak folder data GTA (texdb, models, data, SAMP) ke /sdcard/GTA/ atau /Android/data/com.samp.mobile/files/ terlebih dahulu.",
                    Toast.LENGTH_LONG).show();
            return;
        }}

        String rawNick = (nicknameInput != null) ? nicknameInput.getText().toString() : "";
        String nick = sanitizeNick(rawNick);
        if (nick.isEmpty()) {{
            nick = sanitizeNick(DEFAULT_NICK);
        }}
        if (nick.length() < 3) {{
            Toast.makeText(this, "Nickname minimal 3 karakter (contoh: Nama_Roleplay)", Toast.LENGTH_LONG).show();
            return;
        }}
        if (nicknameInput != null) {{
            nicknameInput.setText(nick);
        }}
        hideKeyboard(this);
        saveNicknameToIni(nick);

        Intent gameIntent = new Intent(MainActivity.this, SAMP.class);
        gameIntent.putExtra("player_name", nick);
        gameIntent.putExtra("game_data_dir", dataDir);
        startActivity(gameIntent);
    }}

    private void setupClickListeners() {{
        startButton.setOnClickListener(v -> {{
            v.animate().scaleX(0.92f).scaleY(0.92f).setDuration(90)
                    .withEndAction(() -> v.animate().scaleX(1f).scaleY(1f).setDuration(90).start())
                    .start();
            if (storagePermissionGranted) {{
                startGame();
            }} else {{
                checkAndRequestStoragePermission();
            }}
        }});
    }}

    public static void hideKeyboard(Activity activity) {{
        try {{
            InputMethodManager inputManager = (InputMethodManager) activity
                    .getSystemService(Context.INPUT_METHOD_SERVICE);
            View currentFocusedView = activity.getCurrentFocus();
            if (currentFocusedView != null && inputManager != null) {{
                inputManager.hideSoftInputFromWindow(currentFocusedView.getWindowToken(), InputMethodManager.HIDE_NOT_ALWAYS);
            }}
        }} catch (Exception ignored) {{ }}
    }}

    @Override
    protected void onDestroy() {{
        super.onDestroy();
        handler.removeCallbacksAndMessages(null);
    }}
}}
""", encoding="utf-8")

    # 7. Tulis layout main_activity.xml, drawable/background.xml, drawable/button.xml, values/strings.xml, values/dimens.xml
    (res_root / "layout" / "main_activity.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/background"
    android:padding="@dimen/margin_medium">

    <TextView
        android:id="@+id/title1"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/client_name"
        android:textColor="#FFFFFF"
        android:textSize="@dimen/title1_text_size"
        android:textStyle="bold"
        android:layout_alignParentTop="true"
        android:layout_alignParentStart="true"
        android:layout_marginTop="@dimen/title_margin_top"
        android:layout_marginStart="@dimen/horizontal_margin"
        android:shadowColor="#000000"
        android:shadowDx="2"
        android:shadowDy="2"
        android:shadowRadius="2"/>

    <TextView
        android:id="@+id/title2"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/samp_ver"
        android:textColor="#B0BEC5"
        android:textSize="@dimen/title2_text_size"
        android:textStyle="bold"
        android:layout_below="@id/title1"
        android:layout_alignStart="@id/title1"
        android:layout_marginTop="8dp"
        android:shadowColor="#000000"
        android:shadowDx="2"
        android:shadowDy="2"
        android:shadowRadius="2"/>

    <TextView
        android:id="@+id/authorText"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/authors"
        android:textColor="#87CEEB"
        android:textSize="@dimen/small_text_size"
        android:layout_alignParentBottom="true"
        android:layout_alignParentStart="true"
        android:layout_marginBottom="@dimen/bottom_margin"
        android:layout_marginStart="@dimen/horizontal_margin"
        android:shadowColor="#000000"
        android:shadowDx="1"
        android:shadowDy="1"
        android:shadowRadius="1"/>

    <TextView
        android:id="@+id/bugText"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/bug_info"
        android:textColor="#E0E0E0"
        android:textSize="@dimen/small_text_size"
        android:layout_above="@id/authorText"
        android:layout_alignStart="@id/authorText"
        android:layout_marginBottom="6dp"
        android:shadowColor="#000000"
        android:shadowDx="1"
        android:shadowDy="1"
        android:shadowRadius="1"/>

    <EditText
        android:id="@+id/nicknameInput"
        android:layout_width="@dimen/button_width"
        android:layout_height="46dp"
        android:layout_above="@id/startButton"
        android:layout_alignEnd="@id/startButton"
        android:layout_marginBottom="12dp"
        android:background="#CC141824"
        android:paddingStart="14dp"
        android:paddingEnd="14dp"
        android:hint="Nickname (Nama_RP)"
        android:textColor="#FFFFFF"
        android:textColorHint="#99FFFFFF"
        android:textSize="14sp"
        android:singleLine="true"
        android:maxLength="20"
        android:inputType="textPersonName|textNoSuggestions"
        android:imeOptions="actionDone"
        android:elevation="6dp" />

    <Button
        android:id="@+id/startButton"
        android:layout_width="@dimen/button_width"
        android:layout_height="@dimen/button_height"
        android:text="@string/play_bth"
        android:textSize="@dimen/button_text_size"
        android:textStyle="bold"
        android:layout_alignParentBottom="true"
        android:layout_alignParentEnd="true"
        android:layout_marginBottom="@dimen/bottom_margin"
        android:layout_marginEnd="@dimen/horizontal_margin"
        android:background="@drawable/button"
        android:textColor="#FFFFFF"
        android:elevation="8dp"/>

</RelativeLayout>
""", encoding="utf-8")

    (res_root / "drawable" / "background.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient
        android:startColor="#0F172A"
        android:centerColor="#1E1B4B"
        android:endColor="#111827"
        android:angle="135"/>
</shape>
""", encoding="utf-8")

    (res_root / "drawable" / "button.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android">
    <corners android:radius="8dp" />
    <solid android:color="#2563EB" />
    <stroke android:width="1dp" android:color="#60A5FA" />
</shape>
""", encoding="utf-8")

    (res_root / "values" / "strings.xml").write_text(f"""<resources>
    <string name="app_name">{args.app_name}</string>
    <string name="play_bth">MASUK SERVER</string>
    <string name="samp_ver">{args.server_title} Official Client (32/64-bit)</string>
    <string name="client_name">{args.server_title}</string>
    <string name="bug_info">Support Data Lite &amp; Data Full (Tanpa OBB)</string>
    <string name="authors">Official {args.server_title}</string>
</resources>
""", encoding="utf-8")

    (res_root / "values" / "dimens.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <dimen name="fab_margin">16dp</dimen>
    <dimen name="hud_margin_start">16dp</dimen>
    <dimen name="hud_margin_top">8dp</dimen>
    <dimen name="title1_text_size">24sp</dimen>
    <dimen name="title2_text_size">16sp</dimen>
    <dimen name="small_text_size">12sp</dimen>
    <dimen name="medium_text_size">14sp</dimen>
    <dimen name="very_small_text_size">10sp</dimen>
    <dimen name="button_width">220dp</dimen>
    <dimen name="button_height">52dp</dimen>
    <dimen name="button_text_size">16sp</dimen>
    <dimen name="horizontal_margin">20dp</dimen>
    <dimen name="bottom_margin">20dp</dimen>
    <dimen name="title_margin_top">20dp</dimen>
    <dimen name="cache_padding">6dp</dimen>
    <dimen name="icon_button_size">48dp</dimen>
    <dimen name="text_small">8sp</dimen>
    <dimen name="text_medium">10sp</dimen>
    <dimen name="text_large">12sp</dimen>
    <dimen name="margin_small">12dp</dimen>
    <dimen name="margin_medium">16dp</dimen>
</resources>
""", encoding="utf-8")

    # 8. Sanitize assets/settings.ini agar 0 plaintext leak
    assets_ini = app_main / "assets" / "settings.ini"
    if assets_ini.exists():
        assets_ini.write_text(f"""[client]
host = 127.0.0.1
port = 7777
name = {args.default_nick}
autoaim = 0

[debug]
debug = false
online = true

[gui]
Font = arial.ttf
FontSize = 30.0
FontOutline = 2
ChatPosX = 325.0
ChatPosY = 25.0
ChatSizeX = 1150.0
ChatSizeY = 220.0
ChatMaxMessages = 6
HealthBarWidth = 60.0
HealthBarHeight = 10.0
androidkeyboard = 0
""", encoding="utf-8")

    # 9. Patch AndroidManifest.xml (MainActivity sebagai LAUNCHER landscape, extractNativeLibs="true", tanpa gwpAsanMode)
    manifest = app_main / "AndroidManifest.xml"
    manifest.write_text("""<?xml version="1.0" encoding="utf-8" standalone="no"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    package="com.samp.mobile"
    android:installLocation="auto">

    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.VIBRATE" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE"/>
    <uses-permission android:name="android.permission.RECORD_AUDIO" />

    <uses-feature android:glEsVersion="0x00020000" android:required="true"/>
    <uses-feature android:name="android.hardware.touchscreen" android:required="false" />
    <uses-feature android:name="android.hardware.microphone" android:required="false" />

    <application
        android:requestLegacyExternalStorage="true"
        android:extractNativeLibs="true"
        android:banner="@mipmap/ic_launcher"
        android:hardwareAccelerated="true"
        android:icon="@mipmap/ic_launcher"
        android:isGame="true"
        android:largeHeap="true"
        android:label="@string/app_name"
        android:networkSecurityConfig="@xml/network_security_config"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.NoActionBar"
        android:usesCleartextTraffic="true"
        android:windowSoftInputMode="adjustNothing">

        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.provider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/provider_paths" />
        </provider>

        <activity
            android:name="com.samp.mobile.launcher.MainActivity"
            android:screenOrientation="sensorLandscape"
            android:theme="@style/Theme.AppCompat.NoActionBar"
            android:configChanges="keyboard|keyboardHidden|orientation|screenSize|uiMode"
            android:windowSoftInputMode="adjustNothing"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <activity
            android:name="com.samp.mobile.game.SAMP"
            android:screenOrientation="sensorLandscape"
            android:theme="@style/Theme.AppCompat.NoActionBar"
            android:configChanges="keyboard|keyboardHidden|orientation|screenSize|uiMode"
            android:launchMode="singleTask"
            android:windowSoftInputMode="adjustPan"
            android:exported="false" />
    </application>
</manifest>
""", encoding="utf-8")
    print("[+] Patched Java layer, resources, and AndroidManifest.xml (Zero-Blackscreen + Multi-Path Data Auto-Detector)")


def patch_gradle_and_proguard(repo: Path):
    # 1. Root build.gradle
    root_bg = repo / "build.gradle"
    root_bg.write_text("""buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.2.2'
    }
}

allprojects {
    repositories {
        google()
        mavenCentral()
        maven { url 'https://jitpack.io' }
    }
}

task clean(type: Delete) {
    delete rootProject.buildDir
}
""", encoding="utf-8")

    # 2. app/build.gradle (Dual-ABI armeabi-v7a + arm64-v8a, R8, Official Keystore, Legacy Packaging)
    app_bg = repo / "app" / "build.gradle"
    app_bg.write_text("""plugins {
    id 'com.android.application'
}

android {
    namespace 'com.samp.mobile'
    compileSdk 34

    signingConfigs {
        release {
            def ksPath = System.getenv("KEYSTORE_FILE") ?: System.getenv("SIGNING_STORE_FILE")
            if (ksPath != null && !ksPath.isEmpty()) {
                storeFile file(ksPath)
                storePassword System.getenv("KEYSTORE_PASSWORD") ?: System.getenv("SIGNING_STORE_PASSWORD")
                keyAlias System.getenv("KEY_ALIAS") ?: System.getenv("SIGNING_KEY_ALIAS")
                keyPassword System.getenv("KEY_PASSWORD") ?: System.getenv("SIGNING_KEY_PASSWORD")
                enableV1Signing true
                enableV2Signing true
            }
        }
    }

    defaultConfig {
        applicationId "com.samp.mobile"
        minSdk 24
        targetSdk 34
        versionCode 120
        versionName "1.2.0"

        multiDexEnabled true

        ndk {
            abiFilters 'armeabi-v7a', 'arm64-v8a'
            debugSymbolLevel 'NONE'
        }
    }

    packagingOptions {
        jniLibs {
            useLegacyPackaging true
            pickFirsts += ['**/*.so']
            excludes += ['META-INF/*']
        }
        resources {
            excludes += ['META-INF/*']
        }
    }

    ndkVersion '26.2.11394342'

    externalNativeBuild {
        cmake {
            path "src/main/cpp/CMakeLists.txt"
        }
    }

    buildTypes {
        release {
            debuggable false
            jniDebuggable false
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
            if ((System.getenv("KEYSTORE_FILE") ?: System.getenv("SIGNING_STORE_FILE")) != null) {
                signingConfig signingConfigs.release
            }
        }
        debug {
            debuggable false
            jniDebuggable false
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
            if ((System.getenv("KEYSTORE_FILE") ?: System.getenv("SIGNING_STORE_FILE")) != null) {
                signingConfig signingConfigs.release
            }
        }
    }

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }

    lintOptions {
        checkReleaseBuilds false
        abortOnError false
    }

    buildFeatures {
        prefab true
    }
}

dependencies {
    implementation fileTree(dir: "libs", include: ["*.jar"])
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.9.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    implementation 'com.intuit.sdp:sdp-android:1.1.0'
    implementation 'com.bytedance.android:shadowhook:1.0.9'
}
""", encoding="utf-8")

    # 3. app/proguard-rules.pro
    pg = repo / "app" / "proguard-rules.pro"
    pg.write_text("""# R8 / ProGuard Hardening Rules — XySAMP Mobile (Dual-ABI GTA-2.10)
-ignorewarnings
-dontwarn com.bda.controller.**
-dontwarn com.wardrumstudios.**
-dontwarn com.nvidia.**

-keepattributes Signature,InnerClasses,EnclosingMethod,Annotation

# Keep JNI entrypoints & engine classes called from libGTASA.so, libsamp.so, libImmEmulatorJ.so
-keep class com.nvidia.devtech.** { *; }
-keep class com.wardrumstudios.** { *; }
-keep class com.samp.mobile.game.** { *; }
-keep class com.samp.mobile.launcher.util.** { *; }
-keep class com.bda.controller.** { *; }
-keep class com.bytedance.shadowhook.** { *; }
-keep class com.immersion.** { *; }

-keepclasseswithmembernames class * {
    native <methods>;
}
""", encoding="utf-8")
    print("[+] Patched build.gradle, app/build.gradle (armeabi-v7a + arm64-v8a), and app/proguard-rules.pro")


def generate_server_pawn_script(args):
    dist_dir = ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    pawn_file = dist_dir / "gate_client.pwn"

    pawn_code = f"""// ============================================================================
// gate_client.pwn — Filterscript Verifikasi Client Khusus ({args.server_title})
// ============================================================================
// Taruh di folder `filterscripts/gate_client.pwn`, compile dengan `pawncc`,
// lalu tambahkan `gate_client` ke baris `filterscripts` di `server.cfg`.
// ============================================================================

#include <a_samp>

#define REQUIRED_CLIENT_TAG     "{args.tag}"
#define HANDSHAKE_KEY           ({args.key})
#define RPC_CLIENT_CHECK        (103)
#define CHECK_TYPE_HANDSHAKE    (0x48)

new bool:g_PlayerVerified[MAX_PLAYERS];
new g_PlayerChallenge[MAX_PLAYERS];
new g_VerifyTimer[MAX_PLAYERS];

forward VerifyClientTimeout(playerid);

stock CalcExpectedHandshake(challenge, offset, count)
{{
    new x = (challenge ^ HANDSHAKE_KEY) + ((offset << 16) | count);
    x ^= (x >>> 16);
    x = x * 0x7FEB352D;
    x ^= (x >>> 15);
    return (x & 0xFF);
}}

public OnFilterScriptInit()
{{
    print("====================================================");
    print(" [{args.server_title}] Client Lockdown Gate Loaded ");
    print(" Required Client Tag : " REQUIRED_CLIENT_TAG);
    print("====================================================");
    return 1;
}}

public OnPlayerConnect(playerid)
{{
    g_PlayerVerified[playerid] = false;

    // Layer 1: Cek Client Version Tag saat join
    new version[32];
    GetPlayerVersion(playerid, version, sizeof(version));

    if (strcmp(version, REQUIRED_CLIENT_TAG, false) != 0)
    {{
        SendClientMessage(playerid, 0xFF3333FF, "[SERVER] Anda wajib menggunakan APK Resmi {args.server_title}!");
        SetTimerEx("DelayedKick", 350, false, "i", playerid);
        return 1;
    }}

    // Layer 2: Kirim RPC 103 (ClientCheck) Challenge acak
    new challenge = (random(0x7FFF) << 16) | random(0xFFFF);
    g_PlayerChallenge[playerid] = challenge;

    SendClientCheck(playerid, CHECK_TYPE_HANDSHAKE, challenge, 0x10, 0x04);
    g_VerifyTimer[playerid] = SetTimerEx("VerifyClientTimeout", 6000, false, "i", playerid);
    return 1;
}}

public OnClientCheckResponse(playerid, actionid, memaddr, retndata)
{{
    if (actionid == CHECK_TYPE_HANDSHAKE)
    {{
        new expectedEcho = g_PlayerChallenge[playerid] ^ HANDSHAKE_KEY;
        new expectedRet  = CalcExpectedHandshake(g_PlayerChallenge[playerid], 0x10, 0x04);

        if (memaddr == expectedEcho && retndata == expectedRet)
        {{
            g_PlayerVerified[playerid] = true;
            if (g_VerifyTimer[playerid] != 0)
            {{
                KillTimer(g_VerifyTimer[playerid]);
                g_VerifyTimer[playerid] = 0;
            }}
            SendClientMessage(playerid, 0x33FF66FF, "[SERVER] Verifikasi APK Resmi {args.server_title} berhasil (Dual-ABI 32/64-bit).");
        }}
        else
        {{
            SendClientMessage(playerid, 0xFF3333FF, "[SERVER] Verifikasi keamanan APK gagal! Gunakan launcher resmi.");
            SetTimerEx("DelayedKick", 350, false, "i", playerid);
        }}
    }}
    return 1;
}}

public VerifyClientTimeout(playerid)
{{
    g_VerifyTimer[playerid] = 0;
    if (IsPlayerConnected(playerid) && !g_PlayerVerified[playerid])
    {{
        SendClientMessage(playerid, 0xFF3333FF, "[SERVER] Handshake client timeout! Gunakan APK Resmi {args.server_title}.");
        Kick(playerid);
    }}
    return 1;
}}

forward DelayedKick(playerid);
public DelayedKick(playerid)
{{
    if (IsPlayerConnected(playerid)) Kick(playerid);
    return 1;
}}
"""
    pawn_file.write_text(pawn_code, encoding="utf-8")
    print(f"[+] Generated server verification script -> {pawn_file}")


def main():
    args = parse_args()
    repo = Path(args.repo).resolve()
    samp_dir = repo / "app" / "src" / "main" / "cpp" / "samp"

    if not samp_dir.exists():
        print(f"[-] Direktori C++ SA-MP tidak ditemukan: {samp_dir}", file=sys.stderr)
        sys.exit(1)

    write_lockdown_header(samp_dir, args)
    patch_linux_case_sensitivity(samp_dir)
    patch_cmake_strip(samp_dir)
    patch_main_cpp(samp_dir)
    patch_netgame_cpp(samp_dir)
    patch_netrpc_cpp(samp_dir)
    patch_settings_cpp(samp_dir, args)
    patch_imgui_and_image_cpp(samp_dir)
    patch_hooks_cpp(samp_dir)
    patch_java_and_resources(repo, args)
    patch_gradle_and_proguard(repo)
    generate_server_pawn_script(args)
    print("\n[✓] Semua patch Dual-ABI (armeabi-v7a + arm64-v8a) + Zero-Blackscreen berhasil diterapkan!")


if __name__ == "__main__":
    main()
