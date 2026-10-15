package com.samp.mobile.game;

import android.content.Intent;

import com.wardrumstudios.utils.WarGamepad;

import java.io.StringWriter;

import java.io.PrintWriter;

import java.io.File;

import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.inputmethod.InputMethodManager;
import android.widget.Toast;
import com.samp.mobile.game.ui.AttachEdit;
import com.samp.mobile.game.ui.CustomKeyboard;
import com.samp.mobile.game.ui.LoadingScreen;
import com.samp.mobile.game.ui.dialog.DialogManager;
import com.samp.mobile.launcher.util.SharedPreferenceCore;

import java.io.UnsupportedEncodingException;
import java.nio.charset.StandardCharsets;
public class SAMP extends GTASA implements CustomKeyboard.InputListener, HeightProvider.HeightListener {
    private static final String TAG = "SAMP";
    private static SAMP instance;

    private CustomKeyboard mKeyboard;
    private DialogManager mDialog;
    private HeightProvider mHeightProvider;

    private AttachEdit mAttachEdit;
    private LoadingScreen mLoadingScreen;

    public native void sendDialogResponse(int i, int i2, int i3, byte[] str);

    public static SAMP getInstance() {
        return instance;
    }

    private void showTab()
    {

    }

    private void hideTab()
    {

    }

    private void setTab(int id, String name, int score, int ping)
    {

    }

    private void clearTab()
    {

    }

    private void showLoadingScreen()
    {

    }

    private void hideLoadingScreen()
    {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mLoadingScreen.hide();
            }
        });
    }

    public void setPauseState(boolean pause) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (pause) {
                    mDialog.hideWithoutReset();
                    mAttachEdit.hideWithoutReset();
                }
                else {
                    if(mDialog.isShow)
                        mDialog.showWithOldContent();
                    if(mAttachEdit.isShow)
                        mAttachEdit.showWithoutReset();
                }
            }
        });
    }

    public void exitGame(){
        
        markCleanExit();
        finishAndRemoveTask();
        System.exit(0);
    }

    /** Penanda keluar normal. Launcher memakai ini untuk membedakan keluar biasa dari crash/FC. */
    private void markCleanExit() {
        try { new File(getFilesDir(), "game_clean_exit").createNewFile(); } catch (Exception ignored) {}
    }

    public void showDialog(int dialogId, int dialogTypeId, byte[] bArr, byte[] bArr2, byte[] bArr3, byte[] bArr4) {
        final String caption = new String(bArr, StandardCharsets.UTF_8);
        final String content = new String(bArr2, StandardCharsets.UTF_8);
        final String leftBtnText = new String(bArr3, StandardCharsets.UTF_8);
        final String rightBtnText = new String(bArr4, StandardCharsets.UTF_8);
        runOnUiThread(() -> { this.mDialog.show(dialogId, dialogTypeId, caption, content, leftBtnText, rightBtnText); });
    }

    private native void onInputEnd(byte[] str);
    @Override
    public void OnInputEnd(String str)
    {
        byte[] toReturn = null;
        try
        {
            toReturn = str.getBytes("windows-1251");
        }
        catch(UnsupportedEncodingException e)
        {

        }

        try {
            onInputEnd(toReturn);
        }
        catch (UnsatisfiedLinkError e5) {
            Log.e(TAG, e5.getMessage());
        }
    }

    private void showKeyboard()
    {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                Log.d("AXL", "showKeyboard()");
                mKeyboard.ShowInputLayout();
            }
        });
    }

    private void hideKeyboard()
    {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mKeyboard.HideInputLayout();
            }
        });
    }

    private void showEditObject()
    {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mAttachEdit.show();
            }
        });
    }

    private void hideEditObject()
    {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mAttachEdit.hide();
            }
        });
    }

    private void loadMonetLoaderIfEnabled() {
        if (!getIntent().getBooleanExtra("enable_monetloader", false)) return;
        try {
            System.loadLibrary("luajit-5.1");
            System.loadLibrary("monetloader");
            Log.i(TAG, "MonetLoader 3.8.0 loaded (optional runtime)");
            Toast.makeText(this, "MonetLoader aktif untuk sesi ini.", Toast.LENGTH_SHORT).show();
        } catch (Throwable error) {
            Log.e(TAG, "Optional MonetLoader could not load; continuing without mods", error);
            Toast.makeText(this, "MonetLoader gagal dimuat; game tetap dilanjutkan tanpa mod.", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        Log.i(TAG, "**** onCreate");
        // Anti force close: crash Java di proses game ditangani di sini (tanpa dialog 'app has stopped').
        // Launcher melihat proses ini mati tanpa penanda keluar normal, lalu membuka game ulang.
        Thread.setDefaultUncaughtExceptionHandler((t, ex) -> {
            try {
                StringWriter sw = new StringWriter();
                ex.printStackTrace(new PrintWriter(sw));
                File dir = com.samp.mobile.launcher.AppLog.resolveDir(SAMP.this);
                if (!dir.exists()) dir.mkdirs();
                java.io.FileOutputStream fos = new java.io.FileOutputStream(
                        new File(dir, "game_crash_" + System.currentTimeMillis() + ".txt"));
                fos.write(("thread=" + t.getName() + "\n" + sw).getBytes("UTF-8"));
                fos.close();
            } catch (Exception ignored) {}
            android.os.Process.killProcess(android.os.Process.myPid());
            System.exit(10);
        });
        // Nilai input dari launcher (berbagi lewat Intent karena proses terpisah).
        Intent wgIn = getIntent();
        if (wgIn != null) {
            if (wgIn.hasExtra("wg_kbm")) WarGamepad.sEnableKeyboardMouse = wgIn.getBooleanExtra("wg_kbm", true);
            if (wgIn.hasExtra("wg_pad")) WarGamepad.sEnableGamepad = wgIn.getBooleanExtra("wg_pad", true);
            if (wgIn.hasExtra("wg_sens")) WarGamepad.sMouseSensitivity = wgIn.getFloatExtra("wg_sens", 1.0f);
        }
        loadMonetLoaderIfEnabled();
        super.onCreate(savedInstanceState);

        //if(!SignatureChecker.isSignatureValid(this, getPackageName()))
        //{
            //Toast.makeText(this, "Use original launcher! No remake", Toast.LENGTH_LONG).show();
            //return;
        //}

        //mHeightProvider = new HeightProvider(this);

        mKeyboard = new CustomKeyboard(this);

        mDialog = new DialogManager(this);

        mAttachEdit = new AttachEdit(this);

        mLoadingScreen = new LoadingScreen(this);

        instance = this;

        try {
            initializeSAMP();
        } catch (UnsatisfiedLinkError e5) {
            Log.e(TAG, e5.getMessage());
        }

    }

    private native void initializeSAMP();



    @Override
    public void onStart() {
        Log.i(TAG, "**** onStart");
        super.onStart();
    }

    @Override
    public void onRestart() {
        Log.i(TAG, "**** onRestart");
        super.onRestart();
    }

    @Override
    public void onResume() {
        Log.i(TAG, "**** onResume");
        super.onResume();
        //mHeightProvider.init(view);
    }

    public native void onEventBackPressed();

    @Override
    public void onBackPressed() {
        super.onBackPressed();
        onEventBackPressed();
    }

    @Override
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
    }

    @Override
    public void onPause() {
        Log.i(TAG, "**** onPause");
        super.onPause();
    }

    @Override
    public void onStop() {
        Log.i(TAG, "**** onStop");
        super.onStop();
    }

    @Override
    public void onDestroy() {
        Log.i(TAG, "**** onDestroy");
        if (isFinishing()) markCleanExit();
        super.onDestroy();
    }

    @Override
    public void onHeightChanged(int orientation, int height) {
        //mKeyboard.onHeightChanged(height);
        //mDialog.onHeightChanged(height);
    }
}
