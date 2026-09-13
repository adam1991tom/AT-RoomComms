using System.Diagnostics;
using System.Reflection;
using Microsoft.Win32;

namespace ATRoomComms.Client;

internal static class Program
{
    internal static readonly string AppVersion =
        Assembly.GetExecutingAssembly().GetName().Version?.ToString(3) ?? "0.0.0";
    internal const string RegistryPath = @"SOFTWARE\AT Software\AT RoomComms Client";
    internal const string GitHubRepo = "adam1991tom/AT-RoomComms";

    [STAThread]
    private static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();

        try
        {
            bool changeServer = args.Any(a => a.Equals("--change-server", StringComparison.OrdinalIgnoreCase));
            string serverUrl = Settings.ReadServerUrl();

            if (changeServer || string.IsNullOrWhiteSpace(serverUrl))
            {
                using var setup = new ServerSetupForm(serverUrl);
                if (setup.ShowDialog() != DialogResult.OK)
                {
                    return;
                }
                serverUrl = setup.ServerUrl;
                Settings.WriteServerUrl(serverUrl);
            }

            Settings.SyncStartupRegistration(Settings.LaunchAtStartup);
            Application.Run(new MainForm(serverUrl));
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"AT RoomComms could not start.\n\n{ex.Message}",
                "AT RoomComms",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}

internal static class Settings
{
    internal static string NormaliseUrl(string value)
    {
        value = (value ?? string.Empty).Trim().TrimEnd('/');
        if (string.IsNullOrWhiteSpace(value)) return string.Empty;
        if (!value.StartsWith("http://", StringComparison.OrdinalIgnoreCase) &&
            !value.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
        {
            value = "http://" + value;
        }
        return value;
    }

    internal static string ReadServerUrl()
    {
        using RegistryKey? user = Registry.CurrentUser.OpenSubKey(Program.RegistryPath);
        string? value = user?.GetValue("ServerUrl") as string;
        if (!string.IsNullOrWhiteSpace(value)) return NormaliseUrl(value);

        using RegistryKey? machine = Registry.LocalMachine.OpenSubKey(Program.RegistryPath);
        value = machine?.GetValue("ServerUrl") as string;
        return NormaliseUrl(value ?? string.Empty);
    }

    internal static void WriteServerUrl(string value)
    {
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(Program.RegistryPath, writable: true);
        key.SetValue("ServerUrl", NormaliseUrl(value), RegistryValueKind.String);
    }

    private const string RunKeyPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run";
    private const string RunValueName = "AT RoomComms Client";

    internal static bool ReadBool(string name, bool defaultValue)
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(Program.RegistryPath);
        object? value = key?.GetValue(name);
        return value is int i ? i != 0 : defaultValue;
    }

    internal static void WriteBool(string name, bool value)
    {
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(Program.RegistryPath, writable: true);
        key.SetValue(name, value ? 1 : 0, RegistryValueKind.DWord);
    }

    internal static bool MinimizeToTray
    {
        get => ReadBool("MinimizeToTray", true);
        set => WriteBool("MinimizeToTray", value);
    }

    internal static bool NotificationsEnabled
    {
        get => ReadBool("NotificationsEnabled", true);
        set => WriteBool("NotificationsEnabled", value);
    }

    /// <summary>
    /// Per-user launch-at-startup, defaulting to on so a fresh install still starts
    /// automatically without any configuration. Backed by a flag (not just registry
    /// key presence) so SyncStartupRegistration can self-heal the actual Run key
    /// every launch, e.g. after a Windows update or profile migration clears it.
    /// </summary>
    internal static bool LaunchAtStartup
    {
        get => ReadBool("LaunchAtStartup", true);
        set
        {
            WriteBool("LaunchAtStartup", value);
            SyncStartupRegistration(value);
        }
    }

    /// <summary>Applies the current LaunchAtStartup preference to the actual per-user Run key.</summary>
    internal static void SyncStartupRegistration(bool enabled)
    {
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(RunKeyPath, writable: true);
        if (enabled)
        {
            key.SetValue(RunValueName, $"\"{Application.ExecutablePath}\"", RegistryValueKind.String);
        }
        else
        {
            key.DeleteValue(RunValueName, throwOnMissingValue: false);
        }
    }
}
