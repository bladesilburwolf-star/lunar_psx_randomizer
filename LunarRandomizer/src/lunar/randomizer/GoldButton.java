package lunar.randomizer;

import java.awt.Color;
import java.awt.Cursor;
import java.awt.Dimension;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;

import javax.swing.JButton;

/** Flat dark-blue button with gold border / text. */
public class GoldButton extends JButton {

    private boolean hover;
    private boolean press;

    public GoldButton(String text) {
        super(text);
        setFocusPainted(false);
        setContentAreaFilled(false);
        setBorderPainted(false);
        setForeground(Theme.GOLD_LIGHT);
        setFont(Theme.FONT_HEADER);
        setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        setPreferredSize(new Dimension(140, 34));

        addMouseListener(new MouseAdapter() {
            @Override
            public void mouseEntered(MouseEvent e) {
                hover = true;
                repaint();
            }

            @Override
            public void mouseExited(MouseEvent e) {
                hover = false;
                press = false;
                repaint();
            }

            @Override
            public void mousePressed(MouseEvent e) {
                press = true;
                repaint();
            }

            @Override
            public void mouseReleased(MouseEvent e) {
                press = false;
                repaint();
            }
        });
    }

    @Override
    protected void paintComponent(Graphics g) {
        Graphics2D g2 = (Graphics2D) g.create();
        g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

        Color fill = press ? Theme.BG_ELEVATED : (hover ? Theme.BG_ELEVATED : Theme.BG_PANEL);
        g2.setColor(fill);
        g2.fillRoundRect(0, 0, getWidth() - 1, getHeight() - 1, 6, 6);

        g2.setColor(isEnabled() ? Theme.GOLD : Theme.GOLD_DIM);
        g2.drawRoundRect(0, 0, getWidth() - 1, getHeight() - 1, 6, 6);

        g2.setColor(isEnabled() ? Theme.GOLD_LIGHT : Theme.TEXT_MUTED);
        g2.setFont(getFont());
        FontMetrics fm = g2.getFontMetrics();
        String t = getText();
        int x = (getWidth() - fm.stringWidth(t)) / 2;
        int y = (getHeight() + fm.getAscent() - fm.getDescent()) / 2;
        g2.drawString(t, x, y);
        g2.dispose();
    }
}
