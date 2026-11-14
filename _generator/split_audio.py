# Cuts the whole-test recordings (tests 1-10 and 16-26, one MP3 each) into the four sections, so each section
# of a test page can have its own player. Tests 11-15 already come as four files.
# Run after parse_sources.py (which lists the whole recordings in data/tests.json):
#   python -X utf8 -I _generator/split_audio.py            (needs ffmpeg on the PATH)
# Writes audio/test-NN-s1.mp3 ... s4.mp3 (no re-encoding), replaces the 'Whole test' entry of data/tests.json by the
# four sections and removes the whole recording from audio/.
#
# Where the cuts are: after the 30 or 60 seconds of silence in which the student checks the answers of a section
# (the recording says "That is the end of Section 1. You now have ... to check your answers"), just before the
# "Now turn to Section 2" announcement. The times were found with ffmpeg's silencedetect (-30 dB, 8 s): a check
# silence of 28-60 s, then 6-24 s of speech, then the next reading silence; for tests 1-10 they were compared with the
# tapescripts ("end of part N" positions), which agree within the speed differences of the voices.
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEAD = 0.4  # seconds kept before the announcement, so "Now turn to..." is not clipped

# test number: the three section boundaries in seconds (end of the check silence of sections 1, 2 and 3)
CUTS = {
    1: (348.4, 729.5, 1151.5),
    2: (491.8, 900.8, 1399.5),
    3: (489.9, 972.5, 1410.5),
    4: (443.3, 778.1, 1237.0),
    5: (445.3, 863.6, 1296.3),
    6: (339.9, 698.5, 992.6),
    7: (546.7, 971.6, 1549.0),
    8: (404.8, 751.5, 1155.5),
    9: (370.3, 739.9, 1062.4),
    10: (414.8, 826.8, 1425.3),
    16: (345.9, 748.8, 1124.5),
    17: (449.6, 945.5, 1366.8),
    18: (396.6, 689.5, 1047.9),
    19: (438.6, 719.0, 1102.7),
    20: (439.1, 753.8, 1067.9),
    21: (433.9, 969.2, 1408.5),
    22: (420.1, 802.0, 1148.1),
    23: (484.9, 939.5, 1350.8),
    24: (458.0, 904.3, 1325.9),
    25: (553.7, 983.1, 1425.0),
    26: (518.4, 1002.0, 1494.2),
}


def cut(src, dst, start, end):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    subprocess.run(cmd + ["-c", "copy", str(dst)], check=True)


def main():
    path = ROOT / "data" / "tests.json"
    tests = json.loads(path.read_text(encoding="utf-8"))
    for t in tests:
        n = t["n"]
        if len(t["audio"]) != 1:
            continue
        src = ROOT / t["audio"][0]["file"]
        marks = [0.0] + [c - LEAD for c in CUTS[n]] + [None]
        audio = []
        for s in range(4):
            name = f"audio/test-{n:02d}-s{s + 1}.mp3"
            cut(src, ROOT / name, marks[s], marks[s + 1])
            audio.append({"label": f"Section {s + 1}", "file": name})
        t["audio"] = audio
        src.unlink()
        print(f"Test {n}: 4 sections")
    path.write_text(json.dumps(tests, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


main()
