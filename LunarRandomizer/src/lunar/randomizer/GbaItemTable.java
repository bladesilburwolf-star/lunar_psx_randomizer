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
 * Lunar Legend (GBA) combined item table at ROM 0x7FA424.
 * 12-byte records: buy u16, sell u16, …, primary stat u16 @ +6.
 */
public final class GbaItemTable {

    public static final int TABLE_OFF = 0x7FA424;
    public static final int RECORD_SIZE = 12;
    public static final int DEFAULT_COUNT = 200;

    public static final class Item {
        public int buy;
        public int sell;
        public int stat;
        public final byte[] raw;

        public Item(byte[] record) {
            this.raw = record.clone();
            ByteBuffer bb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
            buy = bb.getShort(0) & 0xFFFF;
            sell = bb.getShort(2) & 0xFFFF;
            stat = bb.getShort(6) & 0xFFFF;
        }

        public byte[] pack() {
            byte[] out = raw.clone();
            ByteBuffer bb = ByteBuffer.wrap(out).order(ByteOrder.LITTLE_ENDIAN);
            bb.putShort(0, (short) clampU16(buy));
            bb.putShort(2, (short) clampU16(sell));
            bb.putShort(6, (short) clampU16(stat));
            return out;
        }

        public boolean isPriced() {
            return buy > 0 && buy < 30000;
        }
    }

    public static final class Ranges {
        public double priceMin = 0.60;
        public double priceMax = 1.75;
        public double statMin = 0.80;
        public double statMax = 1.35;
        public boolean randomizeStats = true;
    }

    public static List<Item> loadFromRom(Path rom, int count) throws IOException {
        byte[] data = Files.readAllBytes(rom);
        if (data.length < TABLE_OFF + count * RECORD_SIZE) {
            throw new IOException("ROM too small for item table at 0x7FA424");
        }
        List<Item> list = new ArrayList<Item>(count);
        for (int i = 0; i < count; i++) {
            byte[] rec = new byte[RECORD_SIZE];
            System.arraycopy(data, TABLE_OFF + i * RECORD_SIZE, rec, 0, RECORD_SIZE);
            list.add(new Item(rec));
        }
        return list;
    }

    public static void patchRom(Path inRom, Path outRom, List<Item> items) throws IOException {
        byte[] data = Files.readAllBytes(inRom);
        for (int i = 0; i < items.size(); i++) {
            byte[] rec = items.get(i).pack();
            System.arraycopy(rec, 0, data, TABLE_OFF + i * RECORD_SIZE, RECORD_SIZE);
        }
        Files.write(outRom, data);
    }

    public static List<Item> randomize(List<Item> source, Ranges ranges, long seed) {
        Random rng = new Random(seed);
        List<Item> result = new ArrayList<Item>(source.size());
        for (Item it : source) {
            Item copy = new Item(it.pack());
            if (copy.isPriced()) {
                double pf = ranges.priceMin + rng.nextDouble() * (ranges.priceMax - ranges.priceMin);
                copy.buy = clampU16(Math.max(1, (int) Math.round(copy.buy * pf)));
                copy.sell = clampU16(copy.buy / 2);
            }
            if (ranges.randomizeStats && copy.stat > 0 && copy.stat < 300) {
                double sf = ranges.statMin + rng.nextDouble() * (ranges.statMax - ranges.statMin);
                copy.stat = clampU16(Math.max(1, (int) Math.round(copy.stat * sf)));
                if (copy.stat > 255) {
                    copy.stat = 255;
                }
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
}
