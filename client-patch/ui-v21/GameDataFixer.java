package com.samp.mobile.launcher;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipInputStream;

/**
 * Ekstraksi ZIP data GTA + perbaikan struktur agar cocok dengan client:
 *  1. Path ZIP dinormalisasi: semua isi folder "files/" dipindah ke root data
 *     (contoh: "DATA LITE .../files/texdb/..." -> "texdb/...").
 *  2. File texdb bernama "<db>.RENAME.(dat|tmb|toc)" diganti menjadi "<db>.unc.*".
 *     Client mencari varian dxt/etc/pvr/unc; varian unc dipakai sebagai fallback
 *     (lihat TryOpenTexdbAnyFormat di hooks.cpp), sehingga tekstur tetap terbaca di GPU apa pun.
 *  3. Laporan validasi ditulis ke log (AppLog) agar mudah dilacak bila masih ada yang kurang.
 */
final class GameDataFixer {

    private static final String[] TEXDB_DBS = {"gta3", "gta_int", "mobile", "txd", "menu", "samp", "player", "playerhi"};
    private static final String[] TEXDB_FMTS = {"dxt", "etc", "pvr", "unc"};

    private GameDataFixer() {}

    /** Ekstrak ZIP ke root. Mengembalikan jumlah file yang ditulis. */
    static int extractZip(File zipFile, File root) throws IOException {
        String prefix = detectStripPrefix(zipFile);
        AppLog.i("DATA", "Ekstrak " + zipFile.getName() + " | prefix dilepas: '" + prefix + "'");
        int written = 0;
        try (ZipInputStream zis = new ZipInputStream(new BufferedInputStream(new FileInputStream(zipFile), 65536))) {
            ZipEntry entry;
            byte[] buffer = new byte[65536];
            while ((entry = zis.getNextEntry()) != null) {
                String name = entry.getName().replace('\\', '/');
                while (name.startsWith("/")) name = name.substring(1);
                if (name.contains("..")) continue;
                if (!prefix.isEmpty()) {
                    if (!name.regionMatches(true, 0, prefix, 0, prefix.length())) continue;
                    name = name.substring(prefix.length());
                }
                if (name.isEmpty()) continue;

                File outFile = new File(root, name);
                if (entry.isDirectory()) {
                    outFile.mkdirs();
                } else {
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.exists()) parent.mkdirs();
                    try (BufferedOutputStream bos = new BufferedOutputStream(new FileOutputStream(outFile), 65536)) {
                        int len;
                        while ((len = zis.read(buffer)) != -1) bos.write(buffer, 0, len);
                        bos.flush();
                    }
                    written++;
                }
                zis.closeEntry();
            }
        }
        AppLog.i("DATA", "Ekstrak selesai: " + written + " file ditulis ke " + root.getAbsolutePath());
        return written;
    }

    /**
     * Prefix yang dilepas: path sampai folder "files/" (depth <= 2) bila ada,
     * kalau tidak ada dan semua entri berada dalam satu folder atas, folder itu.
     */
    static String detectStripPrefix(File zipFile) throws IOException {
        String filesPrefix = null;
        String top = null;
        boolean singleTop = true;
        try (ZipFile zf = new ZipFile(zipFile)) {
            Enumeration<? extends ZipEntry> en = zf.entries();
            while (en.hasMoreElements()) {
                String n = en.nextElement().getName().replace('\\', '/');
                String[] parts = n.split("/");
                if (filesPrefix == null) {
                    for (int i = 0; i < Math.min(parts.length - 1, 3); i++) {
                        if (parts[i].equalsIgnoreCase("files")) {
                            StringBuilder sb = new StringBuilder();
                            for (int j = 0; j <= i; j++) sb.append(parts[j]).append('/');
                            filesPrefix = sb.toString();
                            break;
                        }
                    }
                }
                if (parts.length > 1) {
                    if (top == null) top = parts[0] + "/";
                    else if (!top.equals(parts[0] + "/")) singleTop = false;
                } else {
                    singleTop = false;
                }
            }
        }
        if (filesPrefix != null) return filesPrefix;
        if (singleTop && top != null) return top;
        return "";
    }

    /** Ubah "<db>.RENAME.<ext>" menjadi "<db>.unc.<ext>" di seluruh folder texdb. */
    static int normalizeTexdb(File root) {
        File texdb = child(root, "texdb");
        if (texdb == null || !texdb.isDirectory()) return 0;
        int changed = 0;
        List<File> files = new ArrayList<>();
        collect(texdb, files);
        for (File f : files) {
            String name = f.getName();
            int idx = name.toLowerCase(Locale.ROOT).indexOf(".rename.");
            if (idx < 0) continue;
            String target = name.substring(0, idx) + ".unc." + name.substring(idx + ".rename.".length());
            File dst = new File(f.getParentFile(), target);
            try {
                if (dst.exists() && !dst.delete()) continue;
                if (f.renameTo(dst)) {
                    changed++;
                    AppLog.i("DATA", "texdb: " + f.getParentFile().getName() + "/" + name + " -> " + target);
                }
            } catch (SecurityException e) {
                AppLog.e("DATA", "Gagal rename " + name + ": " + e.getMessage());
            }
        }
        return changed;
    }

    /** Dipanggil sebelum game dimulai: normalisasi lalu tulis laporan ke log. */
    static void prepareAndReport(File root) {
        try {
            if (root == null || !root.isDirectory()) {
                AppLog.w("DATA", "Folder data tidak ditemukan: " + root);
                return;
            }
            int renamed = normalizeTexdb(root);
            AppLog.i("DATA", "Normalisasi texdb: " + renamed + " file diganti");
            report(root);
        } catch (Exception e) {
            AppLog.e("DATA", "prepareAndReport gagal", e);
        }
    }

    static void report(File root) {
        String[] required = {
                "texdb/gta3.img", "texdb/gta_int.img", "texdb/samp.img", "texdb/SAMPCOL.img",
                "models/coll/peds.col", "anim/anim.img", "anim/cuts.img", "anim/ped.ifp",
                "data/gta.dat", "data/default.dat", "data/peds.ide", "data/vehicles.ide",
                "data/handling.cfg", "data/weapon.dat", "data/timecyc.dat", "stream.ini",
                "SAMP/main.scm", "SAMP/script.img", "SAMP/SAMP.ide", "SAMP/settings.json",
                "audio/CONFIG/BankLkup.dat", "fonts/arial.ttf"
        };
        int missing = 0;
        StringBuilder miss = new StringBuilder();
        for (String r : required) {
            if (!exists(root, r)) {
                missing++;
                miss.append(' ').append(r);
            }
        }
        AppLog.i("DATA", "Validasi file inti: " + (required.length - missing) + "/" + required.length + " ada");
        if (missing > 0) AppLog.w("DATA", "File inti hilang:" + miss);

        for (String db : TEXDB_DBS) {
            StringBuilder have = new StringBuilder();
            for (String fmt : TEXDB_FMTS) {
                if (exists(root, "texdb/" + db + "/" + db + "." + fmt + ".dat")
                        && exists(root, "texdb/" + db + "/" + db + "." + fmt + ".toc")) {
                    have.append(fmt).append(' ');
                }
            }
            if (have.length() == 0) {
                AppLog.w("DATA", "texdb/" + db + ": TIDAK ADA varian dat+toc");
            } else {
                AppLog.i("DATA", "texdb/" + db + ": varian tersedia = " + have.toString().trim());
            }
        }
    }

    static boolean exists(File root, String relPath) {
        return resolve(root, relPath) != null;
    }

    /** Pencarian path tanpa memperhatikan huruf besar/kecil (seperti FOpenCaseInsensitive di client). */
    static File resolve(File root, String relPath) {
        File cur = root;
        for (String seg : relPath.split("/")) {
            if (seg.isEmpty()) continue;
            File next = child(cur, seg);
            if (next == null) return null;
            cur = next;
        }
        return cur;
    }

    private static File child(File dir, String name) {
        if (dir == null || !dir.isDirectory()) return null;
        File direct = new File(dir, name);
        if (direct.exists()) return direct;
        File[] list = dir.listFiles();
        if (list == null) return null;
        for (File f : list) {
            if (f.getName().equalsIgnoreCase(name)) return f;
        }
        return null;
    }

    private static void collect(File dir, List<File> out) {
        File[] list = dir.listFiles();
        if (list == null) return;
        for (File f : list) {
            if (f.isDirectory()) collect(f, out);
            else out.add(f);
        }
    }
}
