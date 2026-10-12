package com.samp.mobile.game;

import android.content.Intent;
import android.content.res.Configuration;
import android.os.Bundle;
import android.view.KeyEvent;

import com.bytedance.shadowhook.ShadowHook;
import com.wardrumstudios.utils.WarMedia;

public class GTASA extends WarMedia {
    static String vmVersion;
    private boolean once = false;

    static {
        ShadowHook.init(new ShadowHook.ConfigBuilder()
                .setMode(ShadowHook.Mode.UNIQUE)
                .build());

        vmVersion = null;
        try {
            vmVersion = System.getProperty("java.vm.version");
            System.loadLibrary("ImmEmulatorJ");
        } catch (Throwable ignored) {
        }
        try {
            System.loadLibrary("SCAnd");
        } catch (Throwable ignored) {
        }
        try {
            System.loadLibrary("OpenAL64");
        } catch (Throwable t) {
            try {
                System.loadLibrary("OpenAL32");
            } catch (Throwable ignored) {
            }
        }
        System.loadLibrary("GTASA");
        System.loadLibrary("bass");
        System.loadLibrary("samp");
    }

    public static void staticEnterSocialClub() {}
    public static void staticExitSocialClub() {}
    public void AfterDownloadFunction() {}
    public void EnterSocialClub() {}
    public void ExitSocialClub() {}

    public boolean ServiceAppCommand(String str, String str2) {
        return false;
    }

    public int ServiceAppCommandValue(String str, String str2) {
        return 0;
    }

    public native void main();

    @Override
    public void onActivityResult(int i, int i2, Intent intent) {
        super.onActivityResult(i, i2, intent);
    }

    @Override
    public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
    }

    @Override
    public void onCreate(Bundle bundle) {
        if (!once) {
            once = true;
        }
        super.onCreate(bundle);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
    }

    @Override
    public boolean onKeyDown(int i, KeyEvent keyEvent) {
        return super.onKeyDown(i, keyEvent);
    }

    @Override
    public void onPause() {
        super.onPause();
    }

    @Override
    public void onRestart() {
        super.onRestart();
    }

    @Override
    public void onResume() {
        super.onResume();
    }

    @Override
    public void onStart() {
        super.onStart();
    }

    @Override
    public void onStop() {
        super.onStop();
    }

    public native void setCurrentScreenSize(int i, int i2);
}
