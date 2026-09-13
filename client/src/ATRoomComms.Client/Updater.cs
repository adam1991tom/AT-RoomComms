using System.ComponentModel;
using System.Diagnostics;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text.Json.Serialization;

namespace ATRoomComms.Client;

internal static class Updater
{
    private const string TagPrefix = "client-v";

    /// <summary>
    /// Checks GitHub Releases for a newer client build. If found, downloads the MSI
    /// asset and launches a silent machine-wide upgrade via msiexec, then exits this
    /// process so the installer can replace the running files.
    /// Never throws - a failed or blocked check must not affect normal startup.
    /// </summary>
    internal static async Task CheckAndApplyAsync(Action<string>? onStatus = null)
    {
        try
        {
            using var http = new HttpClient();
            http.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("ATRoomComms-Client", Program.AppVersion));
            http.Timeout = TimeSpan.FromSeconds(15);

            List<GitHubRelease>? releases = await http.GetFromJsonAsync<List<GitHubRelease>>(
                $"https://api.github.com/repos/{Program.GitHubRepo}/releases");

            GitHubRelease? latest = releases?
                .Where(r => !r.Draft && r.TagName.StartsWith(TagPrefix, StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(r => ParseVersion(r.TagName[TagPrefix.Length..]))
                .FirstOrDefault();
            if (latest is null) return;

            string latestVersion = latest.TagName[TagPrefix.Length..];
            if (!IsNewer(latestVersion, Program.AppVersion)) return;

            GitHubAsset? asset = latest.Assets?.FirstOrDefault(
                a => a.Name.EndsWith(".msi", StringComparison.OrdinalIgnoreCase));
            if (asset is null) return;

            GitHubAsset? shaAsset = latest.Assets?.FirstOrDefault(
                a => a.Name.Equals(asset.Name + ".sha256", StringComparison.OrdinalIgnoreCase));
            if (shaAsset is null)
            {
                onStatus?.Invoke("Update skipped - release is missing its checksum file.");
                return;
            }

            onStatus?.Invoke($"Downloading AT RoomComms v{latestVersion}…");
            string tempMsi = Path.Combine(Path.GetTempPath(), asset.Name);
            byte[] bytes = await http.GetByteArrayAsync(asset.BrowserDownloadUrl);

            string expectedHash = (await http.GetStringAsync(shaAsset.BrowserDownloadUrl)).Trim();
            string actualHash = Convert.ToHexString(SHA256.HashData(bytes));
            if (!string.Equals(expectedHash, actualHash, StringComparison.OrdinalIgnoreCase))
            {
                onStatus?.Invoke("Update aborted - downloaded file failed checksum verification.");
                return;
            }

            await File.WriteAllBytesAsync(tempMsi, bytes);

            onStatus?.Invoke($"Installing AT RoomComms v{latestVersion}…");
            var psi = new ProcessStartInfo
            {
                FileName = "msiexec.exe",
                Arguments = $"/i \"{tempMsi}\" /qn /norestart",
                UseShellExecute = true,
                Verb = "runas",
            };

            try
            {
                Process.Start(psi);
                Environment.Exit(0);
            }
            catch (Win32Exception)
            {
                // The user declined the elevation prompt. Try again next launch.
                onStatus?.Invoke("Update available - restart AT RoomComms and approve the prompt to install it.");
            }
        }
        catch
        {
            // Network unavailable, GitHub unreachable, malformed response, etc.
            // Silently skip - this must never block or crash normal startup.
        }
    }

    private static bool IsNewer(string latest, string current) =>
        ParseVersion(latest) is { } l && ParseVersion(current) is { } c && l > c;

    private static Version? ParseVersion(string s) => Version.TryParse(s, out var v) ? v : null;

    private sealed class GitHubRelease
    {
        [JsonPropertyName("tag_name")] public string TagName { get; set; } = "";
        [JsonPropertyName("draft")] public bool Draft { get; set; }
        [JsonPropertyName("assets")] public List<GitHubAsset>? Assets { get; set; }
    }

    private sealed class GitHubAsset
    {
        [JsonPropertyName("name")] public string Name { get; set; } = "";
        [JsonPropertyName("browser_download_url")] public string BrowserDownloadUrl { get; set; } = "";
    }
}
