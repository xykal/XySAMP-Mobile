#!/usr/bin/env python3
"""
lockdown.py - Patcher Security & Lockdown SA-MP Mobile (fork kuzia15/SAMP-Mobile GTA-2.11)
Fitur:
  1. XOR-Obfuscated Host, Tag, & Default Nick di lockdown.h (Anti-strings & Anti-HexEdit)
  2. Zero-Leak di settings.cpp, settings.ini, logcat.txt, dan classes.dex (IP & Tag tidak bocor)
  3. Lapis 3 Handshake (RPC_ClientCheck ID 103) + Anti-Frida / Anti-Ptrace / Anti-GameGuardian
  4. APK Signing Certificate Pinning (SHA-256 check di MainActivity.java - Anti-Repackage/MT Manager)
  5. R8 Code Shrinking & Obfuscation (isMinifyEnabled=true, isShrinkResources=true) + Strip Native Symbols
  6. Input Nickname di Launcher + Bahasa Indonesia + Sinkronisasi server/gate_client.pwn
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_PKG = HERE.parent
TEMPLATE = ROOT_PKG / "client-patch" / "lockdown.h.template"
DEFAULT_PWN = ROOT_PKG / "server" / "gate_client.pwn"

MARK_BEGIN = "// >>> LOCKDOWN:PATCH-BEGIN (jangan dihapus, dipake patcher)"
MARK_END = "// <<< LOCKDOWN:PATCH-END"

HS_BEGIN = "// >>> LOCKDOWN:HANDSHAKE-BEGIN"
HS_END = "// <<< LOCKDOWN:HANDSHAKE-END"

OVERRIDE_BLOCK = """
\t""" + MARK_BEGIN + """
#if !LOCK_ALLOW_INI_OVERRIDE
\t// Decode host, port, dan tag dari XOR byte array di RAM (anti-strings & anti-hexedit)
\tLockdown_DecodeHost(m_Settings.szHost, MAX_SETTINGS_STRING);
\tm_Settings.iPort = LOCK_SERVER_PORT;
\tLockdown_DecodeTag(m_Settings.szVersion, MAX_SETTINGS_STRING);

\t// nickname random internal (__android_xxxx) -> ganti jadi default kita
\tif (m_Settings.szNickName[0] == '\\0' ||
\t\tstrncmp(m_Settings.szNickName, "__android_", 10) == 0)
\t{
\t\tLockdown_DecodeName(m_Settings.szNickName, 24);
\t}
\tLockdown_SanitizeNick(m_Settings.szNickName, 24);
#endif
\t""" + MARK_END + """
"""

HANDSHAKE_RPC_BLOCK = """
""" + HS_BEGIN + """
static int RPC_ClientCheck = 103;

void ClientCheck(RPCParameters *rpcParams)
{
\tunsigned char* Data = reinterpret_cast<unsigned char*>(rpcParams->input);
\tint iBitLength = rpcParams->numberOfBitsOfData;
\tRakNet::BitStream bsData(Data, (iBitLength / 8) + 1, false);

\tuint8_t byteType = 0;
\tuint32_t dwAddress = 0;
\tuint16_t wOffset = 0;
\tuint16_t wCount = 0;

\tif (!bsData.Read(byteType) || !bsData.Read(dwAddress) || !bsData.Read(wOffset) || !bsData.Read(wCount))
\t\treturn;

#if LOCK_HANDSHAKE_ENABLE
\tuint32_t dwReplyAddr = dwAddress ^ (uint32_t)LOCK_HANDSHAKE_KEY;
\t// Jika terdeteksi debugger / Frida / APK dimodifikasi, acak jawaban biar server langsung kick
\tif (Lockdown_IsTampered()) {
\t\tdwReplyAddr ^= 0xDEADCAFEu;
\t}
\tuint8_t byteReplyChecksum = (uint8_t)(((dwReplyAddr) ^ (dwReplyAddr >> 8) ^ (dwReplyAddr >> 16) ^ (dwReplyAddr >> 24) ^ byteType) & 0xFF);
#else
\tuint32_t dwReplyAddr = dwAddress;
\tuint8_t byteReplyChecksum = 0;
#endif

\tRakNet::BitStream bsSend;
\tbsSend.Write(byteType);
\tbsSend.Write(dwReplyAddr);
\tbsSend.Write(byteReplyChecksum);

\tif (pNetGame && pNetGame->GetRakClient()) {
\t\tpNetGame->GetRakClient()->RPC(&RPC_ClientCheck, &bsSend, HIGH_PRIORITY, RELIABLE, 0, false, UNASSIGNED_NETWORK_ID, nullptr);
\t}
}
""" + HS_END + """
"""

NICKNAME_XML_WIDGET = """
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
"""

PROGUARD_RULES = """# =============================================================================
#  R8 / ProGuard Security & JNI Keep Rules for XySAMP Mobile
# =============================================================================
-optimizationpasses 5
-allowaccessmodification
-repackageclasses 'x'

# Hapus log debug/verbose/info di build release biar ga bocor di logcat
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
}

# Keep semua class & method JNI yang dipanggil dari libsamp.so & libGame.so
-keep class com.nvidia.devtech.** { *; }
-keep class com.wardrumstudios.utils.** { *; }
-keep class com.rockstargames.** { *; }
-keep class com.gta.game.** { *; }
-keep class com.gta.launcher.activity.MainActivity { *; }
-keep class com.bytedance.shadowhook.** { *; }

# Keep native methods
-keepclasseswithmembernames,includedescriptorclasses class * {
    native <methods>;
}

-dontwarn javax.servlet.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
-dontwarn com.google.firebase.**
-dontwarn com.joom.paranoid.**
"""


def log(msg):
    print(f"  [+] {msg}")


def fail(msg):
    print(f"\n[!] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def read(p: Path) -> str:
    if not p.exists():
        fail(f"file nggak ketemu: {p}")
    return p.read_text(encoding="utf-8", errors="surrogateescape")


def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8", errors="surrogateescape")


def sanitize_nick(name: str) -> str:
    clean = re.sub(r"\s+", "_", name.strip())
    clean = re.sub(r"[^A-Za-z0-9_\[\]\$=()@\.]", "", clean)
    return (clean or "Warga_XyVerse")[:20]


def xor_encode_bytes(text: str, seed: int):
    raw = text.encode("utf-8")
    enc = []
    for i, b in enumerate(raw):
        mask = (seed + i * 37) & 0xFF
        enc.append(f"0x{(b ^ mask):02X}")
    if not enc:
        enc = ["0x00"]
    return ", ".join(enc), len(raw)


def patch_settings_cpp(repo: Path, port: int):
    p = repo / "app/src/main/cpp/samp/settings.cpp"
    src = read(p)

    if '#include "lockdown.h"' not in src:
        anchor = '#include "settings.h"'
        if anchor not in src:
            fail('anchor #include "settings.h" nggak ketemu di settings.cpp')
        src = src.replace(anchor, anchor + '\n#include "lockdown.h"', 1)
        log("settings.cpp: + include lockdown.h")

    if "Lockdown_EnsureDefaultIni" not in src:
        anchor = "INIReader reader(buff);"
        if anchor not in src:
            fail("anchor 'INIReader reader(buff);' nggak ketemu")
        repl = (
            "#if LOCK_GENERATE_DEFAULT_INI\n"
            "\tLockdown_EnsureDefaultIni(buff);\n"
            "#endif\n"
            "\tINIReader reader(buff);"
        )
        src = src.replace(anchor, repl, 1)
        log("settings.cpp: + auto-generate settings.ini")

    if MARK_BEGIN in src and MARK_END in src:
        pattern = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END), re.S)
        src = pattern.sub(OVERRIDE_BLOCK.strip(), src, count=1)
        log("settings.cpp: blok XOR decode override di-update (zero-leak)")
    else:
        anchor = 'm_Settings.bAutoAim = reader.GetBoolean("client", "autoaim", false);'
        if anchor not in src:
            fail("anchor bAutoAim nggak ketemu di settings.cpp")
        src = src.replace(anchor, anchor + "\n" + OVERRIDE_BLOCK, 1)
        log("settings.cpp: + blok XOR decode override host/port/tag")

    # Jangan taruh host asli di fallback INIReader supaya string IP ga muncul di .rodata
    src = re.sub(
        r'reader\.Get\("client",\s*"host",\s*"[^"]*"\)',
        'reader.Get("client", "host", "127.0.0.1")',
        src,
    )
    src = re.sub(
        r'reader\.GetInteger\("client",\s*"port",\s*\d+\)',
        f'reader.GetInteger("client", "port", {port})',
        src,
    )

    write(p, src)


def patch_netrpc_cpp(repo: Path):
    p = repo / "app/src/main/cpp/samp/net/netrpc.cpp"
    src = read(p)

    if '#include "../lockdown.h"' not in src:
        anchor = '#include "../settings.h"'
        if anchor not in src:
            fail('anchor #include "../settings.h" nggak ketemu di netrpc.cpp')
        src = src.replace(anchor, anchor + '\n#include "../lockdown.h"', 1)
        log("netrpc.cpp: + include ../lockdown.h")

    if HS_BEGIN in src and HS_END in src:
        pattern = re.compile(re.escape(HS_BEGIN) + r".*?" + re.escape(HS_END), re.S)
        src = pattern.sub(HANDSHAKE_RPC_BLOCK.strip(), src, count=1)
        log("netrpc.cpp: handler ClientCheck + Anti-Tamper di-update")
    else:
        anchor = "void RegisterRPCs(RakClientInterface *pRakClient)"
        if anchor not in src:
            fail("anchor RegisterRPCs nggak ketemu di netrpc.cpp")
        src = src.replace(anchor, HANDSHAKE_RPC_BLOCK + "\n" + anchor, 1)
        log("netrpc.cpp: + handler ClientCheck (Lapis 3 Handshake + Anti-Tamper)")

    if "RegisterAsRemoteProcedureCall(&RPC_ClientCheck, ClientCheck)" not in src:
        if "// RPC_ClientCheckResponse" in src:
            src = src.replace(
                "// RPC_ClientCheckResponse",
                "pRakClient->RegisterAsRemoteProcedureCall(&RPC_ClientCheck, ClientCheck); // RPC_ClientCheckResponse",
                1,
            )
        else:
            anchor = "pRakClient->RegisterAsRemoteProcedureCall(&RPC_InitGame, InitGame);"
            src = src.replace(
                anchor,
                anchor + "\n\tpRakClient->RegisterAsRemoteProcedureCall(&RPC_ClientCheck, ClientCheck);",
                1,
            )
        log("netrpc.cpp: + register RPC_ClientCheck")

    if "UnregisterAsRemoteProcedureCall(&RPC_ClientCheck)" not in src:
        anchor = "pRakClient->UnregisterAsRemoteProcedureCall(&RPC_InitGame);"
        if anchor in src:
            src = src.replace(
                anchor,
                anchor + "\n\tpRakClient->UnregisterAsRemoteProcedureCall(&RPC_ClientCheck);",
                1,
            )
            log("netrpc.cpp: + unregister RPC_ClientCheck")

    write(p, src)


def patch_launcher_nickname(repo: Path, port: int, default_name: str, cert_sha256: str):
    xml_path = repo / "app/src/main/res/layout/main_activity.xml"
    if xml_path.exists():
        xml_src = read(xml_path)
        if "@+id/nicknameInput" not in xml_src:
            anchor = '<Button\n        android:id="@+id/startButton"'
            if anchor not in xml_src:
                anchor = "</RelativeLayout>"
                xml_src = xml_src.replace(anchor, NICKNAME_XML_WIDGET + "\n" + anchor, 1)
            else:
                xml_src = xml_src.replace(anchor, NICKNAME_XML_WIDGET.strip() + "\n\n    " + anchor, 1)
            write(xml_path, xml_src)
            log("main_activity.xml: + input box Nickname (@+id/nicknameInput)")

    java_path = repo / "app/src/main/java/com/gta/launcher/activity/MainActivity.java"
    if not java_path.exists():
        return

    clean_sha = cert_sha256.replace(":", "").strip().lower()

    java_content = f"""package com.gta.launcher.activity;

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

import com.gta.game.R;
import com.gta.game.SAMP;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity {{
    private static final String PREFS_NAME = "samp_launcher_prefs";
    private static final String KEY_NICKNAME = "player_nickname";
    private static final String INI_PATH = "/storage/emulated/0/GTA/SAMP/settings.ini";
    private static final String TAMPER_FILE = "/storage/emulated/0/GTA/SAMP/.tampered";
    private static final String DEFAULT_NICK = "{default_name}";
    private static final int LOCKED_PORT = {port};
    // SHA-256 Official Release Keystore Pinning (Anti-Repackage / Anti-Mod APK)
    private static final String EXPECTED_CERT_SHA256 = "{clean_sha}";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private Button startButton;
    private EditText nicknameInput;
    private TextView title1, title2, authorText;
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
                    loadSavedNickname();
                }} else {{
                    storagePermissionGranted = false;
                    Toast.makeText(this, "Izin penyimpanan diperlukan untuk membaca file GTA SA", Toast.LENGTH_LONG).show();
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
                        loadSavedNickname();
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
            loadSavedNickname();
            setupClickListeners();
            checkAndRequestStoragePermission();
        }} catch (Exception e) {{
            finish();
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
            File f = new File(TAMPER_FILE);
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
            File ini = new File(INI_PATH);
            if (ini.exists()) {{
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {{
                    String line;
                    while ((line = br.readLine()) != null) {{
                        String trimmed = line.trim();
                        if (trimmed.toLowerCase().startsWith("name=")) {{
                            String val = trimmed.substring(5).trim();
                            if (!val.isEmpty() && !val.startsWith("__android_")) {{
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
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit().putString(KEY_NICKNAME, nick).apply();

        try {{
            File ini = new File(INI_PATH);
            File parent = ini.getParentFile();
            if (parent != null && !parent.exists()) {{
                parent.mkdirs();
            }}

            if (!ini.exists()) {{
                // Jangan pernah tulis IP atau Tag rahasia ke settings.ini
                String content = "[client]\\n"
                        + "name=" + nick + "\\n"
                        + "host=127.0.0.1\\n"
                        + "port=" + LOCKED_PORT + "\\n"
                        + "password=\\n"
                        + "version=0.3.7\\n"
                        + "autoaim=false\\n\\n"
                        + "[debug]\\n"
                        + "debug=false\\n"
                        + "online=true\\n";
                try (FileOutputStream fos = new FileOutputStream(ini, false)) {{
                    fos.write(content.getBytes(StandardCharsets.UTF_8));
                }}
                return true;
            }}

            List<String> lines = new ArrayList<>();
            boolean nameUpdated = false;
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {{
                String line;
                while ((line = br.readLine()) != null) {{
                    if (line.trim().toLowerCase().startsWith("name=")) {{
                        lines.add("name=" + nick);
                        nameUpdated = true;
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
            return true;
        }} catch (Exception e) {{
            return false;
        }}
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
"""
    write(java_path, java_content)
    log("MainActivity.java: + SHA-256 Official Keystore Pinning + Zero-Leak settings.ini")


def patch_strings(repo: Path, app_name: str, brand: str):
    p = repo / "app/src/main/res/values/strings.xml"
    if not p.exists():
        return
    src = read(p)
    subs = [
        ("app_name", app_name),
        ("client_name", brand),
        ("samp_ver", f"{brand} Official Client"),
        ("authors", f"Official {brand}"),
        ("bug_info", f"Pastikan menggunakan APK resmi {brand}."),
    ]
    for key, val in subs:
        pattern = re.compile(rf'(<string name="{key}">).*?(</string>)', re.S)
        if pattern.search(src):
            src = pattern.sub(lambda m: m.group(1) + val + m.group(2), src)
    write(p, src)
    log("strings.xml: branding diganti")


def patch_gradle_r8_and_security(repo: Path, strip_fb: bool):
    # 1. Root build.gradle.kts
    root_gradle = repo / "build.gradle.kts"
    if root_gradle.exists():
        rsrc = read(root_gradle)
        rsrc = re.sub(
            r'^\s*maven\s*\{\s*url\s*=\s*uri\("https://mint\.splunk\.com/gradle/"\)\s*\}',
            '        // maven { url = uri("https://mint.splunk.com/gradle/") } // dead repo',
            rsrc,
            flags=re.M,
        )
        if strip_fb:
            for dep in [
                'classpath("com.google.gms:google-services:4.3.15")',
                'classpath("com.google.firebase:firebase-crashlytics-gradle:2.5.2")',
            ]:
                if dep in rsrc and f"// {dep}" not in rsrc:
                    rsrc = rsrc.replace(dep, f"// {dep}")
        write(root_gradle, rsrc)

    # 2. gradle.properties
    gprop = repo / "gradle.properties"
    if gprop.exists():
        psrc = read(gprop)
        psrc = psrc.replace("-Xmx2048m", "-Xmx4096m")
        write(gprop, psrc)

    # 3. Tulis proguard-rules.pro yang aman untuk JNI + agresif untuk R8
    pg_file = repo / "app/proguard-rules.pro"
    write(pg_file, PROGUARD_RULES)
    log("app/proguard-rules.pro: R8 obfuscation & JNI keep rules dipasang")

    # 4. Strip flag -g dari CMakeLists.txt di samp supaya binary C++ bersih dari debug info
    samp_cmake = repo / "app/src/main/cpp/samp/CMakeLists.txt"
    if samp_cmake.exists():
        csrc = read(samp_cmake)
        csrc = csrc.replace(
            "-w -s -g -fvisibility=hidden -pthread -Wall -O3 -fexceptions -fstack-protector-strong",
            "-w -s -fvisibility=hidden -fvisibility-inlines-hidden -pthread -O3 -fexceptions -fstack-protector-strong",
        )
        write(samp_cmake, csrc)
        log("samp/CMakeLists.txt: strip DWARF -g & hide inline symbols")

    # 5. app/build.gradle.kts: aktifin R8 (isMinifyEnabled = true, isShrinkResources = true, debugSymbolLevel = "NONE")
    app_gradle = repo / "app/build.gradle.kts"
    if app_gradle.exists():
        asrc = read(app_gradle)

        if strip_fb:
            for plug in [
                'id("com.google.gms.google-services")',
                'id("com.google.firebase.crashlytics")',
            ]:
                if plug in asrc and f"// {plug}" not in asrc:
                    asrc = asrc.replace(plug, f"// {plug}")

            asrc = re.sub(
                r"(?m)^(\s*)firebaseCrashlytics\s*\{[^}]*\}",
                lambda m: "\n".join(f"{m.group(1)}// {ln.lstrip()}" for ln in m.group(0).splitlines()),
                asrc,
            )

            for fb_dep in [
                'implementation("com.google.firebase:firebase-analytics")',
                'implementation(platform("com.google.firebase:firebase-bom:34.13.0"))',
                'implementation("com.google.firebase:firebase-messaging")',
                'implementation("com.google.firebase:firebase-config")',
            ]:
                if fb_dep in asrc and f"// {fb_dep}" not in asrc:
                    asrc = asrc.replace(fb_dep, f"// {fb_dep}")

        if 'pickFirsts.add("**/*.so")' not in asrc:
            asrc = asrc.replace(
                'jniLibs {\n            excludes.add("META-INF/*")',
                'jniLibs {\n            excludes.add("META-INF/*")\n            pickFirsts.add("**/*.so")',
                1,
            )

        if 'signingConfigs {' not in asrc and 'create("release")' not in asrc:
            signing_block = """    signingConfigs {
        create("release") {
            val ksFile = System.getenv("KEYSTORE_FILE") ?: project.findProperty("RELEASE_STORE_FILE")?.toString()
            if (!ksFile.isNullOrBlank() && file(ksFile).exists()) {
                storeFile = file(ksFile)
                storePassword = System.getenv("KEYSTORE_PASSWORD") ?: project.findProperty("RELEASE_STORE_PASSWORD")?.toString() ?: "android123"
                keyAlias = System.getenv("KEY_ALIAS") ?: project.findProperty("RELEASE_KEY_ALIAS")?.toString() ?: "release"
                keyPassword = System.getenv("KEY_PASSWORD") ?: project.findProperty("RELEASE_KEY_PASSWORD")?.toString() ?: "android123"
            }
        }
    }

    buildTypes {"""
            asrc = asrc.replace("    buildTypes {", signing_block, 1)

        if "signingConfig =" not in asrc:
            asrc = re.sub(
                r"(release\s*\{)",
                r'\1\n            val relSign = signingConfigs.findByName("release")\n            signingConfig = if (relSign?.storeFile != null) relSign else signingConfigs.getByName("debug")',
                asrc,
                count=1,
            )

        # Aktifkan R8 Minify + ShrinkResources + Strip Native Debug Symbols pada blok release
        rel_pos = asrc.find("release {")
        if rel_pos != -1:
            head = asrc[:rel_pos]
            tail = asrc[rel_pos:]
            tail = tail.replace('debugSymbolLevel = "FULL"', 'debugSymbolLevel = "NONE"', 1)
            tail = tail.replace(
                "isMinifyEnabled = false",
                "isMinifyEnabled = true\n            isShrinkResources = true",
                1,
            )
            asrc = head + tail

        asrc = re.sub(
            r'val apkName = "[^"]*-\$\{buildType\.name\}\.apk"',
            'val apkName = "XySAMP-Mobile-${buildType.name}.apk"',
            asrc,
        )

        write(app_gradle, asrc)
        log("app/build.gradle.kts: R8 (isMinifyEnabled=true, isShrinkResources=true) & debugSymbolLevel=NONE aktif")

    if strip_fb:
        gsj = repo / "app/google-services.json"
        if gsj.exists():
            gsj.rename(gsj.with_suffix(".json.disabled"))

        for jf in (repo / "app/src/main/java").rglob("*.java"):
            s = jf.read_text(encoding="utf-8", errors="surrogateescape")
            if "firebase" not in s.lower():
                continue
            out = []
            for ln in s.splitlines(keepends=True):
                if re.match(r"\s*import\s+com\.google\.firebase", ln) and not ln.lstrip().startswith("//"):
                    out.append("//" + ln)
                elif re.search(r"FirebaseCrashlytics\s*\.", ln) and not ln.lstrip().startswith("//"):
                    out.append("//" + ln)
                else:
                    out.append(ln)
            write(jf, "".join(out))

        main_cpp = repo / "app/src/main/cpp/samp/main.cpp"
        if main_cpp.exists():
            msrc = read(main_cpp)
            if "firebase::crashlytics::Log(buffer);" in msrc and "//firebase::crashlytics::Log(buffer);" not in msrc:
                msrc = msrc.replace("firebase::crashlytics::Log(buffer);", "//firebase::crashlytics::Log(buffer);")
                write(main_cpp, msrc)

    cpp_zip = repo / "app/src/main/cpp/cpp.zip"
    if cpp_zip.exists():
        cpp_zip.unlink()

    gui_h = repo / "app/src/main/cpp/samp/gui/gui.h"
    if gui_h.exists():
        gtxt = read(gui_h)
        if "samp_widgets/playerTabList.h" in gtxt:
            write(gui_h, gtxt.replace("samp_widgets/playerTabList.h", "samp_widgets/playertablist.h"))

    rgba_cpp = repo / "app/src/main/cpp/samp/game/rgba.cpp"
    if rgba_cpp.exists():
        rtxt = read(rgba_cpp)
        if '#include "RGBA.h"' in rtxt:
            write(rgba_cpp, rtxt.replace('#include "RGBA.h"', '#include "rgba.h"'))


def sync_gate_pwn(pwn_path: Path, tag: str, key: str):
    if not pwn_path.exists():
        return
    src = read(pwn_path)
    src = re.sub(
        r'(#define\s+CLIENT_TAG\s+)"[^"]*"',
        lambda m: f'{m.group(1)}"{tag}"',
        src,
    )
    src = re.sub(
        r"(#define\s+HANDSHAKE_KEY\s+)0x[0-9A-Fa-f]+",
        lambda m: f"{m.group(1)}{key}",
        src,
    )
    write(pwn_path, src)
    log(f"gate_client.pwn disinkronin -> CLIENT_TAG=\"{tag}\", HANDSHAKE_KEY={key} ({pwn_path})")


def main():
    ap = argparse.ArgumentParser(description="Lockdown & Hardening client SA-MP Mobile")
    ap.add_argument("--repo", required=True, help="folder repo SAMP-Mobile")
    ap.add_argument("--host", required=True, help="IP atau domain server lu")
    ap.add_argument("--port", type=int, default=7777, help="Port UDP server SA-MP")
    ap.add_argument("--tag", default="XYSAMP-1.0", help="tag client, maks 25 char")
    ap.add_argument("--name", default="Warga_XyVerse", help="nickname default")
    ap.add_argument("--key", default="0x9F4E7C2B", help="kunci hex 32-bit untuk Handshake Lapis 3")
    ap.add_argument(
        "--cert-sha256",
        default="93fa85c2c42e17125bb66adbeab49fa3ccfcee646429aeb5078bdc322ea9341c",
        help="SHA-256 cert fingerprint dari Official Release Keystore",
    )
    ap.add_argument("--app-name", default="XySAMP Mobile", help="nama aplikasi di HP")
    ap.add_argument("--brand", default="XyVerse Roleplay", help="branding di launcher")
    ap.add_argument("--strip-firebase", action="store_true", default=True)
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not (repo / "app/src/main/cpp/samp").exists():
        fail(f"{repo} bukan repo SAMP-Mobile")

    if len(args.tag) > 25:
        fail(f"tag '{args.tag}' kepanjangan ({len(args.tag)} char). Maks 25 char.")

    if not re.match(r"^0x[0-9A-Fa-f]{1,8}$", args.key):
        fail(f"--key '{args.key}' harus hex 32-bit (contoh: 0x9F4E7C2B)")

    clean_name = sanitize_nick(args.name)
    key_int = int(args.key, 16)
    xor_seed = ((key_int & 0xFF) ^ ((key_int >> 8) & 0xFF) ^ 0xA7) & 0xFF
    if xor_seed == 0:
        xor_seed = 0xA7

    enc_host, len_host = xor_encode_bytes(args.host, xor_seed)
    enc_tag, len_tag = xor_encode_bytes(args.tag, xor_seed)
    enc_name, len_name = xor_encode_bytes(clean_name, xor_seed)

    print(f"\n=== LOCKDOWN + HARDENING CLIENT (port={args.port}, xor_seed=0x{xor_seed:02X}) ===\n")

    tpl_path = TEMPLATE if TEMPLATE.exists() else (repo / "client-patch/lockdown.h.template")
    if not tpl_path.exists():
        fail("template lockdown.h.template nggak ketemu")
    tpl = read(tpl_path)
    h = (
        tpl.replace("@PORT@", str(args.port))
        .replace("@KEY@", args.key)
        .replace("@XOR_SEED@", f"0x{xor_seed:02X}u")
        .replace("@ENC_HOST_BYTES@", enc_host)
        .replace("@ENC_HOST_LEN@", str(len_host))
        .replace("@ENC_TAG_BYTES@", enc_tag)
        .replace("@ENC_TAG_LEN@", str(len_tag))
        .replace("@ENC_NAME_BYTES@", enc_name)
        .replace("@ENC_NAME_LEN@", str(len_name))
    )
    out = repo / "app/src/main/cpp/samp/lockdown.h"
    write(out, h)
    log(f"lockdown.h ditulis (XOR-encoded host/tag/nick + Anti-Tamper) -> {out.relative_to(repo)}")

    patch_settings_cpp(repo, args.port)
    patch_netrpc_cpp(repo)
    patch_launcher_nickname(repo, args.port, clean_name, args.cert_sha256)
    patch_strings(repo, args.app_name, args.brand)
    patch_gradle_r8_and_security(repo, args.strip_firebase)

    for pwn_candidate in [DEFAULT_PWN, repo / "server/gate_client.pwn"]:
        if pwn_candidate.exists():
            sync_gate_pwn(pwn_candidate, args.tag, args.key)

    print("\n=== HARDENING SELESAI ===\n")


if __name__ == "__main__":
    main()
