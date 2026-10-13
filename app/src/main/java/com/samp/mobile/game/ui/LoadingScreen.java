package com.samp.mobile.game.ui;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import androidx.constraintlayout.widget.ConstraintLayout;
import com.samp.mobile.R;

public class LoadingScreen {
    private final Activity activity;
    private final ConstraintLayout mainLayout;

    public LoadingScreen(Activity activity) {
        this.activity = activity;
        mainLayout = (ConstraintLayout) activity.getLayoutInflater().inflate(R.layout.loadingscreen, null);
        activity.addContentView(mainLayout, new ConstraintLayout.LayoutParams(-1, -1));
        // Auto-hide setelah 2.5 detik supaya OpenGL ImGui SplashScreen terlihat jelas & bebas blackscreen
        new Handler(Looper.getMainLooper()).postDelayed(this::hide, 2500);
    }

    public void hide() {
        if (mainLayout != null) {
            mainLayout.setVisibility(View.GONE);
            try {
                if (mainLayout.getParent() instanceof ViewGroup) {
                    ((ViewGroup) mainLayout.getParent()).removeView(mainLayout);
                }
            } catch (Throwable ignored) {}
        }
    }
}
