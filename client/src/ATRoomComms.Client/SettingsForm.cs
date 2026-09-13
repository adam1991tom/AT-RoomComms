namespace ATRoomComms.Client;

internal sealed class SettingsForm : Form
{
    private readonly TextBox _serverBox = new();
    private readonly Label _status = new();
    private readonly CheckBox _minimizeToTray = new() { Text = "Minimize to the tray instead of closing" };
    private readonly CheckBox _launchAtStartup = new() { Text = "Launch AT RoomComms when I sign in to Windows" };
    private readonly CheckBox _notifications = new() { Text = "Show desktop notifications" };
    private readonly Button _save = new();
    private readonly Button _test = new();
    private readonly Button _checkUpdate = new();

    internal bool ServerChanged { get; private set; }
    internal string ServerUrl { get; private set; }

    internal SettingsForm(string currentServerUrl)
    {
        ServerUrl = currentServerUrl;

        AutoScaleMode = AutoScaleMode.Dpi;
        AutoScaleDimensions = new SizeF(96F, 96F);
        Text = "AT RoomComms — Settings";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ClientSize = new Size(560, 420);
        BackColor = Branding.Bg;
        ForeColor = Branding.Text;
        Font = new Font("Segoe UI", 10F);

        var title = new Label
        {
            Text = "Settings",
            Font = new Font("Segoe UI Semibold", 18F, FontStyle.Bold),
            AutoSize = true,
            Location = new Point(28, 24),
        };

        var serverLabel = new Label
        {
            Text = "SERVER ADDRESS",
            ForeColor = Branding.Accent,
            AutoSize = true,
            Location = new Point(30, 78),
        };
        _serverBox.Text = currentServerUrl;
        _serverBox.Location = new Point(30, 100);
        _serverBox.Size = new Size(500, 31);
        _serverBox.BackColor = Branding.Panel;
        _serverBox.ForeColor = Branding.Text;
        _serverBox.BorderStyle = BorderStyle.FixedSingle;

        _status.Text = "";
        _status.ForeColor = Branding.Muted;
        _status.AutoSize = true;
        _status.Location = new Point(30, 138);

        _test.Text = "Test connection";
        _test.Location = new Point(30, 168);
        _test.Size = new Size(150, 36);
        Branding.StyleSecondary(_test);
        _test.Click += async (_, _) => await TestConnectionAsync();

        _minimizeToTray.ForeColor = Branding.Text;
        _minimizeToTray.AutoSize = true;
        _minimizeToTray.Location = new Point(30, 224);
        _minimizeToTray.Checked = Settings.MinimizeToTray;

        _launchAtStartup.ForeColor = Branding.Text;
        _launchAtStartup.AutoSize = true;
        _launchAtStartup.Location = new Point(30, 254);
        _launchAtStartup.Checked = Settings.LaunchAtStartup;

        _notifications.ForeColor = Branding.Text;
        _notifications.AutoSize = true;
        _notifications.Location = new Point(30, 284);
        _notifications.Checked = Settings.NotificationsEnabled;

        _checkUpdate.Text = "Check for updates";
        _checkUpdate.Location = new Point(30, 330);
        _checkUpdate.Size = new Size(160, 36);
        Branding.StyleSecondary(_checkUpdate);
        _checkUpdate.Click += async (_, _) => await CheckUpdateAsync();

        _save.Text = "Save";
        _save.Location = new Point(430, 366);
        _save.Size = new Size(100, 40);
        Branding.StylePrimary(_save);
        _save.Click += (_, _) => SaveAndClose();

        var version = new Label
        {
            Text = $"AT RoomComms Client v{Program.AppVersion}",
            ForeColor = Branding.Muted,
            AutoSize = true,
            Location = new Point(30, 378),
        };

        Controls.AddRange([
            title, serverLabel, _serverBox, _status, _test,
            _minimizeToTray, _launchAtStartup, _notifications,
            _checkUpdate, _save, version,
        ]);
        AcceptButton = _save;
    }

    private async Task TestConnectionAsync()
    {
        string url = Settings.NormaliseUrl(_serverBox.Text);
        if (string.IsNullOrWhiteSpace(url))
        {
            _status.Text = "Enter a server address first.";
            _status.ForeColor = Color.FromArgb(255, 110, 130);
            return;
        }
        _test.Enabled = false;
        _status.Text = "Checking the RoomComms server…";
        _status.ForeColor = Branding.Muted;
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(8) };
            using HttpResponseMessage response = await client.GetAsync(url + "/api/health");
            if (!response.IsSuccessStatusCode)
            {
                throw new HttpRequestException($"Server returned HTTP {(int)response.StatusCode}.");
            }
            _status.Text = "Connected successfully.";
            _status.ForeColor = Color.FromArgb(86, 220, 145);
        }
        catch (Exception ex)
        {
            _status.Text = "Could not connect: " + ex.Message;
            _status.ForeColor = Color.FromArgb(255, 110, 130);
        }
        finally
        {
            _test.Enabled = true;
        }
    }

    private async Task CheckUpdateAsync()
    {
        _checkUpdate.Enabled = false;
        _status.Text = "Checking for updates…";
        _status.ForeColor = Branding.Muted;
        bool found = false;
        await Updater.CheckAndApplyAsync(msg =>
        {
            found = true;
            _status.Text = msg;
        });
        if (!found)
        {
            _status.Text = "You're on the latest version.";
            _status.ForeColor = Color.FromArgb(86, 220, 145);
        }
        _checkUpdate.Enabled = true;
    }

    private void SaveAndClose()
    {
        string normalised = Settings.NormaliseUrl(_serverBox.Text);
        if (string.IsNullOrWhiteSpace(normalised))
        {
            _status.Text = "Enter a server address first.";
            _status.ForeColor = Color.FromArgb(255, 110, 130);
            return;
        }
        ServerChanged = normalised != Settings.NormaliseUrl(ServerUrl);
        ServerUrl = normalised;
        Settings.WriteServerUrl(normalised);
        Settings.MinimizeToTray = _minimizeToTray.Checked;
        Settings.LaunchAtStartup = _launchAtStartup.Checked;
        Settings.NotificationsEnabled = _notifications.Checked;
        DialogResult = DialogResult.OK;
        Close();
    }
}
