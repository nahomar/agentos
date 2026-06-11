//! Hardware Abstraction Layer — Platform detection and adaptation.

pub fn detect_platform() -> &'static str {
    #[cfg(target_os = "macos")]
    { "macOS" }
    #[cfg(target_os = "linux")]
    { "Linux" }
    #[cfg(target_os = "android")]
    { "Android" }
    #[cfg(target_os = "ios")]
    { "iOS" }
    #[cfg(target_os = "windows")]
    { "Windows" }
    #[cfg(not(any(
        target_os = "macos",
        target_os = "linux",
        target_os = "android",
        target_os = "ios",
        target_os = "windows"
    )))]
    { "Unknown" }
}

pub trait Platform {
    fn name(&self) -> &str;
    fn get_local_ip(&self) -> Option<String>;
}
