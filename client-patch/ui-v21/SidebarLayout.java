package com.samp.mobile.launcher;

import android.content.Context;
import android.util.AttributeSet;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.widget.LinearLayout;

/**
 * Sidebar kiri. Menangkap gestur fling horizontal (tanpa mengganggu klik tombol).
 * Swipe ke kiri = perkecil, swipe ke kanan = besarkan.
 */
public class SidebarLayout extends LinearLayout {

    public interface SwipeListener {
        void onSwipe(boolean expand);
    }

    private SwipeListener swipeListener;
    private final GestureDetector gestureDetector;

    public SidebarLayout(Context context, AttributeSet attrs) {
        super(context, attrs);
        final float density = getResources().getDisplayMetrics().density;
        gestureDetector = new GestureDetector(context, new GestureDetector.SimpleOnGestureListener() {
            @Override
            public boolean onFling(MotionEvent e1, MotionEvent e2, float velocityX, float velocityY) {
                if (e1 == null || e2 == null || swipeListener == null) return false;
                float dx = e2.getX() - e1.getX();
                boolean horizontal = Math.abs(velocityX) > Math.abs(velocityY) * 1.5f;
                if (horizontal && Math.abs(dx) > 48 * density && Math.abs(velocityX) > 500) {
                    swipeListener.onSwipe(velocityX > 0);
                    return true;
                }
                return false;
            }
        });
    }

    public void setSwipeListener(SwipeListener listener) {
        this.swipeListener = listener;
    }

    @Override
    public boolean onInterceptTouchEvent(MotionEvent ev) {
        // Tetap meneruskan sentuhan ke tombol anak; hanya mengamati untuk fling.
        gestureDetector.onTouchEvent(ev);
        return false;
    }

    @Override
    public boolean onTouchEvent(MotionEvent ev) {
        gestureDetector.onTouchEvent(ev);
        return super.onTouchEvent(ev);
    }
}
