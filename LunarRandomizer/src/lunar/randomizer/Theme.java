package lunar.randomizer;

import java.awt.Color;
import java.awt.Font;
import javax.swing.BorderFactory;
import javax.swing.UIManager;
import javax.swing.border.Border;
import javax.swing.border.CompoundBorder;
import javax.swing.border.EmptyBorder;
import javax.swing.border.LineBorder;

/**
 * Dark blue + gold visual theme for Lunar Randomizer.
 * Tuned for readability on Windows 7 classic / Aero.
 */
public final class Theme {

    public static final Color BG_DARKEST   = new Color(0x08, 0x0E, 0x1A);
    public static final Color BG_DARK      = new Color(0x0D, 0x16, 0x28);
    public static final Color BG_PANEL     = new Color(0x14, 0x22, 0x3C);
    public static final Color BG_ELEVATED  = new Color(0x1A, 0x2C, 0x4A);
    public static final Color BG_INPUT     = new Color(0x0A, 0x12, 0x22);

    public static final Color GOLD         = new Color(0xD4, 0xAF, 0x37);
    public static final Color GOLD_LIGHT   = new Color(0xF0, 0xD7, 0x6B);
    public static final Color GOLD_DIM     = new Color(0x9A, 0x7B, 0x1A);

    public static final Color TEXT_PRIMARY = new Color(0xE8, 0xEC, 0xF4);
    public static final Color TEXT_MUTED   = new Color(0x8A, 0x96, 0xB0);
    public static final Color TEXT_GOLD    = GOLD_LIGHT;

    public static final Color ACCENT       = new Color(0x2A, 0x5A, 0x9E);
    public static final Color SUCCESS      = new Color(0x3D, 0xB8, 0x6E);
    public static final Color WARNING      = new Color(0xE0, 0x8A, 0x2A);

    // Sized for 720p / 1280x960 readability without eating the whole window
    public static final Font  FONT_UI      = new Font("Segoe UI", Font.PLAIN, 13);
    public static final Font  FONT_TITLE   = new Font("Segoe UI", Font.BOLD, 16);
    public static final Font  FONT_HEADER  = new Font("Segoe UI", Font.BOLD, 13);
    public static final Font  FONT_MONO    = new Font("Consolas", Font.PLAIN, 12);

    private Theme() {}

    public static void apply() {
        try {
            UIManager.setLookAndFeel(UIManager.getCrossPlatformLookAndFeelClassName());
        } catch (Exception ignored) {
            // fall through with defaults
        }

        UIManager.put("Panel.background", BG_DARK);
        UIManager.put("Panel.foreground", TEXT_PRIMARY);
        UIManager.put("OptionPane.background", BG_PANEL);
        UIManager.put("OptionPane.messageForeground", TEXT_PRIMARY);
        UIManager.put("Label.foreground", TEXT_PRIMARY);
        UIManager.put("Label.font", FONT_UI);
        UIManager.put("Button.font", FONT_UI);
        UIManager.put("ToggleButton.font", FONT_UI);
        UIManager.put("CheckBox.font", FONT_UI);
        UIManager.put("CheckBox.foreground", TEXT_PRIMARY);
        UIManager.put("CheckBox.background", BG_PANEL);
        UIManager.put("TextField.background", BG_INPUT);
        UIManager.put("TextField.foreground", TEXT_PRIMARY);
        UIManager.put("TextField.caretForeground", GOLD);
        UIManager.put("TextField.selectionBackground", ACCENT);
        UIManager.put("TextField.font", FONT_UI);
        UIManager.put("TextArea.background", BG_INPUT);
        UIManager.put("TextArea.foreground", TEXT_PRIMARY);
        UIManager.put("TextArea.caretForeground", GOLD);
        UIManager.put("TextArea.font", FONT_MONO);
        UIManager.put("TabbedPane.background", BG_DARK);
        UIManager.put("TabbedPane.foreground", TEXT_PRIMARY);
        UIManager.put("TabbedPane.selected", BG_PANEL);
        UIManager.put("TabbedPane.contentAreaColor", BG_PANEL);
        UIManager.put("ScrollPane.background", BG_PANEL);
        UIManager.put("Viewport.background", BG_INPUT);
        UIManager.put("List.background", BG_INPUT);
        UIManager.put("List.foreground", TEXT_PRIMARY);
        UIManager.put("List.selectionBackground", ACCENT);
        UIManager.put("List.selectionForeground", TEXT_PRIMARY);
        UIManager.put("ComboBox.background", BG_INPUT);
        UIManager.put("ComboBox.foreground", TEXT_PRIMARY);
        UIManager.put("ComboBox.font", FONT_UI);
        UIManager.put("Slider.background", BG_PANEL);
        UIManager.put("Slider.foreground", GOLD);
        UIManager.put("TitledBorder.titleColor", GOLD);
        UIManager.put("TitledBorder.font", FONT_HEADER);
        UIManager.put("ToolTip.background", BG_ELEVATED);
        UIManager.put("ToolTip.foreground", TEXT_PRIMARY);
    }

    public static Border panelBorder() {
        return new CompoundBorder(
                new LineBorder(GOLD_DIM, 1),
                new EmptyBorder(10, 12, 10, 12));
    }

    public static Border goldLine() {
        return BorderFactory.createLineBorder(GOLD, 1);
    }
}
