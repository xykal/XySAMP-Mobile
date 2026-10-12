package com.gta.launcher.activity;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
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
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity {
    private static final String PREFS_NAME = "samp_launcher_prefs";
    private static final String KEY_NICKNAME = "player_nickname";
    private static final String INI_PATH = "/storage/emulated/0/GTA/SAMP/settings.ini";
    private static final String DEFAULT_NICK = "Warga_XyVerse";
    private static final String LOCKED_HOST = "play.xyverse.my.id";
    private static final int LOCKED_PORT = 7777;
    private static final String LOCKED_TAG = "XYSAMP-1.0";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private Button startButton;
    private EditText nicknameInput;
    private TextView title1, title2, authorText;
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
                    loadSavedNickname();
                } else {
                    storagePermissionGranted = false;
                    Toast.makeText(this, "Izin penyimpanan diperlukan untuk membaca file GTA SA", Toast.LENGTH_LONG).show();
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
                        loadSavedNickname();
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
            loadSavedNickname();
            setupClickListeners();
            checkAndRequestStoragePermission();
        } catch (Exception e) {
            Log.e("MainActivity", "Critical error in onCreate: " + e.getMessage(), e);
            finish();
        }
    }

    private void initViews() {
        title1 = findViewById(R.id.title1);
        title2 = findViewById(R.id.title2);
        authorText = findViewById(R.id.authorText);
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
            File ini = new File(INI_PATH);
            if (ini.exists()) {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        String trimmed = line.trim();
                        if (trimmed.toLowerCase().startsWith("name=")) {
                            String val = trimmed.substring(5).trim();
                            if (!val.isEmpty() && !val.startsWith("__android_")) {
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
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit().putString(KEY_NICKNAME, nick).apply();

        try {
            File ini = new File(INI_PATH);
            File parent = ini.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }

            if (!ini.exists()) {
                String content = "[client]\n"
                        + "name=" + nick + "\n"
                        + "host=" + LOCKED_HOST + "\n"
                        + "port=" + LOCKED_PORT + "\n"
                        + "password=\n"
                        + "version=" + LOCKED_TAG + "\n"
                        + "autoaim=false\n\n"
                        + "[debug]\n"
                        + "debug=false\n"
                        + "online=true\n";
                try (FileOutputStream fos = new FileOutputStream(ini, false)) {
                    fos.write(content.getBytes(StandardCharsets.UTF_8));
                }
                return true;
            }

            List<String> lines = new ArrayList<>();
            boolean nameUpdated = false;
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) {
                    if (line.trim().toLowerCase().startsWith("name=")) {
                        lines.add("name=" + nick);
                        nameUpdated = true;
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
            return true;
        } catch (Exception e) {
            Log.e("MainActivity", "Gagal simpan settings.ini: " + e.getMessage());
            return false;
        }
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
        } catch (Exception e) {
            Log.e("MainActivity", "Error in setFullScreenMode: " + e.getMessage());
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            setFullScreenMode();
        }
    }

    private void startGame() {
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
