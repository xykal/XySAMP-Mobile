package com.wardrumstudios.utils;

import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.ViewParent;

public class WarGamepad extends WarBilling {
    // Xbox 360 / Rockstar Wardrum button bit indices
    public static final int BTN_A         = 0;  // Cross / Sprint / Accept
    public static final int BTN_B         = 1;  // Circle / Fire / Melee
    public static final int BTN_X         = 2;  // Square / Jump / Brake
    public static final int BTN_Y         = 3;  // Triangle / Enter-Exit Vehicle (F)
    public static final int BTN_START     = 4;  // Start / Menu
    public static final int BTN_BACK      = 5;  // Select / Camera View (V)
    public static final int BTN_L1        = 6;  // L1 / LB
    public static final int BTN_R1        = 7;  // R1 / RB / Handbrake / Aim
    public static final int BTN_DPAD_UP   = 8;  // D-Pad Up
    public static final int BTN_DPAD_DOWN = 9;  // D-Pad Down
    public static final int BTN_DPAD_LEFT = 10; // D-Pad Left / Prev Weapon (Q / Scroll Down)
    public static final int BTN_DPAD_RIGHT= 11; // D-Pad Right / Next Weapon (E / Scroll Up)
    public static final int BTN_L3        = 12; // L3 / Crouch (C) / Horn (H)
    public static final int BTN_R3        = 13; // R3 / Look Behind (Middle Mouse)

    public static volatile boolean sEnableKeyboardMouse = true;
    public static volatile boolean sEnableGamepad = true;
    private static volatile boolean sActivePeripheralInput = false;
    private static volatile int sButtonMask = 0;
    public static volatile float sMouseSensitivity = 1.0f;
    private static final float[] sMouseLook = new float[2]; // akumulasi gerak mouse -> stick kanan
    private static float sLastMouseX = Float.NaN, sLastMouseY = Float.NaN;
    private static final float[] sAxes = new float[6]; // 0:LX, 1:LY, 2:RX, 3:RY, 4:LT(Aim), 5:RT(Fire/Gas)

    // Keyboard WASD state
    private static boolean sKeyW = false, sKeyS = false, sKeyA = false, sKeyD = false;
    private static boolean sKeyUp = false, sKeyDown = false, sKeyLeft = false, sKeyRight = false;

    public static boolean hasConnectedGamepad() {
        try {
            int[] ids = InputDevice.getDeviceIds();
            for (int id : ids) {
                InputDevice dev = InputDevice.getDevice(id);
                if (dev == null) continue;
                int src = dev.getSources();
                if ((src & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD ||
                    (src & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK) {
                    return true;
                }
            }
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean hasConnectedKeyboard() {
        try {
            int[] ids = InputDevice.getDeviceIds();
            for (int id : ids) {
                InputDevice dev = InputDevice.getDevice(id);
                if (dev == null) continue;
                if ((dev.getSources() & InputDevice.SOURCE_KEYBOARD) == InputDevice.SOURCE_KEYBOARD &&
                    dev.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC) {
                    return true;
                }
            }
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean hasConnectedMouse() {
        try {
            int[] ids = InputDevice.getDeviceIds();
            for (int id : ids) {
                InputDevice dev = InputDevice.getDevice(id);
                if (dev == null) continue;
                int src = dev.getSources();
                if ((src & InputDevice.SOURCE_MOUSE) == InputDevice.SOURCE_MOUSE ||
                    (src & InputDevice.SOURCE_TOUCHPAD) == InputDevice.SOURCE_TOUCHPAD) {
                    return true;
                }
            }
        } catch (Throwable ignored) {}
        return false;
    }

    private static void setBtn(int bit, boolean down) {
        if (bit < 0 || bit > 15) return;
        if (down) {
            sButtonMask |= (1 << bit);
            sActivePeripheralInput = true;
        } else {
            sButtonMask &= ~(1 << bit);
        }
    }

    private static void recomputeWasdAxes() {
        float lx = 0.0f;
        float ly = 0.0f;
        if (sKeyA || sKeyLeft)  lx -= 1.0f;
        if (sKeyD || sKeyRight) lx += 1.0f;
        if (sKeyW || sKeyUp)    ly -= 1.0f;
        if (sKeyS || sKeyDown)  ly += 1.0f;
        sAxes[0] = lx;
        sAxes[1] = ly;
    }

    public static boolean handleKeyEvent(int keyCode, KeyEvent event, boolean isDown) {
        if (event == null) return false;
        int src = event.getSource();
        boolean isPad = ((src & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD) ||
                        ((src & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK);

        if (isPad && sEnableGamepad) {
            switch (keyCode) {
                case KeyEvent.KEYCODE_BUTTON_A:      setBtn(BTN_A, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_B:      setBtn(BTN_B, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_X:      setBtn(BTN_X, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_Y:      setBtn(BTN_Y, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_START:  setBtn(BTN_START, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_SELECT: setBtn(BTN_BACK, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_L1:     setBtn(BTN_L1, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_R1:     setBtn(BTN_R1, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_L2:     sAxes[4] = isDown ? 1.0f : 0.0f; sActivePeripheralInput = true; return true;
                case KeyEvent.KEYCODE_BUTTON_R2:     sAxes[5] = isDown ? 1.0f : 0.0f; sActivePeripheralInput = true; return true;
                case KeyEvent.KEYCODE_BUTTON_THUMBL: setBtn(BTN_L3, isDown); return true;
                case KeyEvent.KEYCODE_BUTTON_THUMBR: setBtn(BTN_R3, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_UP:       setBtn(BTN_DPAD_UP, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_DOWN:     setBtn(BTN_DPAD_DOWN, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_LEFT:     setBtn(BTN_DPAD_LEFT, isDown); return true;
                case KeyEvent.KEYCODE_DPAD_RIGHT:    setBtn(BTN_DPAD_RIGHT, isDown); return true;
            }
        }

        if (sEnableKeyboardMouse) {
            switch (keyCode) {
                case KeyEvent.KEYCODE_W:          sKeyW = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_S:          sKeyS = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_A:          sKeyA = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_D:          sKeyD = isDown; sActivePeripheralInput = true; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_UP:    sKeyUp = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_DOWN:  sKeyDown = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_LEFT:  sKeyLeft = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_DPAD_RIGHT: sKeyRight = isDown; recomputeWasdAxes(); return false;
                case KeyEvent.KEYCODE_SPACE:      setBtn(BTN_X, isDown); return false;
                case KeyEvent.KEYCODE_SHIFT_LEFT:
                case KeyEvent.KEYCODE_SHIFT_RIGHT:setBtn(BTN_A, isDown); return false;
                case KeyEvent.KEYCODE_F:
                case KeyEvent.KEYCODE_ENTER:      setBtn(BTN_Y, isDown); return false;
                case KeyEvent.KEYCODE_C:
                case KeyEvent.KEYCODE_H:          setBtn(BTN_L3, isDown); return false;
                case KeyEvent.KEYCODE_Q:          setBtn(BTN_DPAD_LEFT, isDown); return false;
                case KeyEvent.KEYCODE_E:          setBtn(BTN_DPAD_RIGHT, isDown); return false;
                case KeyEvent.KEYCODE_V:          setBtn(BTN_BACK, isDown); return false;
                case KeyEvent.KEYCODE_ESCAPE:     setBtn(BTN_START, isDown); return false;
            }
        }
        return false;
    }

    public static boolean handleGenericMotion(MotionEvent event) {
        if (event == null) return false;
        int src = event.getSource();

        // 1. Gamepad / Joystick Analog Sticks, Triggers & Hat D-Pad
        if (sEnableGamepad && (((src & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK) ||
                               ((src & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD))) {
            sActivePeripheralInput = true;
            float lx = event.getAxisValue(MotionEvent.AXIS_X);
            float ly = event.getAxisValue(MotionEvent.AXIS_Y);
            float rx = event.getAxisValue(MotionEvent.AXIS_Z);
            if (Math.abs(rx) < 0.05f) rx = event.getAxisValue(MotionEvent.AXIS_RX);
            float ry = event.getAxisValue(MotionEvent.AXIS_RZ);
            if (Math.abs(ry) < 0.05f) ry = event.getAxisValue(MotionEvent.AXIS_RY);

            float lt = Math.max(event.getAxisValue(MotionEvent.AXIS_LTRIGGER), event.getAxisValue(MotionEvent.AXIS_BRAKE));
            float rt = Math.max(event.getAxisValue(MotionEvent.AXIS_RTRIGGER),
                       Math.max(event.getAxisValue(MotionEvent.AXIS_GAS), event.getAxisValue(MotionEvent.AXIS_THROTTLE)));

            sAxes[0] = Math.abs(lx) > 0.08f ? lx : 0.0f;
            sAxes[1] = Math.abs(ly) > 0.08f ? ly : 0.0f;
            sAxes[2] = Math.abs(rx) > 0.08f ? rx : 0.0f;
            sAxes[3] = Math.abs(ry) > 0.08f ? ry : 0.0f;
            sAxes[4] = lt;
            sAxes[5] = rt;

            float hatX = event.getAxisValue(MotionEvent.AXIS_HAT_X);
            float hatY = event.getAxisValue(MotionEvent.AXIS_HAT_Y);
            setBtn(BTN_DPAD_LEFT,  hatX < -0.25f);
            setBtn(BTN_DPAD_RIGHT, hatX >  0.25f);
            setBtn(BTN_DPAD_UP,    hatY < -0.25f);
            setBtn(BTN_DPAD_DOWN,  hatY >  0.25f);
            return true;
        }

        // 2. USB OTG / Bluetooth Mouse Buttons & Scroll Wheel
        if (sEnableKeyboardMouse && ((src & InputDevice.SOURCE_MOUSE) == InputDevice.SOURCE_MOUSE)) {
            int btns = event.getButtonState();
            boolean leftClick   = (btns & MotionEvent.BUTTON_PRIMARY) != 0;
            boolean rightClick  = (btns & MotionEvent.BUTTON_SECONDARY) != 0;
            boolean middleClick = (btns & MotionEvent.BUTTON_TERTIARY) != 0;

            setBtn(BTN_B, leftClick);
            setBtn(BTN_R1, rightClick);
            sAxes[4] = rightClick ? 1.0f : 0.0f;
            sAxes[5] = leftClick ? 1.0f : 0.0f;
            setBtn(BTN_R3, middleClick);

            int act = event.getActionMasked();
            if (act == MotionEvent.ACTION_HOVER_MOVE || act == MotionEvent.ACTION_MOVE) {
                float dx = event.getAxisValue(MotionEvent.AXIS_RELATIVE_X);
                float dy = event.getAxisValue(MotionEvent.AXIS_RELATIVE_Y);
                if (dx == 0.0f && dy == 0.0f && !Float.isNaN(sLastMouseX)) {
                    dx = event.getX() - sLastMouseX;
                    dy = event.getY() - sLastMouseY;
                }
                sLastMouseX = event.getX();
                sLastMouseY = event.getY();
                float gain = 0.02f * sMouseSensitivity;
                sMouseLook[0] = clampUnit(sMouseLook[0] + dx * gain);
                sMouseLook[1] = clampUnit(sMouseLook[1] + dy * gain);
                sActivePeripheralInput = true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_SCROLL) {
                float vScroll = event.getAxisValue(MotionEvent.AXIS_VSCROLL);
                if (vScroll > 0.1f) {
                    setBtn(BTN_DPAD_RIGHT, true);
                    setBtn(BTN_DPAD_RIGHT, false);
                } else if (vScroll < -0.1f) {
                    setBtn(BTN_DPAD_LEFT, true);
                    setBtn(BTN_DPAD_LEFT, false);
                }
            }
            return false;
        }
        return false;
    }

    public int GetGamepadType() {
        if ((sEnableGamepad && hasConnectedGamepad()) || sActivePeripheralInput) {
            return 1;
        }
        return -1;
    }

    public int GetGamepadType(int index) {
        if (index == 0 && ((sEnableGamepad && hasConnectedGamepad()) || sActivePeripheralInput)) {
            return 1;
        }
        return -1;
    }

    public int GetGamepadButtons() {
        return sButtonMask;
    }

    public int GetGamepadButtons(int index) {
        return index == 0 ? sButtonMask : 0;
    }

    private static float clampUnit(float v) {
        return v > 1.0f ? 1.0f : (v < -1.0f ? -1.0f : v);
    }

    /** Stick kanan = analog + gerak mouse (dengan peluruhan per pembacaan / frame). */
    private static float readAxis(int axisId) {
        float v = sAxes[axisId];
        if (axisId == 2 || axisId == 3) {
            int k = axisId - 2;
            if (sEnableKeyboardMouse) v += sMouseLook[k];
            sMouseLook[k] *= 0.6f;
            if (Math.abs(sMouseLook[k]) < 0.001f) sMouseLook[k] = 0.0f;
            v = clampUnit(v);
        }
        return v;
    }

    public float GetGamepadAxis(int axisId) {
        if (axisId >= 0 && axisId < sAxes.length) {
            return readAxis(axisId);
        }
        return 0.0f;
    }

    public float GetGamepadAxis(int index, int axisId) {
        if (index == 0 && axisId >= 0 && axisId < sAxes.length) {
            return readAxis(axisId);
        }
        return 0.0f;
    }

    public int GetGamepadTrack(int index, int trackId, int coord) {
        return 0;
    }

    public int GetGamepadTrack(int i, int i2) {
        return 0;
    }

    public native boolean processTouchpadAsPointer(ViewParent viewParent, boolean z);
}
