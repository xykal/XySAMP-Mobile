#include "main.h"
#include "settings.h"
#include "lockdown.h"
#include "vendor/inih/cpp/INIReader.h"
#include "vendor/SimpleIni/SimpleIni.h"
#include "game/game.h"
#include <cstdio>
#include <sys/stat.h>

extern CGame *pGame;

CSettings::CSettings()
{
    FLog("Loading settings..");
    memset(&m_Settings, 0, sizeof(m_Settings));

    char buff[256];
    snprintf(buff, sizeof(buff), "%sSAMP/settings.ini", g_pszStorage ? g_pszStorage : "/storage/emulated/0/GTA/");

    INIReader reader(buff);
    bool iniOk = (reader.ParseError() >= 0);

    char defaultNick[32];
    snprintf(defaultNick, sizeof(defaultNick), "Warga_Lombok_%d", (rand() % 899) + 100);

    std::string nick = iniOk ? reader.Get("client", "name", defaultNick) : std::string(defaultNick);
    if (nick.empty() || nick == "Nick_Name" || nick.find("__android_") == 0) {
        nick = defaultNick;
    }
    size_t length = nick.copy(m_Settings.szNickName, 24);
    m_Settings.szNickName[length] = '\0';

    std::string pass = iniOk ? reader.Get("client", "password", "") : "";
    length = pass.copy(m_Settings.szPassword, MAX_SETTINGS_STRING);
    m_Settings.szPassword[length] = '\0';

    std::string host = iniOk ? reader.Get("client", "host", XySAMP::GetLockedHost()) : XySAMP::GetLockedHost();
    if (host.empty() || host.size() > MAX_SETTINGS_STRING) host = XySAMP::GetLockedHost();
    size_t hostLength = host.copy(m_Settings.szHost, MAX_SETTINGS_STRING);
    m_Settings.szHost[hostLength] = '\0';
    long configuredPort = iniOk ? reader.GetInteger("client", "port", XySAMP::GetLockedPort()) : XySAMP::GetLockedPort();
    if (configuredPort < 1 || configuredPort > 65535) configuredPort = XySAMP::GetLockedPort();
    m_Settings.iPort = static_cast<int>(configuredPort);
    strncpy(m_Settings.szVersion, XySAMP::GetClientVersion(), MAX_SETTINGS_STRING);
    m_Settings.szVersion[MAX_SETTINGS_STRING - 1] = '\0';

    m_Settings.bAutoAim = iniOk ? reader.GetBoolean("client", "autoaim", false) : false;
    m_Settings.bDebug = false;
    m_Settings.bOnline = true;

    std::string fontName = iniOk ? reader.Get("gui", "Font", "arial.ttf") : "arial.ttf";
    if (fontName.empty()) fontName = "arial.ttf";
    length = fontName.copy(m_Settings.szFont, MAX_SETTINGS_STRING);
    m_Settings.szFont[length] = '\0';

    m_Settings.fFontSize = iniOk ? (float)reader.GetReal("gui", "FontSize", 30.0) : 30.0f;
    m_Settings.iFontOutline = iniOk ? (int)reader.GetInteger("gui", "FontOutline", 2) : 2;

    m_Settings.fChatPosX = iniOk ? (float)reader.GetReal("gui", "ChatPosX", 325.0) : 325.0f;
    m_Settings.fChatPosY = iniOk ? (float)reader.GetReal("gui", "ChatPosY", 25.0) : 25.0f;
    m_Settings.fChatSizeX = iniOk ? (float)reader.GetReal("gui", "ChatSizeX", 1150.0) : 1150.0f;
    m_Settings.fChatSizeY = iniOk ? (float)reader.GetReal("gui", "ChatSizeY", 220.0) : 220.0f;
    m_Settings.iChatMaxMessages = iniOk ? (int)reader.GetInteger("gui", "ChatMaxMessages", 7) : 7;
    m_Settings.bChatTimestamp = iniOk ? reader.GetBoolean("gui", "ChatTimestamp", false) : false;
    m_Settings.fScrollSensitivity = iniOk ? (float)reader.GetReal("gui", "ScrollSensitivity", 1.0) : 1.0f;
    if (m_Settings.fScrollSensitivity < 0.2f) m_Settings.fScrollSensitivity = 0.2f;
    if (m_Settings.fScrollSensitivity > 3.0f) m_Settings.fScrollSensitivity = 3.0f;
    for (int t = 0; t < 10; ++t)
    {
        char key[40];
        snprintf(key, sizeof(key), "Slot%dEnabled", t);
        m_Settings.aToy[t].bEnabled = iniOk ? reader.GetBoolean("toys", key, true) : true;
        snprintf(key, sizeof(key), "Slot%dBone", t);
        m_Settings.aToy[t].iBone = iniOk ? (int)reader.GetInteger("toys", key, 0) : 0;
        if (m_Settings.aToy[t].iBone < 0 || m_Settings.aToy[t].iBone > 18) m_Settings.aToy[t].iBone = 0;
        snprintf(key, sizeof(key), "Slot%dOffsetX", t);
        m_Settings.aToy[t].fOffX = iniOk ? (float)reader.GetReal("toys", key, 0.0) : 0.0f;
        snprintf(key, sizeof(key), "Slot%dOffsetY", t);
        m_Settings.aToy[t].fOffY = iniOk ? (float)reader.GetReal("toys", key, 0.0) : 0.0f;
        snprintf(key, sizeof(key), "Slot%dOffsetZ", t);
        m_Settings.aToy[t].fOffZ = iniOk ? (float)reader.GetReal("toys", key, 0.0) : 0.0f;
        snprintf(key, sizeof(key), "Slot%dScale", t);
        m_Settings.aToy[t].fScale = iniOk ? (float)reader.GetReal("toys", key, 1.0) : 1.0f;
        if (m_Settings.aToy[t].fScale < 0.5f) m_Settings.aToy[t].fScale = 0.5f;
        if (m_Settings.aToy[t].fScale > 2.0f) m_Settings.aToy[t].fScale = 2.0f;
        if (m_Settings.aToy[t].fOffX < -0.5f) m_Settings.aToy[t].fOffX = -0.5f;
        if (m_Settings.aToy[t].fOffX > 0.5f) m_Settings.aToy[t].fOffX = 0.5f;
        if (m_Settings.aToy[t].fOffY < -0.5f) m_Settings.aToy[t].fOffY = -0.5f;
        if (m_Settings.aToy[t].fOffY > 0.5f) m_Settings.aToy[t].fOffY = 0.5f;
        if (m_Settings.aToy[t].fOffZ < -0.5f) m_Settings.aToy[t].fOffZ = -0.5f;
        if (m_Settings.aToy[t].fOffZ > 0.5f) m_Settings.aToy[t].fOffZ = 0.5f;
    }

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

    if (!iniOk && g_pszStorage) {
        char sampDir[256];
        snprintf(sampDir, sizeof(sampDir), "%sSAMP", g_pszStorage);
        mkdir(sampDir, 0775);
        FILE* fp = fopen(buff, "w");
        if (fp) {
            fprintf(fp, "[client]\nname=%s\nhost=%s\nport=%d\nversion=0.3.7\n\n[gui]\nFont=arial.ttf\nFontSize=30.0\nFontOutline=2\nChatMaxMessages=7\nFPSLimit=60\nVoiceChatEnable=true\nfirstperson=true\ncutout=true\nfps=true\nhparmourtext=true\noutfitguns=true\n", m_Settings.szNickName, XySAMP::GetLockedHost(), XySAMP::GetLockedPort());
            fclose(fp);
        }
    }

    FLog("Settings loaded.");
}

const stSettings& CSettings::GetReadOnly()
{
    return m_Settings;
}

stSettings& CSettings::GetWrite()
{
    return m_Settings;
}
