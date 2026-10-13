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
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.SwitchCompat;

import com.samp.mobile.game.SAMP;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
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

/**
 * Lombok Holiday — Launcher v3.0.0
 * Dibangkitkan otomatis oleh tools/lockdown.py (placeholder diganti saat build).
 */
public class MainActivity extends AppCompatActivity {

    // ===================== KONFIGURASI (inject saat build) =====================
    private static final String PREFS_NAME = "lombok_holiday_prefs";
    private static final String MOD_PREFS = "configlauncher";
    private static final String KEY_NICKNAME = "player_nickname";
    private static final String KEY_PASSWORD = "server_password";
    private static final String KEY_FPS = "fps_limit";
    private static final String KEY_CHAT_LINES = "chat_lines";
    private static final String KEY_FONT_SIZE = "font_size";
    private static final String KEY_CUSTOM_ZIP_URL = "custom_zip_url";
    private static final String KEY_CUSTOM_SERVERS = "custom_servers";
    private static final String KEY_REMOTE_CACHE = "remote_config_cache";
    private static final String KEY_MLOADER = "MLOADER";
    private static final String KEY_CLEO = "CLEO";
    private static final String DEFAULT_NICK = "Warga_Lombok";
    private static final int LOCKED_PORT = 7777;
    private static final String SERVER_TITLE = "Lombok Holiday Roleplay";
    private static final String EXPECTED_CERT_SHA256 = "93fa85c2c42e17125bb66adbeab49fa3ccfcee646429aeb5078bdc322ea9341c";
    private static final String REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/xykal/XySAMP-Mobile/main/data-config.json";
    private static final String PACKAGE_ID = "com.lombokholiday.mobile";
    private static final String APP_VERSION = "3.0.0";
    /** Koneksi ke server lain (selain server resmi). Diaktifkan hanya bila admin mengizinkan. */
    private static final boolean MULTI_SERVER_ENABLED = false;

    // ===================== WARNA (Modern Cyber Blue-Purple) =====================
    private static final int C_BG = 0xFF0B1020;
    private static final int C_PANEL = 0xFF101829;
    private static final int C_CARD = 0xFF162038;
    private static final int C_INPUT = 0xFF1E2A47;
    private static final int C_TEXT = 0xFFE2E8F0;
    private static final int C_MUTED = 0xFF94A3B8;
    private static final int C_A = 0xFF38BDF8;
    private static final int C_B = 0xFFA78BFA;
    private static final int C_OK = 0xFF34D399;
    private static final int C_WARN = 0xFFFBBF24;
    private static final int MP = ViewGroup.LayoutParams.MATCH_PARENT;
    private static final int WP = ViewGroup.LayoutParams.WRAP_CONTENT;

    private static final int[] FPS_VALUES = {30, 60, 90, 120};
    private static final int[] CHAT_VALUES = {5, 7, 9, 12};
    private static final int[] FONT_VALUES = {24, 30, 36};
    private static final String[] PAGE_TITLES = {"Beranda", "Server", "Data GTA", "Pengaturan", "Kontrol", "Tentang"};
    private static final String[] PAGE_ICONS = {"\uD83C\uDFE0", "\uD83C\uDF10", "\uD83D\uDCE6", "\u2699\uFE0F", "\uD83C\uDFAE", "\u2139\uFE0F"};

    // ===================== STATE =====================
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private volatile boolean isDownloading = false;
    private SharedPreferences prefs;
    private SharedPreferences modPrefs;

    private FrameLayout pageContainer;
    private LinearLayout sidebar;
    private View scrim;
    private TextView topTitle;
    private boolean sidebarOpen = false;
    private final View[] pages = new View[PAGE_TITLES.length];
    private final TextView[] navItems = new TextView[PAGE_TITLES.length];

    // Remote config (banner, news, data, server)
    private final List<String[]> banners = new ArrayList<>();   // {badge, title, subtitle, accentHex}
    private final List<String[]> newsItems = new ArrayList<>(); // {tag, date, title, body}
    private final List<String[]> remoteServers = new ArrayList<>(); // {name, desc, status}
    private String liteDataUrl = "", fullDataUrl = "";
    private String liteName = "Data Lite", fullName = "Data Full";
    private String liteSize = "", fullSize = "";

    // Home
    private FrameLayout bannerHost;
    private LinearLayout bannerDots;
    private TextView bannerBadge, bannerTitle, bannerSubtitle;
    private int bannerIndex = 0;
    private float touchX0 = 0f;
    private final Runnable bannerTick = new Runnable() {
        @Override
        public void run() {
            showBanner(bannerIndex + 1);
            handler.postDelayed(this, 4500);
        }
    };
    private LinearLayout newsContainer;
    private TextView homeServerLine;
    private EditText nicknameInput, passwordInput;

    // Server
    private LinearLayout serverListContainer;

    // Data
    private TextView dataBadge, dataPathText, downloadStatusText, liteDescText, fullDescText;
    private TextView btnDownloadLite, btnDownloadFull;
    private EditText customUrlInput;
    private ProgressBar downloadProgressBar;

    // Settings
    private int selectedFps = 60, selectedChatLines = 7, selectedFont = 30;
    private final List<TextView> fpsChips = new ArrayList<>();
    private final List<TextView> chatChips = new ArrayList<>();
    private final List<TextView> fontChips = new ArrayList<>();
    private SwitchCompat swVoice, swFpsCounter, swFirstPerson, swCutout, swAndroidKb, swHpArmour;
    private SwitchCompat swOutfitGuns, swRadarRect, swPcMoney, swSkyBox, swSnow, swBooster;
    private SwitchCompat swMLoader, swCleo;

    // Controls
    private TextView peripheralStatusText;

    // About
    private TextView aboutSignatureText;

    // ===================== LIFECYCLE =====================
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            modPrefs = getSharedPreferences(MOD_PREFS, MODE_PRIVATE);
            initDefaultContent();

            if (!verifyOfficialSignature()) {
                markTampered(true);
                Toast.makeText(this, "PERINGATAN: APK telah dimodifikasi / bukan rilis resmi!", Toast.LENGTH_LONG).show();
                finish();
                return;
            }
            markTampered(false);

            buildUi();
            loadSavedSettings();
            showPage(0);
            requestStorageIfNeeded();
            onPermissionReady();
            loadCachedRemoteConfig();
            fetchRemoteConfig();
            refreshPeripheralsStatus();
        } catch (Exception e) {
            finish();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        handler.removeCallbacks(bannerTick);
        handler.postDelayed(bannerTick, 4500);
        if (dataBadge != null) updateDataStatusLabel(resolveGameDataDir(this));
        refreshPeripheralsStatus();
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacks(bannerTick);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        handler.removeCallbacksAndMessages(null);
    }

    @Override
    public void onBackPressed() {
        if (sidebarOpen) {
            closeSidebar();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus && Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            View decor = getWindow().getDecorView();
            decor.setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_FULLSCREEN);
        }
    }

    private void initDefaultContent() {
        banners.clear();
        banners.add(new String[]{"SELAMAT DATANG", "Lombok Holiday Roleplay",
                "Performa tinggi, Voice Chat jernih, dan kontrol lengkap untuk HP kamu.", "#38BDF8"});
        newsItems.clear();
        newsItems.add(new String[]{"INFO", "Terbaru", "Selamat datang di Launcher Lombok Holiday",
                "Unduh data game dari tab Data GTA, lalu masuk server dari tab Beranda."});
    }

    // ===================== UI BUILDER =====================
    private void buildUi() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(C_BG);

        LinearLayout main = vertical();

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(14), dp(14), dp(14), dp(8));

        TextView menuBtn = text("\u2261  MENU", 13, C_TEXT, true);
        menuBtn.setGravity(Gravity.CENTER);
        menuBtn.setPadding(dp(14), dp(10), dp(14), dp(10));
        menuBtn.setBackground(rounded(C_CARD, 14));
        menuBtn.setOnClickListener(v -> toggleSidebar());
        top.addView(menuBtn);

        topTitle = text("Beranda", 17, C_TEXT, true);
        topTitle.setPadding(dp(14), 0, 0, 0);
        top.addView(topTitle, new LinearLayout.LayoutParams(0, WP, 1f));

        TextView abi = text(abiLabel(), 11, C_A, true);
        abi.setPadding(dp(10), dp(6), dp(10), dp(6));
        abi.setBackground(rounded(0x3338BDF8, 10));
        top.addView(abi);
        main.addView(top, new LinearLayout.LayoutParams(MP, WP));

        pageContainer = new FrameLayout(this);
        main.addView(pageContainer, new LinearLayout.LayoutParams(MP, 0, 1f));
        root.addView(main, new FrameLayout.LayoutParams(MP, MP));

        pages[0] = buildHomePage();
        pages[1] = buildServerPage();
        pages[2] = buildDataPage();
        pages[3] = buildSettingsPage();
        pages[4] = buildControlsPage();
        pages[5] = buildAboutPage();
        for (View p : pages) {
            p.setVisibility(View.GONE);
            pageContainer.addView(p, new FrameLayout.LayoutParams(MP, MP));
        }

        scrim = new View(this);
        scrim.setBackgroundColor(0x99000000);
        scrim.setVisibility(View.GONE);
        scrim.setOnClickListener(v -> closeSidebar());
        root.addView(scrim, new FrameLayout.LayoutParams(MP, MP));

        sidebar = buildSidebar();
        FrameLayout.LayoutParams slp = new FrameLayout.LayoutParams(dp(276), MP);
        slp.gravity = Gravity.START;
        root.addView(sidebar, slp);
        sidebar.setTranslationX(-dp(300));

        setContentView(root);
    }

    private LinearLayout buildSidebar() {
        LinearLayout s = vertical();
        s.setPadding(dp(16), dp(44), dp(16), dp(20));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(C_PANEL);
        float r = dp(28);
        bg.setCornerRadii(new float[]{0, 0, r, r, r, r, 0, 0});
        s.setBackground(bg);
        s.setClickable(true);

        LinearLayout brand = new LinearLayout(this);
        brand.setOrientation(LinearLayout.HORIZONTAL);
        brand.setGravity(Gravity.CENTER_VERTICAL);
        TextView logo = text("LH", 16, Color.WHITE, true);
        logo.setGravity(Gravity.CENTER);
        logo.setBackground(gradient(C_A, C_B, 16));
        brand.addView(logo, new LinearLayout.LayoutParams(dp(50), dp(50)));
        LinearLayout bt = vertical();
        bt.setPadding(dp(12), 0, 0, 0);
        bt.addView(text("Lombok Holiday", 17, C_TEXT, true));
        bt.addView(text("Official Client v" + APP_VERSION, 12, C_MUTED, false));
        brand.addView(bt);
        s.addView(brand, new LinearLayout.LayoutParams(MP, WP));

        for (int i = 0; i < PAGE_TITLES.length; i++) {
            final int idx = i;
            TextView t = text(PAGE_ICONS[i] + "   " + PAGE_TITLES[i], 15, C_MUTED, false);
            t.setPadding(dp(16), dp(14), dp(16), dp(14));
            t.setClickable(true);
            t.setOnClickListener(v -> {
                showPage(idx);
                closeSidebar();
            });
            navItems[i] = t;
            add(s, t, 6);
        }

        View spacer = new View(this);
        s.addView(spacer, new LinearLayout.LayoutParams(MP, 0, 1f));

        LinearLayout foot = vertical();
        foot.setPadding(dp(14), dp(12), dp(14), dp(12));
        foot.setBackground(rounded(C_CARD, 16));
        foot.addView(text("Keamanan: AKTIF", 12, C_OK, true));
        foot.addView(text("Official Signed \u2022 R8 \u2022 Anti-Tamper", 11, C_MUTED, false));
        s.addView(foot, new LinearLayout.LayoutParams(MP, WP));
        return s;
    }

    private void toggleSidebar() {
        if (sidebarOpen) closeSidebar();
        else openSidebar();
    }

    private void openSidebar() {
        sidebarOpen = true;
        scrim.setVisibility(View.VISIBLE);
        scrim.setAlpha(0f);
        scrim.animate().alpha(1f).setDuration(200).start();
        sidebar.animate().translationX(0).setDuration(260).start();
    }

    private void closeSidebar() {
        sidebarOpen = false;
        scrim.animate().alpha(0f).setDuration(200).withEndAction(() -> scrim.setVisibility(View.GONE)).start();
        sidebar.animate().translationX(-dp(300)).setDuration(220).start();
    }

    private void showPage(int idx) {
        for (int i = 0; i < pages.length; i++) {
            pages[i].setVisibility(i == idx ? View.VISIBLE : View.GONE);
            boolean sel = i == idx;
            navItems[i].setBackground(sel ? gradient(0x4438BDF8, 0x44A78BFA, 16) : null);
            navItems[i].setTextColor(sel ? Color.WHITE : C_MUTED);
            navItems[i].setTypeface(null, sel ? Typeface.BOLD : Typeface.NORMAL);
        }
        topTitle.setText(PAGE_TITLES[idx]);
    }

    // ----- HOME -----
    private View buildHomePage() {
        LinearLayout c = page();

        bannerHost = new FrameLayout(this);
        bannerHost.setBackground(gradient(C_A, C_B, 24));
        bannerHost.setMinimumHeight(dp(180));
        LinearLayout bl = vertical();
        bl.setPadding(dp(18), dp(16), dp(18), dp(36));
        bannerBadge = text("", 11, Color.WHITE, true);
        bannerBadge.setPadding(dp(10), dp(5), dp(10), dp(5));
        bannerBadge.setBackground(rounded(0x33000000, 8));
        bl.addView(bannerBadge, new LinearLayout.LayoutParams(WP, WP));
        bannerTitle = text("", 20, Color.WHITE, true);
        add(bl, bannerTitle, 12);
        bannerSubtitle = text("", 13, 0xEEFFFFFF, false);
        add(bl, bannerSubtitle, 6);
        bannerHost.addView(bl, new FrameLayout.LayoutParams(MP, MP));

        bannerDots = new LinearLayout(this);
        bannerDots.setOrientation(LinearLayout.HORIZONTAL);
        bannerDots.setGravity(Gravity.CENTER_VERTICAL);
        FrameLayout.LayoutParams dlp = new FrameLayout.LayoutParams(WP, WP, Gravity.BOTTOM | Gravity.START);
        dlp.setMargins(dp(18), 0, 0, dp(14));
        bannerHost.addView(bannerDots, dlp);

        bannerHost.setOnTouchListener((v, ev) -> {
            switch (ev.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    touchX0 = ev.getX();
                    handler.removeCallbacks(bannerTick);
                    return true;
                case MotionEvent.ACTION_UP:
                    float dx = ev.getX() - touchX0;
                    if (dx < -dp(40)) showBanner(bannerIndex + 1);
                    else if (dx > dp(40)) showBanner(bannerIndex - 1);
                    handler.postDelayed(bannerTick, 4500);
                    return true;
                case MotionEvent.ACTION_CANCEL:
                    handler.postDelayed(bannerTick, 4500);
                    return true;
                default:
                    return true;
            }
        });
        c.addView(bannerHost, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout play = card();
        play.addView(text("Mulai Bermain", 18, C_TEXT, true));
        homeServerLine = text("", 12, C_MUTED, false);
        add(play, homeServerLine, 4);
        nicknameInput = input("Nickname_Roleplay", InputType.TYPE_CLASS_TEXT);
        add(play, nicknameInput, 14);
        passwordInput = input("Password server (opsional)",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        add(play, passwordInput, 8);
        add(play, accentButton("MASUK SERVER", v -> startGame()), 14);
        c.addView(play, new LinearLayout.LayoutParams(MP, WP));

        c.addView(text("Berita Terbaru", 18, C_TEXT, true), marginParams(4));
        newsContainer = vertical();
        c.addView(newsContainer, new LinearLayout.LayoutParams(MP, WP));
        return scroll(c);
    }

    // ----- SERVER -----
    private View buildServerPage() {
        LinearLayout c = page();

        LinearLayout active = card();
        active.addView(text("SERVER AKTIF", 11, C_A, true));
        active.addView(text(SERVER_TITLE, 19, C_TEXT, true));
        add(active, text("Koneksi dikunci ke server resmi dan dilindungi handshake keamanan.", 13, C_MUTED, false), 6);
        add(active, accentButton("MAIN DI SERVER INI", v -> startGame()), 14);
        c.addView(active, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout list = card();
        list.addView(text("Daftar Server", 18, C_TEXT, true));
        add(list, text("Tekan lama server tambahan untuk menghapus.", 12, C_MUTED, false), 4);
        serverListContainer = vertical();
        add(list, serverListContainer, 10);
        add(list, ghostButton("+ TAMBAH SERVER", v -> showAddServerDialog()), 12);
        c.addView(list, new LinearLayout.LayoutParams(MP, WP));
        return scroll(c);
    }

    // ----- DATA -----
    private View buildDataPage() {
        LinearLayout c = page();

        LinearLayout status = card();
        dataBadge = text("", 12, C_OK, true);
        dataBadge.setPadding(dp(10), dp(6), dp(10), dp(6));
        status.addView(dataBadge, new LinearLayout.LayoutParams(WP, WP));
        dataPathText = text("", 12, C_MUTED, false);
        add(status, dataPathText, 8);
        c.addView(status, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout lite = card();
        lite.addView(text("Data Lite", 17, C_TEXT, true));
        liteDescText = text("", 12, C_MUTED, false);
        add(lite, liteDescText, 4);
        btnDownloadLite = accentButton("DOWNLOAD DATA LITE", v -> startInAppDataDownload(liteDataUrl, liteName));
        add(lite, btnDownloadLite, 12);
        c.addView(lite, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout full = card();
        full.addView(text("Data Full", 17, C_TEXT, true));
        fullDescText = text("", 12, C_MUTED, false);
        add(full, fullDescText, 4);
        btnDownloadFull = accentButton("DOWNLOAD DATA FULL", v -> startInAppDataDownload(fullDataUrl, fullName));
        add(full, btnDownloadFull, 12);
        c.addView(full, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout custom = card();
        custom.addView(text("URL ZIP Custom", 17, C_TEXT, true));
        customUrlInput = input("https://.../data.zip", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        customUrlInput.setText(prefs.getString(KEY_CUSTOM_ZIP_URL, ""));
        add(custom, customUrlInput, 10);
        add(custom, ghostButton("DOWNLOAD DARI URL", v -> {
            String u = customUrlInput.getText().toString().trim();
            if (!u.startsWith("https://") && !u.startsWith("http://")) {
                Toast.makeText(this, "URL harus diawali https://", Toast.LENGTH_SHORT).show();
                return;
            }
            prefs.edit().putString(KEY_CUSTOM_ZIP_URL, u).apply();
            startInAppDataDownload(u, "Data Custom");
        }), 10);
        c.addView(custom, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout prog = card();
        downloadProgressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        downloadProgressBar.setMax(100);
        downloadProgressBar.setProgressTintList(ColorStateList.valueOf(C_A));
        downloadProgressBar.setProgressBackgroundTintList(ColorStateList.valueOf(C_INPUT));
        prog.addView(downloadProgressBar, new LinearLayout.LayoutParams(MP, dp(10)));
        downloadStatusText = text("Siap. Data diekstrak otomatis tanpa OBB.", 12, C_MUTED, false);
        add(prog, downloadStatusText, 8);
        c.addView(prog, new LinearLayout.LayoutParams(MP, WP));
        return scroll(c);
    }

    // ----- SETTINGS -----
    private View buildSettingsPage() {
        LinearLayout c = page();

        LinearLayout perf = card();
        perf.addView(text("Performa & Tampilan Chat", 18, C_TEXT, true));
        add(perf, text("Batas FPS", 12, C_MUTED, true), 12);
        add(perf, chipRow(new String[]{"30", "60", "90", "120"}, FPS_VALUES, selectedFps, fpsChips,
                v -> selectedFps = v), 6);
        add(perf, text("Baris Chat", 12, C_MUTED, true), 12);
        add(perf, chipRow(new String[]{"5", "7", "9", "12"}, CHAT_VALUES, selectedChatLines, chatChips,
                v -> selectedChatLines = v), 6);
        add(perf, text("Ukuran Font", 12, C_MUTED, true), 12);
        add(perf, chipRow(new String[]{"Kecil", "Sedang", "Besar"}, FONT_VALUES, selectedFont, fontChips,
                v -> selectedFont = v), 6);
        swBooster = toggle(perf, "Mode Booster", "Matikan efek berat (Salju, SkyBox, Outfit Guns) agar lebih ringan", false);
        c.addView(perf, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout fx = card();
        fx.addView(text("Tampilan & Kontrol", 18, C_TEXT, true));
        swVoice = toggle(fx, "Voice Chat", "Aktifkan voice chat in-game", false);
        swFpsCounter = toggle(fx, "FPS Counter", "Tampilkan angka FPS di layar", false);
        swFirstPerson = toggle(fx, "Kamera First-Person", "Mode bidik orang pertama", false);
        swCutout = toggle(fx, "Layar Penuh (Cutout)", "Pakai area poni / notch", true);
        swAndroidKb = toggle(fx, "Keyboard Android", "Gunakan keyboard sistem untuk chat", false);
        swHpArmour = toggle(fx, "Angka HP & Armour", "Tampilkan angka darah & armor", true);
        swOutfitGuns = toggle(fx, "Outfit Guns", "Senjata terlihat di badan", true);
        swRadarRect = toggle(fx, "Radar Kotak", "Bentuk radar persegi", false);
        swPcMoney = toggle(fx, "Format Uang Gaya PC", "Contoh: $00000000", true);
        swSkyBox = toggle(fx, "Efek Langit (SkyBox)", "Langit HD", true);
        swSnow = toggle(fx, "Efek Salju", "Partikel salju", false);
        c.addView(fx, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout mods = card();
        mods.addView(text("Mod Loader (Eksperimental)", 18, C_TEXT, true));
        add(mods, text("MonetLoader memuat mod Lua dari folder monetloader/. CLEO menyiapkan folder cleo/ — library CLEO belum disertakan di build ini.", 12, C_MUTED, false), 4);
        swMLoader = toggle(mods, "MonetLoader (Lua)", "Aktifkan loader mod .lua", false);
        swCleo = toggle(mods, "CLEO (folder cleo/)", "Siapkan folder CLEO untuk script .cs", false);
        c.addView(mods, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout actions = card();
        actions.addView(accentButton("SIMPAN PENGATURAN", v -> {
            hideKeyboard(this);
            String nick = sanitizeNick(nicknameInput.getText().toString());
            if (nick.isEmpty()) nick = sanitizeNick(DEFAULT_NICK);
            nicknameInput.setText(nick);
            boolean ok = saveAllSettingsToIni(nick);
            Toast.makeText(this, ok ? "Pengaturan tersimpan ke SAMP/settings.ini" : "Gagal menyimpan pengaturan", Toast.LENGTH_SHORT).show();
        }), new LinearLayout.LayoutParams(MP, WP));
        add(actions, ghostButton("RESET DEFAULT", v -> resetDefaults()), 10);
        add(actions, ghostButton("REPAIR DATA & FONT", v -> {
            File dir = new File(resolveGameDataDir(this));
            provisionSampDirectory(dir);
            new File(dir, "SAMP/.tampered").delete();
            Toast.makeText(this, "Repair selesai: font & struktur SAMP diperbaiki", Toast.LENGTH_SHORT).show();
            updateDataStatusLabel(resolveGameDataDir(this));
        }), 10);
        c.addView(actions, new LinearLayout.LayoutParams(MP, WP));
        return scroll(c);
    }

    // ----- CONTROLS -----
    private View buildControlsPage() {
        LinearLayout c = page();

        LinearLayout st = card();
        st.addView(text("Perangkat Terdeteksi", 18, C_TEXT, true));
        peripheralStatusText = text("", 13, C_TEXT, false);
        add(st, peripheralStatusText, 10);
        add(st, ghostButton("SCAN ULANG", v -> refreshPeripheralsStatus()), 12);
        c.addView(st, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout map = card();
        map.addView(text("Kontrol Keyboard & Mouse", 16, C_TEXT, true));
        add(map, text("WASD / Panah : gerak & setir\nSpace : lompat / rem tangan\nShift : lari\nF / Enter : masuk kendaraan\nT / F6 / / : buka chat\nESC : kembali / menu\nKlik kiri : tembak / pukul\nKlik kanan (tahan) : bidik\nScroll : ganti senjata", 13, C_MUTED, false), 8);
        c.addView(map, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout pad = card();
        pad.addView(text("Gamepad / Controller", 16, C_TEXT, true));
        add(pad, text("PS4, PS5, Xbox, dan joystick HID. Analog kiri = gerak, analog kanan = kamera, R2 = tembak, L2 = bidik, X/Kotak = lompat, Segitiga/Y = masuk kendaraan.", 13, C_MUTED, false), 8);
        c.addView(pad, new LinearLayout.LayoutParams(MP, WP));
        return scroll(c);
    }

    // ----- ABOUT -----
    private View buildAboutPage() {
        LinearLayout c = page();
        LinearLayout info = card();
        info.addView(text("Lombok Holiday", 20, C_TEXT, true));
        add(info, text("Versi " + APP_VERSION + "\nPackage: " + PACKAGE_ID + "\nABI aktif: " + abiLabel(), 13, C_MUTED, false), 8);
        aboutSignatureText = text("", 13, C_OK, true);
        add(info, aboutSignatureText, 12);
        c.addView(info, new LinearLayout.LayoutParams(MP, WP));

        LinearLayout fit = card();
        fit.addView(text("Fitur Launcher", 16, C_TEXT, true));
        add(fit, text("\u2022 Banner slider & berita otomatis (remote config)\n\u2022 Daftar server & tambah server\n\u2022 Download data Lite / Full + URL custom (tanpa OBB)\n\u2022 Pengaturan FPS, font, chat & booster\n\u2022 MonetLoader & CLEO (eksperimental)\n\u2022 Keyboard fisik, mouse OTG/BT, gamepad\n\u2022 Dukungan multi-touch hingga 4 jari", 13, C_MUTED, false), 8);
        c.addView(fit, new LinearLayout.LayoutParams(MP, WP));
        return scroll(c);
    }

    // ===================== UI HELPERS =====================
    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private LinearLayout vertical() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }

    private LinearLayout page() {
        LinearLayout l = vertical();
        l.setPadding(dp(16), dp(6), dp(16), dp(40));
        return l;
    }

    private ScrollView scroll(LinearLayout content) {
        ScrollView sv = new ScrollView(this);
        sv.setFillViewport(true);
        sv.setVerticalScrollBarEnabled(false);
        sv.addView(content, new FrameLayout.LayoutParams(MP, WP));
        return sv;
    }

    private LinearLayout card() {
        LinearLayout c = vertical();
        c.setPadding(dp(16), dp(16), dp(16), dp(16));
        c.setBackground(rounded(C_CARD, 22));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(MP, WP);
        lp.setMargins(0, 0, 0, dp(12));
        c.setLayoutParams(lp);
        return c;
    }

    private LinearLayout.LayoutParams marginParams(int topDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(MP, WP);
        lp.setMargins(0, dp(topDp), 0, dp(8));
        return lp;
    }

    private void add(LinearLayout parent, View v, int topDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(MP, WP);
        lp.setMargins(0, dp(topDp), 0, 0);
        parent.addView(v, lp);
    }

    private TextView text(String s, float sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(null, Typeface.BOLD);
        return t;
    }

    private EditText input(String hint, int inputType) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setHintTextColor(C_MUTED);
        e.setTextColor(C_TEXT);
        e.setTextSize(15);
        e.setSingleLine(true);
        e.setInputType(inputType);
        e.setBackground(rounded(C_INPUT, 14));
        e.setPadding(dp(14), dp(12), dp(14), dp(12));
        return e;
    }

    private TextView button(String label, GradientDrawable bg, View.OnClickListener l) {
        TextView b = new TextView(this);
        b.setText(label);
        b.setGravity(Gravity.CENTER);
        b.setTextColor(Color.WHITE);
        b.setTypeface(null, Typeface.BOLD);
        b.setTextSize(14);
        b.setPadding(dp(16), dp(14), dp(16), dp(14));
        b.setBackground(bg);
        b.setClickable(true);
        b.setFocusable(true);
        b.setOnClickListener(l);
        return b;
    }

    private TextView accentButton(String label, View.OnClickListener l) {
        return button(label, gradient(C_A, C_B, 16), l);
    }

    private TextView ghostButton(String label, View.OnClickListener l) {
        return button(label, rounded(C_INPUT, 16), l);
    }

    private GradientDrawable rounded(int color, int radiusDp) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(radiusDp));
        return g;
    }

    private GradientDrawable gradient(int a, int b, int radiusDp) {
        GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{a, b});
        g.setCornerRadius(dp(radiusDp));
        return g;
    }

    private SwitchCompat toggle(LinearLayout parent, String title, String desc, boolean checked) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(0, dp(8), 0, dp(8));
        LinearLayout col = vertical();
        col.addView(text(title, 14, C_TEXT, true));
        if (desc != null && !desc.isEmpty()) col.addView(text(desc, 12, C_MUTED, false));
        row.addView(col, new LinearLayout.LayoutParams(0, WP, 1f));
        SwitchCompat sw = new SwitchCompat(this);
        sw.setChecked(checked);
        ColorStateList states = new ColorStateList(
                new int[][]{{android.R.attr.state_checked}, {}},
                new int[]{C_A, 0xFF64748B});
        ColorStateList tracks = new ColorStateList(
                new int[][]{{android.R.attr.state_checked}, {}},
                new int[]{0x6638BDF8, 0xFF334155});
        sw.setThumbTintList(states);
        sw.setTrackTintList(tracks);
        row.addView(sw);
        parent.addView(row, new LinearLayout.LayoutParams(MP, WP));
        return sw;
    }

    private interface IntPick {
        void pick(int v);
    }

    private LinearLayout chipRow(String[] labels, final int[] values, int current,
                                 final List<TextView> outChips, final IntPick onPick) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        outChips.clear();
        for (int i = 0; i < labels.length; i++) {
            final int v = values[i];
            TextView c = new TextView(this);
            c.setText(labels[i]);
            c.setGravity(Gravity.CENTER);
            c.setTextSize(13);
            c.setTypeface(null, Typeface.BOLD);
            c.setPadding(0, dp(10), 0, dp(10));
            c.setClickable(true);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, WP, 1f);
            lp.setMargins(dp(3), 0, dp(3), 0);
            row.addView(c, lp);
            c.setOnClickListener(x -> {
                onPick.pick(v);
                restyleChips(outChips, v, values);
            });
            outChips.add(c);
        }
        restyleChips(outChips, current, values);
        return row;
    }

    private void restyleChips(List<TextView> chips, int current, int[] values) {
        for (int i = 0; i < chips.size() && i < values.length; i++) {
            boolean sel = values[i] == current;
            TextView c = chips.get(i);
            c.setBackground(sel ? gradient(C_A, C_B, 12) : rounded(C_INPUT, 12));
            c.setTextColor(sel ? Color.WHITE : C_MUTED);
        }
    }

    private int parseColor(String hex, int fallback) {
        try {
            return Color.parseColor(hex);
        } catch (Exception e) {
            return fallback;
        }
    }

    private String abiLabel() {
        String abi = (Build.SUPPORTED_ABIS != null && Build.SUPPORTED_ABIS.length > 0) ? Build.SUPPORTED_ABIS[0] : "arm64-v8a";
        return "ABI: " + abi.toUpperCase(Locale.ROOT);
    }

    // ===================== HOME: BANNER & NEWS =====================
    private void showBanner(int idx) {
        if (banners.isEmpty() || bannerHost == null) return;
        int n = banners.size();
        bannerIndex = ((idx % n) + n) % n;
        String[] b = banners.get(bannerIndex);
        bannerBadge.setText(b[0]);
        bannerTitle.setText(b[1]);
        bannerSubtitle.setText(b[2]);
        bannerHost.setBackground(gradient(parseColor(b[3], C_A), C_B, 24));
        bannerDots.removeAllViews();
        for (int i = 0; i < n; i++) {
            View d = new View(this);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(i == bannerIndex ? dp(18) : dp(6), dp(6));
            lp.setMargins(dp(3), 0, dp(3), 0);
            d.setBackground(rounded(i == bannerIndex ? Color.WHITE : 0x66FFFFFF, 3));
            bannerDots.addView(d, lp);
        }
    }

    private void renderNews() {
        if (newsContainer == null) return;
        newsContainer.removeAllViews();
        for (String[] n : newsItems) {
            LinearLayout card = card();
            TextView tag = text(n[0], 11, C_A, true);
            tag.setPadding(dp(8), dp(4), dp(8), dp(4));
            tag.setBackground(rounded(0x2238BDF8, 8));
            card.addView(tag, new LinearLayout.LayoutParams(WP, WP));
            add(card, text(n[2], 15, C_TEXT, true), 10);
            add(card, text(n[3], 13, C_MUTED, false), 6);
            add(card, text(n[1], 11, 0xFF64748B, false), 8);
            newsContainer.addView(card, new LinearLayout.LayoutParams(MP, WP));
        }
    }

    // ===================== SERVER LIST =====================
    private JSONArray loadCustomServers() {
        try {
            return new JSONArray(prefs.getString(KEY_CUSTOM_SERVERS, "[]"));
        } catch (Exception e) {
            return new JSONArray();
        }
    }

    private void renderServers() {
        if (serverListContainer == null) return;
        serverListContainer.removeAllViews();
        addServerRow(SERVER_TITLE, "Server resmi \u2022 Terkunci", "Aktif", true, -1);
        for (String[] s : remoteServers) {
            addServerRow(s[0], s[1], s[2], false, -1);
        }
        JSONArray custom = loadCustomServers();
        for (int i = 0; i < custom.length(); i++) {
            JSONObject o = custom.optJSONObject(i);
            if (o == null) continue;
            String name = o.optString("name", "Server");
            String addr = o.optString("host", "") + ":" + o.optInt("port", 7777);
            addServerRow(name, addr, MULTI_SERVER_ENABLED ? "Tambahan" : "Nonaktif", false, i);
        }
    }

    private void addServerRow(String name, String sub, String badge, boolean official, final int customIndex) {
        LinearLayout row = vertical();
        row.setPadding(dp(14), dp(12), dp(14), dp(12));
        row.setBackground(rounded(official ? 0x2238BDF8 : C_INPUT, 16));
        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.addView(text(name, 15, C_TEXT, true), new LinearLayout.LayoutParams(0, WP, 1f));
        TextView b = text(badge, 11, official ? C_OK : C_MUTED, true);
        top.addView(b);
        row.addView(top, new LinearLayout.LayoutParams(MP, WP));
        add(row, text(sub, 12, C_MUTED, false), 4);
        row.setClickable(true);
        row.setOnClickListener(v -> {
            if (official) {
                Toast.makeText(this, "Server resmi dipilih. Tekan MAIN DI SERVER INI.", Toast.LENGTH_SHORT).show();
            } else if (!MULTI_SERVER_ENABLED) {
                Toast.makeText(this, "Koneksi ke server lain belum diaktifkan di build ini.", Toast.LENGTH_LONG).show();
            } else {
                Toast.makeText(this, "Server dipilih: " + name, Toast.LENGTH_SHORT).show();
            }
        });
        if (customIndex >= 0) {
            row.setOnLongClickListener(v -> {
                new AlertDialog.Builder(this)
                        .setTitle("Hapus server?")
                        .setMessage(name)
                        .setPositiveButton("Hapus", (d, w) -> {
                            JSONArray arr = loadCustomServers();
                            JSONArray next = new JSONArray();
                            for (int i = 0; i < arr.length(); i++) {
                                if (i != customIndex) next.put(arr.optJSONObject(i));
                            }
                            prefs.edit().putString(KEY_CUSTOM_SERVERS, next.toString()).apply();
                            renderServers();
                        })
                        .setNegativeButton("Batal", null)
                        .show();
                return true;
            });
        }
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(MP, WP);
        lp.setMargins(0, dp(8), 0, 0);
        serverListContainer.addView(row, lp);
    }

    private void showAddServerDialog() {
        LinearLayout form = vertical();
        form.setPadding(dp(20), dp(10), dp(20), 0);
        EditText name = input("Nama server", InputType.TYPE_CLASS_TEXT);
        EditText host = input("IP / domain server", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        EditText port = input("Port (default 7777)", InputType.TYPE_CLASS_NUMBER);
        port.setText("7777");
        add(form, name, 0);
        add(form, host, 10);
        add(form, port, 10);
        new AlertDialog.Builder(this)
                .setTitle("Tambah Server")
                .setView(form)
                .setPositiveButton("Simpan", (d, w) -> {
                    String n = name.getText().toString().trim();
                    String h = host.getText().toString().trim();
                    int p;
                    try {
                        p = Integer.parseInt(port.getText().toString().trim());
                    } catch (Exception e) {
                        p = -1;
                    }
                    if (n.isEmpty() || !h.matches("^[A-Za-z0-9.\\-]+$") || p < 1 || p > 65535) {
                        Toast.makeText(this, "Isi nama, host (huruf/angka/titik), dan port 1-65535", Toast.LENGTH_LONG).show();
                        return;
                    }
                    try {
                        JSONArray arr = loadCustomServers();
                        JSONObject o = new JSONObject();
                        o.put("name", n);
                        o.put("host", h);
                        o.put("port", p);
                        arr.put(o);
                        prefs.edit().putString(KEY_CUSTOM_SERVERS, arr.toString()).apply();
                        renderServers();
                        Toast.makeText(this, "Server ditambahkan", Toast.LENGTH_SHORT).show();
                    } catch (Exception e) {
                        Toast.makeText(this, "Gagal menyimpan server", Toast.LENGTH_SHORT).show();
                    }
                })
                .setNegativeButton("Batal", null)
                .show();
    }

    // ===================== REMOTE CONFIG =====================
    private void loadCachedRemoteConfig() {
        String cached = prefs.getString(KEY_REMOTE_CACHE, "");
        if (cached != null && !cached.isEmpty()) applyRemoteConfig(cached);
    }

    private void fetchRemoteConfig() {
        if (REMOTE_CONFIG_URL == null || REMOTE_CONFIG_URL.isEmpty()) return;
        executor.execute(() -> {
            String body = httpGet(REMOTE_CONFIG_URL, 8000);
            if (body == null) return;
            prefs.edit().putString(KEY_REMOTE_CACHE, body).apply();
            handler.post(() -> applyRemoteConfig(body));
        });
    }

    private void applyRemoteConfig(String body) {
        try {
            JSONObject o = new JSONObject(body);
            JSONArray b = o.optJSONArray("banners");
            if (b != null && b.length() > 0) {
                banners.clear();
                for (int i = 0; i < b.length(); i++) {
                    JSONObject x = b.optJSONObject(i);
                    if (x == null) continue;
                    banners.add(new String[]{x.optString("badge", "INFO"), x.optString("title", ""),
                            x.optString("subtitle", ""), x.optString("accent", "#38BDF8")});
                }
            }
            JSONArray n = o.optJSONArray("news");
            if (n != null && n.length() > 0) {
                newsItems.clear();
                for (int i = 0; i < n.length(); i++) {
                    JSONObject x = n.optJSONObject(i);
                    if (x == null) continue;
                    newsItems.add(new String[]{x.optString("tag", "INFO"), x.optString("date", ""),
                            x.optString("title", ""), x.optString("body", "")});
                }
            }
            JSONArray s = o.optJSONArray("servers");
            if (s != null) {
                remoteServers.clear();
                for (int i = 0; i < s.length(); i++) {
                    JSONObject x = s.optJSONObject(i);
                    if (x == null) continue;
                    remoteServers.add(new String[]{x.optString("name", "Server"), x.optString("description", ""),
                            x.optString("status", "Info")});
                }
            }
            JSONObject lite = o.optJSONObject("data_lite");
            if (lite != null) {
                liteDataUrl = lite.optString("url", "");
                liteName = lite.optString("name", "Data Lite");
                liteSize = lite.optString("size_mb", "");
            }
            JSONObject full = o.optJSONObject("data_full");
            if (full != null) {
                fullDataUrl = full.optString("url", "");
                fullName = full.optString("name", "Data Full");
                fullSize = full.optString("size_mb", "");
            }
            if (bannerHost != null) showBanner(0);
            renderNews();
            renderServers();
            updateDataButtons();
        } catch (Exception ignored) {
        }
    }

    private String httpGet(String u, int timeoutMs) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(u).openConnection();
            conn.setConnectTimeout(timeoutMs);
            conn.setReadTimeout(timeoutMs);
            conn.setRequestProperty("Cache-Control", "no-cache");
            if (conn.getResponseCode() != HttpURLConnection.HTTP_OK) return null;
            try (InputStream in = new BufferedInputStream(conn.getInputStream());
                 ByteArrayOutputStream bo = new ByteArrayOutputStream()) {
                byte[] buf = new byte[4096];
                int n;
                while ((n = in.read(buf)) != -1) bo.write(buf, 0, n);
                return bo.toString("UTF-8");
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private void updateDataButtons() {
        if (btnDownloadLite == null) return;
        boolean hasLite = liteDataUrl != null && !liteDataUrl.isEmpty();
        boolean hasFull = fullDataUrl != null && !fullDataUrl.isEmpty();
        btnDownloadLite.setAlpha(hasLite ? 1f : 0.45f);
        btnDownloadFull.setAlpha(hasFull ? 1f : 0.45f);
        liteDescText.setText(hasLite
                ? liteName + (liteSize.isEmpty() ? "" : " \u2022 ~" + liteSize + " MB") + " \u2022 Tanpa OBB"
                : "Link Data Lite belum dikonfigurasi di data-config.json");
        fullDescText.setText(hasFull
                ? fullName + (fullSize.isEmpty() ? "" : " \u2022 ~" + fullSize + " MB") + " \u2022 Tanpa OBB"
                : "Link Data Full belum dikonfigurasi di data-config.json");
    }

    // ===================== IN-APP DATA DOWNLOADER =====================
    private File getPreferredWritableDataDir() {
        File f = new File(resolveGameDataDir(this));
        if (!f.exists()) f.mkdirs();
        if (!f.canWrite()) {
            File ext = getExternalFilesDir(null);
            if (ext != null) {
                ext.mkdirs();
                return ext;
            }
        }
        return f;
    }

    private void startInAppDataDownload(final String zipUrl, final String label) {
        if (zipUrl == null || zipUrl.isEmpty()) {
            Toast.makeText(this, label + " belum dikonfigurasi. Gunakan URL ZIP Custom.", Toast.LENGTH_LONG).show();
            return;
        }
        if (isDownloading) {
            Toast.makeText(this, "Unduhan sedang berjalan, harap tunggu...", Toast.LENGTH_SHORT).show();
            return;
        }
        isDownloading = true;
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
                if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL && existingBytes > 0) {
                    tempZip.delete();
                    existingBytes = 0;
                    conn.disconnect();
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setInstanceFollowRedirects(true);
                    code = conn.getResponseCode();
                }
                if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                    final int errCode = code;
                    handler.post(() -> {
                        isDownloading = false;
                        downloadStatusText.setText("Link unduhan gagal (HTTP " + errCode + "). Coba URL ZIP Custom.");
                    });
                    return;
                }

                long contentLength = conn.getContentLengthLong();
                long totalBytes = (code == HttpURLConnection.HTTP_PARTIAL && contentLength > 0)
                        ? (existingBytes + contentLength) : contentLength;
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
                                        "Mengunduh %s: %.1f / %.1f MB (%d%%) \u2022 %.2f MB/s",
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
                    downloadStatusText.setText("Mengekstrak " + label + " ke folder data...");
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
                    downloadStatusText.setText("Selesai! " + label + " terpasang di: " + active);
                    Toast.makeText(MainActivity.this, label + " selesai diunduh & diekstrak!", Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                final String msg = e.getMessage();
                handler.post(() -> {
                    isDownloading = false;
                    downloadProgressBar.setIndeterminate(false);
                    downloadStatusText.setText("Unduhan terhenti: " + msg + " (klik lagi untuk lanjut otomatis)");
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

                // Normalisasi bila ZIP punya folder pembungkus (misal "com.rockstargames.gtasa/files/texdb/...")
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

    // ===================== STORAGE & DATA DIR =====================
    private void requestStorageIfNeeded() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                if (!Environment.isExternalStorageManager()) {
                    new AlertDialog.Builder(this)
                            .setTitle("Izin Akses File")
                            .setMessage("Lombok Holiday perlu izin akses file untuk menyimpan data game di /Android/data.")
                            .setPositiveButton("Buka Izin", (d, w) -> {
                                try {
                                    Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                            Uri.parse("package:" + getPackageName()));
                                    startActivity(intent);
                                } catch (Exception e) {
                                    startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
                                }
                            })
                            .setNegativeButton("Nanti", null)
                            .show();
                }
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                requestPermissions(new String[]{
                        android.Manifest.permission.READ_EXTERNAL_STORAGE,
                        android.Manifest.permission.WRITE_EXTERNAL_STORAGE}, 1001);
            }
        } catch (Exception ignored) {
        }
    }

    private void onPermissionReady() {
        String dir = resolveGameDataDir(this);
        provisionSampDirectory(new File(dir));
        updateDataStatusLabel(dir);
        updateDataButtons();
    }

    private void updateDataStatusLabel(String dir) {
        if (dataBadge == null || dataPathText == null) return;
        File d = new File(dir);
        if (hasGtaCache(d)) {
            dataBadge.setText("DATA SIAP \u2022 TANPA OBB");
            dataBadge.setTextColor(C_OK);
            dataBadge.setBackground(rounded(0x3310B981, 10));
            dataPathText.setText("Lokasi data: " + dir);
        } else {
            dataBadge.setText("DATA BELUM ADA");
            dataBadge.setTextColor(C_WARN);
            dataBadge.setBackground(rounded(0x33F59E0B, 10));
            dataPathText.setText("Unduh Data Lite / Full di bawah, atau taruh folder data GTA di /sdcard/GTA/");
        }
        if (homeServerLine != null) {
            homeServerLine.setText("Server: " + SERVER_TITLE + "  \u2022  " + (hasGtaCache(d) ? "Data siap" : "Data belum ada"));
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
        } catch (Exception ignored) {
        }
        candidates.add("/storage/emulated/0/Android/data/" + PACKAGE_ID + "/files/");
        candidates.add("/storage/emulated/0/GTA/");
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
        } catch (Exception ignored) {
        }
        return "/storage/emulated/0/GTA/";
    }

    private void provisionSampDirectory(File baseDir) {
        try {
            File fontsDir = new File(new File(baseDir, "SAMP"), "fonts");
            if (!fontsDir.exists()) fontsDir.mkdirs();
            String[] fontTargets = new String[]{"arial.ttf", "Arial.ttf", "arial_bold.ttf"};
            for (String ft : fontTargets) {
                File outFont = new File(fontsDir, ft);
                if (!outFont.exists() || outFont.length() < 1024) {
                    copyBundledFont(outFont);
                }
            }
        } catch (Exception ignored) {
        }
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
            } catch (Exception ignored) {
            }
        }
    }

    // ===================== SECURITY =====================
    private boolean verifyOfficialSignature() {
        if (EXPECTED_CERT_SHA256 == null || EXPECTED_CERT_SHA256.isEmpty()) {
            return true;
        }
        try {
            PackageInfo pkgInfo = getPackageManager().getPackageInfo(getPackageName(),
                    PackageManager.GET_SIGNING_CERTIFICATES);
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
        } catch (Exception ignored) {
        }
    }

    private String sanitizeNick(String raw) {
        if (raw == null) return "";
        String s = raw.trim().replace(' ', '_');
        s = s.replaceAll("[^A-Za-z0-9_\\[\\]$=()@.]", "");
        if (s.length() > 20) s = s.substring(0, 20);
        return s;
    }

    // ===================== SETTINGS =====================
    private void loadSavedSettings() {
        String savedNick = prefs.getString(KEY_NICKNAME, "");
        String savedPass = prefs.getString(KEY_PASSWORD, "");
        if (savedNick.isEmpty()) {
            File ini = new File(resolveGameDataDir(this), "SAMP/settings.ini");
            if (ini.exists()) {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(new FileInputStream(ini), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        String trimmed = line.trim();
                        if (trimmed.toLowerCase(Locale.ROOT).startsWith("name=")) {
                            String val = trimmed.substring(5).trim();
                            if (!val.isEmpty() && !val.startsWith("__android_") && !val.equals("Nick_Name")) {
                                savedNick = val;
                                break;
                            }
                        }
                    }
                } catch (Exception ignored) {
                }
            }
        }
        if (nicknameInput != null && !savedNick.isEmpty() && !savedNick.equals(DEFAULT_NICK)) {
            nicknameInput.setText(savedNick);
        }
        if (passwordInput != null && !savedPass.isEmpty()) {
            passwordInput.setText(savedPass);
        }

        selectedFont = prefs.getInt(KEY_FONT_SIZE, 30);
        selectedFps = prefs.getInt(KEY_FPS, 60);
        selectedChatLines = prefs.getInt(KEY_CHAT_LINES, 7);
        restyleChips(fpsChips, selectedFps, FPS_VALUES);
        restyleChips(chatChips, selectedChatLines, CHAT_VALUES);
        restyleChips(fontChips, selectedFont, FONT_VALUES);

        if (swVoice != null) {
            swVoice.setChecked(prefs.getBoolean("t_voice", false));
            swFpsCounter.setChecked(prefs.getBoolean("t_fps", false));
            swFirstPerson.setChecked(prefs.getBoolean("t_fpp", false));
            swCutout.setChecked(prefs.getBoolean("t_cutout", true));
            swAndroidKb.setChecked(prefs.getBoolean("t_akb", false));
            swHpArmour.setChecked(prefs.getBoolean("t_hp", true));
            swOutfitGuns.setChecked(prefs.getBoolean("t_outfit", true));
            swRadarRect.setChecked(prefs.getBoolean("t_radar", false));
            swPcMoney.setChecked(prefs.getBoolean("t_pcmoney", true));
            swSkyBox.setChecked(prefs.getBoolean("t_skybox", true));
            swSnow.setChecked(prefs.getBoolean("t_snow", false));
            swBooster.setChecked(prefs.getBoolean("t_booster", false));
            swMLoader.setChecked(modPrefs.getBoolean(KEY_MLOADER, false));
            swCleo.setChecked(modPrefs.getBoolean(KEY_CLEO, false));
        }
    }

    private void resetDefaults() {
        selectedFps = 60;
        selectedChatLines = 7;
        selectedFont = 30;
        restyleChips(fpsChips, selectedFps, FPS_VALUES);
        restyleChips(chatChips, selectedChatLines, CHAT_VALUES);
        restyleChips(fontChips, selectedFont, FONT_VALUES);
        swVoice.setChecked(false);
        swFpsCounter.setChecked(false);
        swFirstPerson.setChecked(false);
        swCutout.setChecked(true);
        swAndroidKb.setChecked(false);
        swHpArmour.setChecked(true);
        swOutfitGuns.setChecked(true);
        swRadarRect.setChecked(false);
        swPcMoney.setChecked(true);
        swSkyBox.setChecked(true);
        swSnow.setChecked(false);
        swBooster.setChecked(false);
        swMLoader.setChecked(false);
        swCleo.setChecked(false);
        Toast.makeText(this, "Pengaturan dikembalikan ke default. Tekan SIMPAN untuk menerapkan.", Toast.LENGTH_SHORT).show();
    }

    private static String flag(boolean v) {
        return v ? "true" : "false";
    }

    private boolean saveAllSettingsToIni(String nick) {
        String activeDir = resolveGameDataDir(this);
        String pass = (passwordInput != null) ? passwordInput.getText().toString().trim() : "";

        boolean booster = swBooster.isChecked();
        boolean snow = swSnow.isChecked() && !booster;
        boolean skybox = swSkyBox.isChecked() && !booster;
        boolean outfit = swOutfitGuns.isChecked() && !booster;
        boolean mload = swMLoader.isChecked();
        boolean cleo = swCleo.isChecked();

        prefs.edit()
                .putString(KEY_NICKNAME, nick)
                .putString(KEY_PASSWORD, pass)
                .putInt(KEY_FPS, selectedFps)
                .putInt(KEY_CHAT_LINES, selectedChatLines)
                .putInt(KEY_FONT_SIZE, selectedFont)
                .putBoolean("t_voice", swVoice.isChecked())
                .putBoolean("t_fps", swFpsCounter.isChecked())
                .putBoolean("t_fpp", swFirstPerson.isChecked())
                .putBoolean("t_cutout", swCutout.isChecked())
                .putBoolean("t_akb", swAndroidKb.isChecked())
                .putBoolean("t_hp", swHpArmour.isChecked())
                .putBoolean("t_outfit", swOutfitGuns.isChecked())
                .putBoolean("t_radar", swRadarRect.isChecked())
                .putBoolean("t_pcmoney", swPcMoney.isChecked())
                .putBoolean("t_skybox", swSkyBox.isChecked())
                .putBoolean("t_snow", swSnow.isChecked())
                .putBoolean("t_booster", booster)
                .apply();
        modPrefs.edit().putBoolean(KEY_MLOADER, mload).putBoolean(KEY_CLEO, cleo).apply();

        List<String> targetDirs = new ArrayList<>();
        targetDirs.add(activeDir);
        try {
            File ext = getExternalFilesDir(null);
            if (ext != null) {
                String p = ext.getAbsolutePath() + "/";
                if (!targetDirs.contains(p)) targetDirs.add(p);
            }
        } catch (Exception ignored) {
        }
        if (!targetDirs.contains("/storage/emulated/0/GTA/")) {
            targetDirs.add("/storage/emulated/0/GTA/");
        }

        String iniContent = "[client]\n"
                + "name=" + nick + "\n"
                + "port=" + LOCKED_PORT + "\n"
                + "password=" + pass + "\n"
                + "version=0.3.7\n"
                + "autoaim=false\n\n"
                + "[debug]\n"
                + "debug=false\n"
                + "online=true\n\n"
                + "[gui]\n"
                + "Font=arial.ttf\n"
                + "FontSize=" + selectedFont + ".0\n"
                + "FontOutline=2\n"
                + "ChatPosX=325.0\n"
                + "ChatPosY=25.0\n"
                + "ChatSizeX=1150.0\n"
                + "ChatSizeY=220.0\n"
                + "ChatMaxMessages=" + selectedChatLines + "\n"
                + "FPSLimit=" + selectedFps + "\n"
                + "VoiceChatEnable=" + flag(swVoice.isChecked()) + "\n"
                + "fps=" + flag(swFpsCounter.isChecked()) + "\n"
                + "firstperson=" + flag(swFirstPerson.isChecked()) + "\n"
                + "cutout=" + flag(swCutout.isChecked()) + "\n"
                + "androidkeyboard=" + flag(swAndroidKb.isChecked()) + "\n"
                + "hparmourtext=" + flag(swHpArmour.isChecked()) + "\n"
                + "outfitguns=" + flag(outfit) + "\n"
                + "radarrect=" + flag(swRadarRect.isChecked()) + "\n"
                + "pcmoney=" + flag(swPcMoney.isChecked()) + "\n"
                + "skybox=" + flag(skybox) + "\n"
                + "snow=" + flag(snow) + "\n";

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
            } catch (Exception ignored) {
            }
        }
        // Folder mod: dibuat hanya bila fitur diaktifkan
        if (mload || cleo) {
            File base = new File(activeDir);
            if (mload) new File(base, "monetloader").mkdirs();
            if (cleo) new File(base, "cleo").mkdirs();
        }
        return ok;
    }

    // ===================== GAME LAUNCH =====================
    private void startGame() {
        String dataDir = resolveGameDataDir(this);
        if (!hasGtaCache(new File(dataDir))) {
            Toast.makeText(this, "Data GTA belum terpasang. Unduh Data Lite/Full di tab Data GTA dulu.", Toast.LENGTH_LONG).show();
            return;
        }
        String nick = sanitizeNick(nicknameInput.getText().toString());
        if (nick.isEmpty()) nick = sanitizeNick(DEFAULT_NICK);
        if (nick.length() < 3) {
            Toast.makeText(this, "Nickname minimal 3 karakter (contoh: Nama_Roleplay)", Toast.LENGTH_LONG).show();
            return;
        }
        nicknameInput.setText(nick);
        hideKeyboard(this);
        saveAllSettingsToIni(nick);

        Intent gameIntent = new Intent(MainActivity.this, SAMP.class);
        gameIntent.putExtra("player_name", nick);
        gameIntent.putExtra("game_data_dir", dataDir);
        startActivity(gameIntent);
    }

    public static void hideKeyboard(Activity activity) {
        try {
            InputMethodManager inputManager = (InputMethodManager) activity.getSystemService(Context.INPUT_METHOD_SERVICE);
            View focused = activity.getCurrentFocus();
            if (focused != null && inputManager != null) {
                inputManager.hideSoftInputFromWindow(focused.getWindowToken(), InputMethodManager.HIDE_NOT_ALWAYS);
            }
        } catch (Exception ignored) {
        }
    }

    // ===================== PERIPHERALS =====================
    private void refreshPeripheralsStatus() {
        if (peripheralStatusText == null) return;
        StringBuilder sb = new StringBuilder();
        for (int id : InputDevice.getDeviceIds()) {
            InputDevice d = InputDevice.getDevice(id);
            if (d == null || d.isVirtual()) continue;
            int src = d.getSources();
            String type = null;
            if ((src & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD
                    || (src & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK) {
                type = "Gamepad";
            } else if ((src & InputDevice.SOURCE_MOUSE) == InputDevice.SOURCE_MOUSE) {
                type = "Mouse";
            } else if (d.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC) {
                type = "Keyboard";
            }
            if (type != null) {
                sb.append("\u2022 ").append(type).append(": ").append(d.getName()).append("\n");
            }
        }
        if (sb.length() == 0) {
            sb.append("Belum ada perangkat eksternal. Sambungkan keyboard/mouse OTG/Bluetooth atau gamepad.");
        }
        peripheralStatusText.setText(sb.toString().trim());
        if (aboutSignatureText != null) {
            aboutSignatureText.setText("Signature resmi: TERVERIFIKASI");
        }
    }
}
