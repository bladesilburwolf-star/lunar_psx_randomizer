package lunar.randomizer;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
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
 * Combined Lunar SSSC randomizer — enemies + item prices.
 * Dark blue / gold theme. Java 8 compatible Swing for Windows 7+.
 */
public class MainFrame extends JFrame {

    private final JTextField seedField = new JTextField("42", 10);
    private final JTextArea logArea = new JTextArea(5, 40);

    // Enemy
    private final JTextField enemyInField = new JTextField(28);
    private final JTextField enemyOutField = new JTextField(28);
    private final RangeSliderRow hpRow = new RangeSliderRow("HP");
    private final RangeSliderRow atkRow = new RangeSliderRow("ATK");
    private final RangeSliderRow defRow = new RangeSliderRow("DEF");
    private final RangeSliderRow expRow = new RangeSliderRow("EXP");
    private final RangeSliderRow silRow = new RangeSliderRow("Silver");
    private final JCheckBox shuffleCheck = new JCheckBox("Shuffle similar-level packs");
    private final JSpinner bandSpinner = new JSpinner(new SpinnerNumberModel(3, 1, 20, 1));

    // Items
    private final JTextField itemInField = new JTextField(28);
    private final JTextField itemOutField = new JTextField(28);
    private final RangeSliderRow priceRow = new RangeSliderRow("Price");

    public MainFrame() {
        super("Lunar Silver Star Story — Randomizer");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        // Fit 720p and 1280x960 comfortably; content scrolls inside tabs
        setMinimumSize(new Dimension(640, 480));
        setPreferredSize(new Dimension(900, 640));
        getContentPane().setBackground(Theme.BG_DARKEST);
        setLayout(new BorderLayout(0, 0));

        add(buildHeader(), BorderLayout.NORTH);
        add(buildBody(), BorderLayout.CENTER);
        add(buildFooter(), BorderLayout.SOUTH);

        // Defaults matching Python tools
        hpRow.setRange(0.75, 1.40);
        atkRow.setRange(0.80, 1.35);
        defRow.setRange(0.75, 1.40);
        expRow.setRange(0.70, 1.50);
        silRow.setRange(0.70, 1.50);
        priceRow.setRange(0.60, 1.75);

        shuffleCheck.setOpaque(false);
        shuffleCheck.setForeground(Theme.TEXT_PRIMARY);

        log("Ready. Load enemy_master.bin / item_master.bin, set seed & ranges, then Randomize.");
        log("After writing bins: use patch_exe.py / patch_item_exe.py (chain) and CDmage/tuximage to inject SLUS_006.28.");
        pack();
        setLocationRelativeTo(null);
    }

    private JPanel buildHeader() {
        JPanel p = new JPanel(new BorderLayout());
        p.setBackground(Theme.BG_DARK);
        p.setBorder(new EmptyBorder(12, 16, 8, 16));

        JLabel title = new JLabel("LUNAR  ·  SILVER STAR STORY COMPLETE");
        title.setFont(Theme.FONT_TITLE);
        title.setForeground(Theme.GOLD_LIGHT);

        JLabel sub = new JLabel("Enemy stats  ·  Item prices  ·  Seed-based");
        sub.setFont(Theme.FONT_UI);
        sub.setForeground(Theme.TEXT_MUTED);

        JPanel left = new JPanel();
        left.setOpaque(false);
        left.setLayout(new BoxLayout(left, BoxLayout.Y_AXIS));
        left.add(title);
        left.add(Box.createVerticalStrut(4));
        left.add(sub);

        JPanel seedPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 8, 0));
        seedPanel.setOpaque(false);
        JLabel seedL = new JLabel("Seed");
        seedL.setForeground(Theme.GOLD);
        styleField(seedField);
        seedField.setPreferredSize(new Dimension(100, 28));
        GoldButton rndSeed = new GoldButton("Random");
        rndSeed.setPreferredSize(new Dimension(90, 28));
        rndSeed.addActionListener(e -> seedField.setText(Long.toString(System.currentTimeMillis() & 0x7FFFFFFF)));
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
        // Each tab scrolls independently — works at 720p / 1280x960
        tabs.addTab("  Enemies  ", wrapScroll(buildEnemyPanel()));
        tabs.addTab("  Items  ", wrapScroll(buildItemPanel()));
        tabs.addTab("  Pipeline  ", wrapScroll(buildPipelinePanel()));

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
        logScroll.setHorizontalScrollBarPolicy(JScrollPane.HORIZONTAL_SCROLLBAR_AS_NEEDED);
        logScroll.setPreferredSize(new Dimension(100, 100));
        logScroll.setMinimumSize(new Dimension(100, 72));

        wrap.add(tabs, BorderLayout.CENTER);
        wrap.add(logScroll, BorderLayout.SOUTH);
        return wrap;
    }

    /** Vertical scrollbar for tab content on short screens. */
    private JScrollPane wrapScroll(JPanel content) {
        // Align content to top so BoxLayout panels don't stretch oddly
        JPanel holder = new JPanel(new BorderLayout());
        holder.setBackground(Theme.BG_PANEL);
        holder.add(content, BorderLayout.NORTH);

        JScrollPane sp = new JScrollPane(holder);
        sp.setBorder(BorderFactory.createEmptyBorder());
        sp.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED);
        sp.setHorizontalScrollBarPolicy(JScrollPane.HORIZONTAL_SCROLLBAR_AS_NEEDED);
        sp.getVerticalScrollBar().setUnitIncrement(16);
        sp.getHorizontalScrollBar().setUnitIncrement(16);
        sp.getViewport().setBackground(Theme.BG_PANEL);
        return sp;
    }

    private JPanel buildEnemyPanel() {
        JPanel p = new JPanel();
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBackground(Theme.BG_PANEL);
        p.setBorder(new EmptyBorder(8, 10, 12, 10));

        p.add(fileRow("Input", enemyInField, "enemy_master.bin", true));
        p.add(Box.createVerticalStrut(4));
        p.add(fileRow("Output", enemyOutField, "enemy_master_randomized.bin", false));
        p.add(Box.createVerticalStrut(8));

        JPanel ranges = section("Stat multipliers");
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
        run.setPreferredSize(new Dimension(160, 32));
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

        p.add(fileRow("Input", itemInField, "item_master.bin", true));
        p.add(Box.createVerticalStrut(4));
        p.add(fileRow("Output", itemOutField, "item_master_randomized.bin", false));
        p.add(Box.createVerticalStrut(8));

        JPanel ranges = section("Price multipliers");
        ranges.setLayout(new BoxLayout(ranges, BoxLayout.Y_AXIS));
        ranges.add(priceRow);
        JLabel note = new JLabel("Sell = buy ÷ 2. Buy=0 items stay free.");
        note.setForeground(Theme.TEXT_MUTED);
        note.setFont(Theme.FONT_UI);
        ranges.add(Box.createVerticalStrut(4));
        ranges.add(note);
        p.add(ranges);
        p.add(Box.createVerticalStrut(8));

        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        actions.setOpaque(false);
        GoldButton run = new GoldButton("Randomize Items");
        run.setPreferredSize(new Dimension(160, 32));
        run.addActionListener(e -> runItems());
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
            "Recommended pipeline\n\n"
          + "1. Extract tables from SLUS_006.28 (Python tools, once):\n"
          + "     python extract_enemy_table.py SLUS_006.28 -o enemy_master.bin\n"
          + "     python extract_item_table.py  SLUS_006.28 -o item_master.bin\n\n"
          + "2. Use this GUI to randomize the .bin tables (same seed for a full run).\n\n"
          + "3. Patch EXE — chain both patches:\n"
          + "     python patch_exe.py SLUS_006.28 enemy_master_randomized.bin -o step1.exe\n"
          + "     python patch_item_exe.py step1.exe item_master_randomized.bin -o SLUS_006.28\n\n"
          + "4. Inject with CDmage (Windows) or tuximage — replace SLUS_006.28 inside the CUE/BIN once.\n\n"
          + "Do not extract track01 as ISO and rebuild; that broke boots earlier.\n\n"
          + "Future tabs: shop inventories, party growth, disc tools (BIN/CUE, LUNADATA)."
        );
        p.add(help, BorderLayout.CENTER);
        return p;
    }

    private JPanel buildFooter() {
        JPanel p = new JPanel(new FlowLayout(FlowLayout.RIGHT, 12, 8));
        p.setBackground(Theme.BG_DARK);
        JLabel ver = new JLabel("v0.1.1  ·  scrollable  ·  720p OK  ·  Win7+");
        ver.setForeground(Theme.TEXT_MUTED);
        ver.setFont(Theme.FONT_UI);
        p.add(ver);
        return p;
    }

    private JPanel fileRow(String label, JTextField field, String defaultName, boolean open) {
        JPanel row = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 2));
        row.setOpaque(false);
        JLabel l = new JLabel(label);
        l.setForeground(Theme.GOLD);
        l.setPreferredSize(new Dimension(56, 22));
        styleField(field);
        field.setText(defaultName);
        field.setPreferredSize(new Dimension(280, 26));
        GoldButton browse = new GoldButton("Browse…");
        browse.setPreferredSize(new Dimension(90, 26));
        browse.addActionListener(e -> browseFile(field, open));
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

    private void browseFile(JTextField target, boolean open) {
        JFileChooser fc = new JFileChooser();
        fc.setFileFilter(new FileNameExtensionFilter("Binary tables (*.bin)", "bin"));
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
                // try relative to cwd / common locations
                File alt = new File("enemy_master.bin");
                if (!alt.isFile()) {
                    alt = new File("../enemy_randomizer/enemy_master.bin");
                }
                if (alt.isFile()) {
                    in = alt.toPath();
                    enemyInField.setText(in.toString());
                } else {
                    throw new IllegalArgumentException("Input not found: " + in);
                }
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

            int active = 0;
            for (EnemyTable.Enemy e : enemies) {
                if (e.isActive()) {
                    active++;
                }
            }
            log(String.format(
                    "Enemies: loaded %d (%d active) → wrote %s  seed=%d  HP[%.2f–%.2f] ATK[%.2f–%.2f]",
                    enemies.size(), active, out.toAbsolutePath(), seed,
                    ranges.hpMin, ranges.hpMax, ranges.atkMin, ranges.atkMax));
        } catch (Exception ex) {
            log("ERROR (enemies): " + ex.getMessage());
            JOptionPane.showMessageDialog(this, ex.getMessage(), "Enemy randomize",
                    JOptionPane.ERROR_MESSAGE);
        }
    }

    private void runItems() {
        try {
            long seed = readSeed();
            Path in = Paths.get(itemInField.getText().trim());
            Path out = Paths.get(itemOutField.getText().trim());
            if (!in.toFile().isFile()) {
                File alt = new File("item_master.bin");
                if (!alt.isFile()) {
                    alt = new File("../item_randomizer/item_master.bin");
                }
                if (alt.isFile()) {
                    in = alt.toPath();
                    itemInField.setText(in.toString());
                } else {
                    throw new IllegalArgumentException("Input not found: " + in);
                }
            }

            List<ItemTable.Item> items = ItemTable.load(in);
            ItemTable.Ranges ranges = new ItemTable.Ranges();
            ranges.priceMin = priceRow.getMin();
            ranges.priceMax = priceRow.getMax();
            List<ItemTable.Item> result = ItemTable.randomize(items, ranges, seed);
            ItemTable.save(out, result);

            int priced = 0;
            for (ItemTable.Item it : items) {
                if (it.isPriced()) {
                    priced++;
                }
            }
            log(String.format(
                    "Items: loaded %d (%d priced) → wrote %s  seed=%d  price[%.2f–%.2f×]",
                    items.size(), priced, out.toAbsolutePath(), seed,
                    ranges.priceMin, ranges.priceMax));
        } catch (Exception ex) {
            log("ERROR (items): " + ex.getMessage());
            JOptionPane.showMessageDialog(this, ex.getMessage(), "Item randomize",
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
