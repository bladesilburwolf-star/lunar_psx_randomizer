package lunar.randomizer;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.util.Hashtable;

import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JSlider;
import javax.swing.SwingConstants;
import javax.swing.event.ChangeEvent;
import javax.swing.event.ChangeListener;

/**
 * Min/max multiplier pair as two sliders (percent 25–250 → 0.25–2.50).
 */
public class RangeSliderRow extends JPanel {

    private final JSlider minSlider;
    private final JSlider maxSlider;
    private final JLabel valueLabel;

    public RangeSliderRow(String label) {
        setOpaque(false);
        setLayout(new GridBagLayout());
        GridBagConstraints c = new GridBagConstraints();
        c.insets = new Insets(1, 2, 1, 2);
        c.anchor = GridBagConstraints.WEST;

        JLabel name = new JLabel(label);
        name.setForeground(Theme.TEXT_GOLD);
        name.setFont(Theme.FONT_UI);
        name.setPreferredSize(new Dimension(56, 20));
        c.gridx = 0;
        c.gridy = 0;
        c.gridheight = 2;
        add(name, c);

        c.gridheight = 1;
        c.fill = GridBagConstraints.HORIZONTAL;
        c.weightx = 1.0;

        minSlider = makeSlider(75);
        maxSlider = makeSlider(140);

        JLabel minL = new JLabel("Min");
        minL.setForeground(Theme.TEXT_MUTED);
        minL.setFont(Theme.FONT_UI);
        c.gridx = 1;
        c.gridy = 0;
        c.weightx = 0;
        add(minL, c);
        c.gridx = 2;
        c.weightx = 1.0;
        add(minSlider, c);

        JLabel maxL = new JLabel("Max");
        maxL.setForeground(Theme.TEXT_MUTED);
        maxL.setFont(Theme.FONT_UI);
        c.gridx = 1;
        c.gridy = 1;
        c.weightx = 0;
        add(maxL, c);
        c.gridx = 2;
        c.weightx = 1.0;
        add(maxSlider, c);

        valueLabel = new JLabel(" ");
        valueLabel.setForeground(Theme.TEXT_PRIMARY);
        valueLabel.setFont(Theme.FONT_MONO);
        valueLabel.setPreferredSize(new Dimension(100, 20));
        c.gridx = 3;
        c.gridy = 0;
        c.gridheight = 2;
        c.weightx = 0;
        add(valueLabel, c);

        ChangeListener sync = new ChangeListener() {
            @Override
            public void stateChanged(ChangeEvent e) {
                if (minSlider.getValue() > maxSlider.getValue()) {
                    if (e.getSource() == minSlider) {
                        maxSlider.setValue(minSlider.getValue());
                    } else {
                        minSlider.setValue(maxSlider.getValue());
                    }
                }
                updateLabel();
            }
        };
        minSlider.addChangeListener(sync);
        maxSlider.addChangeListener(sync);
        updateLabel();
    }

    private JSlider makeSlider(int initialPct) {
        JSlider s = new JSlider(25, 250, initialPct);
        s.setMajorTickSpacing(50);
        s.setMinorTickSpacing(25);
        s.setPaintTicks(true);
        s.setOpaque(false);
        s.setForeground(Theme.GOLD);
        s.setBackground(Theme.BG_PANEL);
        Hashtable<Integer, JLabel> labels = new Hashtable<Integer, JLabel>();
        labels.put(50, tick("0.5×"));
        labels.put(100, tick("1×"));
        labels.put(150, tick("1.5×"));
        labels.put(200, tick("2×"));
        s.setLabelTable(labels);
        s.setPaintLabels(true);
        s.setPreferredSize(new Dimension(200, 36));
        return s;
    }

    private static JLabel tick(String t) {
        JLabel l = new JLabel(t, SwingConstants.CENTER);
        l.setForeground(Theme.TEXT_MUTED);
        l.setFont(Theme.FONT_UI.deriveFont(10f));
        return l;
    }

    private void updateLabel() {
        valueLabel.setText(String.format("%.2f× – %.2f×", getMin(), getMax()));
    }

    public double getMin() {
        return minSlider.getValue() / 100.0;
    }

    public double getMax() {
        return maxSlider.getValue() / 100.0;
    }

    public void setRange(double min, double max) {
        minSlider.setValue((int) Math.round(min * 100));
        maxSlider.setValue((int) Math.round(max * 100));
        updateLabel();
    }
}
