using System.Diagnostics;
using Microsoft.Win32;

namespace ATRoomComms.Client;

internal static class Program
{
    internal const string AppVersion = "0.2.0";
    internal const string RegistryPath = @"SOFTWARE\AT Software\AT RoomComms Client";

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
}
