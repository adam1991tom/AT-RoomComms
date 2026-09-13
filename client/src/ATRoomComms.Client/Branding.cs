namespace ATRoomComms.Client;

/// <summary>
/// AT RoomComms brand palette, matching the web app's default (blue) theme
/// so the native shell and the embedded page feel like one product.
/// </summary>
internal static class Branding
{
    internal static readonly Color Bg = Color.FromArgb(5, 6, 10);
    internal static readonly Color Panel = Color.FromArgb(16, 19, 30);
    internal static readonly Color Accent = Color.FromArgb(30, 160, 220);
    internal static readonly Color Accent2 = Color.FromArgb(12, 110, 156);
    internal static readonly Color Text = Color.FromArgb(238, 240, 248);
    internal static readonly Color Muted = Color.FromArgb(136, 146, 176);

    internal static void StylePrimary(Button button)
    {
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderSize = 0;
        button.BackColor = Accent;
        button.ForeColor = Color.White;
        button.Cursor = Cursors.Hand;
    }

    internal static void StyleSecondary(Button button)
    {
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderColor = Accent2;
        button.BackColor = Panel;
        button.ForeColor = Text;
        button.Cursor = Cursors.Hand;
    }
}
