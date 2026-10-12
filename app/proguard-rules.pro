# R8 / ProGuard Hardening Rules — XySAMP Mobile (Dual-ABI GTA-2.10)
-ignorewarnings
-dontwarn com.bda.controller.**
-dontwarn com.wardrumstudios.**
-dontwarn com.nvidia.**

-keepattributes Signature,InnerClasses,EnclosingMethod,Annotation

# Keep JNI entrypoints & engine classes called from libGTASA.so, libsamp.so, libImmEmulatorJ.so
-keep class com.nvidia.devtech.** { *; }
-keep class com.wardrumstudios.** { *; }
-keep class com.samp.mobile.game.** { *; }
-keep class com.samp.mobile.launcher.util.** { *; }
-keep class com.bda.controller.** { *; }
-keep class com.bytedance.shadowhook.** { *; }
-keep class com.immersion.** { *; }

-keepclasseswithmembernames class * {
    native <methods>;
}
