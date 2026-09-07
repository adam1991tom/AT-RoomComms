using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace ATRoomComms.Client;

internal sealed class MainForm : Form
{
    private string _serverUrl;
    private readonly WebView2 _webView = new() { Dock = DockStyle.Fill };
    private readonly Panel _topBar = new() { Dock = DockStyle.Top, Height = 48 };
    private readonly Label _status = new() { AutoSize = true };
    private readonly NotifyIcon _notifyIcon;
    private readonly DateTime _startedAtUtc = DateTime.UtcNow;
    private readonly System.Windows.Forms.Timer _telemetryTimer = new() { Interval = 20_000 };
    private bool _reallyClose;
    private bool _hasShownTrayHint;
    private string? _lastError;

    internal MainForm(string serverUrl)
    {
        _serverUrl = Settings.NormaliseUrl(serverUrl);
        Text = $"AT RoomComms — v{Program.AppVersion}";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(900, 620);
        Size = new Size(1280, 820);
        BackColor = Branding.Bg;
        ForeColor = Branding.Text;

        _notifyIcon = new NotifyIcon
        {
            Icon = Icon,
            Text = "AT RoomComms",
            Visible = true,
            ContextMenuStrip = BuildTrayMenu(),
        };
        _notifyIcon.DoubleClick += (_, _) => RestoreFromTray();
        _notifyIcon.BalloonTipClicked += (_, _) => RestoreFromTray();

        _topBar.BackColor = Branding.Panel;
        var appName = new Label
        {
            Text = "AT RoomComms",
            Font = new Font("Segoe UI Semibold", 11F, FontStyle.Bold),
            ForeColor = Branding.Text,
            AutoSize = true,
            Location = new Point(16, 13),
        };
        _status.Text = $"{Environment.MachineName.ToUpperInvariant()}  •  Connecting…";
        _status.ForeColor = Branding.Muted;
        _status.Location = new Point(155, 15);

        var settingsButton = MakeButton("Settings", 100, Branding.Panel);
        settingsButton.Click += (_, _) => OpenSettings();

        var speakerButton = MakeButton("Speaker Preview", 135, Branding.Accent2);
        speakerButton.Click += (_, _) => OpenSpeakerPreview();

        var refreshButton = MakeButton("Refresh", 90, Branding.Accent);
        refreshButton.Click += (_, _) => _webView.Reload();

        _topBar.Controls.Add(settingsButton);
        _topBar.Controls.Add(speakerButton);
        _topBar.Controls.Add(refreshButton);
        _topBar.Controls.Add(appName);
        _topBar.Controls.Add(_status);

        Controls.Add(_webView);
        Controls.Add(_topBar);

        _telemetryTimer.Tick += (_, _) => SendTelemetry();

        Shown += async (_, _) =>
        {
            await InitialiseAsync();
            _telemetryTimer.Start();
            _ = Updater.CheckAndApplyAsync(ShowUpdateStatus);
        };
        FormClosing += MainForm_FormClosing;
        Resize += MainForm_Resize;
        FormClosed += (_, _) => { _telemetryTimer.Dispose(); _notifyIcon.Dispose(); };
    }

    private ContextMenuStrip BuildTrayMenu()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add("Open AT RoomComms", null, (_, _) => RestoreFromTray());
        menu.Items.Add("Speaker Preview", null, (_, _) => { RestoreFromTray(); OpenSpeakerPreview(); });
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Settings…", null, (_, _) => { RestoreFromTray(); OpenSettings(); });
        menu.Items.Add("Check for Updates", null, async (_, _) => await Updater.CheckAndApplyAsync(ShowUpdateStatus));
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Quit AT RoomComms", null, (_, _) => { _reallyClose = true; Close(); });
        return menu;
    }

    private void RestoreFromTray()
    {
        Show();
        WindowState = FormWindowState.Normal;
        Activate();
    }

    private void MainForm_Resize(object? sender, EventArgs e)
    {
        if (WindowState == FormWindowState.Minimized && Settings.MinimizeToTray)
        {
            Hide();
        }
    }

    private void MainForm_FormClosing(object? sender, FormClosingEventArgs e)
    {
        if (_reallyClose || e.CloseReason != CloseReason.UserClosing || !Settings.MinimizeToTray)
        {
            return;
        }
        e.Cancel = true;
        Hide();
        if (!_hasShownTrayHint)
        {
            _hasShownTrayHint = true;
            _notifyIcon.BalloonTipTitle = "AT RoomComms";
            _notifyIcon.BalloonTipText = "Still running in the background. Right-click the tray icon to quit.";
            _notifyIcon.BalloonTipIcon = ToolTipIcon.Info;
            _notifyIcon.ShowBalloonTip(5000);
        }
    }

    private void ShowUpdateStatus(string message)
    {
        if (InvokeRequired) { BeginInvoke(() => ShowUpdateStatus(message)); return; }
        _status.Text = message;
        _notifyIcon.BalloonTipTitle = "AT RoomComms Update";
        _notifyIcon.BalloonTipText = message;
        _notifyIcon.BalloonTipIcon = ToolTipIcon.Info;
        _notifyIcon.ShowBalloonTip(6000);
    }

    private static Button MakeButton(string text, int width, Color colour)
    {
        var button = new Button
        {
            Text = text,
            Dock = DockStyle.Right,
            Width = width,
            FlatStyle = FlatStyle.Flat,
            BackColor = colour,
            ForeColor = Color.White,
        };
        button.FlatAppearance.BorderSize = 0;
        return button;
    }

    private async Task InitialiseAsync()
    {
        try
        {
            string userData = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "AT RoomComms",
                "WebView2");
            Directory.CreateDirectory(userData);

            CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(null, userData);
            await _webView.EnsureCoreWebView2Async(env);
            _webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
            _webView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
            _webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
            _webView.CoreWebView2.WebMessageReceived += WebMessageReceived;
            _webView.CoreWebView2.NavigationCompleted += (_, e) =>
            {
                _status.Text = e.IsSuccess
                    ? $"{Environment.MachineName.ToUpperInvariant()}  •  Connected"
                    : $"{Environment.MachineName.ToUpperInvariant()}  •  Connection failed";
                _status.ForeColor = e.IsSuccess
                    ? Color.FromArgb(90, 225, 145)
                    : Color.FromArgb(255, 105, 125);
            };
            _webView.CoreWebView2.ProcessFailed += (_, e) =>
            {
                _lastError = $"WebView2 process failed: {e.ProcessFailedKind}";
                _webView.Reload();
            };
            NavigateClient();
        }
        catch (WebView2RuntimeNotFoundException)
        {
            _lastError = "WebView2 runtime not found";
            MessageBox.Show(
                "Microsoft Edge WebView2 Runtime is required. Windows 11 normally includes it. Install the Evergreen WebView2 Runtime, then reopen AT RoomComms.",
                "WebView2 Runtime Required",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
            Close();
        }
        catch (Exception ex)
        {
            _lastError = ex.Message;
            MessageBox.Show(ex.Message, "AT RoomComms", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void NavigateClient(bool speakerPreview = false)
    {
        string device = Uri.EscapeDataString(Environment.MachineName.ToUpperInvariant());
        string appVersion = Uri.EscapeDataString(Program.AppVersion);
        string speaker = speakerPreview ? "&speaker=1" : string.Empty;
        _webView.Source = new Uri($"{_serverUrl}/?device={device}&client=windows&clientVersion={appVersion}{speaker}");
    }

    private void OpenSpeakerPreview() => NavigateClient(speakerPreview: true);

    private void OpenSettings()
    {
        using var settings = new SettingsForm(_serverUrl);
        if (settings.ShowDialog(this) == DialogResult.OK && settings.ServerChanged)
        {
            _serverUrl = settings.ServerUrl;
            NavigateClient();
        }
    }

    private void WebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        try
        {
            using JsonDocument doc = JsonDocument.Parse(e.WebMessageAsJson);
            JsonElement root = doc.RootElement;
            if (!root.TryGetProperty("type", out JsonElement type) || type.GetString() != "notification") return;
            if (!Settings.NotificationsEnabled) return;

            string title = root.TryGetProperty("title", out JsonElement titleElement)
                ? titleElement.GetString() ?? "AT RoomComms"
                : "AT RoomComms";
            string body = root.TryGetProperty("body", out JsonElement bodyElement)
                ? bodyElement.GetString() ?? "New message"
                : "New message";
            string priority = root.TryGetProperty("priority", out JsonElement priorityElement)
                ? priorityElement.GetString() ?? "normal"
                : "normal";

            ToolTipIcon icon = priority switch
            {
                "emergency" => ToolTipIcon.Error,
                "urgent" => ToolTipIcon.Warning,
                "important" => ToolTipIcon.Warning,
                _ => ToolTipIcon.Info
            };

            // Windows can silently drop a balloon tip shown right after the icon
            // is (re-)made visible; re-asserting Visible first is a known mitigation.
            _notifyIcon.Visible = true;
            _notifyIcon.BalloonTipTitle = title.Length > 63 ? title[..63] : title;
            _notifyIcon.BalloonTipText = body.Length > 255 ? body[..255] : body;
            _notifyIcon.BalloonTipIcon = icon;
            _notifyIcon.ShowBalloonTip(priority == "emergency" ? 15000 : 8000);
        }
        catch (Exception ex)
        {
            // Invalid page messages, or a failed balloon tip, must never crash a
            // live client - but do record it so it's visible on the Devices page.
            _lastError = $"Notification failed: {ex.Message}";
        }
    }

    private void SendTelemetry()
    {
        if (_webView.CoreWebView2 is null) return;
        try
        {
            var payload = JsonSerializer.Serialize(new
            {
                type = "telemetry",
                presenting = PowerPointDetector.IsPresenting(),
                uptimeSeconds = (int)(DateTime.UtcNow - _startedAtUtc).TotalSeconds,
                diagnostics = new
                {
                    os = Environment.OSVersion.VersionString,
                    webview2 = TryGetWebView2Version(),
                    clientVersion = Program.AppVersion,
                    lastError = _lastError ?? "",
                },
            });
            _webView.CoreWebView2.PostWebMessageAsJson(payload);
        }
        catch
        {
            // The page may not be ready yet; skip this tick.
        }
    }

    private static string TryGetWebView2Version()
    {
        try { return CoreWebView2Environment.GetAvailableBrowserVersionString(); }
        catch { return "unknown"; }
    }
}

/// <summary>
/// Lightweight, dependency-free presence check: is PowerPoint currently running a
/// slideshow? Looks for POWERPNT.EXE plus a visible window using PowerPoint's own
/// slideshow window class, which has been stable since Office 2003. This does not
/// know the deck name or slide number - only whether a presentation is live.
/// </summary>
internal static class PowerPointDetector
{
    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    internal static bool IsPresenting()
    {
        try
        {
            if (System.Diagnostics.Process.GetProcessesByName("POWERPNT").Length == 0)
            {
                return false;
            }

            bool found = false;
            EnumWindows((hWnd, _) =>
            {
                if (!IsWindowVisible(hWnd)) return true;
                var sb = new StringBuilder(256);
                GetClassName(hWnd, sb, sb.Capacity);
                string cls = sb.ToString();
                if (cls.Equals("screenClass", StringComparison.OrdinalIgnoreCase) ||
                    cls.StartsWith("PPTFrameClass", StringComparison.OrdinalIgnoreCase))
                {
                    found = true;
                    return false;
                }
                return true;
            }, IntPtr.Zero);
            return found;
        }
        catch
        {
            return false;
        }
    }
}
