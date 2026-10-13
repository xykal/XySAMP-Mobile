# R8 / ProGuard Hardening Rules — Lombok Holiday Roleplay (Per-ABI Split)
-ignorewarnings
-dontwarn com.bda.controller.**
-dontwarn com.wardrumstudios.**
-dontwarn com.nvidia.**

-keepattributes Signature,InnerClasses,EnclosingMethod,Annotation

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
