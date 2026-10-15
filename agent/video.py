"""Vertical 1080x1920 text-story video, ffmpeg only (no GPU, no paid APIs)."""
import pathlib
import shutil
import subprocess
import textwrap

FONT = next((p for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf") if pathlib.Path(p).exists()), None)


def render(lines, out="out/story.mp4", secs=4):
    if not lines:
        raise ValueError("no lines")
    if not FONT:
        raise RuntimeError("DejaVu font not installed (apt install fonts-dejavu-core)")
    out_path = pathlib.Path(out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / "seg"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    listing = []
    for i, line in enumerate(lines):
        txt, seg = work / f"t{i}.txt", work / f"s{i}.mp4"
        txt.write_text("\n".join(textwrap.wrap(line, 22)))
        vf = (f"drawtext=fontfile={FONT}:textfile={txt}:fontcolor=white:fontsize=64:line_spacing=18:"
              "x=(w-text_w)/2:y=(h-text_h)/2")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x101418:s=1080x1920:d={secs}:r=30",
             "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(secs), "-vf", vf,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(seg)],
            check=True, capture_output=True, timeout=120)
        listing.append(f"file '{seg}'")
    (work / "list.txt").write_text("\n".join(listing))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"),
                    "-c", "copy", str(out_path)], check=True, capture_output=True, timeout=120)
    return str(out_path)
