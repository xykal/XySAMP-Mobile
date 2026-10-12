# =============================================================================
#  R8 / ProGuard Security & JNI Keep Rules for XySAMP Mobile
# =============================================================================
-optimizationpasses 5
-allowaccessmodification
-repackageclasses 'x'

# Hapus log debug/verbose/info di build release biar ga bocor di logcat
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
}

# Keep semua class & method JNI yang dipanggil dari libsamp.so & libGame.so
-keep class com.nvidia.devtech.** { *; }
-keep class com.wardrumstudios.utils.** { *; }
-keep class com.rockstargames.** { *; }
-keep class com.gta.game.** { *; }
-keep class com.gta.launcher.activity.MainActivity { *; }
-keep class com.bytedance.shadowhook.** { *; }

# Keep native methods
-keepclasseswithmembernames,includedescriptorclasses class * {
    native <methods>;
}

-dontwarn javax.servlet.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
-dontwarn com.google.firebase.**
-dontwarn com.joom.paranoid.**
