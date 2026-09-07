using System.Net.Http.Json;

namespace ATRoomComms.Client;

internal sealed class ServerSetupForm : Form
{
    private readonly TextBox _serverBox = new();
    private readonly Label _status = new();
    private readonly Button _save = new();
    private readonly Button _test = new();

    internal string ServerUrl { get; private set; } = string.Empty;

    internal ServerSetupForm(string current)
    {
        Text = "AT RoomComms — Server Setup";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ClientSize = new Size(570, 330);
        BackColor = Branding.Bg;
        ForeColor = Branding.Text;
        Font = new Font("Segoe UI", 10F);

        var title = new Label
        {
            Text = "Connect this laptop to RoomComms",
            Font = new Font("Segoe UI Semibold", 19F, FontStyle.Bold),
            AutoSize = true,
            Location = new Point(30, 28)
        };
        var subtitle = new Label
        {
            Text = $"Computer: {Environment.MachineName.ToUpperInvariant()}\nEnter the local RoomComms Docker server address.",
            ForeColor = Color.FromArgb(180, 170, 205),
            AutoSize = true,
            Location = new Point(33, 78)
        };
        var serverLabel = new Label
        {
            Text = "SERVER ADDRESS",
            ForeColor = Branding.Accent,
            AutoSize = true,
            Location = new Point(33, 139)
        };
        _serverBox.Text = current;
        _serverBox.PlaceholderText = "Example: 10.100.70.101:5070";
        _serverBox.Location = new Point(33, 165);
        _serverBox.Size = new Size(504, 31);
        _serverBox.BackColor = Branding.Panel;
        _serverBox.ForeColor = Branding.Text;
        _serverBox.BorderStyle = BorderStyle.FixedSingle;

        _status.Text = "The address can be changed later from Settings.";
        _status.ForeColor = Branding.Muted;
        _status.AutoSize = true;
        _status.Location = new Point(33, 207);

        _test.Text = "Test connection";
        _test.Location = new Point(248, 258);
        _test.Size = new Size(140, 42);
        Branding.StyleSecondary(_test);
        _test.Click += async (_, _) => await TestConnectionAsync();

        _save.Text = "Save and open";
        _save.Location = new Point(397, 258);
        _save.Size = new Size(140, 42);
        Branding.StylePrimary(_save);
        _save.Click += async (_, _) => await SaveAsync();

        Controls.AddRange([title, subtitle, serverLabel, _serverBox, _status, _test, _save]);
        AcceptButton = _save;
    }


    private async Task<bool> CheckAsync()
    {
        string url = Settings.NormaliseUrl(_serverBox.Text);
        if (string.IsNullOrWhiteSpace(url))
        {
            _status.Text = "Enter a server address first.";
            _status.ForeColor = Color.FromArgb(255, 110, 130);
            return false;
        }

        _test.Enabled = _save.Enabled = false;
        _status.Text = "Checking the RoomComms server…";
        _status.ForeColor = Color.FromArgb(190, 170, 225);

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
            ServerUrl = url;
            return true;
        }
        catch (Exception ex)
        {
            _status.Text = "Could not connect: " + ex.Message;
            _status.ForeColor = Color.FromArgb(255, 110, 130);
            return false;
        }
        finally
        {
            _test.Enabled = _save.Enabled = true;
        }
    }

    private async Task TestConnectionAsync() => await CheckAsync();

    private async Task SaveAsync()
    {
        if (await CheckAsync())
        {
            DialogResult = DialogResult.OK;
            Close();
        }
    }
}
