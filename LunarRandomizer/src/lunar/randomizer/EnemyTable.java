package lunar.randomizer;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Lunar SSSC enemy master table: 128 × 38-byte (0x26) records.
 * Field layout matches wdtools / enemy_randomizer.py.
 */
public final class EnemyTable {

    public static final int RECORD_SIZE = 0x26;
    public static final int NUM_RECORDS = 128;

    public static final class Enemy {
        public int type;
        public int level;
        public int hp;
        public int attack;
        public int defense;
        public int agility;
        public int wisdom;
        public int magicDefense;
        public int exp;
        public int silver;
        public final byte[] raw; // full 38-byte record

        public Enemy(byte[] record) {
            if (record.length != RECORD_SIZE) {
                throw new IllegalArgumentException("Enemy record must be 38 bytes");
            }
            this.raw = record.clone();
            ByteBuffer bb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
            type = raw[0] & 0xFF;
            level = raw[1] & 0xFF;
            hp = bb.getShort(0x02) & 0xFFFF;
            attack = bb.getShort(0x04) & 0xFFFF;
            defense = bb.getShort(0x06) & 0xFFFF;
            agility = bb.getShort(0x08) & 0xFFFF;
            wisdom = bb.getShort(0x0A) & 0xFFFF;
            magicDefense = bb.getShort(0x0C) & 0xFFFF;
            exp = bb.getShort(0x1A) & 0xFFFF;
            silver = bb.getShort(0x1C) & 0xFFFF;
        }

        public byte[] pack() {
            byte[] out = raw.clone();
            ByteBuffer bb = ByteBuffer.wrap(out).order(ByteOrder.LITTLE_ENDIAN);
            out[0] = (byte) (type & 0xFF);
            out[1] = (byte) (level & 0xFF);
            bb.putShort(0x02, (short) clampU16(hp));
            bb.putShort(0x04, (short) clampU16(attack));
            bb.putShort(0x06, (short) clampU16(defense));
            bb.putShort(0x08, (short) clampU16(agility));
            bb.putShort(0x0A, (short) clampU16(wisdom));
            bb.putShort(0x0C, (short) clampU16(magicDefense));
            bb.putShort(0x1A, (short) clampU16(exp));
            bb.putShort(0x1C, (short) clampU16(silver));
            return out;
        }

        /** Skip empty / sentinel slots. */
        public boolean isActive() {
            return level >= 1 && hp >= 5;
        }
    }

    public static final class Ranges {
        public double hpMin = 0.75, hpMax = 1.40;
        public double atkMin = 0.80, atkMax = 1.35;
        public double defMin = 0.75, defMax = 1.40;
        public double expMin = 0.70, expMax = 1.50;
        public double silverMin = 0.70, silverMax = 1.50;
    }

    public static List<Enemy> load(Path path) throws IOException {
        byte[] data = Files.readAllBytes(path);
        if (data.length % RECORD_SIZE != 0) {
            throw new IOException("File size " + data.length + " is not a multiple of " + RECORD_SIZE);
        }
        int n = data.length / RECORD_SIZE;
        List<Enemy> list = new ArrayList<Enemy>(n);
        for (int i = 0; i < n; i++) {
            byte[] rec = new byte[RECORD_SIZE];
            System.arraycopy(data, i * RECORD_SIZE, rec, 0, RECORD_SIZE);
            list.add(new Enemy(rec));
        }
        return list;
    }

    public static void save(Path path, List<Enemy> enemies) throws IOException {
        byte[] out = new byte[enemies.size() * RECORD_SIZE];
        for (int i = 0; i < enemies.size(); i++) {
            byte[] rec = enemies.get(i).pack();
            System.arraycopy(rec, 0, out, i * RECORD_SIZE, RECORD_SIZE);
        }
        Files.write(path, out);
    }

    public static List<Enemy> randomize(List<Enemy> source, Ranges ranges, long seed,
                                        boolean shuffleSimilar, int levelBand) {
        Random rng = new Random(seed);
        List<Enemy> result = new ArrayList<Enemy>(source.size());
        for (Enemy e : source) {
            result.add(new Enemy(e.pack()));
        }

        for (Enemy e : result) {
            if (!e.isActive()) {
                continue;
            }
            e.hp = scale(rng, e.hp, ranges.hpMin, ranges.hpMax);
            e.attack = scale(rng, e.attack, ranges.atkMin, ranges.atkMax);
            e.defense = scale(rng, e.defense, ranges.defMin, ranges.defMax);
            e.exp = scale(rng, e.exp, ranges.expMin, ranges.expMax);
            e.silver = scale(rng, e.silver, ranges.silverMin, ranges.silverMax);
        }

        if (shuffleSimilar && result.size() > 1) {
            Map<Integer, List<Integer>> bands = new HashMap<Integer, List<Integer>>();
            for (int i = 0; i < result.size(); i++) {
                Enemy e = result.get(i);
                if (!e.isActive()) {
                    continue;
                }
                int key = e.level / Math.max(1, levelBand);
                List<Integer> idxs = bands.get(key);
                if (idxs == null) {
                    idxs = new ArrayList<Integer>();
                    bands.put(key, idxs);
                }
                idxs.add(i);
            }
            for (List<Integer> idxs : bands.values()) {
                if (idxs.size() < 2) {
                    continue;
                }
                List<int[]> packs = new ArrayList<int[]>();
                for (int i : idxs) {
                    Enemy e = result.get(i);
                    packs.add(new int[] { e.hp, e.attack, e.defense, e.exp, e.silver });
                }
                Collections.shuffle(packs, rng);
                for (int j = 0; j < idxs.size(); j++) {
                    Enemy e = result.get(idxs.get(j));
                    int[] p = packs.get(j);
                    e.hp = p[0];
                    e.attack = p[1];
                    e.defense = p[2];
                    e.exp = p[3];
                    e.silver = p[4];
                }
            }
        }

        return result;
    }

    private static int scale(Random rng, int value, double lo, double hi) {
        if (value <= 0) {
            return value;
        }
        double factor = lo + rng.nextDouble() * (hi - lo);
        return Math.max(1, (int) Math.round(value * factor));
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
