package lunar.randomizer;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Lunar SSSC item economy table: 72 × 18-byte (0x12) records.
 * buy @0, sell @2 (sell always buy/2). Other bytes preserved.
 * Matches Claude item_randomizer / NOTES.md @ decomp 0x99244.
 */
public final class ItemTable {

    public static final int RECORD_SIZE = 0x12;
    public static final int NUM_RECORDS = 72;

    public static final class Item {
        public int buy;
        public int sell;
        public int stat;   // offset 0x0A, u8. CONFIRMED: ATK for weapons /
                            // DEF-analog for other categories. Cross-verified
                            // 20/20 exact matches against GBA Lunar Legend's
                            // equivalent item stat. See item_randomizer/NOTES.md.
        public final byte[] raw;

        public Item(byte[] record) {
            if (record.length != RECORD_SIZE) {
                throw new IllegalArgumentException("Item record must be 18 bytes");
            }
            this.raw = record.clone();
            ByteBuffer bb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
            buy = bb.getShort(0) & 0xFFFF;
            sell = bb.getShort(2) & 0xFFFF;
            stat = raw[0x0A] & 0xFF;
        }

        public byte[] pack() {
            byte[] out = raw.clone();
            ByteBuffer bb = ByteBuffer.wrap(out).order(ByteOrder.LITTLE_ENDIAN);
            bb.putShort(0, (short) clampU16(buy));
            bb.putShort(2, (short) clampU16(sell));
            out[0x0A] = (byte) clampU8(stat);
            return out;
        }

        public boolean isPriced() {
            return buy > 0;
        }

        public boolean hasStat() {
            return stat > 0;
        }
    }

    public static final class Ranges {
        public double priceMin = 0.60;
        public double priceMax = 1.75;
        public double statMin = 0.75;
        public double statMax = 1.50;
    }

    public static List<Item> load(Path path) throws IOException {
        byte[] data = Files.readAllBytes(path);
        if (data.length % RECORD_SIZE != 0) {
            throw new IOException("File size " + data.length + " is not a multiple of " + RECORD_SIZE);
        }
        int n = data.length / RECORD_SIZE;
        List<Item> list = new ArrayList<Item>(n);
        for (int i = 0; i < n; i++) {
            byte[] rec = new byte[RECORD_SIZE];
            System.arraycopy(data, i * RECORD_SIZE, rec, 0, RECORD_SIZE);
            list.add(new Item(rec));
        }
        return list;
    }

    public static void save(Path path, List<Item> items) throws IOException {
        byte[] out = new byte[items.size() * RECORD_SIZE];
        for (int i = 0; i < items.size(); i++) {
            byte[] rec = items.get(i).pack();
            System.arraycopy(rec, 0, out, i * RECORD_SIZE, RECORD_SIZE);
        }
        Files.write(path, out);
    }

    public static List<Item> randomize(List<Item> source, Ranges ranges, long seed) {
        Random rng = new Random(seed);
        List<Item> result = new ArrayList<Item>(source.size());
        for (Item it : source) {
            Item copy = new Item(it.pack());
            if (copy.isPriced()) {
                double factor = ranges.priceMin + rng.nextDouble() * (ranges.priceMax - ranges.priceMin);
                int newBuy = Math.max(1, (int) Math.round(copy.buy * factor));
                copy.buy = clampU16(newBuy);
                copy.sell = clampU16(copy.buy / 2);
            }
            if (copy.hasStat()) {
                double sFactor = ranges.statMin + rng.nextDouble() * (ranges.statMax - ranges.statMin);
                int newStat = Math.max(1, (int) Math.round(copy.stat * sFactor));
                copy.stat = clampU8(newStat);
            }
            result.add(copy);
        }
        return result;
    }

    private static int clampU16(int v) {
        if (v < 0) {
            return 0;
        }
        if (v > 0xFFFF) {
            return 0xFFFF;
        }
        return v;
    }

    private static int clampU8(int v) {
        if (v < 0) {
            return 0;
        }
        if (v > 0xFF) {
            return 0xFF;
        }
        return v;
    }
}
