package com.samp.mobile.launcher;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import com.samp.mobile.R;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Unduhan data GTA (Lite/Full) sebagai foreground service.
 * - Tetap berjalan saat app di-background.
 * - Lanjut otomatis (HTTP Range) dari file .part bila koneksi putus.
 * - Setelah selesai langsung ekstrak dan pasang data (tanpa langkah manual).
 * - Status disimpan di SharedPreferences, sehingga UI bisa menampilkan
 *   progres yang benar setelah app ditutup lalu dibuka lagi.
 */
public class DataDownloadService extends Service {

    public static final String PREFS = "lombok_data_download";
    public static final String K_URL = "url";
    public static final String K_LABEL = "label";
    public static final String K_DIR = "dir";
    /** idle | downloading | extracting | done | error */
    public static final String K_STATE = "state";
    public static final String K_DONE = "done";
    public static final String K_TOTAL = "total";
    public static final String K_SPEED = "speed";
    public static final String K_MSG = "msg";

    private static final String ACTION_START = "com.samp.mobile.action.DATA_START";
    private static final String CHANNEL_ID = "lombok_data";
    private static final int NOTIF_ID = 4071;
    private static final int MAX_RETRY = 10;
    private static final String PART_PREFIX = "lombok_data_";

    private volatile boolean workerRunning = false;
    private PowerManager.WakeLock wakeLock;

    public static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** True bila ada unduhan yang belum selesai (termasuk yang terhenti karena app ditutup). */
    public static boolean isPending(Context c) {
        String s = prefs(c).getString(K_STATE, "idle");
        return "downloading".equals(s) || "extracting".equals(s);
    }

    /** Mulai atau lanjutkan unduhan. File .part yang sudah ada dipakai ulang. */
    public static void startJob(Context c, String url, String label, String dir) {
        prefs(c).edit()
                .putString(K_URL, url)
                .putString(K_LABEL, label)
                .putString(K_DIR, dir)
                .putString(K_STATE, "downloading")
                .putString(K_MSG, "Menghubungkan ke server unduhan " + label + "...")
                .putLong(K_DONE, 0L)
                .putLong(K_TOTAL, 0L)
                .putFloat(K_SPEED, 0f)
                .apply();
        launch(c);
    }

    /** Pastikan service berjalan untuk unduhan yang masih pending. */
    public static void launch(Context c) {
        Intent i = new Intent(c, DataDownloadService.class).setAction(ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            c.startForegroundService(i);
        } else {
            c.startService(i);
        }
    }

    static File partFile(File dir, String url) {
        return new File(dir, PART_PREFIX + Integer.toHexString(url.hashCode()) + ".zip.part");
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        AppLog.ensure(this);
        createChannel();
        startForeground(NOTIF_ID, buildNotification("Menyiapkan unduhan data...", -1));
        if (!isPending(this)) {
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        AppLog.i("DL", "onStartCommand: pending=" + isPending(this) + " worker=" + workerRunning);
        if (!workerRunning) {
            workerRunning = true;
            new Thread(this::runJob, "lombok-data-download").start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        releaseWakeLock();
    }

    private void runJob() {
        acquireWakeLock();
        try {
            SharedPreferences p = prefs(this);
            String url = p.getString(K_URL, "");
            String label = p.getString(K_LABEL, "Data");
            File dir = new File(p.getString(K_DIR, ""));
            if (url.isEmpty() || dir.getPath().isEmpty()) {
                fail("Konfigurasi unduhan tidak lengkap. Coba lagi dari menu Data.");
                return;
            }
            if (!dir.exists()) dir.mkdirs();
            File part = partFile(dir, url);
            AppLog.i("DL", "Mulai unduhan " + label + " | url=" + url + " | part=" + part.getName()
                    + " (" + (part.exists() ? part.length() : 0) + " byte sudah ada)");

            boolean needDownload = !("extracting".equals(p.getString(K_STATE, "")) && part.exists());
            if (needDownload) {
                int attempt = 0;
                while (true) {
                    try {
                        downloadOnce(url, label, part);
                        break;
                    } catch (Exception e) {
                        attempt++;
                        String reason = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                        AppLog.w("DL", "Percobaan " + attempt + " gagal: " + reason);
                        if (attempt >= MAX_RETRY) {
                            fail("Unduhan terhenti (" + reason + "). Tekan DOWNLOAD lagi, unduhan lanjut dari posisi terakhir.");
                            return;
                        }
                        long waitMs = Math.min(30000L, 2000L * attempt);
                        setMsg("Koneksi terputus, mencoba lagi (" + attempt + "/" + MAX_RETRY + ") dalam " + (waitMs / 1000) + " detik...");
                        notifyProgress("Koneksi terputus, mencoba lagi...", -1);
                        if (!sleep(waitMs)) return;
                    }
                }
            }

            p.edit().putString(K_STATE, "extracting")
                    .putString(K_MSG, "Mengekstrak " + label + " ke folder data...")
                    .apply();
            notifyProgress("Mengekstrak " + label + "...", -1);
            try {
                GameDataFixer.extractZip(part, dir);
                GameDataFixer.prepareAndReport(dir);
            } catch (Exception e) {
                AppLog.e("DATA", "Ekstrak gagal", e);
                // ZIP rusak: hapus agar unduhan berikutnya dimulai dari awal.
                part.delete();
                fail("Gagal mengekstrak " + label + " (" + e.getMessage() + "). Tekan DOWNLOAD lagi untuk mengunduh ulang.");
                return;
            }
            provisionSampDirectory(dir);
            part.delete();

            AppLog.i("DL", "Unduhan & ekstrak " + label + " selesai");
            p.edit()
                    .putString(K_STATE, "done")
                    .putString(K_MSG, label + " berhasil dipasang. Siap dimainkan.")
                    .apply();
            notifyDone(label + " siap dimainkan");
        } finally {
            workerRunning = false;
            releaseWakeLock();
            stopForeground(true);
            stopSelf();
        }
    }

    /** Satu percobaan unduh; melanjutkan dari .part bila ada. Melempar exception bila belum lengkap. */
    private void downloadOnce(String zipUrl, String label, File part) throws IOException {
        long existing = part.exists() ? part.length() : 0L;
        HttpURLConnection conn = (HttpURLConnection) new URL(zipUrl).openConnection();
        try {
            conn.setInstanceFollowRedirects(true);
            conn.setConnectTimeout(20000);
            conn.setReadTimeout(60000);
            conn.setRequestProperty("User-Agent", "LombokHoliday/2.1");
            if (existing > 0) {
                conn.setRequestProperty("Range", "bytes=" + existing + "-");
            }
            int code = conn.getResponseCode();
            if (code == 416 && existing > 0) {
                return; // Range di luar ukuran: file .part sudah utuh
            }
            if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                throw new IOException("server mengembalikan HTTP " + code);
            }
            String type = conn.getContentType();
            if (type != null && type.toLowerCase(Locale.ROOT).contains("text/html")) {
                throw new IOException("link mengembalikan halaman web, bukan file ZIP. Cek izin berbagi Google Drive");
            }

            boolean append = (code == HttpURLConnection.HTTP_PARTIAL);
            if (!append) existing = 0L; // server mengabaikan Range: mulai dari awal
            long len = conn.getContentLengthLong();
            long total = len > 0 ? (append ? existing + len : len) : -1L;

            setProgress(existing, total, 0f, "Mengunduh " + label + "...");

            try (InputStream in = new BufferedInputStream(conn.getInputStream(), 1 << 16);
                 FileOutputStream fos = new FileOutputStream(part, append)) {
                byte[] buf = new byte[1 << 16];
                long done = existing;
                long lastT = System.currentTimeMillis();
                long lastB = done;
                int n;
                while ((n = in.read(buf)) != -1) {
                    if (Thread.currentThread().isInterrupted()) throw new IOException("dihentikan");
                    fos.write(buf, 0, n);
                    done += n;
                    long now = System.currentTimeMillis();
                    if (now - lastT >= 500) {
                        float spd = (float) ((done - lastB) / 1048576.0 / ((now - lastT) / 1000.0));
                        setProgress(done, total, spd, "Mengunduh " + label + "...");
                        int pct = total > 0 ? (int) (done * 100L / total) : -1;
                        notifyProgress("Mengunduh " + label + " (" + pct + "%)", pct);
                        lastT = now;
                        lastB = done;
                    }
                }
                fos.flush();
            }
            if (total > 0 && part.length() < total) {
                throw new IOException("koneksi terputus di " + (part.length() / 1048576L) + " MB");
            }
        } finally {
            conn.disconnect();
        }
    }

    private void setProgress(long done, long total, float speed, String msg) {
        prefs(this).edit()
                .putLong(K_DONE, done)
                .putLong(K_TOTAL, total)
                .putFloat(K_SPEED, speed)
                .putString(K_MSG, msg)
                .apply();
    }

    private void setMsg(String msg) {
        prefs(this).edit().putString(K_MSG, msg).apply();
    }

    private void fail(String msg) {
        prefs(this).edit()
                .putString(K_STATE, "error")
                .putString(K_MSG, msg)
                .putFloat(K_SPEED, 0f)
                .apply();
        notifyDone(msg);
    }

    private boolean sleep(long ms) {
        try {
            Thread.sleep(ms);
            return true;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null && nm.getNotificationChannel(CHANNEL_ID) == null) {
                NotificationChannel ch = new NotificationChannel(CHANNEL_ID, "Unduhan Data GTA", NotificationManager.IMPORTANCE_LOW);
                ch.setDescription("Progres unduhan dan pemasangan data game");
                nm.createNotificationChannel(ch);
            }
        }
    }

    private android.app.Notification buildNotification(String text, int pct) {
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_notif_lh)
                .setContentTitle("Lombok Holiday")
                .setContentText(text)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setPriority(NotificationCompat.PRIORITY_LOW);
        if (pct >= 0) {
            b.setProgress(100, pct, false);
        } else {
            b.setProgress(0, 0, true);
        }
        return b.build();
    }

    private void notifyProgress(String text, int pct) {
        try {
            NotificationManagerCompat.from(this).notify(NOTIF_ID, buildNotification(text, pct));
        } catch (Exception ignored) {
        }
    }

    private void notifyDone(String text) {
        try {
            NotificationCompat.Builder b = new NotificationCompat.Builder(this, CHANNEL_ID)
                    .setSmallIcon(R.drawable.ic_notif_lh)
                    .setContentTitle("Lombok Holiday")
                    .setContentText(text)
                    .setAutoCancel(true)
                    .setPriority(NotificationCompat.PRIORITY_DEFAULT);
            NotificationManagerCompat.from(this).notify(NOTIF_ID + 1, b.build());
        } catch (Exception ignored) {
        }
    }

    private void acquireWakeLock() {
        try {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            if (pm != null && wakeLock == null) {
                wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "lombok:data-download");
                wakeLock.setReferenceCounted(false);
                wakeLock.acquire(6L * 60L * 60L * 1000L);
            }
        } catch (Exception ignored) {
        }
    }

    private void releaseWakeLock() {
        try {
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        } catch (Exception ignored) {
        }
        wakeLock = null;
    }

    private void provisionSampDirectory(File baseDir) {
        try {
            File fontsDir = new File(new File(baseDir, "SAMP"), "fonts");
            if (!fontsDir.exists()) fontsDir.mkdirs();
            String[] fontTargets = new String[]{"arial.ttf", "Arial.ttf", "arial_bold.ttf"};
            for (String ft : fontTargets) {
                File outFont = new File(fontsDir, ft);
                if (!outFont.exists() || outFont.length() < 1024) {
                    try (java.io.InputStream is = getResources().openRawResource(R.font.roboto_medium);
                         FileOutputStream fos = new FileOutputStream(outFont)) {
                        byte[] buf = new byte[4096];
                        int n;
                        while ((n = is.read(buf)) != -1) fos.write(buf, 0, n);
                    }
                }
            }
        } catch (Exception ignored) {
        }
    }
}
