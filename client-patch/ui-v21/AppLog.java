package com.samp.mobile.launcher;

import android.content.Intent;

import android.app.PendingIntent;

import android.app.AlarmManager;

import android.content.Context;
import android.os.Build;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.io.BufferedWriter;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.io.StringWriter;
import java.io.Writer;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

/**
 * Log launcher yang disimpan ke:
 *   /storage/emulated/0/Android/media/<package>/log/
 * (fallback: <external files>/log bila media dir tidak tersedia).
 *
 * Setiap sesi membuat satu file launcher_<waktu>.log. Sesi yang tidak
 * ditutup dengan benar (crash / force close) akan ditandai di sesi berikutnya.
 * Log game native (FLog) ditulis ke samp_log.txt di folder yang sama.
 */
public final class AppLog {

    private static final String END_MARKER = "=== SESSION END (normal) ===";
    private static final int KEEP_FILES = 20;
    private static final SimpleDateFormat TS = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT);
    private static final SimpleDateFormat LINE_TS = new SimpleDateFormat("HH:mm:ss.SSS", Locale.ROOT);

    private static File logDir;
    private static Context appCtx;
    private static boolean lastSessionCrashed = false;
    private static File currentFile;
    private static PrintWriter writer;
    private static boolean installed = false;

    static {
        TS.setTimeZone(TimeZone.getDefault());
        LINE_TS.setTimeZone(TimeZone.getDefault());
    }

    private AppLog() {}

    /** Folder log: Android/media/<pkg>/log (atau fallback). */
    public static File resolveDir(Context ctx) {
        File base = null;
        try {
            File[] media = ctx.getExternalMediaDirs();
            if (media != null && media.length > 0) base = media[0];
        } catch (Exception ignored) {}
        if (base == null) {
            try {
                base = ctx.getExternalFilesDir(null);
            } catch (Exception ignored) {}
        }
        if (base == null) base = new File("/storage/emulated/0/Android/media/" + ctx.getPackageName());
        return new File(base, "log");
    }

    /** Path folder log yang juga dipakai native (samp_log.txt). */
    public static synchronized String logDirPath() {
        return logDir == null ? "" : logDir.getAbsolutePath();
    }

    /** Buka sesi log hanya bila belum ada (dipakai service yang bisa hidup sendiri). */
    public static synchronized void ensure(Context ctx) {
        if (writer == null) init(ctx);
    }

    public static synchronized void init(Context ctx) {
        try {
            appCtx = ctx.getApplicationContext();
            logDir = resolveDir(ctx);
            if (!logDir.exists()) logDir.mkdirs();

            // Sesi sebelumnya: apakah berakhir normal?
            List<File> old = listLogFiles();
            if (!old.isEmpty()) {
                File last = old.get(old.size() - 1);
                if (!fileEndsWithMarker(last)) {
                    rawAppend(last, "\n=== SESSION TIDAK BERAKHIR NORMAL (crash / force close / app dihentikan sistem) ===\n");
                    lastSessionCrashed = true;
                }
            }

            currentFile = new File(logDir, "launcher_" + TS.format(new Date()) + ".log");
            writer = new PrintWriter(new BufferedWriter(new OutputStreamWriter(new FileOutputStream(currentFile, true), "UTF-8")), true);
            writeLine("I", "APP", "=== SESSION START ===");
            writeLine("I", "APP", "package=" + ctx.getPackageName()
                    + " | device=" + Build.MANUFACTURER + " " + Build.MODEL
                    + " | android=" + Build.VERSION.RELEASE + " (sdk " + Build.VERSION.SDK_INT + ")"
                    + " | abi=" + Arrays.toString(Build.SUPPORTED_ABIS)
                    + " | hardware=" + Build.HARDWARE);
            writeLine("I", "APP", "logDir=" + logDir.getAbsolutePath());
            trimOld();
            installCrashHandler();
        } catch (Exception e) {
            // Logging tidak boleh menggagalkan app.
        }
    }

    private static void installCrashHandler() {
        if (installed) return;
        installed = true;
        final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((t, ex) -> {
            try {
                e("CRASH", "Uncaught exception di thread " + t.getName(), ex);
                writeLine("E", "CRASH", "=== CRASH: sesi berakhir karena exception ===");
                closeQuietly();
                scheduleRelaunch();
            } catch (Exception ignored) {}
            // Anti force close: tanpa dialog 'app has stopped'. Launcher dibuka ulang oleh alarm di atas.
            android.os.Process.killProcess(android.os.Process.myPid());
            System.exit(10);
        });
    }

    private static void scheduleRelaunch() {
        if (appCtx == null) return;
        try {
            Intent i = appCtx.getPackageManager().getLaunchIntentForPackage(appCtx.getPackageName());
            if (i == null) return;
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            PendingIntent pi = PendingIntent.getActivity(appCtx, 4242, i,
                    PendingIntent.FLAG_CANCEL_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            AlarmManager am = (AlarmManager) appCtx.getSystemService(Context.ALARM_SERVICE);
            if (am != null) am.set(AlarmManager.RTC, System.currentTimeMillis() + 1500L, pi);
        } catch (Exception ignored) {}
    }

    /** true sekali jika sesi sebelumnya tidak berakhir normal (crash / FC). */
    public static synchronized boolean takeCrashNotice() {
        boolean v = lastSessionCrashed;
        lastSessionCrashed = false;
        return v;
    }


    public static synchronized void i(String tag, String msg) { writeLine("I", tag, msg); }
    public static synchronized void w(String tag, String msg) { writeLine("W", tag, msg); }
    public static synchronized void e(String tag, String msg) { writeLine("E", tag, msg); }

    public static synchronized void e(String tag, String msg, Throwable t) {
        writeLine("E", tag, msg);
        if (t != null) {
            StringWriter sw = new StringWriter();
            t.printStackTrace(new PrintWriter(sw));
            writeRaw(sw.toString());
        }
    }

    /** Dipanggil saat app benar-benar ditutup (onDestroy dengan isFinishing). */
    public static synchronized void endSession() {
        if (writer == null) return;
        writeLine("I", "APP", END_MARKER);
        closeQuietly();
    }

    public static synchronized void closeQuietly() {
        try {
            if (writer != null) writer.flush();
        } catch (Exception ignored) {}
    }

    private static void writeLine(String level, String tag, String msg) {
        String line = LINE_TS.format(new Date()) + " " + level + "/" + tag + ": " + msg;
        if (writer != null) {
            writer.println(line);
            writer.flush();
        }
    }

    private static void writeRaw(String text) {
        if (writer != null) {
            writer.print(text);
            writer.flush();
        }
    }

    private static List<File> listLogFiles() {
        List<File> out = new ArrayList<>();
        if (logDir == null) return out;
        File[] files = logDir.listFiles((d, n) -> n.startsWith("launcher_") && n.endsWith(".log"));
        if (files == null) return out;
        Arrays.sort(files);
        out.addAll(Arrays.asList(files));
        return out;
    }

    private static void trimOld() {
        List<File> files = listLogFiles();
        while (files.size() > KEEP_FILES) {
            File f = files.remove(0);
            if (currentFile != null && f.equals(currentFile)) break;
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
    }

    private static boolean fileEndsWithMarker(File f) {
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String line;
            boolean found = false;
            while ((line = br.readLine()) != null) {
                if (line.contains(END_MARKER)) found = true;
            }
            return found;
        } catch (IOException e) {
            return true; // tidak bisa dibaca: jangan tandai salah
        }
    }

    private static void rawAppend(File f, String text) {
        try (FileOutputStream fos = new FileOutputStream(f, true)) {
            fos.write(text.getBytes("UTF-8"));
        } catch (IOException ignored) {}
    }
}
