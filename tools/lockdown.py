#!/usr/bin/env python3
"""
lockdown.py — Lombok Holiday Official Client Patcher (v2.1.0)
-------------------------------------------------------------
Fitur utama: rounded sidebar dashboard dengan carousel/banner dan berita dinamis,
daftar server multi-server, settings/preset FPS, controls perangkat, input empat
jari, dan mod center MonetLoader opsional. CLEO Android runtime belum dibundel.
Security: XOR obfuscation, R8, official signing pinning, anti-tamper, dan RPC
103 handshake yang hanya mengirim secret ke endpoint resmi.
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
    p = argparse.ArgumentParser(description="Build and patch Lombok Holiday Mobile Client v2.1.0")
    p.add_argument("--repo", required=True, help="Path ke clone repository")
    p.add_argument("--host", required=True, help="IP atau hostname server SA-MP")
    p.add_argument("--port", required=True, type=int, help="Port UDP server SA-MP")
    p.add_argument("--tag", default="LOMBOKHOLIDAY-2.1", help="Custom client version tag (maks 24 char)")
    p.add_argument("--key", required=True, help="32-bit hex key dari secret owner (jangan commit ke repo)")
    p.add_argument("--app-name", default="Lombok Holiday", help="Nama aplikasi Android")
    p.add_argument("--server-title", "--brand", dest="server_title", default="Lombok Holiday Roleplay", help="Nama server di tampilan launcher")
    p.add_argument("--default-nick", "--name", dest="default_nick", default="Warga_Lombok", help="Default nickname")
    p.add_argument("--package-id", default="com.lombokholiday.mobile", help="Application ID Android")
    p.add_argument("--cert-sha256", default="93fa85c2c42e17125bb66adbeab49fa3ccfcee646429aeb5078bdc322ea9341c",
                   help="SHA-256 fingerprint sertifikat Official Keystore")
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
    for p in samp_dir.rglob("*"):
        if p.is_file() and p.suffix in (".cpp", ".h", ".hpp", ".c"):
            raw = p.read_bytes()
            if b"\xef\xbb\xbf" in raw:
                p.write_bytes(raw.replace(b"\xef\xbb\xbf", b""))

    gui_h = samp_dir / "gui" / "gui.h"
    if gui_h.exists():
        txt = gui_h.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace("samp_widgets/playerTabList.h", "samp_widgets/playertablist.h")
        gui_h.write_text(txt, encoding="utf-8")

    rgba_cpp = samp_dir / "game" / "rgba.cpp"
    if rgba_cpp.exists():
        txt = rgba_cpp.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace('#include "RGBA.h"', '#include "rgba.h"')
        rgba_cpp.write_text(txt, encoding="utf-8")

    net_h = samp_dir / "voice_new" / "Network.h"
    if net_h.exists():
        txt = net_h.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace("../vendor/RakNet/", "../vendor/raknet/")
        net_h.write_text(txt, encoding="utf-8")

    main_h = samp_dir / "main.h"
    if main_h.exists():
        txt = main_h.read_text(encoding="utf-8", errors="ignore")
        txt = txt.replace('#define FONT_NAME "arial_bold.ttf"', '#define FONT_NAME "arial.ttf"')
        main_h.write_text(txt, encoding="utf-8")

    print("[+] Cleaned UTF-8 BOMs & fixed Linux header case-sensitivity in C++ sources")


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
    txt = main_cpp.read_text(encoding="utf-8-sig", errors="ignore").replace("\ufeff", "")

    if '#include "lockdown.h"' not in txt:
        txt = '#include "lockdown.h"\n' + txt

    pattern = re.compile(r'pNetGame\s*=\s*new\s+CNetGame\s*\([^;]+\)\s*;')
    replacement = (
        'pNetGame = new CNetGame(\n'
        '            pSettings->Get().szHost,\n'
        '            pSettings->Get().iPort,\n'
        '            pSettings->Get().szNickName,\n'
        '            pSettings->Get().szPassword);'
    )
    txt, count = pattern.subn(replacement, txt)
    if count == 0:
        raise RuntimeError("Gagal menemukan inisialisasi CNetGame di main.cpp")

    # Pastikan Java LoadingScreen langsung disembunyikan begitu OpenGL ImGui SplashScreen siap
    if "if (pJavaWrapper) pJavaWrapper->HideLoadingScreen();" not in txt:
        txt = txt.replace(
            "pUI->performLayout();",
            "pUI->performLayout();\n\tif (pJavaWrapper) pJavaWrapper->HideLoadingScreen();",
        )

    main_cpp.write_text(txt, encoding="utf-8")
    print(f"[+] Patched {main_cpp} (selected server from settings.ini + instant OpenGL SplashScreen handoff)")


def patch_netgame_cpp(samp_dir: Path, args):
    netgame_cpp = samp_dir / "net" / "netgame.cpp"
    txt = netgame_cpp.read_text(encoding="utf-8-sig", errors="ignore").replace("\ufeff", "")

    if '#include "../lockdown.h"' not in txt:
        txt = '#include "../lockdown.h"\n' + txt

    host_block = (
        'const char* targetHost = (szHostOrIp && szHostOrIp[0]) ? szHostOrIp : XySAMP::GetLockedHost();' + chr(10)
        + 'strncpy(m_szHostOrIp, targetHost, sizeof(m_szHostOrIp) - 1);' + chr(10)
        + 'm_szHostOrIp[sizeof(m_szHostOrIp) - 1] = ' + chr(39) + chr(92) + '0' + chr(39) + ';'
    )
    txt = re.sub(
        r'strncpy\s*\(\s*m_szHostOrIp\s*,\s*szHostOrIp\s*,\s*sizeof\s*\(\s*m_szHostOrIp\s*\)\s*\)\s*;',
        host_block,
        txt,
    )
    txt = re.sub(
        r'm_iPort\s*=\s*iPort\s*;',
        'm_iPort = (iPort >= 1 && iPort <= 65535) ? iPort : XySAMP::GetLockedPort();',
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
    txt = txt.replace(
        '"{FFFFFF}2.1 Client started"',
        f'"{{00E5FF}}[{args.server_title}]{{FFFFFF}} Client Resmi aktif — Selamat bermain!"',
    )

    netgame_cpp.write_text(txt, encoding="utf-8")
    print(f"[+] Patched {netgame_cpp} (selected host/port + branded client tag and welcome message)")


def patch_netrpc_cpp(samp_dir: Path):
    netrpc_cpp = samp_dir / "net" / "netrpc.cpp"
    txt = netrpc_cpp.read_text(encoding="utf-8-sig", errors="ignore").replace("\ufeff", "")

    if '#include "../lockdown.h"' not in txt:
        txt = '#include "../lockdown.h"\n' + txt
    if '#include <strings.h>' not in txt:
        txt = '#include <strings.h>\n' + txt

    handler_code = """
// --- Lombok Holiday Custom ClientCheck (RPC 103) Challenge-Response + Anti-Tamper ---
static int RPC_ClientCheck = 103;
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

    if (byteType == 0x48) {
        const bool officialTarget = pNetGame->m_iPort == XySAMP::GetLockedPort() &&
            strcasecmp(pNetGame->m_szHostOrIp, XySAMP::GetLockedHost()) == 0;
        if (!officialTarget) {
            RakNet::BitStream bsSend;
            bsSend.Write(byteType);
            bsSend.Write(dwAddress);
            bsSend.Write((uint8_t)0);
            pNetGame->GetRakClient()->RPC(&RPC_ClientCheck, &bsSend, HIGH_PRIORITY, RELIABLE, 0, false, UNASSIGNED_NETWORK_ID, NULL);
            return;
        }
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
        pNetGame->GetRakClient()->RPC(&RPC_ClientCheck, &bsSend, HIGH_PRIORITY, RELIABLE, 0, false, UNASSIGNED_NETWORK_ID, NULL);
        return;
    }

    RakNet::BitStream bsSend;
    bsSend.Write(byteType);
    bsSend.Write(dwAddress);
    bsSend.Write((uint8_t)0);
    pNetGame->GetRakClient()->RPC(&RPC_ClientCheck, &bsSend, HIGH_PRIORITY, RELIABLE, 0, false, UNASSIGNED_NETWORK_ID, NULL);
}
"""

    if "void ClientCheck(RPCParameters" not in txt:
        txt = txt.replace(
            "void RegisterRPCs(RakClientInterface *pRakClient)",
            handler_code + "\nvoid RegisterRPCs(RakClientInterface *pRakClient)",
        )
    elif "static int RPC_ClientCheck = 103;" not in txt:
        txt = txt.replace("void ClientCheck(RPCParameters *rpcParams)", "static int RPC_ClientCheck = 103;\nvoid ClientCheck(RPCParameters *rpcParams)")

    if "pRakClient->RegisterAsRemoteProcedureCall(&RPC_ClientCheck" not in txt:
        txt = txt.replace(
            "pRakClient->RegisterAsRemoteProcedureCall(&RPC_InitGame, InitGame);",
            "pRakClient->RegisterAsRemoteProcedureCall(&RPC_InitGame, InitGame);\n"
            "\tpRakClient->RegisterAsRemoteProcedureCall(&RPC_ClientCheck, ClientCheck);",
        )

    netrpc_cpp.write_text(txt, encoding="utf-8")
    print(f"[+] Patched {netrpc_cpp} (RPC_ClientCheck ID 103 challenge-response)")


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

    std::string host = iniOk ? reader.Get("client", "host", XySAMP::GetLockedHost()) : XySAMP::GetLockedHost();
    if (host.empty() || host.size() > MAX_SETTINGS_STRING) host = XySAMP::GetLockedHost();
    size_t hostLength = host.copy(m_Settings.szHost, MAX_SETTINGS_STRING);
    m_Settings.szHost[hostLength] = '\\0';
    long configuredPort = iniOk ? reader.GetInteger("client", "port", XySAMP::GetLockedPort()) : XySAMP::GetLockedPort();
    if (configuredPort < 1 || configuredPort > 65535) configuredPort = XySAMP::GetLockedPort();
    m_Settings.iPort = static_cast<int>(configuredPort);
    strncpy(m_Settings.szVersion, XySAMP::GetClientVersion(), MAX_SETTINGS_STRING);
    m_Settings.szVersion[MAX_SETTINGS_STRING - 1] = '\\0';

    m_Settings.bAutoAim = iniOk ? reader.GetBoolean("client", "autoaim", false) : false;
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
    m_Settings.iChatMaxMessages = iniOk ? (int)reader.GetInteger("gui", "ChatMaxMessages", 7) : 7;

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
    m_Settings.iCutout = iniOk ? reader.GetBoolean("gui", "cutout", true) : true;
    m_Settings.iFPSCounter = iniOk ? reader.GetBoolean("gui", "fps", true) : true;
    m_Settings.iFPSCount = iniOk ? (int)reader.GetInteger("gui", "FPSLimit", 60) : 60;
    m_Settings.iHPArmourText = iniOk ? reader.GetBoolean("gui", "hparmourtext", true) : true;
    m_Settings.iOutfitGuns = iniOk ? reader.GetBoolean("gui", "outfitguns", true) : true;
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
            fprintf(fp, "[client]\\nname=%s\\nhost=%s\\nport=%d\\nversion=0.3.7\\n\\n[gui]\\nFont=arial.ttf\\nFontSize=30.0\\nFontOutline=2\\nChatMaxMessages=7\\nFPSLimit=60\\nVoiceChatEnable=true\\nfirstperson=true\\ncutout=true\\nfps=true\\nhparmourtext=true\\noutfitguns=true\\n", m_Settings.szNickName, XySAMP::GetLockedHost(), XySAMP::GetLockedPort());
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
    print(f"[+] Patched {settings_cpp}")


def patch_imgui_and_image_cpp(samp_dir: Path):
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
    print("[+] Verified ImGui multi-font fallback & Image null-safety")


def patch_hooks_cpp(samp_dir: Path, args):
    hooks_cpp = samp_dir / "game" / "hooks.cpp"
    txt = hooks_cpp.read_text(encoding="utf-8", errors="ignore")

    # Pastikan kandidat folder com.lombokholiday.mobile terdaftar di NvUtilInit_hook
    if "com.lombokholiday.mobile" not in txt and "NvUtilInit_hook" in txt:
        txt = txt.replace(
            '"/storage/emulated/0/GTA/",',
            f'"/storage/emulated/0/Android/data/{args.package_id}/files/",\n            "/storage/emulated/0/GTA/",',
        )
    # Pastikan jika NvFOpen_orig diminta Text/*.gxt bahasa lain, fallback ke Text/american.gxt
    if 'NvFOpen_orig(r0, "Text/american.gxt", r2, r3)' not in txt and "NvFOpen_orig(r0, r1, r2, r3)" in txt:
        txt = txt.replace(
            "        if (apkSt) {\n            return apkSt;\n        }",
            '        if (apkSt) {\n            return apkSt;\n        }\n'
            '        if (strncasecmp(r1, "Text/", 5) == 0) {\n'
            '            apkSt = NvFOpen_orig(r0, "Text/american.gxt", r2, r3);\n'
            '            if (apkSt) return apkSt;\n'
            '        }',
        )
    hooks_cpp.write_text(txt, encoding="utf-8")
    print(f"[+] Updated {hooks_cpp} with {args.package_id} path & american.gxt fallback")


def patch_peripherals_and_game_java(repo: Path, args):
    java_root = repo / "app" / "src" / "main" / "java"
    res_root = repo / "app" / "src" / "main" / "res"

    # 1. WarGamepad.java: Full Gamepad (PS4/PS5/Xbox/Joystick) + Physical Keyboard (WASD/Action) + Mouse (OTG/BT)
    wargamepad = java_root / "com" / "wardrumstudios" / "utils" / "WarGamepad.java"
    wargamepad.write_text("""package com.wardrumstudios.utils;

import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.ViewParent;

public class WarGamepad extends WarBilling {
    // Xbox 360 / Rockstar Wardrum button bit indices
    public static final int BTN_A         = 0;  // Cross / Sprint / Accept
    public static final int BTN_B         = 1;  // Circle / Fire / Melee
    public static final int BTN_X         = 2;  // Square / Jump / Brake
    public static final int BTN_Y         = 3;  // Triangle / Enter-Exit Vehicle (F)
    public static final int BTN_START     = 4;  // Start / Menu
    public static final int BTN_BACK      = 5;  // Select / Camera View (V)
    public static final int BTN_L1        = 6;  // L1 / LB
    public static final int BTN_R1        = 7;  // R1 / RB / Handbrake / Aim
    public static final int BTN_DPAD_UP   = 8;  // D-Pad Up
    public static final int BTN_DPAD_DOWN = 9;  // D-Pad Down
    public static final int BTN_DPAD_LEFT = 10; // D-Pad Left / Prev Weapon (Q / Scroll Down)
    public static final int BTN_DPAD_RIGHT= 11; // D-Pad Right / Next Weapon (E / Scroll Up)
    public static final int BTN_L3        = 12; // L3 / Crouch (C) / Horn (H)
    public static final int BTN_R3        = 13; // R3 / Look Behind (Middle Mouse)

    public static volatile boolean sEnableKeyboardMouse = true;
    public static volatile boolean sEnableGamepad = true;
    private static volatile boolean sActivePeripheralInput = false;
    private static volatile int sButtonMask = 0;
    private static final float[] sAxes = new float[6]; // 0:LX, 1:LY, 2:RX, 3:RY, 4:LT(Aim), 5:RT(Fire/Gas)

    // Keyboard WASD state
    private static boolean sKeyW = false, sKeyS = false, sKeyA = false, sKeyD = false;
    private static boolean sKeyUp = false, sKeyDown = false, sKeyLeft = false, sKeyRight = false;

    public static boolean hasConnectedGamepad() {
        try {
            int[] ids = InputDevice.getDeviceIds();
            for (int id : ids) {
                InputDevice dev = InputDevice.getDevice(id);
                if (dev == null) continue;
                int src = dev.getSources();
                if ((src & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD ||
                    (src & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK) {
                    return true;
                }
            }
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean hasConnectedKeyboard() {
        try {
            int[] ids = InputDevice.getDeviceIds();
            for (int id : ids) {
                InputDevice dev = InputDevice.getDevice(id);
                if (dev == null) continue;
                if ((dev.getSources() & InputDevice.SOURCE_KEYBOARD) == InputDevice.SOURCE_KEYBOARD &&
                    dev.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC) {
                    return true;
                }
            }
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean hasConnectedMouse() {
        try {
            int[] ids = InputDevice.getDeviceIds();
            for (int id : ids) {
                InputDevice dev = InputDevice.getDevice(id);
                if (dev == null) continue;
                int src = dev.getSources();
                if ((src & InputDevice.SOURCE_MOUSE) == InputDevice.SOURCE_MOUSE ||
                    (src & InputDevice.SOURCE_TOUCHPAD) == InputDevice.SOURCE_TOUCHPAD) {
                    return true;
                }
            }
        } catch (Throwable ignored) {}
        return false;
    }

    private static void setBtn(int bit, boolean down) {
        if (bit < 0 || bit > 15) return;
        if (down) {
            sButtonMask |= (1 << bit);
            sActivePeripheralInput = true;
        } else {
            sButtonMask &= ~(1 << bit);
        }
    }

    private static void recomputeWasdAxes() {
        float lx = 0.0f;
        float ly = 0.0f;
        if (sKeyA || sKeyLeft)  lx -= 1.0f;
        if (sKeyD || sKeyRight) lx += 1.0f;
        if (sKeyW || sKeyUp)    ly -= 1.0f;
        if (sKeyS || sKeyDown)  ly += 1.0f;
        sAxes[0] = lx;
        sAxes[1] = ly;
    }

    public static boolean handleKeyEvent(int keyCode, KeyEvent event, boolean isDown) {
        if (event == null) return false;
        int src = event.getSource();
        boolean isPad = ((src & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD) ||
                        ((src & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK);

        if (isPad && sEnableGamepad) {
            switch (keyCode) {
                case KeyEvent.KEYCODE_BUTTON_A:      setBtn(BTN_A, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_B:      setBtn(BTN_B, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_X:      setBtn(BTN_X, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_Y:      setBtn(BTN_Y, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_START:  setBtn(BTN_START, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_SELECT: setBtn(BTN_BACK, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_L1:     setBtn(BTN_L1, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_R1:     setBtn(BTN_R1, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_L2:     sAxes[4] = isDown ? 1.0f : 0.0f; sActivePeripheralInput = true; return true;
                case KeyEvent.KEYCODE_BUTTON_R2:     sAxes[5] = isDown ? 1.0f : 0.0f; sActivePeripheralInput = true; return true;
                case KeyEvent.KEYCODE_BUTTON_THUMBL: setBtn(BTN_L3, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_THUMBR: setBtn(BTN_R3, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_UP:       setBtn(BTN_DPAD_UP, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_DOWN:     setBtn(BTN_DPAD_DOWN, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_LEFT:     setBtn(BTN_DPAD_LEFT, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_RIGHT:    setBtn(BTN_DPAD_RIGHT, isDown); return true;
            }
        }

        if (sEnableKeyboardMouse) {
            switch (keyCode) {
                case KeyEvent.KEYCODE_W:          sKeyW = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_S:          sKeyS = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_A:          sKeyA = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_D:          sKeyD = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_UP:    sKeyUp = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_DOWN:  sKeyDown = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_LEFT:  sKeyLeft = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_RIGHT: sKeyRight = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_SPACE:      setBtn(BTN_X, isDown); return false;
                case KeyEvent.KEYCODE_SHIFT_LEFT:
                case KeyEvent.KEYCODE_SHIFT_RIGHT:setBtn(BTN_A, isDown); return false;
                case KeyEvent.KEYCODE_F:
                case KeyEvent.KEYCODE_ENTER:      setBtn(BTN_Y, isDown); return false;
                case KeyEvent.KEYCODE_C:
                case KeyEvent.KEYCODE_H:          setBtn(BTN_L3, isDown); return false;
                case KeyEvent.KEYCODE_Q:          setBtn(BTN_DPAD_LEFT, isDown); return false;
                case KeyEvent.KEYCODE_E:          setBtn(BTN_DPAD_RIGHT, isDown); return false;
                case KeyEvent.KEYCODE_V:          setBtn(BTN_BACK, isDown); return false;
            }
        }
        return false;
    }

    public static boolean handleGenericMotion(MotionEvent event) {
        if (event == null) return false;
        int src = event.getSource();

        // 1. Gamepad / Joystick Analog Sticks, Triggers & Hat D-Pad
        if (sEnableGamepad && (((src & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK) ||
                               ((src & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD))) {
            sActivePeripheralInput = true;
            float lx = event.getAxisValue(MotionEvent.AXIS_X);
            float ly = event.getAxisValue(MotionEvent.AXIS_Y);
            float rx = event.getAxisValue(MotionEvent.AXIS_Z);
            if (Math.abs(rx) < 0.05f) rx = event.getAxisValue(MotionEvent.AXIS_RX);
            float ry = event.getAxisValue(MotionEvent.AXIS_RZ);
            if (Math.abs(ry) < 0.05f) ry = event.getAxisValue(MotionEvent.AXIS_RY);

            float lt = Math.max(event.getAxisValue(MotionEvent.AXIS_LTRIGGER), event.getAxisValue(MotionEvent.AXIS_BRAKE));
            float rt = Math.max(event.getAxisValue(MotionEvent.AXIS_RTRIGGER),
                       Math.max(event.getAxisValue(MotionEvent.AXIS_GAS), event.getAxisValue(MotionEvent.AXIS_THROTTLE)));

            sAxes[0] = Math.abs(lx) > 0.08f ? lx : 0.0f;
            sAxes[1] = Math.abs(ly) > 0.08f ? ly : 0.0f;
            sAxes[2] = Math.abs(rx) > 0.08f ? rx : 0.0f;
            sAxes[3] = Math.abs(ry) > 0.08f ? ry : 0.0f;
            sAxes[4] = lt;
            sAxes[5] = rt;

            float hatX = event.getAxisValue(MotionEvent.AXIS_HAT_X);
            float hatY = event.getAxisValue(MotionEvent.AXIS_HAT_Y);
            setBtn(BTN_DPAD_LEFT,  hatX < -0.25f);
            setBtn(BTN_DPAD_RIGHT, hatX >  0.25f);
            setBtn(BTN_DPAD_UP,    hatY < -0.25f);
            setBtn(BTN_DPAD_DOWN,  hatY >  0.25f);
            return true;
        }

        // 2. USB OTG / Bluetooth Mouse Buttons & Scroll Wheel
        if (sEnableKeyboardMouse && ((src & InputDevice.SOURCE_MOUSE) == InputDevice.SOURCE_MOUSE)) {
            int btns = event.getButtonState();
            boolean leftClick   = (btns & MotionEvent.BUTTON_PRIMARY) != 0;
            boolean rightClick  = (btns & MotionEvent.BUTTON_SECONDARY) != 0;
            boolean middleClick = (btns & MotionEvent.BUTTON_TERTIARY) != 0;

            setBtn(BTN_B, leftClick);
            setBtn(BTN_R1, rightClick);
            sAxes[4] = rightClick ? 1.0f : 0.0f;
            sAxes[5] = leftClick ? 1.0f : 0.0f;
            setBtn(BTN_R3, middleClick);

            if (event.getActionMasked() == MotionEvent.ACTION_SCROLL) {
                float vScroll = event.getAxisValue(MotionEvent.AXIS_VSCROLL);
                if (vScroll > 0.1f) {
                    setBtn(BTN_DPAD_RIGHT, true);
                    setBtn(BTN_DPAD_RIGHT, false);
                } else if (vScroll < -0.1f) {
                    setBtn(BTN_DPAD_LEFT, true);
                    setBtn(BTN_DPAD_LEFT, false);
                }
            }
            return false;
        }
        return false;
    }

    public int GetGamepadType() {
        if ((sEnableGamepad && hasConnectedGamepad()) || sActivePeripheralInput) {
            return 1;
        }
        return -1;
    }

    public int GetGamepadType(int index) {
        if (index == 0 && ((sEnableGamepad && hasConnectedGamepad()) || sActivePeripheralInput)) {
            return 1;
        }
        return -1;
    }

    public int GetGamepadButtons() {
        return sButtonMask;
    }

    public int GetGamepadButtons(int index) {
        return index == 0 ? sButtonMask : 0;
    }

    public float GetGamepadAxis(int axisId) {
        if (axisId >= 0 && axisId < sAxes.length) {
            return sAxes[axisId];
        }
        return 0.0f;
    }

    public float GetGamepadAxis(int index, int axisId) {
        if (index == 0 && axisId >= 0 && axisId < sAxes.length) {
            return sAxes[axisId];
        }
        return 0.0f;
    }

    public int GetGamepadTrack(int index, int trackId, int coord) {
        return 0;
    }

    public int GetGamepadTrack(int i, int i2) {
        return 0;
    }

    public native boolean processTouchpadAsPointer(ViewParent viewParent, boolean z);
}
""", encoding="utf-8")

    # 2. Patch NvEventQueueActivity.java agar meneruskan onGenericMotionEvent & key events ke WarGamepad
    nvev = java_root / "com" / "nvidia" / "devtech" / "NvEventQueueActivity.java"
    ntxt = nvev.read_text(encoding="utf-8", errors="ignore")
    if "WarGamepad.handleKeyEvent" not in ntxt:
        ntxt = ntxt.replace(
            "public boolean onKeyDown(int keyCode, KeyEvent event)\n    {",
            "public boolean onKeyDown(int keyCode, KeyEvent event)\n    {\n"
            "        if (com.wardrumstudios.utils.WarGamepad.handleKeyEvent(keyCode, event, true)) {\n"
            "            return true;\n"
            "        }",
        )
        ntxt = ntxt.replace(
            "public boolean onKeyUp(int keyCode, KeyEvent event)\n    {",
            "public boolean onKeyUp(int keyCode, KeyEvent event)\n    {\n"
            "        if (com.wardrumstudios.utils.WarGamepad.handleKeyEvent(keyCode, event, false)) {\n"
            "            return true;\n"
            "        }",
        )
        ntxt = ntxt.replace(
            "public boolean onTouchEvent(MotionEvent event)\n    {\n        return super.onTouchEvent(event);\n    }",
            "public boolean onTouchEvent(MotionEvent event)\n    {\n        return super.onTouchEvent(event);\n    }\n\n"
            "    @Override\n"
            "    public boolean onGenericMotionEvent(MotionEvent event)\n    {\n"
            "        if (com.wardrumstudios.utils.WarGamepad.handleGenericMotion(event)) {\n"
            "            return true;\n"
            "        }\n"
            "        return super.onGenericMotionEvent(event);\n"
            "    }",
        )
        ntxt = ntxt.replace(
            "view.setFocusableInTouchMode(true);",
            "view.setFocusableInTouchMode(true);\n        view.requestFocus();",
        )
        nvev.write_text(ntxt, encoding="utf-8")

    # 3. Patch SAMP.java untuk shortcut Keyboard Fisik (T / F6 / Slash -> Buka Chat, ESC -> Back)
    samp_java = java_root / "com" / "samp" / "mobile" / "game" / "SAMP.java"
    stxt = samp_java.read_text(encoding="utf-8", errors="ignore")
    old_key_down = re.compile(
        r"@Override\s*public boolean onKeyDown\(int keyCode, KeyEvent event\)\s*\{.*?\n    \}",
        re.DOTALL,
    )
    new_key_down = """@Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK || keyCode == KeyEvent.KEYCODE_ESCAPE) {
            onEventBackPressed();
            return true;
        }
        // Shortcut Keyboard Fisik PC-Style: T, F6, atau '/' membuka Chat Box SA-MP
        if (event != null && event.getRepeatCount() == 0) {
            if (keyCode == KeyEvent.KEYCODE_T || keyCode == KeyEvent.KEYCODE_F6 || keyCode == KeyEvent.KEYCODE_SLASH) {
                if (mKeyboard != null && !mDialog.isShow) {
                    showKeyboard();
                    return true;
                }
            }
        }
        return super.onKeyDown(keyCode, event);
    }"""
    stxt, _ = old_key_down.subn(new_key_down, stxt, count=1)
    samp_java.write_text(stxt, encoding="utf-8")

    # 4. Patch LoadingScreen.java & loadingscreen.xml agar tampil elegan & auto-hide tanpa menutupi OpenGL SurfaceView
    loading_java = java_root / "com" / "samp" / "mobile" / "game" / "ui" / "LoadingScreen.java"
    loading_java.write_text("""package com.samp.mobile.game.ui;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import androidx.constraintlayout.widget.ConstraintLayout;
import com.samp.mobile.R;

public class LoadingScreen {
    private final Activity activity;
    private final ConstraintLayout mainLayout;

    public LoadingScreen(Activity activity) {
        this.activity = activity;
        mainLayout = (ConstraintLayout) activity.getLayoutInflater().inflate(R.layout.loadingscreen, null);
        activity.addContentView(mainLayout, new ConstraintLayout.LayoutParams(-1, -1));
        // Auto-hide setelah 2.5 detik supaya OpenGL ImGui SplashScreen terlihat jelas & bebas blackscreen
        new Handler(Looper.getMainLooper()).postDelayed(this::hide, 2500);
    }

    public void hide() {
        if (mainLayout != null) {
            mainLayout.setVisibility(View.GONE);
            try {
                if (mainLayout.getParent() instanceof ViewGroup) {
                    ((ViewGroup) mainLayout.getParent()).removeView(mainLayout);
                }
            } catch (Throwable ignored) {}
        }
    }
}
""", encoding="utf-8")

    (res_root / "layout" / "loadingscreen.xml").write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/background">

    <ImageView
        android:id="@+id/imageView3"
        android:layout_width="110dp"
        android:layout_height="110dp"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintVertical_bias="0.38"
        app:srcCompat="@drawable/logo" />

    <TextView
        android:id="@+id/loadingTitle"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="14dp"
        android:text="{args.server_title}"
        android:textColor="#FFFFFF"
        android:textSize="20sp"
        android:textStyle="bold"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toBottomOf="@+id/imageView3" />

    <TextView
        android:id="@+id/loadingSub"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="4dp"
        android:text="Menyiapkan Engine GTA:SA &amp; OpenGL..."
        android:textColor="#38BDF8"
        android:textSize="13sp"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toBottomOf="@+id/loadingTitle" />

    <ProgressBar
        android:id="@+id/progressBar2"
        style="?android:attr/progressBarStyleHorizontal"
        android:layout_width="260dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="16dp"
        android:indeterminate="true"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toBottomOf="@+id/loadingSub" />
</androidx.constraintlayout.widget.ConstraintLayout>
""", encoding="utf-8")

    print("[+] Patched WarGamepad.java, NvEventQueueActivity.java, SAMP.java, and LoadingScreen.java")


def patch_launcher_dashboard_and_downloader(repo: Path, args):
    app_main = repo / "app" / "src" / "main"
    java_root = app_main / "java"
    res_root = app_main / "res"
    launcher_dir = java_root / "com" / "samp" / "mobile" / "launcher"

    # Update Adaptive Icon XMLs
    (res_root / "drawable" / "ic_launcher_background.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient
        android:startColor="#0B132B"
        android:centerColor="#1E1B4B"
        android:endColor="#3B0764"
        android:angle="135" />
</shape>
""", encoding="utf-8")

    (res_root / "drawable" / "background.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient
        android:startColor="#090D1A"
        android:centerColor="#131B36"
        android:endColor="#1E113A"
        android:angle="135"/>
</shape>
""", encoding="utf-8")

    (res_root / "drawable" / "button.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android">
    <corners android:radius="10dp" />
    <gradient
        android:startColor="#0284C7"
        android:endColor="#7C3AED"
        android:angle="0" />
    <stroke android:width="1dp" android:color="#38BDF8" />
</shape>
""", encoding="utf-8")

    # Tulis main_activity.xml: Modern Cyber Blue-Purple Dashboard dengan Sidebar + 3 Panel (Beranda/Downloader, Settings Lengkap, Peripherals)
    (res_root / "layout" / "main_activity.xml").write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="horizontal"
    android:background="@drawable/background"
    android:baselineAligned="false">

    <!-- SIDEBAR NAVIGASI KIRI -->
    <LinearLayout
        android:layout_width="215dp"
        android:layout_height="match_parent"
        android:orientation="vertical"
        android:background="#B30B1021"
        android:padding="14dp">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="horizontal"
            android:gravity="center_vertical">

            <ImageView
                android:id="@+id/logoImage"
                android:layout_width="46dp"
                android:layout_height="46dp"
                android:src="@drawable/logo" />

            <LinearLayout
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_weight="1"
                android:layout_marginStart="10dp"
                android:orientation="vertical">

                <TextView
                    android:id="@+id/title1"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="{args.app_name}"
                    android:textColor="#FFFFFF"
                    android:textSize="15sp"
                    android:textStyle="bold" />

                <TextView
                    android:id="@+id/title2"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="ROLEPLAY CLIENT"
                    android:textColor="#38BDF8"
                    android:textSize="10sp"
                    android:textStyle="bold" />
            </LinearLayout>
        </LinearLayout>

        <TextView
            android:id="@+id/abiBadgeText"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginTop="8dp"
            android:background="#331E293B"
            android:padding="5dp"
            android:gravity="center"
            android:text="ABI: ARM64 / ARMv7"
            android:textColor="#A78BFA"
            android:textSize="10sp"
            android:textStyle="bold" />

        <View
            android:layout_width="match_parent"
            android:layout_height="1dp"
            android:layout_marginTop="10dp"
            android:layout_marginBottom="10dp"
            android:background="#2638BDF8" />

        <Button
            android:id="@+id/tabBtnHome"
            android:layout_width="match_parent"
            android:layout_height="40dp"
            android:text="BERANDA &amp; DATA"
            android:textColor="#FFFFFF"
            android:textSize="12sp"
            android:textStyle="bold"
            android:background="#CC1D4ED8" />

        <Button
            android:id="@+id/tabBtnSettings"
            android:layout_width="match_parent"
            android:layout_height="40dp"
            android:layout_marginTop="8dp"
            android:text="PENGATURAN (SETTINGS)"
            android:textColor="#CBD5E1"
            android:textSize="11sp"
            android:textStyle="bold"
            android:background="#661E293B" />

        <Button
            android:id="@+id/tabBtnControls"
            android:layout_width="match_parent"
            android:layout_height="40dp"
            android:layout_marginTop="8dp"
            android:text="KEYBOARD / MOUSE / PAD"
            android:textColor="#CBD5E1"
            android:textSize="11sp"
            android:textStyle="bold"
            android:background="#661E293B" />

        <View
            android:layout_width="match_parent"
            android:layout_height="0dp"
            android:layout_weight="1" />

        <TextView
            android:id="@+id/authorText"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:gravity="center"
            android:text="{args.server_title} v2.0"
            android:textColor="#64748B"
            android:textSize="10sp" />
    </LinearLayout>

    <!-- AREA KONTEN UTAMA KANAN -->
    <FrameLayout
        android:layout_width="0dp"
        android:layout_height="match_parent"
        android:layout_weight="1"
        android:padding="14dp">

        <!-- ================= PANEL 1: BERANDA & IN-APP DATA DOWNLOADER ================= -->
        <ScrollView
            android:id="@+id/panelHome"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:fillViewport="true">

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:orientation="vertical">

                <!-- Kartu Input Akun & Tombol Play -->
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:background="#99111827"
                    android:padding="14dp">

                    <TextView
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content"
                        android:text="AKUN ROLEPLAY &amp; KONEKSI SERVER"
                        android:textColor="#38BDF8"
                        android:textSize="12sp"
                        android:textStyle="bold" />

                    <LinearLayout
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="10dp"
                        android:orientation="horizontal"
                        android:gravity="center_vertical">

                        <EditText
                            android:id="@+id/nicknameInput"
                            android:layout_width="0dp"
                            android:layout_height="44dp"
                            android:layout_weight="1.2"
                            android:background="#CC1E293B"
                            android:paddingStart="12dp"
                            android:paddingEnd="12dp"
                            android:hint="Nickname (Nama_Roleplay)"
                            android:textColor="#FFFFFF"
                            android:textColorHint="#94A3B8"
                            android:textSize="13sp"
                            android:singleLine="true"
                            android:maxLength="20"
                            android:inputType="textPersonName|textNoSuggestions"
                            android:imeOptions="actionDone" />

                        <EditText
                            android:id="@+id/passwordInput"
                            android:layout_width="0dp"
                            android:layout_height="44dp"
                            android:layout_weight="0.8"
                            android:layout_marginStart="8dp"
                            android:background="#CC1E293B"
                            android:paddingStart="12dp"
                            android:paddingEnd="12dp"
                            android:hint="Password Server (Opsional)"
                            android:textColor="#FFFFFF"
                            android:textColorHint="#64748B"
                            android:textSize="12sp"
                            android:singleLine="true"
                            android:inputType="textPassword"
                            android:imeOptions="actionDone" />

                        <Button
                            android:id="@+id/startButton"
                            android:layout_width="165dp"
                            android:layout_height="44dp"
                            android:layout_marginStart="10dp"
                            android:background="@drawable/button"
                            android:text="MASUK SERVER"
                            android:textColor="#FFFFFF"
                            android:textSize="13sp"
                            android:textStyle="bold" />
                    </LinearLayout>
                </LinearLayout>

                <!-- Kartu Status Data GTA & In-App Data Downloader -->
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="12dp"
                    android:orientation="vertical"
                    android:background="#99111827"
                    android:padding="14dp">

                    <LinearLayout
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:orientation="horizontal"
                        android:gravity="center_vertical">

                        <TextView
                            android:layout_width="0dp"
                            android:layout_height="wrap_content"
                            android:layout_weight="1"
                            android:text="MANAJER DATA GTA:SA (SUPPORT LITE &amp; FULL TANPA OBB)"
                            android:textColor="#A78BFA"
                            android:textSize="12sp"
                            android:textStyle="bold" />

                        <TextView
                            android:id="@+id/dataBadgeStatus"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:paddingStart="8dp"
                            android:paddingEnd="8dp"
                            android:paddingTop="3dp"
                            android:paddingBottom="3dp"
                            android:background="#3310B981"
                            android:text="MENGECEK DATA..."
                            android:textColor="#34D399"
                            android:textSize="10sp"
                            android:textStyle="bold" />
                    </LinearLayout>

                    <TextView
                        android:id="@+id/bugText"
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="6dp"
                        android:text="Mendeteksi direktori data GTA..."
                        android:textColor="#E2E8F0"
                        android:textSize="11sp" />

                    <ProgressBar
                        android:id="@+id/downloadProgressBar"
                        style="?android:attr/progressBarStyleHorizontal"
                        android:layout_width="match_parent"
                        android:layout_height="10dp"
                        android:layout_marginTop="10dp"
                        android:max="100"
                        android:progress="0"
                        android:visibility="gone" />

                    <TextView
                        android:id="@+id/downloadStatusText"
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="4dp"
                        android:text="Siap mengunduh data langsung di dalam aplikasi (Auto-Extract)."
                        android:textColor="#94A3B8"
                        android:textSize="11sp" />

                    <LinearLayout
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="10dp"
                        android:orientation="horizontal">

                        <Button
                            android:id="@+id/btnDownloadLite"
                            android:layout_width="0dp"
                            android:layout_height="38dp"
                            android:layout_weight="1"
                            android:background="#CC0284C7"
                            android:text="DOWNLOAD DATA LITE"
                            android:textColor="#FFFFFF"
                            android:textSize="11sp"
                            android:textStyle="bold" />

                        <Button
                            android:id="@+id/btnDownloadFull"
                            android:layout_width="0dp"
                            android:layout_height="38dp"
                            android:layout_weight="1"
                            android:layout_marginStart="8dp"
                            android:background="#CC7C3AED"
                            android:text="DOWNLOAD DATA FULL"
                            android:textColor="#FFFFFF"
                            android:textSize="11sp"
                            android:textStyle="bold" />

                        <Button
                            android:id="@+id/btnCustomUrl"
                            android:layout_width="0dp"
                            android:layout_height="38dp"
                            android:layout_weight="0.9"
                            android:layout_marginStart="8dp"
                            android:background="#CC334155"
                            android:text="URL ZIP CUSTOM"
                            android:textColor="#E2E8F0"
                            android:textSize="11sp"
                            android:textStyle="bold" />
                    </LinearLayout>
                </LinearLayout>
            </LinearLayout>
        </ScrollView>

        <!-- ================= PANEL 2: PENGATURAN LENGKAP (SETTINGS) ================= -->
        <ScrollView
            android:id="@+id/panelSettings"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:visibility="gone"
            android:fillViewport="true">

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:orientation="vertical"
                android:background="#99111827"
                android:padding="14dp">

                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="PENGATURAN GRAFIS, CHAT &amp; FITUR GAME (SAMP/settings.ini)"
                    android:textColor="#38BDF8"
                    android:textSize="13sp"
                    android:textStyle="bold" />

                <!-- Pilihan FPS Limit -->
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="10dp"
                    android:orientation="horizontal"
                    android:gravity="center_vertical">

                    <TextView
                        android:layout_width="130dp"
                        android:layout_height="wrap_content"
                        android:text="Batas FPS Game:"
                        android:textColor="#FFFFFF"
                        android:textSize="12sp" />

                    <Button
                        android:id="@+id/btnFps30"
                        android:layout_width="64dp"
                        android:layout_height="34dp"
                        android:background="#661E293B"
                        android:text="30 FPS"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />

                    <Button
                        android:id="@+id/btnFps60"
                        android:layout_width="64dp"
                        android:layout_height="34dp"
                        android:layout_marginStart="6dp"
                        android:background="#CC0284C7"
                        android:text="60 FPS"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />

                    <Button
                        android:id="@+id/btnFps90"
                        android:layout_width="64dp"
                        android:layout_height="34dp"
                        android:layout_marginStart="6dp"
                        android:background="#661E293B"
                        android:text="90 FPS"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />

                    <Button
                        android:id="@+id/btnFps120"
                        android:layout_width="70dp"
                        android:layout_height="34dp"
                        android:layout_marginStart="6dp"
                        android:background="#661E293B"
                        android:text="120 FPS"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />
                </LinearLayout>

                <!-- Pilihan Baris Chat & Ukuran Font -->
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="8dp"
                    android:orientation="horizontal"
                    android:gravity="center_vertical">

                    <TextView
                        android:layout_width="130dp"
                        android:layout_height="wrap_content"
                        android:text="Jumlah Baris Chat:"
                        android:textColor="#FFFFFF"
                        android:textSize="12sp" />

                    <Button
                        android:id="@+id/btnChat5"
                        android:layout_width="64dp"
                        android:layout_height="34dp"
                        android:background="#661E293B"
                        android:text="5 Baris"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />

                    <Button
                        android:id="@+id/btnChat7"
                        android:layout_width="64dp"
                        android:layout_height="34dp"
                        android:layout_marginStart="6dp"
                        android:background="#CC0284C7"
                        android:text="7 Baris"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />

                    <Button
                        android:id="@+id/btnChat9"
                        android:layout_width="64dp"
                        android:layout_height="34dp"
                        android:layout_marginStart="6dp"
                        android:background="#661E293B"
                        android:text="9 Baris"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />

                    <Button
                        android:id="@+id/btnChat12"
                        android:layout_width="70dp"
                        android:layout_height="34dp"
                        android:layout_marginStart="6dp"
                        android:background="#661E293B"
                        android:text="12 Baris"
                        android:textColor="#FFFFFF"
                        android:textSize="11sp" />
                </LinearLayout>

                <!-- Grid CheckBox Pengaturan Fitur -->
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="10dp"
                    android:orientation="horizontal">

                    <LinearLayout
                        android:layout_width="0dp"
                        android:layout_height="wrap_content"
                        android:layout_weight="1"
                        android:orientation="vertical">

                        <CheckBox
                            android:id="@+id/cbVoiceChat"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="true"
                            android:text="Voice Chat In-Game (Mic)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbFpsCounter"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="true"
                            android:text="Tampilkan FPS Counter"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbFirstPerson"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="true"
                            android:text="Mode Kamera First-Person (FPP)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbCutout"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="true"
                            android:text="Full Screen (Layar Poni/Cutout)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbAndroidKeyboard"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="false"
                            android:text="Gunakan Keyboard Sistem Android"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />
                    </LinearLayout>

                    <LinearLayout
                        android:layout_width="0dp"
                        android:layout_height="wrap_content"
                        android:layout_weight="1"
                        android:orientation="vertical">

                        <CheckBox
                            android:id="@+id/cbHpArmourText"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="true"
                            android:text="Tampilkan Angka HP &amp; Armour"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbOutfitGuns"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="true"
                            android:text="Senjata Terlihat di Badan (Outfit)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbRadarRect"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="false"
                            android:text="Bentuk Radar Kotak (Rect Radar)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbPcMoney"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="false"
                            android:text="Format Uang Gaya PC ($00000000)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbSkyBox"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="false"
                            android:text="Efek Langit HD (SkyBox)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />

                        <CheckBox
                            android:id="@+id/cbSnow"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:checked="false"
                            android:text="Efek Salju (Winter Snow)"
                            android:textColor="#E2E8F0"
                            android:textSize="12sp" />
                    </LinearLayout>
                </LinearLayout>

                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="10dp"
                    android:orientation="horizontal">

                    <Button
                        android:id="@+id/btnSaveSettings"
                        android:layout_width="0dp"
                        android:layout_height="38dp"
                        android:layout_weight="1"
                        android:background="@drawable/button"
                        android:text="SIMPAN PENGATURAN"
                        android:textColor="#FFFFFF"
                        android:textSize="12sp"
                        android:textStyle="bold" />

                    <Button
                        android:id="@+id/btnResetSettings"
                        android:layout_width="160dp"
                        android:layout_height="38dp"
                        android:layout_marginStart="10dp"
                        android:background="#CC334155"
                        android:text="RESET DEFAULT"
                        android:textColor="#E2E8F0"
                        android:textSize="11sp"
                        android:textStyle="bold" />
                </LinearLayout>
            </LinearLayout>
        </ScrollView>

        <!-- ================= PANEL 3: KEYBOARD FISIK, MOUSE & GAMEPAD ================= -->
        <ScrollView
            android:id="@+id/panelControls"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:visibility="gone"
            android:fillViewport="true">

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:orientation="vertical"
                android:background="#99111827"
                android:padding="14dp">

                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="DUKUNGAN KEYBOARD FISIK, MOUSE (OTG/BT) &amp; GAMEPAD CONTROLLER"
                    android:textColor="#38BDF8"
                    android:textSize="13sp"
                    android:textStyle="bold" />

                <TextView
                    android:id="@+id/peripheralStatusText"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="8dp"
                    android:background="#661E293B"
                    android:padding="10dp"
                    android:text="Memindai perangkat USB OTG / Bluetooth..."
                    android:textColor="#34D399"
                    android:textSize="12sp"
                    android:textStyle="bold" />

                <CheckBox
                    android:id="@+id/cbEnableKeyboardMouse"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="8dp"
                    android:checked="true"
                    android:text="Aktifkan Kontrol Keyboard Fisik (WASD + Chat T/F6) &amp; Mouse (Klik Kiri/Kanan)"
                    android:textColor="#FFFFFF"
                    android:textSize="12sp" />

                <CheckBox
                    android:id="@+id/cbEnableGamepad"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:checked="true"
                    android:text="Aktifkan Kontrol Gamepad / Joystick (PS4, PS5, Xbox, MOGA, USB/BT Pad)"
                    android:textColor="#FFFFFF"
                    android:textSize="12sp" />

                <TextView
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="8dp"
                    android:text="• Keyboard Fisik: WASD = Jalan/Setir | Space = Lompat/Rem | Shift = Lari | F / Enter = Masuk Kendaraan | C = Jongkok | H = Klakson | Q/E = Ganti Senjata | T / F6 / '/' = Buka Chat SA-MP | ESC = Menu/Kembali\n• Mouse OTG/BT: Klik Kiri = Tembak/Pukul | Klik Kanan = Bidik (Aim) | Scroll = Ganti Senjata | Klik Tengah = Lihat Belakang\n• Gamepad: Analog Kiri = Gerak | Analog Kanan = Kamera | R2/B = Tembak | L2/R1 = Bidik | Y/Segitiga = Kendaraan | A/Silang = Lari | X/Kotak = Lompat"
                    android:textColor="#CBD5E1"
                    android:textSize="11sp" />

                <Button
                    android:id="@+id/btnRefreshDevices"
                    android:layout_width="200dp"
                    android:layout_height="36dp"
                    android:layout_marginTop="10dp"
                    android:background="#CC0284C7"
                    android:text="SCAN ULANG PERANGKAT"
                    android:textColor="#FFFFFF"
                    android:textSize="11sp"
                    android:textStyle="bold" />
            </LinearLayout>
        </ScrollView>
    </FrameLayout>
</LinearLayout>
""", encoding="utf-8")

    (res_root / "values" / "strings.xml").write_text(f"""<resources>
    <string name="app_name">{args.app_name}</string>
    <string name="play_bth">MASUK SERVER</string>
    <string name="samp_ver">{args.server_title}</string>
    <string name="client_name">{args.app_name}</string>
    <string name="bug_info">Support Data Lite &amp; Data Full (Tanpa OBB)</string>
    <string name="authors">{args.server_title}</string>
</resources>
""", encoding="utf-8")

    # Tulis MainActivity.java lengkap dengan 3 Tab + Settings Manager + In-App Data Downloader & Auto-Unzip + Peripheral Detector
    cert_pin = (args.cert_sha256 or "").strip().lower().replace(":", "")
    main_activity_java = launcher_dir / "MainActivity.java"
    main_activity_java.write_text(f"""package com.samp.mobile.launcher;

import android.app.Activity;
import android.app.AlertDialog;
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
import android.view.InputDevice;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.samp.mobile.R;
import com.samp.mobile.game.SAMP;
import com.wardrumstudios.utils.WarGamepad;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class MainActivity extends AppCompatActivity {{
    private static final String PREFS_NAME = "lombok_holiday_prefs";
    private static final String KEY_NICKNAME = "player_nickname";
    private static final String KEY_PASSWORD = "server_password";
    private static final String KEY_FPS = "fps_limit";
    private static final String KEY_CHAT_LINES = "chat_lines";
    private static final String KEY_CUSTOM_ZIP_URL = "custom_zip_url";
    private static final String DEFAULT_NICK = "{args.default_nick}";
    private static final int LOCKED_PORT = {args.port};
    private static final String EXPECTED_CERT_SHA256 = "{cert_pin}";
    private static final String REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/xykal/XySAMP-Mobile/main/data-config.json";

    private String liteDataUrl = "";
    private String fullDataUrl = "";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private volatile boolean isDownloading = false;

    // UI Elements
    private Button tabBtnHome, tabBtnSettings, tabBtnControls;
    private ScrollView panelHome, panelSettings, panelControls;
    private Button startButton, btnDownloadLite, btnDownloadFull, btnCustomUrl;
    private Button btnFps30, btnFps60, btnFps90, btnFps120;
    private Button btnChat5, btnChat7, btnChat9, btnChat12;
    private Button btnSaveSettings, btnResetSettings, btnRefreshDevices;
    private EditText nicknameInput, passwordInput;
    private TextView abiBadgeText, dataBadgeStatus, bugText, downloadStatusText, peripheralStatusText;
    private ProgressBar downloadProgressBar;

    private CheckBox cbVoiceChat, cbFpsCounter, cbFirstPerson, cbCutout, cbAndroidKeyboard;
    private CheckBox cbHpArmourText, cbOutfitGuns, cbRadarRect, cbPcMoney, cbSkyBox, cbSnow;
    private CheckBox cbEnableKeyboardMouse, cbEnableGamepad;

    private int selectedFps = 60;
    private int selectedChatLines = 7;
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
                    storagePermissionGranted = true; // App-specific external files dir tetap bisa diakses tanpa izin di Android 10+
                    onPermissionReady();
                }}
            }});

    private final ActivityResultLauncher<Intent> manageStorageLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {{
                storagePermissionGranted = true;
                onPermissionReady();
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
            setupTabsAndListeners();
            checkAndRequestStoragePermission();
            onPermissionReady();
            fetchRemoteDataConfig();
            refreshPeripheralsStatus();
        }} catch (Exception e) {{
            finish();
        }}
    }}

    private void initViews() {{
        tabBtnHome = findViewById(R.id.tabBtnHome);
        tabBtnSettings = findViewById(R.id.tabBtnSettings);
        tabBtnControls = findViewById(R.id.tabBtnControls);

        panelHome = findViewById(R.id.panelHome);
        panelSettings = findViewById(R.id.panelSettings);
        panelControls = findViewById(R.id.panelControls);

        abiBadgeText = findViewById(R.id.abiBadgeText);
        if (abiBadgeText != null) {{
            String abi = (Build.SUPPORTED_ABIS != null && Build.SUPPORTED_ABIS.length > 0) ? Build.SUPPORTED_ABIS[0] : "arm64-v8a";
            abiBadgeText.setText("ABI AKTIF: " + abi.toUpperCase(Locale.ROOT));
        }}

        nicknameInput = findViewById(R.id.nicknameInput);
        passwordInput = findViewById(R.id.passwordInput);
        startButton = findViewById(R.id.startButton);

        dataBadgeStatus = findViewById(R.id.dataBadgeStatus);
        bugText = findViewById(R.id.bugText);
        downloadProgressBar = findViewById(R.id.downloadProgressBar);
        downloadStatusText = findViewById(R.id.downloadStatusText);
        btnDownloadLite = findViewById(R.id.btnDownloadLite);
        btnDownloadFull = findViewById(R.id.btnDownloadFull);
        btnCustomUrl = findViewById(R.id.btnCustomUrl);

        btnFps30 = findViewById(R.id.btnFps30);
        btnFps60 = findViewById(R.id.btnFps60);
        btnFps90 = findViewById(R.id.btnFps90);
        btnFps120 = findViewById(R.id.btnFps120);

        btnChat5 = findViewById(R.id.btnChat5);
        btnChat7 = findViewById(R.id.btnChat7);
        btnChat9 = findViewById(R.id.btnChat9);
        btnChat12 = findViewById(R.id.btnChat12);

        cbVoiceChat = findViewById(R.id.cbVoiceChat);
        cbFpsCounter = findViewById(R.id.cbFpsCounter);
        cbFirstPerson = findViewById(R.id.cbFirstPerson);
        cbCutout = findViewById(R.id.cbCutout);
        cbAndroidKeyboard = findViewById(R.id.cbAndroidKeyboard);
        cbHpArmourText = findViewById(R.id.cbHpArmourText);
        cbOutfitGuns = findViewById(R.id.cbOutfitGuns);
        cbRadarRect = findViewById(R.id.cbRadarRect);
        cbPcMoney = findViewById(R.id.cbPcMoney);
        cbSkyBox = findViewById(R.id.cbSkyBox);
        cbSnow = findViewById(R.id.cbSnow);

        btnSaveSettings = findViewById(R.id.btnSaveSettings);
        btnResetSettings = findViewById(R.id.btnResetSettings);

        peripheralStatusText = findViewById(R.id.peripheralStatusText);
        cbEnableKeyboardMouse = findViewById(R.id.cbEnableKeyboardMouse);
        cbEnableGamepad = findViewById(R.id.cbEnableGamepad);
        btnRefreshDevices = findViewById(R.id.btnRefreshDevices);
    }}

    private void switchTab(int tabIndex) {{
        panelHome.setVisibility(tabIndex == 0 ? View.VISIBLE : View.GONE);
        panelSettings.setVisibility(tabIndex == 1 ? View.VISIBLE : View.GONE);
        panelControls.setVisibility(tabIndex == 2 ? View.VISIBLE : View.GONE);

        tabBtnHome.setBackgroundColor(tabIndex == 0 ? 0xCC1D4ED8 : 0x661E293B);
        tabBtnSettings.setBackgroundColor(tabIndex == 1 ? 0xCC1D4ED8 : 0x661E293B);
        tabBtnControls.setBackgroundColor(tabIndex == 2 ? 0xCC1D4ED8 : 0x661E293B);

        if (tabIndex == 2) {{
            refreshPeripheralsStatus();
        }}
    }}

    private void updateFpsButtons(int fps) {{
        selectedFps = fps;
        btnFps30.setBackgroundColor(fps == 30 ? 0xCC0284C7 : 0x661E293B);
        btnFps60.setBackgroundColor(fps == 60 ? 0xCC0284C7 : 0x661E293B);
        btnFps90.setBackgroundColor(fps == 90 ? 0xCC0284C7 : 0x661E293B);
        btnFps120.setBackgroundColor(fps == 120 ? 0xCC0284C7 : 0x661E293B);
    }}

    private void updateChatLineButtons(int lines) {{
        selectedChatLines = lines;
        btnChat5.setBackgroundColor(lines == 5 ? 0xCC0284C7 : 0x661E293B);
        btnChat7.setBackgroundColor(lines == 7 ? 0xCC0284C7 : 0x661E293B);
        btnChat9.setBackgroundColor(lines == 9 ? 0xCC0284C7 : 0x661E293B);
        btnChat12.setBackgroundColor(lines == 12 ? 0xCC0284C7 : 0x661E293B);
    }}

    private void setupTabsAndListeners() {{
        tabBtnHome.setOnClickListener(v -> switchTab(0));
        tabBtnSettings.setOnClickListener(v -> switchTab(1));
        tabBtnControls.setOnClickListener(v -> switchTab(2));

        btnFps30.setOnClickListener(v -> updateFpsButtons(30));
        btnFps60.setOnClickListener(v -> updateFpsButtons(60));
        btnFps90.setOnClickListener(v -> updateFpsButtons(90));
        btnFps120.setOnClickListener(v -> updateFpsButtons(120));

        btnChat5.setOnClickListener(v -> updateChatLineButtons(5));
        btnChat7.setOnClickListener(v -> updateChatLineButtons(7));
        btnChat9.setOnClickListener(v -> updateChatLineButtons(9));
        btnChat12.setOnClickListener(v -> updateChatLineButtons(12));

        btnSaveSettings.setOnClickListener(v -> {{
            String nick = sanitizeNick(nicknameInput.getText().toString());
            if (nick.isEmpty()) nick = DEFAULT_NICK;
            saveAllSettingsToIni(nick);
            Toast.makeText(this, "Pengaturan berhasil disimpan ke SAMP/settings.ini!", Toast.LENGTH_SHORT).show();
        }});

        btnResetSettings.setOnClickListener(v -> {{
            updateFpsButtons(60);
            updateChatLineButtons(7);
            cbVoiceChat.setChecked(true);
            cbFpsCounter.setChecked(true);
            cbFirstPerson.setChecked(true);
            cbCutout.setChecked(true);
            cbAndroidKeyboard.setChecked(false);
            cbHpArmourText.setChecked(true);
            cbOutfitGuns.setChecked(true);
            cbRadarRect.setChecked(false);
            cbPcMoney.setChecked(false);
            cbSkyBox.setChecked(false);
            cbSnow.setChecked(false);
            String nick = sanitizeNick(nicknameInput.getText().toString());
            if (nick.isEmpty()) nick = DEFAULT_NICK;
            saveAllSettingsToIni(nick);
            Toast.makeText(this, "Pengaturan dikembalikan ke default!", Toast.LENGTH_SHORT).show();
        }});

        cbEnableKeyboardMouse.setOnCheckedChangeListener((b, checked) -> WarGamepad.sEnableKeyboardMouse = checked);
        cbEnableGamepad.setOnCheckedChangeListener((b, checked) -> WarGamepad.sEnableGamepad = checked);
        btnRefreshDevices.setOnClickListener(v -> refreshPeripheralsStatus());

        btnDownloadLite.setOnClickListener(v -> startInAppDataDownload(liteDataUrl, "Data Lite"));
        btnDownloadFull.setOnClickListener(v -> startInAppDataDownload(fullDataUrl, "Data Full"));
        btnCustomUrl.setOnClickListener(v -> showCustomUrlDialog());

        startButton.setOnClickListener(v -> {{
            v.animate().scaleX(0.94f).scaleY(0.94f).setDuration(80)
                    .withEndAction(() -> v.animate().scaleX(1f).scaleY(1f).setDuration(80).start())
                    .start();
            startGame();
        }});
    }}

    private void refreshPeripheralsStatus() {{
        if (peripheralStatusText == null) return;
        boolean hasKb = WarGamepad.hasConnectedKeyboard();
        boolean hasMouse = WarGamepad.hasConnectedMouse();
        boolean hasPad = WarGamepad.hasConnectedGamepad();

        List<String> names = new ArrayList<>();
        try {{
            for (int id : InputDevice.getDeviceIds()) {{
                InputDevice d = InputDevice.getDevice(id);
                if (d != null && !d.isVirtual()) {{
                    int s = d.getSources();
                    if ((s & InputDevice.SOURCE_GAMEPAD) != 0 || (s & InputDevice.SOURCE_JOYSTICK) != 0 ||
                        (s & InputDevice.SOURCE_MOUSE) != 0 ||
                        ((s & InputDevice.SOURCE_KEYBOARD) != 0 && d.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC)) {{
                        names.add(d.getName());
                    }}
                }}
            }}
        }} catch (Throwable ignored) {{}}

        String status = String.format(Locale.ROOT,
                "Status Perangkat: Keyboard Fisik [%s] | Mouse OTG/BT [%s] | Gamepad [%s]%s",
                hasKb ? "TERHUBUNG" : "SIAP",
                hasMouse ? "TERHUBUNG" : "SIAP",
                hasPad ? "TERHUBUNG" : "SIAP",
                names.isEmpty() ? "" : ("\\nPerangkat Terdeteksi: " + String.join(", ", names)));
        peripheralStatusText.setText(status);
    }}

    private void fetchRemoteDataConfig() {{
        executor.execute(() -> {{
            try {{
                HttpURLConnection conn = (HttpURLConnection) new URL(REMOTE_CONFIG_URL).openConnection();
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(5000);
                if (conn.getResponseCode() == 200) {{
                    StringBuilder sb = new StringBuilder();
                    try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {{
                        String line;
                        while ((line = br.readLine()) != null) sb.append(line);
                    }}
                    JSONObject obj = new JSONObject(sb.toString());
                    if (obj.has("data_lite")) {{
                        JSONObject lite = obj.getJSONObject("data_lite");
                        liteDataUrl = lite.optString("url", liteDataUrl);
                    }}
                    if (obj.has("data_full")) {{
                        JSONObject full = obj.getJSONObject("data_full");
                        fullDataUrl = full.optString("url", fullDataUrl);
                    }}
                }}
            }} catch (Exception ignored) {{}}
        }});
    }}

    private void showCustomUrlDialog() {{
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        final EditText input = new EditText(this);
        input.setHint("https://example.com/Data-GTA-Lite.zip");
        input.setText(prefs.getString(KEY_CUSTOM_ZIP_URL, liteDataUrl));
        input.setSingleLine(true);

        new AlertDialog.Builder(this)
                .setTitle("Download Data GTA (.zip) dari URL")
                .setMessage("Masukkan link direct download file .zip Data GTA (Lite/Full). Aplikasi akan otomatis mengunduh dan mengekstrak ke folder data game:")
                .setView(input)
                .setPositiveButton("Download & Ekstrak", (d, w) -> {{
                    String url = input.getText().toString().trim();
                    if (!url.startsWith("http")) {{
                        Toast.makeText(this, "URL harus diawali http:// atau https://", Toast.LENGTH_LONG).show();
                        return;
                    }}
                    prefs.edit().putString(KEY_CUSTOM_ZIP_URL, url).apply();
                    startInAppDataDownload(url, "Data Custom ZIP");
                }})
                .setNegativeButton("Batal", null)
                .show();
    }}

    private File getPreferredWritableDataDir() {{
        try {{
            File ext = getExternalFilesDir(null);
            if (ext != null) {{
                if (!ext.exists()) ext.mkdirs();
                return ext;
            }}
        }} catch (Exception ignored) {{}}
        File gta = new File("/storage/emulated/0/GTA/");
        if (!gta.exists()) gta.mkdirs();
        return gta;
    }}

    private void startInAppDataDownload(final String zipUrl, final String label) {{
        if (isDownloading) {{
            Toast.makeText(this, "Unduhan sedang berjalan, harap tunggu...", Toast.LENGTH_SHORT).show();
            return;
        }}
        isDownloading = true;
        downloadProgressBar.setVisibility(View.VISIBLE);
        downloadProgressBar.setIndeterminate(false);
        downloadProgressBar.setProgress(0);
        downloadStatusText.setText("Menghubungkan ke server unduhan " + label + "...");

        executor.execute(() -> {{
            File targetDir = getPreferredWritableDataDir();
            File tempZip = new File(targetDir, "lombok_data_download.zip.part");
            HttpURLConnection conn = null;
            try {{
                long existingBytes = tempZip.exists() ? tempZip.length() : 0L;
                URL url = new URL(zipUrl);
                conn = (HttpURLConnection) url.openConnection();
                conn.setInstanceFollowRedirects(true);
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(30000);
                if (existingBytes > 0) {{
                    conn.setRequestProperty("Range", "bytes=" + existingBytes + "-");
                }}
                int code = conn.getResponseCode();
                if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {{
                    if (existingBytes > 0) {{
                        tempZip.delete();
                        existingBytes = 0;
                        conn.disconnect();
                        conn = (HttpURLConnection) url.openConnection();
                        conn.setInstanceFollowRedirects(true);
                        code = conn.getResponseCode();
                    }}
                }}
                if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {{
                    final int errCode = code;
                    handler.post(() -> {{
                        isDownloading = false;
                        downloadStatusText.setText("Link unduhan belum tersedia (HTTP " + errCode + "). Gunakan tombol 'URL ZIP CUSTOM' atau unggah file .zip ke Release GitHub.");
                        Toast.makeText(MainActivity.this, "Server mengembalikan HTTP " + errCode + ". Klik 'URL ZIP CUSTOM' untuk memasukkan link .zip data Anda.", Toast.LENGTH_LONG).show();
                    }});
                    return;
                }}

                long contentLength = conn.getContentLengthLong();
                long totalBytes = (code == HttpURLConnection.HTTP_PARTIAL && contentLength > 0)
                        ? (existingBytes + contentLength)
                        : contentLength;
                boolean append = (code == HttpURLConnection.HTTP_PARTIAL);

                try (InputStream in = new BufferedInputStream(conn.getInputStream(), 65536);
                     FileOutputStream fos = new FileOutputStream(tempZip, append)) {{
                    byte[] buf = new byte[65536];
                    long downloaded = append ? existingBytes : 0L;
                    long lastUpdate = System.currentTimeMillis();
                    long bytesAtLastUpdate = downloaded;
                    int n;
                    while ((n = in.read(buf)) != -1) {{
                        fos.write(buf, 0, n);
                        downloaded += n;
                        long now = System.currentTimeMillis();
                        if (now - lastUpdate >= 250) {{
                            long deltaB = downloaded - bytesAtLastUpdate;
                            double speedMb = (deltaB / 1048576.0) / ((now - lastUpdate) / 1000.0);
                            int pct = (totalBytes > 0) ? (int) ((downloaded * 100L) / totalBytes) : 0;
                            final double dlMb = downloaded / 1048576.0;
                            final double totMb = totalBytes > 0 ? (totalBytes / 1048576.0) : 0.0;
                            final int fPct = pct;
                            final double fSpd = speedMb;
                            handler.post(() -> {{
                                downloadProgressBar.setProgress(fPct);
                                downloadStatusText.setText(String.format(Locale.ROOT,
                                        "Mengunduh %s: %.1f / %.1f MB (%d%%) — %.2f MB/s",
                                        label, dlMb, totMb, fPct, fSpd));
                            }});
                            lastUpdate = now;
                            bytesAtLastUpdate = downloaded;
                        }}
                    }}
                    fos.flush();
                }}

                handler.post(() -> {{
                    downloadProgressBar.setIndeterminate(true);
                    downloadStatusText.setText("Mengekstrak " + label + " ke " + targetDir.getAbsolutePath() + " ...");
                }});

                extractZipSmart(tempZip, targetDir);
                tempZip.delete();
                provisionSampDirectory(targetDir);

                handler.post(() -> {{
                    isDownloading = false;
                    downloadProgressBar.setIndeterminate(false);
                    downloadProgressBar.setProgress(100);
                    String active = resolveGameDataDir(MainActivity.this);
                    updateDataStatusLabel(active);
                    downloadStatusText.setText("Selesai! " + label + " berhasil dipasang di: " + active);
                    Toast.makeText(MainActivity.this, label + " selesai diunduh & diekstrak! Siap dimainkan.", Toast.LENGTH_LONG).show();
                }});
            }} catch (Exception e) {{
                final String msg = e.getMessage();
                handler.post(() -> {{
                    isDownloading = false;
                    downloadProgressBar.setIndeterminate(false);
                    downloadStatusText.setText("Unduhan terhenti: " + msg + " (Klik lagi untuk Resume otomatis)");
                }});
            }} finally {{
                if (conn != null) conn.disconnect();
            }}
        }});
    }}

    private void extractZipSmart(File zipFile, File targetRoot) throws Exception {{
        String[] knownRoots = new String[]{{"texdb/", "models/", "data/", "anim/", "audio/", "samp/"}};
        try (ZipInputStream zis = new ZipInputStream(new BufferedInputStream(new FileInputStream(zipFile), 65536))) {{
            ZipEntry entry;
            byte[] buffer = new byte[65536];
            while ((entry = zis.getNextEntry()) != null) {{
                String rawName = entry.getName().replace('\\\\', '/');
                while (rawName.startsWith("/")) rawName = rawName.substring(1);
                if (rawName.contains("..")) continue;

                // Normalisasi apabila di dalam ZIP ada subfolder pembungkus (misal "com.rockstargames.gtasa/files/texdb/...")
                String lower = rawName.toLowerCase(Locale.ROOT);
                for (String kr : knownRoots) {{
                    int idx = lower.indexOf(kr);
                    if (idx > 0 && rawName.charAt(idx - 1) == '/') {{
                        rawName = rawName.substring(idx);
                        break;
                    }}
                }}

                File outFile = new File(targetRoot, rawName);
                if (entry.isDirectory()) {{
                    outFile.mkdirs();
                }} else {{
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.exists()) parent.mkdirs();
                    try (BufferedOutputStream bos = new BufferedOutputStream(new FileOutputStream(outFile), 65536)) {{
                        int len;
                        while ((len = zis.read(buffer)) != -1) {{
                            bos.write(buffer, 0, len);
                        }}
                        bos.flush();
                    }}
                }}
                zis.closeEntry();
            }}
        }}
    }}

    private void onPermissionReady() {{
        String dir = resolveGameDataDir(this);
        provisionSampDirectory(new File(dir));
        loadSavedSettings();
        updateDataStatusLabel(dir);
    }}

    private void updateDataStatusLabel(String dir) {{
        if (bugText == null || dataBadgeStatus == null) return;
        File d = new File(dir);
        if (hasGtaCache(d)) {{
            dataBadgeStatus.setText("DATA SIAP (TANPA OBB)");
            dataBadgeStatus.setTextColor(0xFF34D399);
            dataBadgeStatus.setBackgroundColor(0x3310B981);
            bugText.setText("Lokasi Data Aktif: " + dir);
        }} else {{
            dataBadgeStatus.setText("DATA BELUM ADA");
            dataBadgeStatus.setTextColor(0xFFFBBF24);
            dataBadgeStatus.setBackgroundColor(0x33F59E0B);
            bugText.setText("Data GTA belum ditemukan. Klik tombol 'DOWNLOAD DATA LITE / FULL' di bawah atau taruh folder data GTA di /sdcard/GTA/");
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
        try {{
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) {{
                String p = ext.getAbsolutePath();
                if (!p.endsWith("/")) p += "/";
                candidates.add(p);
            }}
        }} catch (Exception ignored) {{}}
        candidates.add("/storage/emulated/0/Android/data/{args.package_id}/files/");
        candidates.add("/storage/emulated/0/GTA/");
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
        try {{
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) {{
                String p = ext.getAbsolutePath();
                return p.endsWith("/") ? p : (p + "/");
            }}
        }} catch (Exception ignored) {{}}
        return "/storage/emulated/0/GTA/";
    }}

    private void provisionSampDirectory(File baseDir) {{
        try {{
            File sampDir = new File(baseDir, "SAMP");
            File fontsDir = new File(sampDir, "fonts");
            if (!fontsDir.exists()) {{
                fontsDir.mkdirs();
            }}
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

    private String sanitizeNick(String raw) {{
        if (raw == null) return "";
        String s = raw.trim().replace(' ', '_');
        s = s.replaceAll("[^A-Za-z0-9_\\\\[\\\\]$=()@.]", "");
        if (s.length() > 20) s = s.substring(0, 20);
        return s;
    }}

    private void loadSavedSettings() {{
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String savedNick = prefs.getString(KEY_NICKNAME, "");
        String savedPass = prefs.getString(KEY_PASSWORD, "");
        int fps = prefs.getInt(KEY_FPS, 60);
        int lines = prefs.getInt(KEY_CHAT_LINES, 7);

        if (savedNick.isEmpty()) {{
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
                                savedNick = val;
                                break;
                            }}
                        }}
                    }}
                }} catch (Exception ignored) {{ }}
            }}
        }}

        if (nicknameInput != null && !savedNick.isEmpty() && !savedNick.equals(DEFAULT_NICK)) {{
            nicknameInput.setText(savedNick);
        }}
        if (passwordInput != null && !savedPass.isEmpty()) {{
            passwordInput.setText(savedPass);
        }}
        updateFpsButtons(fps);
        updateChatLineButtons(lines);
    }}

    private boolean saveAllSettingsToIni(String nick) {{
        String activeDir = resolveGameDataDir(this);
        String pass = (passwordInput != null) ? passwordInput.getText().toString().trim() : "";

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit()
                .putString(KEY_NICKNAME, nick)
                .putString(KEY_PASSWORD, pass)
                .putInt(KEY_FPS, selectedFps)
                .putInt(KEY_CHAT_LINES, selectedChatLines)
                .apply();

        List<String> targetDirs = new ArrayList<>();
        targetDirs.add(activeDir);
        try {{
            File ext = getExternalFilesDir(null);
            if (ext != null) {{
                String p = ext.getAbsolutePath() + "/";
                if (!targetDirs.contains(p)) targetDirs.add(p);
            }}
        }} catch (Exception ignored) {{}}
        if (!targetDirs.contains("/storage/emulated/0/GTA/")) {{
            targetDirs.add("/storage/emulated/0/GTA/");
        }}

        String iniContent = "[client]\\n"
                + "name=" + nick + "\\n"
                + "host=127.0.0.1\\n"
                + "port=" + LOCKED_PORT + "\\n"
                + "password=" + pass + "\\n"
                + "version=0.3.7\\n"
                + "autoaim=false\\n\\n"
                + "[debug]\\n"
                + "debug=false\\n"
                + "online=true\\n\\n"
                + "[gui]\\n"
                + "Font=arial.ttf\\n"
                + "FontSize=30.0\\n"
                + "FontOutline=2\\n"
                + "ChatPosX=325.0\\n"
                + "ChatPosY=25.0\\n"
                + "ChatSizeX=1150.0\\n"
                + "ChatSizeY=220.0\\n"
                + "ChatMaxMessages=" + selectedChatLines + "\\n"
                + "FPSLimit=" + selectedFps + "\\n"
                + "VoiceChatEnable=" + (cbVoiceChat != null && cbVoiceChat.isChecked() ? "true" : "false") + "\\n"
                + "fps=" + (cbFpsCounter != null && cbFpsCounter.isChecked() ? "true" : "false") + "\\n"
                + "firstperson=" + (cbFirstPerson != null && cbFirstPerson.isChecked() ? "true" : "false") + "\\n"
                + "cutout=" + (cbCutout != null && cbCutout.isChecked() ? "true" : "false") + "\\n"
                + "androidkeyboard=" + (cbAndroidKeyboard != null && cbAndroidKeyboard.isChecked() ? "true" : "false") + "\\n"
                + "hparmourtext=" + (cbHpArmourText != null && cbHpArmourText.isChecked() ? "true" : "false") + "\\n"
                + "outfitguns=" + (cbOutfitGuns != null && cbOutfitGuns.isChecked() ? "true" : "false") + "\\n"
                + "radarrect=" + (cbRadarRect != null && cbRadarRect.isChecked() ? "true" : "false") + "\\n"
                + "pcmoney=" + (cbPcMoney != null && cbPcMoney.isChecked() ? "true" : "false") + "\\n"
                + "skybox=" + (cbSkyBox != null && cbSkyBox.isChecked() ? "true" : "false") + "\\n"
                + "snow=" + (cbSnow != null && cbSnow.isChecked() ? "true" : "false") + "\\n";

        boolean ok = false;
        for (String dir : targetDirs) {{
            try {{
                provisionSampDirectory(new File(dir));
                File ini = new File(dir, "SAMP/settings.ini");
                File parent = ini.getParentFile();
                if (parent != null && !parent.exists()) parent.mkdirs();
                try (FileOutputStream fos = new FileOutputStream(ini, false)) {{
                    fos.write(iniContent.getBytes(StandardCharsets.UTF_8));
                    fos.flush();
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
                    android.Manifest.permission.WRITE_EXTERNAL_STORAGE,
                    android.Manifest.permission.RECORD_AUDIO
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
            refreshPeripheralsStatus();
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
                    "Data GTA SA belum terpasang! Silakan klik tombol 'DOWNLOAD DATA LITE' atau 'DOWNLOAD DATA FULL' di dalam aplikasi terlebih dahulu.",
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
        saveAllSettingsToIni(nick);

        Intent gameIntent = new Intent(MainActivity.this, SAMP.class);
        gameIntent.putExtra("player_name", nick);
        gameIntent.putExtra("game_data_dir", dataDir);
        startActivity(gameIntent);
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
    print("[+] Wrote Modern Cyber Blue-Purple Dashboard UI, Settings Manager, and In-App Data Downloader")


def apply_ui_v21_templates(repo: Path, args):
    ui_root = repo / "client-patch" / "ui-v21"
    main_root = repo / "app" / "src" / "main"
    java_target = main_root / "java" / "com" / "samp" / "mobile" / "launcher" / "MainActivity.java"
    layout_target = main_root / "res" / "layout" / "main_activity.xml"
    java_text = (ui_root / "MainActivity.java.template").read_text(encoding="utf-8")
    cert_pin = (args.cert_sha256 or "").strip().lower().replace(":", "")
    java_values = {
        "@@DEFAULT_NICK@@": args.default_nick,
        "@@SERVER_HOST@@": args.host,
        "@@SERVER_PORT@@": str(args.port),
        "@@CERT_SHA256@@": cert_pin,
    }
    for marker, value in java_values.items():
        java_text = java_text.replace(marker, value)
    if "@@" in java_text:
        raise RuntimeError("Placeholder UI v2.1 belum tersubstitusi di MainActivity.java")
    java_target.write_text(java_text, encoding="utf-8")
    shutil.copy2(ui_root / "main_activity.xml.template", layout_target)
    drawable_source = ui_root / "drawable"
    drawable_target = main_root / "res" / "drawable"
    for source in drawable_source.glob("*.xml"):
        shutil.copy2(source, drawable_target / source.name)
    print("[+] Applied rounded sidebar, carousel, multi-server/news/mod dashboard templates (v2.1.0)")


def patch_gradle_and_proguard(repo: Path, args):
    app_bg = repo / "app" / "build.gradle"
    app_bg.write_text(f"""plugins {{
    id 'com.android.application'
}}

android {{
    namespace 'com.samp.mobile'
    compileSdk 34

    signingConfigs {{
        release {{
            def ksPath = System.getenv("KEYSTORE_FILE") ?: System.getenv("SIGNING_STORE_FILE")
            if (ksPath != null && !ksPath.isEmpty()) {{
                storeFile file(ksPath)
                storePassword System.getenv("KEYSTORE_PASSWORD") ?: System.getenv("SIGNING_STORE_PASSWORD")
                keyAlias System.getenv("KEY_ALIAS") ?: System.getenv("SIGNING_KEY_ALIAS")
                keyPassword System.getenv("KEY_PASSWORD") ?: System.getenv("SIGNING_KEY_PASSWORD")
                enableV1Signing true
                enableV2Signing true
            }}
        }}
    }}

    defaultConfig {{
        applicationId "{args.package_id}"
        minSdk 24
        targetSdk 34
        versionCode 210
        versionName "2.1.0"

        multiDexEnabled true

        ndk {{
            debugSymbolLevel 'NONE'
        }}
    }}

    splits {{
        abi {{
            enable true
            reset()
            include 'armeabi-v7a', 'arm64-v8a'
            universalApk false
        }}
    }}

    packagingOptions {{
        jniLibs {{
            useLegacyPackaging true
            pickFirsts += ['**/*.so']
            excludes += ['META-INF/*']
        }}
        resources {{
            excludes += ['META-INF/*']
        }}
    }}

    ndkVersion '26.2.11394342'

    externalNativeBuild {{
        cmake {{
            path "src/main/cpp/CMakeLists.txt"
        }}
    }}

    buildTypes {{
        release {{
            debuggable false
            jniDebuggable false
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
            if ((System.getenv("KEYSTORE_FILE") ?: System.getenv("SIGNING_STORE_FILE")) != null) {{
                signingConfig signingConfigs.release
            }}
        }}
        debug {{
            debuggable false
            jniDebuggable false
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
            if ((System.getenv("KEYSTORE_FILE") ?: System.getenv("SIGNING_STORE_FILE")) != null) {{
                signingConfig signingConfigs.release
            }}
        }}
    }}

    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }}

    lintOptions {{
        checkReleaseBuilds false
        abortOnError false
    }}

    buildFeatures {{
        prefab true
    }}
}}

dependencies {{
    implementation fileTree(dir: "libs", include: ["*.jar"])
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.9.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    implementation 'com.intuit.sdp:sdp-android:1.1.0'
    implementation 'com.bytedance.android:shadowhook:1.0.9'
}}
""", encoding="utf-8")

    pg = repo / "app" / "proguard-rules.pro"
    pg.write_text("""# R8 / ProGuard Hardening Rules — Lombok Holiday Roleplay (Per-ABI Split)
-ignorewarnings
-dontwarn com.bda.controller.**
-dontwarn com.wardrumstudios.**
-dontwarn com.nvidia.**

-keepattributes Signature,InnerClasses,EnclosingMethod,Annotation

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
    print(f"[+] Patched app/build.gradle (applicationId={args.package_id}, ABI Splits: armeabi-v7a & arm64-v8a)")


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

    new version[32];
    GetPlayerVersion(playerid, version, sizeof(version));

    if (strcmp(version, REQUIRED_CLIENT_TAG, false) != 0)
    {{
        SendClientMessage(playerid, 0xFF3333FF, "[SERVER] Anda wajib menggunakan APK Resmi {args.server_title}!");
        SetTimerEx("DelayedKick", 350, false, "i", playerid);
        return 1;
    }}

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
            SendClientMessage(playerid, 0x33FF66FF, "[SERVER] Verifikasi APK Resmi {args.server_title} berhasil.");
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
    patch_netgame_cpp(samp_dir, args)
    patch_netrpc_cpp(samp_dir)
    patch_settings_cpp(samp_dir, args)
    patch_imgui_and_image_cpp(samp_dir)
    patch_hooks_cpp(samp_dir, args)
    patch_peripherals_and_game_java(repo, args)
    patch_launcher_dashboard_and_downloader(repo, args)
    apply_ui_v21_templates(repo, args)
    patch_gradle_and_proguard(repo, args)
    generate_server_pawn_script(args)
    print(f"\n[✓] Semua patch {args.server_title} ({args.package_id}, ABI Split armeabi-v7a & arm64-v8a) berhasil diterapkan!")


if __name__ == "__main__":
    main()
