package com.samp.mobile.launcher;

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

public class MainActivity extends AppCompatActivity {
    private static final String PREFS_NAME = "samp_launcher_prefs";
    private static final String KEY_NICKNAME = "player_nickname";
    private static final String KEY_DATA_DIR = "active_data_dir";
    private static final String DEFAULT_NICK = "Warga_XyVerse";
    private static final int LOCKED_PORT = 7777;
    // SHA-256 Official Release Keystore Pinning (Anti-Repackage / Anti-Mod APK)
    private static final String EXPECTED_CERT_SHA256 = "93fa85c2c42e17125bb66adbeab49fa3ccfcee646429aeb5078bdc322ea9341c";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private Button startButton;
    private EditText nicknameInput;
    private TextView title1, title2, authorText, bugText;
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
                    storagePermissionGranted = false;
                    Toast.makeText(this, "Izin penyimpanan diperlukan untuk membaca data GTA SA", Toast.LENGTH_LONG).show();
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                        requestManageStoragePermission();
                    }
                }
            });

    private final ActivityResultLauncher<Intent> manageStorageLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    if (Environment.isExternalStorageManager()) {
                        storagePermissionGranted = true;
                        onPermissionReady();
                    } else {
                        storagePermissionGranted = false;
                        Toast.makeText(this, "Berikan izin 'Akses Semua File' agar game bisa berjalan", Toast.LENGTH_LONG).show();
                    }
                }
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
            setupClickListeners();
            checkAndRequestStoragePermission();
            if (storagePermissionGranted) {
                onPermissionReady();
            }
        } catch (Exception e) {
            finish();
        }
    }

    private void onPermissionReady() {
        String dir = resolveGameDataDir(this);
        provisionSampDirectory(new File(dir));
        loadSavedNickname();
        updateDataStatusLabel(dir);
    }

    private void updateDataStatusLabel(String dir) {
        if (bugText == null) return;
        File d = new File(dir);
        if (hasGtaCache(d)) {
            bugText.setText("Data Terdeteksi (Lite/Full Tanpa OBB): " + dir);
        } else {
            bugText.setText("Taruh folder data GTA (Lite/Full) di: /sdcard/GTA/ atau /Android/data/com.samp.mobile/files/");
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
        candidates.add("/storage/emulated/0/GTA/");
        try {
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) {
                String p = ext.getAbsolutePath();
                if (!p.endsWith("/")) p += "/";
                candidates.add(p);
            }
        } catch (Exception ignored) {}
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
        return "/storage/emulated/0/GTA/";
    }

    private void provisionSampDirectory(File baseDir) {
        try {
            File sampDir = new File(baseDir, "SAMP");
            File fontsDir = new File(sampDir, "fonts");
            if (!fontsDir.exists()) {
                fontsDir.mkdirs();
            }
            // Pastikan arial.ttf & arial_bold.ttf selalu ada agar ImGui tidak pernah gagal / blackscreen
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

    private void initViews() {
        title1 = findViewById(R.id.title1);
        title2 = findViewById(R.id.title2);
        authorText = findViewById(R.id.authorText);
        bugText = findViewById(R.id.bugText);
        startButton = findViewById(R.id.startButton);
        nicknameInput = findViewById(R.id.nicknameInput);
    }

    private String sanitizeNick(String raw) {
        if (raw == null) return "";
        String s = raw.trim().replace(' ', '_');
        s = s.replaceAll("[^A-Za-z0-9_\\[\\]$=()@.]", "");
        if (s.length() > 20) s = s.substring(0, 20);
        return s;
    }

    private void loadSavedNickname() {
        if (nicknameInput == null) return;
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String saved = prefs.getString(KEY_NICKNAME, "");

        if (saved.isEmpty()) {
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
                                saved = val;
                                break;
                            }
                        }
                    }
                } catch (Exception ignored) { }
            }
        }

        if (!saved.isEmpty() && !saved.equals(DEFAULT_NICK)) {
            nicknameInput.setText(saved);
        }
    }

    private boolean saveNicknameToIni(String nick) {
        String activeDir = resolveGameDataDir(this);
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit().putString(KEY_NICKNAME, nick).putString(KEY_DATA_DIR, activeDir).apply();

        String[] targetDirs = new String[]{
                activeDir,
                "/storage/emulated/0/GTA/"
        };
        boolean ok = false;
        for (String dir : targetDirs) {
            try {
                provisionSampDirectory(new File(dir));
                File ini = new File(dir, "SAMP/settings.ini");
                File parent = ini.getParentFile();
                if (parent != null && !parent.exists()) {
                    parent.mkdirs();
                }

                if (!ini.exists()) {
                    String content = "[client]\n"
                            + "name=" + nick + "\n"
                            + "host=127.0.0.1\n"
                            + "port=" + LOCKED_PORT + "\n"
                            + "password=\n"
                            + "version=0.3.7\n"
                            + "autoaim=false\n\n"
                            + "[debug]\n"
                            + "debug=false\n"
                            + "online=true\n\n"
                            + "[gui]\n"
                            + "Font=arial.ttf\n"
                            + "FontSize=30.0\n"
                            + "FontOutline=2\n"
                            + "ChatMaxMessages=6\n"
                            + "FPSLimit=60\n";
                    try (FileOutputStream fos = new FileOutputStream(ini, false)) {
                        fos.write(content.getBytes(StandardCharsets.UTF_8));
                    }
                    ok = true;
                    continue;
                }

                List<String> lines = new ArrayList<>();
                boolean nameUpdated = false;
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        String lower = line.trim().toLowerCase();
                        if (lower.startsWith("name=") || lower.startsWith("name =")) {
                            lines.add("name=" + nick);
                            nameUpdated = true;
                        } else if (lower.startsWith("font=") || lower.startsWith("font =")) {
                            lines.add("Font=arial.ttf");
                        } else {
                            lines.add(line);
                        }
                    }
                }

                if (!nameUpdated) {
                    lines.add(0, "[client]");
                    lines.add(1, "name=" + nick);
                }

                StringBuilder sb = new StringBuilder();
                for (String l : lines) {
                    sb.append(l).append("\n");
                }
                try (FileOutputStream fos = new FileOutputStream(ini, false)) {
                    fos.write(sb.toString().getBytes(StandardCharsets.UTF_8));
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
                    android.Manifest.permission.WRITE_EXTERNAL_STORAGE
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
                    "Data GTA SA (Lite / Full) belum ditemukan! Ekstrak folder data GTA (texdb, models, data, SAMP) ke /sdcard/GTA/ atau /Android/data/com.samp.mobile/files/ terlebih dahulu.",
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
        saveNicknameToIni(nick);

        Intent gameIntent = new Intent(MainActivity.this, SAMP.class);
        gameIntent.putExtra("player_name", nick);
        gameIntent.putExtra("game_data_dir", dataDir);
        startActivity(gameIntent);
    }

    private void setupClickListeners() {
        startButton.setOnClickListener(v -> {
            v.animate().scaleX(0.92f).scaleY(0.92f).setDuration(90)
                    .withEndAction(() -> v.animate().scaleX(1f).scaleY(1f).setDuration(90).start())
                    .start();
            if (storagePermissionGranted) {
                startGame();
            } else {
                checkAndRequestStoragePermission();
            }
        });
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
