using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace ATRoomComms.Client;

internal sealed class MainForm : Form
{
    private readonly string _serverUrl;
    private readonly WebView2 _webView = new() { Dock = DockStyle.Fill };
    private readonly Panel _topBar = new() { Dock = DockStyle.Top, Height = 48 };
    private readonly Label _status = new() { AutoSize = true };
    private readonly NotifyIcon _notifyIcon;

    internal MainForm(string serverUrl)
    {
        _serverUrl = Settings.NormaliseUrl(serverUrl);
        Text = $"AT RoomComms Client v{Program.AppVersion}";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(900, 620);
        Size = new Size(1280, 820);
        BackColor = Color.FromArgb(10, 8, 16);
        ForeColor = Color.White;

        _notifyIcon = new NotifyIcon
        {
            Icon = Icon ?? SystemIcons.Application,
            Text = "AT RoomComms",
            Visible = true
        };
        _notifyIcon.BalloonTipClicked += (_, _) =>
        {
            Show();
            WindowState = FormWindowState.Normal;
            Activate();
        };

        _topBar.BackColor = Color.FromArgb(20, 15, 31);
        var appName = new Label
        {
            Text = "AT RoomComms",
            Font = new Font("Segoe UI Semibold", 11F, FontStyle.Bold),
            ForeColor = Color.White,
            AutoSize = true,
            Location = new Point(16, 13)
        };
        _status.Text = $"{Environment.MachineName.ToUpperInvariant()}  •  Connecting…";
        _status.ForeColor = Color.FromArgb(180, 165, 205);
        _status.Location = new Point(155, 15);

        var settingsButton = MakeButton("Change server", 125, Color.FromArgb(43, 31, 65));
        settingsButton.Click += (_, _) => RestartForServerChange();

        var speakerButton = MakeButton("Speaker Preview", 135, Color.FromArgb(73, 42, 122));
        speakerButton.Click += (_, _) => OpenSpeakerPreview();

        var refreshButton = MakeButton("Refresh", 90, Color.FromArgb(91, 48, 177));
        refreshButton.Click += (_, _) => _webView.Reload();

        _topBar.Controls.Add(settingsButton);
        _topBar.Controls.Add(speakerButton);
        _topBar.Controls.Add(refreshButton);
        _topBar.Controls.Add(appName);
        _topBar.Controls.Add(_status);

        Controls.Add(_webView);
        Controls.Add(_topBar);
        Shown += async (_, _) => await InitialiseAsync();
        FormClosed += (_, _) => _notifyIcon.Dispose();
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
            ForeColor = Color.White
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
            _webView.CoreWebView2.ProcessFailed += (_, _) => _webView.Reload();
            NavigateClient();
        }
        catch (WebView2RuntimeNotFoundException)
        {
            MessageBox.Show(
                "Microsoft Edge WebView2 Runtime is required. Windows 11 normally includes it. Install the Evergreen WebView2 Runtime, then reopen AT RoomComms.",
                "WebView2 Runtime Required",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
            Close();
        }
        catch (Exception ex)
        {
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

    private void OpenSpeakerPreview()
    {
        NavigateClient(speakerPreview: true);
    }

    private void WebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        try
        {
            using JsonDocument doc = JsonDocument.Parse(e.WebMessageAsJson);
            JsonElement root = doc.RootElement;
            if (!root.TryGetProperty("type", out JsonElement type) || type.GetString() != "notification") return;

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

            _notifyIcon.BalloonTipTitle = title.Length > 63 ? title[..63] : title;
            _notifyIcon.BalloonTipText = body.Length > 255 ? body[..255] : body;
            _notifyIcon.BalloonTipIcon = icon;
            _notifyIcon.ShowBalloonTip(priority == "emergency" ? 15000 : 8000);
        }
        catch
        {
            // Invalid page messages are ignored so they can never crash a live client.
        }
    }

    private void RestartForServerChange()
    {
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
        {
            FileName = Application.ExecutablePath,
            Arguments = "--change-server",
            UseShellExecute = true
        });
        Close();
    }
}
