package com.samp.mobile.launcher;

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

public class MainActivity extends AppCompatActivity {
    private static final String PREFS_NAME = "lombok_holiday_prefs";
    private static final String KEY_NICKNAME = "player_nickname";
    private static final String KEY_PASSWORD = "server_password";
    private static final String KEY_FPS = "fps_limit";
    private static final String KEY_CHAT_LINES = "chat_lines";
    private static final String KEY_CUSTOM_ZIP_URL = "custom_zip_url";
    private static final String DEFAULT_NICK = "Warga_Lombok";
    private static final int LOCKED_PORT = 7777;
    private static final String EXPECTED_CERT_SHA256 = "93fa85c2c42e17125bb66adbeab49fa3ccfcee646429aeb5078bdc322ea9341c";
    private static final String REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/xykal/XySAMP-Mobile/main/data-config.json";

    private String liteDataUrl = "https://github.com/xykal/XySAMP-Mobile/releases/download/v2.0.0/LombokHoliday-Data-Lite.zip";
    private String fullDataUrl = "https://github.com/xykal/XySAMP-Mobile/releases/download/v2.0.0/LombokHoliday-Data-Full.zip";

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
            registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(), permissions -> {
                boolean allGranted = true;
                for (Boolean granted : permissions.values()) {
                    if (!granted) {
                        allGranted = false;
                        break;
                    }
                }
                if (allGranted) {
                    storagePermissionGranted = true;
                    onPermissionReady();
                } else {
                    storagePermissionGranted = true; // App-specific external files dir tetap bisa diakses tanpa izin di Android 10+
                    onPermissionReady();
                }
            });

    private final ActivityResultLauncher<Intent> manageStorageLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
                storagePermissionGranted = true;
                onPermissionReady();
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            setFullScreenMode();
            setContentView(R.layout.main_activity);
            initViews();
            if (!verifyOfficialSignature()) {
                markTampered(true);
                Toast.makeText(this, "PERINGATAN: APK telah dimodifikasi / bukan rilis resmi!", Toast.LENGTH_LONG).show();
                finish();
                return;
            } else {
                markTampered(false);
            }
            setupTabsAndListeners();
            checkAndRequestStoragePermission();
            onPermissionReady();
            fetchRemoteDataConfig();
            refreshPeripheralsStatus();
        } catch (Exception e) {
            finish();
        }
    }

    private void initViews() {
        tabBtnHome = findViewById(R.id.tabBtnHome);
        tabBtnSettings = findViewById(R.id.tabBtnSettings);
        tabBtnControls = findViewById(R.id.tabBtnControls);

        panelHome = findViewById(R.id.panelHome);
        panelSettings = findViewById(R.id.panelSettings);
        panelControls = findViewById(R.id.panelControls);

        abiBadgeText = findViewById(R.id.abiBadgeText);
        if (abiBadgeText != null) {
            String abi = (Build.SUPPORTED_ABIS != null && Build.SUPPORTED_ABIS.length > 0) ? Build.SUPPORTED_ABIS[0] : "arm64-v8a";
            abiBadgeText.setText("ABI AKTIF: " + abi.toUpperCase(Locale.ROOT));
        }

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
    }

    private void switchTab(int tabIndex) {
        panelHome.setVisibility(tabIndex == 0 ? View.VISIBLE : View.GONE);
        panelSettings.setVisibility(tabIndex == 1 ? View.VISIBLE : View.GONE);
        panelControls.setVisibility(tabIndex == 2 ? View.VISIBLE : View.GONE);

        tabBtnHome.setBackgroundColor(tabIndex == 0 ? 0xCC1D4ED8 : 0x661E293B);
        tabBtnSettings.setBackgroundColor(tabIndex == 1 ? 0xCC1D4ED8 : 0x661E293B);
        tabBtnControls.setBackgroundColor(tabIndex == 2 ? 0xCC1D4ED8 : 0x661E293B);

        if (tabIndex == 2) {
            refreshPeripheralsStatus();
        }
    }

    private void updateFpsButtons(int fps) {
        selectedFps = fps;
        btnFps30.setBackgroundColor(fps == 30 ? 0xCC0284C7 : 0x661E293B);
        btnFps60.setBackgroundColor(fps == 60 ? 0xCC0284C7 : 0x661E293B);
        btnFps90.setBackgroundColor(fps == 90 ? 0xCC0284C7 : 0x661E293B);
        btnFps120.setBackgroundColor(fps == 120 ? 0xCC0284C7 : 0x661E293B);
    }

    private void updateChatLineButtons(int lines) {
        selectedChatLines = lines;
        btnChat5.setBackgroundColor(lines == 5 ? 0xCC0284C7 : 0x661E293B);
        btnChat7.setBackgroundColor(lines == 7 ? 0xCC0284C7 : 0x661E293B);
        btnChat9.setBackgroundColor(lines == 9 ? 0xCC0284C7 : 0x661E293B);
        btnChat12.setBackgroundColor(lines == 12 ? 0xCC0284C7 : 0x661E293B);
    }

    private void setupTabsAndListeners() {
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

        btnSaveSettings.setOnClickListener(v -> {
            String nick = sanitizeNick(nicknameInput.getText().toString());
            if (nick.isEmpty()) nick = DEFAULT_NICK;
            saveAllSettingsToIni(nick);
            Toast.makeText(this, "Pengaturan berhasil disimpan ke SAMP/settings.ini!", Toast.LENGTH_SHORT).show();
        });

        btnResetSettings.setOnClickListener(v -> {
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
        });

        cbEnableKeyboardMouse.setOnCheckedChangeListener((b, checked) -> WarGamepad.sEnableKeyboardMouse = checked);
        cbEnableGamepad.setOnCheckedChangeListener((b, checked) -> WarGamepad.sEnableGamepad = checked);
        btnRefreshDevices.setOnClickListener(v -> refreshPeripheralsStatus());

        btnDownloadLite.setOnClickListener(v -> startInAppDataDownload(liteDataUrl, "Data Lite"));
        btnDownloadFull.setOnClickListener(v -> startInAppDataDownload(fullDataUrl, "Data Full"));
        btnCustomUrl.setOnClickListener(v -> showCustomUrlDialog());

        startButton.setOnClickListener(v -> {
            v.animate().scaleX(0.94f).scaleY(0.94f).setDuration(80)
                    .withEndAction(() -> v.animate().scaleX(1f).scaleY(1f).setDuration(80).start())
                    .start();
            startGame();
        });
    }

    private void refreshPeripheralsStatus() {
        if (peripheralStatusText == null) return;
        boolean hasKb = WarGamepad.hasConnectedKeyboard();
        boolean hasMouse = WarGamepad.hasConnectedMouse();
        boolean hasPad = WarGamepad.hasConnectedGamepad();

        List<String> names = new ArrayList<>();
        try {
            for (int id : InputDevice.getDeviceIds()) {
                InputDevice d = InputDevice.getDevice(id);
                if (d != null && !d.isVirtual()) {
                    int s = d.getSources();
                    if ((s & InputDevice.SOURCE_GAMEPAD) != 0 || (s & InputDevice.SOURCE_JOYSTICK) != 0 ||
                        (s & InputDevice.SOURCE_MOUSE) != 0 ||
                        ((s & InputDevice.SOURCE_KEYBOARD) != 0 && d.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC)) {
                        names.add(d.getName());
                    }
                }
            }
        } catch (Throwable ignored) {}

        String status = String.format(Locale.ROOT,
                "Status Perangkat: Keyboard Fisik [%s] | Mouse OTG/BT [%s] | Gamepad [%s]%s",
                hasKb ? "TERHUBUNG" : "SIAP",
                hasMouse ? "TERHUBUNG" : "SIAP",
                hasPad ? "TERHUBUNG" : "SIAP",
                names.isEmpty() ? "" : ("
Perangkat Terdeteksi: " + String.join(", ", names)));
        peripheralStatusText.setText(status);
    }

    private void fetchRemoteDataConfig() {
        executor.execute(() -> {
            try {
                HttpURLConnection conn = (HttpURLConnection) new URL(REMOTE_CONFIG_URL).openConnection();
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(5000);
                if (conn.getResponseCode() == 200) {
                    StringBuilder sb = new StringBuilder();
                    try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = br.readLine()) != null) sb.append(line);
                    }
                    JSONObject obj = new JSONObject(sb.toString());
                    if (obj.has("data_lite")) {
                        JSONObject lite = obj.getJSONObject("data_lite");
                        liteDataUrl = lite.optString("url", liteDataUrl);
                    }
                    if (obj.has("data_full")) {
                        JSONObject full = obj.getJSONObject("data_full");
                        fullDataUrl = full.optString("url", fullDataUrl);
                    }
                }
            } catch (Exception ignored) {}
        });
    }

    private void showCustomUrlDialog() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        final EditText input = new EditText(this);
        input.setHint("https://example.com/Data-GTA-Lite.zip");
        input.setText(prefs.getString(KEY_CUSTOM_ZIP_URL, liteDataUrl));
        input.setSingleLine(true);

        new AlertDialog.Builder(this)
                .setTitle("Download Data GTA (.zip) dari URL")
                .setMessage("Masukkan link direct download file .zip Data GTA (Lite/Full). Aplikasi akan otomatis mengunduh dan mengekstrak ke folder data game:")
                .setView(input)
                .setPositiveButton("Download & Ekstrak", (d, w) -> {
                    String url = input.getText().toString().trim();
                    if (!url.startsWith("http")) {
                        Toast.makeText(this, "URL harus diawali http:// atau https://", Toast.LENGTH_LONG).show();
                        return;
                    }
                    prefs.edit().putString(KEY_CUSTOM_ZIP_URL, url).apply();
                    startInAppDataDownload(url, "Data Custom ZIP");
                })
                .setNegativeButton("Batal", null)
                .show();
    }

    private File getPreferredWritableDataDir() {
        try {
            File ext = getExternalFilesDir(null);
            if (ext != null) {
                if (!ext.exists()) ext.mkdirs();
                return ext;
            }
        } catch (Exception ignored) {}
        File gta = new File("/storage/emulated/0/GTA/");
        if (!gta.exists()) gta.mkdirs();
        return gta;
    }

    private void startInAppDataDownload(final String zipUrl, final String label) {
        if (isDownloading) {
            Toast.makeText(this, "Unduhan sedang berjalan, harap tunggu...", Toast.LENGTH_SHORT).show();
            return;
        }
        isDownloading = true;
        downloadProgressBar.setVisibility(View.VISIBLE);
        downloadProgressBar.setIndeterminate(false);
        downloadProgressBar.setProgress(0);
        downloadStatusText.setText("Menghubungkan ke server unduhan " + label + "...");

        executor.execute(() -> {
            File targetDir = getPreferredWritableDataDir();
            File tempZip = new File(targetDir, "lombok_data_download.zip.part");
            HttpURLConnection conn = null;
            try {
                long existingBytes = tempZip.exists() ? tempZip.length() : 0L;
                URL url = new URL(zipUrl);
                conn = (HttpURLConnection) url.openConnection();
                conn.setInstanceFollowRedirects(true);
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(30000);
                if (existingBytes > 0) {
                    conn.setRequestProperty("Range", "bytes=" + existingBytes + "-");
                }
                int code = conn.getResponseCode();
                if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                    if (existingBytes > 0) {
                        tempZip.delete();
                        existingBytes = 0;
                        conn.disconnect();
                        conn = (HttpURLConnection) url.openConnection();
                        conn.setInstanceFollowRedirects(true);
                        code = conn.getResponseCode();
                    }
                }
                if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                    final int errCode = code;
                    handler.post(() -> {
                        isDownloading = false;
                        downloadStatusText.setText("Link unduhan belum tersedia (HTTP " + errCode + "). Gunakan tombol 'URL ZIP CUSTOM' atau unggah file .zip ke Release GitHub.");
                        Toast.makeText(MainActivity.this, "Server mengembalikan HTTP " + errCode + ". Klik 'URL ZIP CUSTOM' untuk memasukkan link .zip data Anda.", Toast.LENGTH_LONG).show();
                    });
                    return;
                }

                long contentLength = conn.getContentLengthLong();
                long totalBytes = (code == HttpURLConnection.HTTP_PARTIAL && contentLength > 0)
                        ? (existingBytes + contentLength)
                        : contentLength;
                boolean append = (code == HttpURLConnection.HTTP_PARTIAL);

                try (InputStream in = new BufferedInputStream(conn.getInputStream(), 65536);
                     FileOutputStream fos = new FileOutputStream(tempZip, append)) {
                    byte[] buf = new byte[65536];
                    long downloaded = append ? existingBytes : 0L;
                    long lastUpdate = System.currentTimeMillis();
                    long bytesAtLastUpdate = downloaded;
                    int n;
                    while ((n = in.read(buf)) != -1) {
                        fos.write(buf, 0, n);
                        downloaded += n;
                        long now = System.currentTimeMillis();
                        if (now - lastUpdate >= 250) {
                            long deltaB = downloaded - bytesAtLastUpdate;
                            double speedMb = (deltaB / 1048576.0) / ((now - lastUpdate) / 1000.0);
                            int pct = (totalBytes > 0) ? (int) ((downloaded * 100L) / totalBytes) : 0;
                            final double dlMb = downloaded / 1048576.0;
                            final double totMb = totalBytes > 0 ? (totalBytes / 1048576.0) : 0.0;
                            final int fPct = pct;
                            final double fSpd = speedMb;
                            handler.post(() -> {
                                downloadProgressBar.setProgress(fPct);
                                downloadStatusText.setText(String.format(Locale.ROOT,
                                        "Mengunduh %s: %.1f / %.1f MB (%d%%) — %.2f MB/s",
                                        label, dlMb, totMb, fPct, fSpd));
                            });
                            lastUpdate = now;
                            bytesAtLastUpdate = downloaded;
                        }
                    }
                    fos.flush();
                }

                handler.post(() -> {
                    downloadProgressBar.setIndeterminate(true);
                    downloadStatusText.setText("Mengekstrak " + label + " ke " + targetDir.getAbsolutePath() + " ...");
                });

                extractZipSmart(tempZip, targetDir);
                tempZip.delete();
                provisionSampDirectory(targetDir);

                handler.post(() -> {
                    isDownloading = false;
                    downloadProgressBar.setIndeterminate(false);
                    downloadProgressBar.setProgress(100);
                    String active = resolveGameDataDir(MainActivity.this);
                    updateDataStatusLabel(active);
                    downloadStatusText.setText("Selesai! " + label + " berhasil dipasang di: " + active);
                    Toast.makeText(MainActivity.this, label + " selesai diunduh & diekstrak! Siap dimainkan.", Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                final String msg = e.getMessage();
                handler.post(() -> {
                    isDownloading = false;
                    downloadProgressBar.setIndeterminate(false);
                    downloadStatusText.setText("Unduhan terhenti: " + msg + " (Klik lagi untuk Resume otomatis)");
                });
            } finally {
                if (conn != null) conn.disconnect();
            }
        });
    }

    private void extractZipSmart(File zipFile, File targetRoot) throws Exception {
        String[] knownRoots = new String[]{"texdb/", "models/", "data/", "anim/", "audio/", "samp/"};
        try (ZipInputStream zis = new ZipInputStream(new BufferedInputStream(new FileInputStream(zipFile), 65536))) {
            ZipEntry entry;
            byte[] buffer = new byte[65536];
            while ((entry = zis.getNextEntry()) != null) {
                String rawName = entry.getName().replace('\\', '/');
                while (rawName.startsWith("/")) rawName = rawName.substring(1);
                if (rawName.contains("..")) continue;

                // Normalisasi apabila di dalam ZIP ada subfolder pembungkus (misal "com.rockstargames.gtasa/files/texdb/...")
                String lower = rawName.toLowerCase(Locale.ROOT);
                for (String kr : knownRoots) {
                    int idx = lower.indexOf(kr);
                    if (idx > 0 && rawName.charAt(idx - 1) == '/') {
                        rawName = rawName.substring(idx);
                        break;
                    }
                }

                File outFile = new File(targetRoot, rawName);
                if (entry.isDirectory()) {
                    outFile.mkdirs();
                } else {
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.exists()) parent.mkdirs();
                    try (BufferedOutputStream bos = new BufferedOutputStream(new FileOutputStream(outFile), 65536)) {
                        int len;
                        while ((len = zis.read(buffer)) != -1) {
                            bos.write(buffer, 0, len);
                        }
                        bos.flush();
                    }
                }
                zis.closeEntry();
            }
        }
    }

    private void onPermissionReady() {
        String dir = resolveGameDataDir(this);
        provisionSampDirectory(new File(dir));
        loadSavedSettings();
        updateDataStatusLabel(dir);
    }

    private void updateDataStatusLabel(String dir) {
        if (bugText == null || dataBadgeStatus == null) return;
        File d = new File(dir);
        if (hasGtaCache(d)) {
            dataBadgeStatus.setText("DATA SIAP (TANPA OBB)");
            dataBadgeStatus.setTextColor(0xFF34D399);
            dataBadgeStatus.setBackgroundColor(0x3310B981);
            bugText.setText("Lokasi Data Aktif: " + dir);
        } else {
            dataBadgeStatus.setText("DATA BELUM ADA");
            dataBadgeStatus.setTextColor(0xFFFBBF24);
            dataBadgeStatus.setBackgroundColor(0x33F59E0B);
            bugText.setText("Data GTA belum ditemukan. Klik tombol 'DOWNLOAD DATA LITE / FULL' di bawah atau taruh folder data GTA di /sdcard/GTA/");
        }
    }

    public static boolean hasSubdirIgnoreCase(File dir, String name) {
        if (dir == null || !dir.exists() || !dir.isDirectory()) return false;
        File[] list = dir.listFiles();
        if (list == null) return false;
        for (File f : list) {
            if (f.isDirectory() && f.getName().equalsIgnoreCase(name)) {
                return true;
            }
        }
        return false;
    }

    public static boolean hasGtaCache(File dir) {
        return hasSubdirIgnoreCase(dir, "texdb") || hasSubdirIgnoreCase(dir, "models");
    }

    public static String resolveGameDataDir(Context ctx) {
        List<String> candidates = new ArrayList<>();
        try {
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) {
                String p = ext.getAbsolutePath();
                if (!p.endsWith("/")) p += "/";
                candidates.add(p);
            }
        } catch (Exception ignored) {}
        candidates.add("/storage/emulated/0/Android/data/com.lombokholiday.mobile/files/");
        candidates.add("/storage/emulated/0/GTA/");
        candidates.add("/storage/emulated/0/Android/data/com.samp.mobile/files/");
        candidates.add("/storage/emulated/0/Android/data/com.gta.game/files/");
        candidates.add("/storage/emulated/0/Android/data/ro.alyn_sampmobile.game/files/");
        candidates.add("/storage/emulated/0/Android/data/ru.unisamp_mobile.game/files/");
        candidates.add("/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/");

        for (String c : candidates) {
            File f = new File(c);
            if (hasGtaCache(f)) {
                return c.endsWith("/") ? c : (c + "/");
            }
        }
        try {
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) {
                String p = ext.getAbsolutePath();
                return p.endsWith("/") ? p : (p + "/");
            }
        } catch (Exception ignored) {}
        return "/storage/emulated/0/GTA/";
    }

    private void provisionSampDirectory(File baseDir) {
        try {
            File sampDir = new File(baseDir, "SAMP");
            File fontsDir = new File(sampDir, "fonts");
            if (!fontsDir.exists()) {
                fontsDir.mkdirs();
            }
            String[] fontTargets = new String[]{ "arial.ttf", "Arial.ttf", "arial_bold.ttf" };
            for (String ft : fontTargets) {
                File outFont = new File(fontsDir, ft);
                if (!outFont.exists() || outFont.length() < 1024) {
                    copyBundledFont(outFont);
                }
            }
        } catch (Exception ignored) {}
    }

    private void copyBundledFont(File dest) {
        try (InputStream is = getResources().openRawResource(R.font.roboto_medium);
             FileOutputStream fos = new FileOutputStream(dest)) {
            byte[] buf = new byte[4096];
            int n;
            while ((n = is.read(buf)) != -1) {
                fos.write(buf, 0, n);
            }
            fos.flush();
        } catch (Exception e) {
            try (InputStream is2 = getAssets().open("Fonts/HELVETICANEUELTCOM-MD.TTF");
                 FileOutputStream fos2 = new FileOutputStream(dest)) {
                byte[] buf = new byte[4096];
                int n;
                while ((n = is2.read(buf)) != -1) {
                    fos2.write(buf, 0, n);
                }
                fos2.flush();
            } catch (Exception ignored) {}
        }
    }

    private boolean verifyOfficialSignature() {
        if (EXPECTED_CERT_SHA256 == null || EXPECTED_CERT_SHA256.isEmpty()) {
            return true;
        }
        try {
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
            for (byte b : digest) {
                hex.append(String.format("%02x", b & 0xff));
            }
            return EXPECTED_CERT_SHA256.equalsIgnoreCase(hex.toString());
        } catch (Exception e) {
            return false;
        }
    }

    private void markTampered(boolean tampered) {
        try {
            String dir = resolveGameDataDir(this);
            File f = new File(dir, "SAMP/.tampered");
            if (tampered) {
                File p = f.getParentFile();
                if (p != null && !p.exists()) p.mkdirs();
                try (FileOutputStream fos = new FileOutputStream(f)) {
                    fos.write(1);
                }
            } else if (f.exists()) {
                f.delete();
            }
        } catch (Exception ignored) { }
    }

    private String sanitizeNick(String raw) {
        if (raw == null) return "";
        String s = raw.trim().replace(' ', '_');
        s = s.replaceAll("[^A-Za-z0-9_\\[\\]$=()@.]", "");
        if (s.length() > 20) s = s.substring(0, 20);
        return s;
    }

    private void loadSavedSettings() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String savedNick = prefs.getString(KEY_NICKNAME, "");
        String savedPass = prefs.getString(KEY_PASSWORD, "");
        int fps = prefs.getInt(KEY_FPS, 60);
        int lines = prefs.getInt(KEY_CHAT_LINES, 7);

        if (savedNick.isEmpty()) {
            File ini = new File(resolveGameDataDir(this), "SAMP/settings.ini");
            if (ini.exists()) {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        String trimmed = line.trim();
                        if (trimmed.toLowerCase().startsWith("name=")) {
                            String val = trimmed.substring(5).trim();
                            if (!val.isEmpty() && !val.startsWith("__android_") && !val.equals("Nick_Name")) {
                                savedNick = val;
                                break;
                            }
                        }
                    }
                } catch (Exception ignored) { }
            }
        }

        if (nicknameInput != null && !savedNick.isEmpty() && !savedNick.equals(DEFAULT_NICK)) {
            nicknameInput.setText(savedNick);
        }
        if (passwordInput != null && !savedPass.isEmpty()) {
            passwordInput.setText(savedPass);
        }
        updateFpsButtons(fps);
        updateChatLineButtons(lines);
    }

    private boolean saveAllSettingsToIni(String nick) {
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
        try {
            File ext = getExternalFilesDir(null);
            if (ext != null) {
                String p = ext.getAbsolutePath() + "/";
                if (!targetDirs.contains(p)) targetDirs.add(p);
            }
        } catch (Exception ignored) {}
        if (!targetDirs.contains("/storage/emulated/0/GTA/")) {
            targetDirs.add("/storage/emulated/0/GTA/");
        }

        String iniContent = "[client]\n"
                + "name=" + nick + "\n"
                + "host=127.0.0.1\n"
                + "port=" + LOCKED_PORT + "\n"
                + "password=" + pass + "\n"
                + "version=0.3.7\n"
                + "autoaim=false\n\n"
                + "[debug]\n"
                + "debug=false\n"
                + "online=true\n\n"
                + "[gui]\n"
                + "Font=arial.ttf\n"
                + "FontSize=30.0\n"
                + "FontOutline=2\n"
                + "ChatPosX=325.0\n"
                + "ChatPosY=25.0\n"
                + "ChatSizeX=1150.0\n"
                + "ChatSizeY=220.0\n"
                + "ChatMaxMessages=" + selectedChatLines + "\n"
                + "FPSLimit=" + selectedFps + "\n"
                + "VoiceChatEnable=" + (cbVoiceChat != null && cbVoiceChat.isChecked() ? "true" : "false") + "\n"
                + "fps=" + (cbFpsCounter != null && cbFpsCounter.isChecked() ? "true" : "false") + "\n"
                + "firstperson=" + (cbFirstPerson != null && cbFirstPerson.isChecked() ? "true" : "false") + "\n"
                + "cutout=" + (cbCutout != null && cbCutout.isChecked() ? "true" : "false") + "\n"
                + "androidkeyboard=" + (cbAndroidKeyboard != null && cbAndroidKeyboard.isChecked() ? "true" : "false") + "\n"
                + "hparmourtext=" + (cbHpArmourText != null && cbHpArmourText.isChecked() ? "true" : "false") + "\n"
                + "outfitguns=" + (cbOutfitGuns != null && cbOutfitGuns.isChecked() ? "true" : "false") + "\n"
                + "radarrect=" + (cbRadarRect != null && cbRadarRect.isChecked() ? "true" : "false") + "\n"
                + "pcmoney=" + (cbPcMoney != null && cbPcMoney.isChecked() ? "true" : "false") + "\n"
                + "skybox=" + (cbSkyBox != null && cbSkyBox.isChecked() ? "true" : "false") + "\n"
                + "snow=" + (cbSnow != null && cbSnow.isChecked() ? "true" : "false") + "\n";

        boolean ok = false;
        for (String dir : targetDirs) {
            try {
                provisionSampDirectory(new File(dir));
                File ini = new File(dir, "SAMP/settings.ini");
                File parent = ini.getParentFile();
                if (parent != null && !parent.exists()) parent.mkdirs();
                try (FileOutputStream fos = new FileOutputStream(ini, false)) {
                    fos.write(iniContent.getBytes(StandardCharsets.UTF_8));
                    fos.flush();
                }
                ok = true;
            } catch (Exception ignored) {}
        }
        return ok;
    }

    private void checkAndRequestStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            if (Environment.isExternalStorageManager()) {
                storagePermissionGranted = true;
            } else {
                requestManageStoragePermission();
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            String[] permissions = new String[]{
                    android.Manifest.permission.READ_EXTERNAL_STORAGE,
                    android.Manifest.permission.WRITE_EXTERNAL_STORAGE,
                    android.Manifest.permission.RECORD_AUDIO
            };
            boolean allGranted = true;
            for (String perm : permissions) {
                if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }
            if (allGranted) {
                storagePermissionGranted = true;
            } else {
                requestStoragePermissionLauncher.launch(permissions);
            }
        } else {
            storagePermissionGranted = true;
        }
    }

    private void requestManageStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
                intent.setData(Uri.parse("package:" + getPackageName()));
                manageStorageLauncher.launch(intent);
            } catch (Exception e) {
                Intent intent = new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION);
                manageStorageLauncher.launch(intent);
            }
        }
    }

    private void setFullScreenMode() {
        try {
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
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                WindowManager.LayoutParams params = getWindow().getAttributes();
                params.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
                getWindow().setAttributes(params);
            }
            if (getSupportActionBar() != null) {
                getSupportActionBar().hide();
            }
        } catch (Exception ignored) { }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            setFullScreenMode();
            refreshPeripheralsStatus();
        }
    }

    private void startGame() {
        if (!verifyOfficialSignature()) {
            markTampered(true);
            Toast.makeText(this, "APK tidak resmi / telah dimodifikasi!", Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        String dataDir = resolveGameDataDir(this);
        updateDataStatusLabel(dataDir);
        if (!hasGtaCache(new File(dataDir))) {
            Toast.makeText(this,
                    "Data GTA SA belum terpasang! Silakan klik tombol 'DOWNLOAD DATA LITE' atau 'DOWNLOAD DATA FULL' di dalam aplikasi terlebih dahulu.",
                    Toast.LENGTH_LONG).show();
            return;
        }

        String rawNick = (nicknameInput != null) ? nicknameInput.getText().toString() : "";
        String nick = sanitizeNick(rawNick);
        if (nick.isEmpty()) {
            nick = sanitizeNick(DEFAULT_NICK);
        }
        if (nick.length() < 3) {
            Toast.makeText(this, "Nickname minimal 3 karakter (contoh: Nama_Roleplay)", Toast.LENGTH_LONG).show();
            return;
        }
        if (nicknameInput != null) {
            nicknameInput.setText(nick);
        }
        hideKeyboard(this);
        saveAllSettingsToIni(nick);

        Intent gameIntent = new Intent(MainActivity.this, SAMP.class);
        gameIntent.putExtra("player_name", nick);
        gameIntent.putExtra("game_data_dir", dataDir);
        startActivity(gameIntent);
    }

    public static void hideKeyboard(Activity activity) {
        try {
            InputMethodManager inputManager = (InputMethodManager) activity
                    .getSystemService(Context.INPUT_METHOD_SERVICE);
            View currentFocusedView = activity.getCurrentFocus();
            if (currentFocusedView != null && inputManager != null) {
                inputManager.hideSoftInputFromWindow(currentFocusedView.getWindowToken(), InputMethodManager.HIDE_NOT_ALWAYS);
            }
        } catch (Exception ignored) { }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        handler.removeCallbacksAndMessages(null);
    }
}
