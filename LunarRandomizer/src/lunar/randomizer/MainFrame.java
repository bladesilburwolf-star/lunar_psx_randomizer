package lunar.randomizer;

import java.awt.BorderLayout;
import java.awt.Desktop;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.JCheckBox;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JSpinner;
import javax.swing.JTabbedPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SpinnerNumberModel;
import javax.swing.SwingUtilities;
import javax.swing.border.EmptyBorder;
import javax.swing.border.TitledBorder;
import javax.swing.filechooser.FileNameExtensionFilter;

/**
 * Multi-tab Lunar randomizer (PSX SSSC + GBA Legend).
 * Dark blue / gold theme. Scrollable for 720p. Java 8+.
 */
public class MainFrame extends JFrame {

    private final JTextField seedField = new JTextField("42", 10);
    private final JTextArea logArea = new JTextArea(5, 40);

    // PSX Enemies
    private final JTextField enemyInField = new JTextField(28);
    private final JTextField enemyOutField = new JTextField(28);
    private final RangeSliderRow hpRow = new RangeSliderRow("HP");
    private final RangeSliderRow atkRow = new RangeSliderRow("ATK");
    private final RangeSliderRow defRow = new RangeSliderRow("DEF");
    private final RangeSliderRow expRow = new RangeSliderRow("EXP");
    private final RangeSliderRow silRow = new RangeSliderRow("Silver");
    private final JCheckBox shuffleCheck = new JCheckBox("Shuffle similar-level packs");
    private final JSpinner bandSpinner = new JSpinner(new SpinnerNumberModel(3, 1, 20, 1));

    // PSX Items
    private final JTextField itemInField = new JTextField(28);
    private final JTextField itemOutField = new JTextField(28);
    private final RangeSliderRow priceRow = new RangeSliderRow("Price");

    // GBA Items
    private final JTextField gbaRomInField = new JTextField(28);
    private final JTextField gbaRomOutField = new JTextField(28);
    private final RangeSliderRow gbaPriceRow = new RangeSliderRow("Price");
    private final RangeSliderRow gbaStatRow = new RangeSliderRow("ATK");
    private final JCheckBox gbaStatsCheck = new JCheckBox("Also randomize combat stat", true);

    public MainFrame() {
        super("Lunar Randomizer — SSSC (PSX) + Legend (GBA)");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(640, 480));
        setPreferredSize(new Dimension(900, 640));
        getContentPane().setBackground(Theme.BG_DARKEST);
        setLayout(new BorderLayout(0, 0));

        add(buildHeader(), BorderLayout.NORTH);
        add(buildBody(), BorderLayout.CENTER);
        add(buildFooter(), BorderLayout.SOUTH);

        hpRow.setRange(0.75, 1.40);
        atkRow.setRange(0.80, 1.35);
        defRow.setRange(0.75, 1.40);
        expRow.setRange(0.70, 1.50);
        silRow.setRange(0.70, 1.50);
        priceRow.setRange(0.60, 1.75);
        gbaPriceRow.setRange(0.60, 1.75);
        gbaStatRow.setRange(0.80, 1.35);

        shuffleCheck.setOpaque(false);
        shuffleCheck.setForeground(Theme.TEXT_PRIMARY);
        gbaStatsCheck.setOpaque(false);
        gbaStatsCheck.setForeground(Theme.TEXT_PRIMARY);

        // Default paths relative to install dir
        File base = appDir();
        File dataPsx = new File(base, "data/psx");
        File toolsGba = new File(base, "tools/gba");
        enemyInField.setText(new File(dataPsx, "enemy_master.bin").getPath());
        enemyOutField.setText(new File(dataPsx, "enemy_master_randomized.bin").getPath());
        itemInField.setText(new File(dataPsx, "item_master.bin").getPath());
        itemOutField.setText(new File(dataPsx, "item_master_randomized.bin").getPath());
        gbaRomInField.setText(new File(toolsGba, "lunar.gba").getPath());
        gbaRomOutField.setText(new File(toolsGba, "lunar_randomized.gba").getPath());

        log("Lunar Randomizer ready — shared seed applies to all tabs.");
        log("PSX: randomize bins → tools/psx patch scripts → inject SLUS once (CDmage/tuximage).");
        log("GBA: patches ROM in place at 0x7FA424 (12-byte item records).");
        pack();
        setLocationRelativeTo(null);
    }

    private static File appDir() {
        try {
            File f = new File(MainFrame.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI()).getParentFile();
            if (f != null && f.isDirectory()) {
                return f;
            }
        } catch (Exception ignored) {
        }
        return new File(System.getProperty("user.dir", "."));
    }

    private JPanel buildHeader() {
        JPanel p = new JPanel(new BorderLayout());
        p.setBackground(Theme.BG_DARK);
        p.setBorder(new EmptyBorder(10, 14, 6, 14));

        JLabel title = new JLabel("LUNAR RANDOMIZER");
        title.setFont(Theme.FONT_TITLE);
        title.setForeground(Theme.GOLD_LIGHT);

        JLabel sub = new JLabel("PSX Complete  ·  GBA Legend  ·  one seed");
        sub.setFont(Theme.FONT_UI);
        sub.setForeground(Theme.TEXT_MUTED);

        JPanel left = new JPanel();
        left.setOpaque(false);
        left.setLayout(new BoxLayout(left, BoxLayout.Y_AXIS));
        left.add(title);
        left.add(Box.createVerticalStrut(2));
        left.add(sub);

        JPanel seedPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 8, 0));
        seedPanel.setOpaque(false);
        JLabel seedL = new JLabel("Seed");
        seedL.setForeground(Theme.GOLD);
        styleField(seedField);
        seedField.setPreferredSize(new Dimension(100, 26));
        GoldButton rndSeed = new GoldButton("Random");
        rndSeed.setPreferredSize(new Dimension(90, 26));
        rndSeed.addActionListener(e ->
                seedField.setText(Long.toString(System.currentTimeMillis() & 0x7FFFFFFF)));
        seedPanel.add(seedL);
        seedPanel.add(seedField);
        seedPanel.add(rndSeed);

        p.add(left, BorderLayout.WEST);
        p.add(seedPanel, BorderLayout.EAST);
        return p;
    }

    private JPanel buildBody() {
        JPanel wrap = new JPanel(new BorderLayout(6, 6));
        wrap.setBackground(Theme.BG_DARKEST);
        wrap.setBorder(new EmptyBorder(0, 8, 6, 8));

        JTabbedPane tabs = new JTabbedPane();
        tabs.setFont(Theme.FONT_HEADER);
        tabs.setBackground(Theme.BG_DARK);
        tabs.setForeground(Theme.TEXT_PRIMARY);
        tabs.addTab("  PSX Enemies  ", wrapScroll(buildEnemyPanel()));
        tabs.addTab("  PSX Items  ", wrapScroll(buildItemPanel()));
        tabs.addTab("  GBA Items  ", wrapScroll(buildGbaPanel()));
        tabs.addTab("  Pipeline  ", wrapScroll(buildPipelinePanel()));
        tabs.addTab("  Tools  ", wrapScroll(buildToolsPanel()));

        logArea.setEditable(false);
        logArea.setLineWrap(true);
        logArea.setWrapStyleWord(true);
        logArea.setBackground(Theme.BG_INPUT);
        logArea.setForeground(Theme.TEXT_PRIMARY);
        logArea.setCaretColor(Theme.GOLD);
        logArea.setFont(Theme.FONT_MONO);
        logArea.setBorder(new EmptyBorder(6, 6, 6, 6));
        JScrollPane logScroll = new JScrollPane(logArea);
        logScroll.setBorder(Theme.goldLine());
        logScroll.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_ALWAYS);
        logScroll.setPreferredSize(new Dimension(100, 100));
        logScroll.setMinimumSize(new Dimension(100, 72));

        wrap.add(tabs, BorderLayout.CENTER);
        wrap.add(logScroll, BorderLayout.SOUTH);
        return wrap;
    }

    private JScrollPane wrapScroll(JPanel content) {
        JPanel holder = new JPanel(new BorderLayout());
        holder.setBackground(Theme.BG_PANEL);
        holder.add(content, BorderLayout.NORTH);
        JScrollPane sp = new JScrollPane(holder);
        sp.setBorder(BorderFactory.createEmptyBorder());
        sp.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED);
        sp.setHorizontalScrollBarPolicy(JScrollPane.HORIZONTAL_SCROLLBAR_AS_NEEDED);
        sp.getVerticalScrollBar().setUnitIncrement(16);
        sp.getViewport().setBackground(Theme.BG_PANEL);
        return sp;
    }

    private JPanel buildEnemyPanel() {
        JPanel p = new JPanel();
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBackground(Theme.BG_PANEL);
        p.setBorder(new EmptyBorder(8, 10, 12, 10));

        p.add(fileRow("Input", enemyInField, true, "bin"));
        p.add(Box.createVerticalStrut(4));
        p.add(fileRow("Output", enemyOutField, false, "bin"));
        p.add(Box.createVerticalStrut(8));

        JPanel ranges = section("Stat multipliers (38-byte enemy records)");
        ranges.setLayout(new BoxLayout(ranges, BoxLayout.Y_AXIS));
        ranges.add(hpRow);
        ranges.add(atkRow);
        ranges.add(defRow);
        ranges.add(expRow);
        ranges.add(silRow);
        p.add(ranges);
        p.add(Box.createVerticalStrut(6));

        JPanel opts = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 2));
        opts.setOpaque(false);
        opts.add(shuffleCheck);
        JLabel bandL = new JLabel("Level band");
        bandL.setForeground(Theme.TEXT_MUTED);
        styleSpinner(bandSpinner);
        opts.add(bandL);
        opts.add(bandSpinner);
        p.add(opts);
        p.add(Box.createVerticalStrut(8));

        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        actions.setOpaque(false);
        GoldButton run = new GoldButton("Randomize Enemies");
        run.setPreferredSize(new Dimension(170, 32));
        run.addActionListener(e -> runEnemy());
        actions.add(run);
        p.add(actions);
        return p;
    }

    private JPanel buildItemPanel() {
        JPanel p = new JPanel();
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBackground(Theme.BG_PANEL);
        p.setBorder(new EmptyBorder(8, 10, 12, 10));

        p.add(fileRow("Input", itemInField, true, "bin"));
        p.add(Box.createVerticalStrut(4));
        p.add(fileRow("Output", itemOutField, false, "bin"));
        p.add(Box.createVerticalStrut(8));

        JPanel ranges = section("Price multipliers (18-byte PSX economy records)");
        ranges.setLayout(new BoxLayout(ranges, BoxLayout.Y_AXIS));
        ranges.add(priceRow);
        JLabel note = new JLabel("Sell = buy ÷ 2. Buy=0 (find-only) stays free. ATK table is separate.");
        note.setForeground(Theme.TEXT_MUTED);
        note.setFont(Theme.FONT_UI);
        ranges.add(Box.createVerticalStrut(4));
        ranges.add(note);
        p.add(ranges);
        p.add(Box.createVerticalStrut(8));

        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        actions.setOpaque(false);
        GoldButton run = new GoldButton("Randomize Items");
        run.setPreferredSize(new Dimension(170, 32));
        run.addActionListener(e -> runItems());
        actions.add(run);
        p.add(actions);
        return p;
    }

    private JPanel buildGbaPanel() {
        JPanel p = new JPanel();
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBackground(Theme.BG_PANEL);
        p.setBorder(new EmptyBorder(8, 10, 12, 10));

        p.add(fileRow("ROM in", gbaRomInField, true, "gba"));
        p.add(Box.createVerticalStrut(4));
        p.add(fileRow("ROM out", gbaRomOutField, false, "gba"));
        p.add(Box.createVerticalStrut(8));

        JPanel ranges = section("GBA item table @ 0x7FA424 (12-byte records)");
        ranges.setLayout(new BoxLayout(ranges, BoxLayout.Y_AXIS));
        ranges.add(gbaPriceRow);
        ranges.add(gbaStatRow);
        ranges.add(Box.createVerticalStrut(4));
        ranges.add(gbaStatsCheck);
        JLabel note = new JLabel("Patches buy/sell (+ optional ATK). Writes full 8MB ROM.");
        note.setForeground(Theme.TEXT_MUTED);
        note.setFont(Theme.FONT_UI);
        ranges.add(Box.createVerticalStrut(4));
        ranges.add(note);
        p.add(ranges);
        p.add(Box.createVerticalStrut(8));

        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        actions.setOpaque(false);
        GoldButton run = new GoldButton("Randomize GBA ROM");
        run.setPreferredSize(new Dimension(180, 32));
        run.addActionListener(e -> runGba());
        actions.add(run);
        p.add(actions);
        return p;
    }

    private JPanel buildPipelinePanel() {
        JPanel p = new JPanel(new BorderLayout());
        p.setBackground(Theme.BG_PANEL);
        p.setBorder(new EmptyBorder(10, 12, 12, 12));

        JTextArea help = new JTextArea();
        help.setEditable(false);
        help.setBackground(Theme.BG_PANEL);
        help.setForeground(Theme.TEXT_PRIMARY);
        help.setFont(Theme.FONT_UI);
        help.setLineWrap(true);
        help.setWrapStyleWord(true);
        help.setText(
            "PSX Silver Star Story Complete\n"
          + "────────────────────────────────\n"
          + "1. Extract (once) from SLUS_006.28:\n"
          + "     python tools/psx/extract_enemy_table.py data/psx/SLUS_006.28 -o data/psx/enemy_master.bin\n"
          + "     python tools/psx/extract_item_table.py  data/psx/SLUS_006.28 -o data/psx/item_master.bin\n\n"
          + "2. Use this GUI (same seed) on the PSX Enemies + PSX Items tabs.\n\n"
          + "3. Chain-patch the EXE:\n"
          + "     python tools/psx/patch_exe.py data/psx/SLUS_006.28 data/psx/enemy_master_randomized.bin -o step1.exe\n"
          + "     python tools/psx/patch_item_exe.py step1.exe data/psx/item_master_randomized.bin -o SLUS_006.28\n\n"
          + "4. Inject once with CDmage or: python tools/disc/tuximage.py …\n"
          + "   Do NOT rebuild track01.iso (that broke boots earlier).\n\n"
          + "GBA Lunar Legend\n"
          + "────────────────────────────────\n"
          + "GBA Items tab patches lunar.gba at 0x7FA424 directly (no compress step).\n"
          + "Enemy table on GBA is still unconfirmed — see docs/.\n\n"
          + "Shared seed is in the header and applies to every tab."
        );
        p.add(help, BorderLayout.CENTER);
        return p;
    }

    private JPanel buildToolsPanel() {
        JPanel p = new JPanel();
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBackground(Theme.BG_PANEL);
        p.setBorder(new EmptyBorder(10, 12, 12, 12));

        JLabel intro = new JLabel("Disc / extract helpers (Python, run from terminal)");
        intro.setForeground(Theme.GOLD);
        intro.setFont(Theme.FONT_HEADER);
        p.add(intro);
        p.add(Box.createVerticalStrut(8));

        p.add(toolLine("BIN/CUE viewer", "python tools/disc/bincue_gui.py"));
        p.add(toolLine("LUNADATA.FIL extract", "python tools/disc/lunadata_gui.py"));
        p.add(toolLine("CUE inject (tuximage)", "python tools/disc/tuximage.py"));
        p.add(Box.createVerticalStrut(10));

        JLabel docs = new JLabel("Notes live in docs/ (PSX item table, GBA research, r2, Ghidra GZF)");
        docs.setForeground(Theme.TEXT_MUTED);
        docs.setFont(Theme.FONT_UI);
        p.add(docs);
        p.add(Box.createVerticalStrut(10));

        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        actions.setOpaque(false);
        GoldButton openDocs = new GoldButton("Open docs folder");
        openDocs.setPreferredSize(new Dimension(160, 32));
        openDocs.addActionListener(e -> openFolder(new File(appDir(), "docs")));
        GoldButton openTools = new GoldButton("Open tools folder");
        openTools.setPreferredSize(new Dimension(160, 32));
        openTools.addActionListener(e -> openFolder(new File(appDir(), "tools")));
        actions.add(openDocs);
        actions.add(openTools);
        p.add(actions);
        return p;
    }

    private JLabel toolLine(String name, String cmd) {
        JLabel l = new JLabel("<html><b style='color:#F0D76B'>" + name + "</b>"
                + " &nbsp; <span style='color:#8A96B0;font-family:monospace'>" + cmd + "</span></html>");
        l.setFont(Theme.FONT_UI);
        return l;
    }

    private void openFolder(File dir) {
        try {
            if (!dir.isDirectory()) {
                throw new IllegalArgumentException("Missing: " + dir);
            }
            if (Desktop.isDesktopSupported()) {
                Desktop.getDesktop().open(dir);
            } else {
                log("Open manually: " + dir.getAbsolutePath());
            }
        } catch (Exception ex) {
            log("ERROR: " + ex.getMessage());
        }
    }

    private JPanel buildFooter() {
        JPanel p = new JPanel(new FlowLayout(FlowLayout.RIGHT, 12, 6));
        p.setBackground(Theme.BG_DARK);
        JLabel ver = new JLabel("v0.2  ·  multi-tab  ·  PSX + GBA  ·  Java 8+");
        ver.setForeground(Theme.TEXT_MUTED);
        ver.setFont(Theme.FONT_UI);
        p.add(ver);
        return p;
    }

    private JPanel fileRow(String label, JTextField field, boolean open, String ext) {
        JPanel row = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 2));
        row.setOpaque(false);
        JLabel l = new JLabel(label);
        l.setForeground(Theme.GOLD);
        l.setPreferredSize(new Dimension(56, 22));
        styleField(field);
        field.setPreferredSize(new Dimension(300, 26));
        GoldButton browse = new GoldButton("Browse…");
        browse.setPreferredSize(new Dimension(90, 26));
        browse.addActionListener(e -> browseFile(field, open, ext));
        row.add(l);
        row.add(field);
        row.add(browse);
        return row;
    }

    private JPanel section(String title) {
        JPanel p = new JPanel();
        p.setOpaque(false);
        TitledBorder tb = BorderFactory.createTitledBorder(
                BorderFactory.createLineBorder(Theme.GOLD_DIM), title);
        tb.setTitleColor(Theme.GOLD);
        tb.setTitleFont(Theme.FONT_HEADER);
        p.setBorder(tb);
        return p;
    }

    private void styleField(JTextField f) {
        f.setBackground(Theme.BG_INPUT);
        f.setForeground(Theme.TEXT_PRIMARY);
        f.setCaretColor(Theme.GOLD);
        f.setFont(Theme.FONT_MONO);
        f.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(Theme.GOLD_DIM),
                new EmptyBorder(4, 6, 4, 6)));
    }

    private void styleSpinner(JSpinner s) {
        s.setFont(Theme.FONT_UI);
        JTextField tf = ((JSpinner.DefaultEditor) s.getEditor()).getTextField();
        tf.setBackground(Theme.BG_INPUT);
        tf.setForeground(Theme.TEXT_PRIMARY);
        tf.setCaretColor(Theme.GOLD);
    }

    private void browseFile(JTextField target, boolean open, String ext) {
        JFileChooser fc = new JFileChooser();
        if ("gba".equals(ext)) {
            fc.setFileFilter(new FileNameExtensionFilter("GBA ROM (*.gba)", "gba"));
        } else {
            fc.setFileFilter(new FileNameExtensionFilter("Binary (*.bin)", "bin"));
        }
        File cur = new File(target.getText().trim());
        if (cur.getParentFile() != null && cur.getParentFile().isDirectory()) {
            fc.setCurrentDirectory(cur.getParentFile());
        }
        int result = open ? fc.showOpenDialog(this) : fc.showSaveDialog(this);
        if (result == JFileChooser.APPROVE_OPTION) {
            target.setText(fc.getSelectedFile().getAbsolutePath());
        }
    }

    private long readSeed() {
        try {
            return Long.parseLong(seedField.getText().trim());
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException("Seed must be an integer");
        }
    }

    private void runEnemy() {
        try {
            long seed = readSeed();
            Path in = Paths.get(enemyInField.getText().trim());
            Path out = Paths.get(enemyOutField.getText().trim());
            if (!in.toFile().isFile()) {
                throw new IllegalArgumentException("Input not found: " + in);
            }
            List<EnemyTable.Enemy> enemies = EnemyTable.load(in);
            EnemyTable.Ranges ranges = new EnemyTable.Ranges();
            ranges.hpMin = hpRow.getMin();
            ranges.hpMax = hpRow.getMax();
            ranges.atkMin = atkRow.getMin();
            ranges.atkMax = atkRow.getMax();
            ranges.defMin = defRow.getMin();
            ranges.defMax = defRow.getMax();
            ranges.expMin = expRow.getMin();
            ranges.expMax = expRow.getMax();
            ranges.silverMin = silRow.getMin();
            ranges.silverMax = silRow.getMax();
            int band = ((Number) bandSpinner.getValue()).intValue();
            List<EnemyTable.Enemy> result = EnemyTable.randomize(
                    enemies, ranges, seed, shuffleCheck.isSelected(), band);
            EnemyTable.save(out, result);
            log(String.format("PSX enemies → %s  seed=%d  count=%d",
                    out.toAbsolutePath(), seed, result.size()));
        } catch (Exception ex) {
            log("ERROR (enemies): " + ex.getMessage());
            JOptionPane.showMessageDialog(this, ex.getMessage(), "PSX Enemies",
                    JOptionPane.ERROR_MESSAGE);
        }
    }

    private void runItems() {
        try {
            long seed = readSeed();
            Path in = Paths.get(itemInField.getText().trim());
            Path out = Paths.get(itemOutField.getText().trim());
            if (!in.toFile().isFile()) {
                throw new IllegalArgumentException("Input not found: " + in);
            }
            List<ItemTable.Item> items = ItemTable.load(in);
            ItemTable.Ranges ranges = new ItemTable.Ranges();
            ranges.priceMin = priceRow.getMin();
            ranges.priceMax = priceRow.getMax();
            List<ItemTable.Item> result = ItemTable.randomize(items, ranges, seed);
            ItemTable.save(out, result);
            log(String.format("PSX items → %s  seed=%d  count=%d",
                    out.toAbsolutePath(), seed, result.size()));
        } catch (Exception ex) {
            log("ERROR (items): " + ex.getMessage());
            JOptionPane.showMessageDialog(this, ex.getMessage(), "PSX Items",
                    JOptionPane.ERROR_MESSAGE);
        }
    }

    private void runGba() {
        try {
            long seed = readSeed();
            Path in = Paths.get(gbaRomInField.getText().trim());
            Path out = Paths.get(gbaRomOutField.getText().trim());
            if (!in.toFile().isFile()) {
                throw new IllegalArgumentException("ROM not found: " + in);
            }
            List<GbaItemTable.Item> items = GbaItemTable.loadFromRom(in, GbaItemTable.DEFAULT_COUNT);
            GbaItemTable.Ranges ranges = new GbaItemTable.Ranges();
            ranges.priceMin = gbaPriceRow.getMin();
            ranges.priceMax = gbaPriceRow.getMax();
            ranges.statMin = gbaStatRow.getMin();
            ranges.statMax = gbaStatRow.getMax();
            ranges.randomizeStats = gbaStatsCheck.isSelected();
            List<GbaItemTable.Item> result = GbaItemTable.randomize(items, ranges, seed);
            GbaItemTable.patchRom(in, out, result);
            log(String.format("GBA ROM → %s  seed=%d  records=%d  stats=%s",
                    out.toAbsolutePath(), seed, result.size(),
                    ranges.randomizeStats ? "on" : "off"));
        } catch (Exception ex) {
            log("ERROR (GBA): " + ex.getMessage());
            JOptionPane.showMessageDialog(this, ex.getMessage(), "GBA Items",
                    JOptionPane.ERROR_MESSAGE);
        }
    }

    private void log(String msg) {
        logArea.append(msg + "\n");
        logArea.setCaretPosition(logArea.getDocument().getLength());
    }

    public static void main(String[] args) {
        Theme.apply();
        SwingUtilities.invokeLater(new Runnable() {
            @Override
            public void run() {
                new MainFrame().setVisible(true);
            }
        });
    }
}
