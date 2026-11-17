#!/bin/bash
# Render Rain Garden 3 jam — pola sama dgn render_final.sh (per irisan 900 dtk, tahan restart).
# Irisan dasar A/B/C/D dari merge 1 jam; urutan concat: 1 B C D A B C D A B C 12
set -u
SRC=/home/hatch/workspace/projects/asmr-tools/media/video/merge_loop_Rain_falling_in_garden_7f0c1a96_720p.mp4
WORK=/home/hatch/workspace/asmr-service/work
OUT=/home/hatch/workspace/asmr-service/output/rain-sounds-for-sleep-rain-falling-in-a-quiet-garden-3-hours.mp4
STATUS=$WORK/render3h_status.txt
ENC=(-c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p -c:a aac -b:a 256k)
echo "START $(date)" >> "$STATUS"

seg_ok () {
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null) || return 1
  awk "BEGIN{exit !($d>=899 && $d<=901)}"
}

# irisan polos
for spec in "a 0" "b 900" "c 1800" "d 2700"; do
  set -- $spec; name=$1; off=$2
  if ! seg_ok $WORK/s3h_$name.mp4; then
    ffmpeg -y -v error -ss $off -t 900 -i "$SRC" "${ENC[@]}" $WORK/s3h_$name.mp4 && echo "S3H-$name OK $(date)" >> "$STATUS"
  fi
done
# segmen 1: fade in + kartu teks + audio fade in (dari irisan a)
if ! seg_ok $WORK/s3h_1.mp4; then
  ffmpeg -y -v error -i $WORK/s3h_a.mp4 -loop 1 -t 15 -i $WORK/intro_text.png \
    -filter_complex "[1:v]format=rgba,fade=t=in:st=2:d=2:alpha=1,fade=t=out:st=10:d=2:alpha=1[ov];[0:v]fade=t=in:st=0:d=2[vf];[vf][ov]overlay=0:0[vout];[0:a]afade=t=in:st=0:d=3[aout]" \
    -map "[vout]" -map "[aout]" "${ENC[@]}" $WORK/s3h_1.mp4 && echo "S3H-1 OK $(date)" >> "$STATUS"
fi
# segmen 12: fade out (dari irisan d)
if ! seg_ok $WORK/s3h_12.mp4; then
  ffmpeg -y -v error -i $WORK/s3h_d.mp4 \
    -vf "fade=t=out:st=895:d=5" -af "afade=t=out:st=890:d=10" "${ENC[@]}" $WORK/s3h_12.mp4 && echo "S3H-12 OK $(date)" >> "$STATUS"
fi

if seg_ok $WORK/s3h_1.mp4 && seg_ok $WORK/s3h_a.mp4 && seg_ok $WORK/s3h_b.mp4 && seg_ok $WORK/s3h_c.mp4 && seg_ok $WORK/s3h_d.mp4 && seg_ok $WORK/s3h_12.mp4; then
  printf "file '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\nfile '%s'\n" \
    $WORK/s3h_1.mp4 $WORK/s3h_b.mp4 $WORK/s3h_c.mp4 $WORK/s3h_d.mp4 \
    $WORK/s3h_a.mp4 $WORK/s3h_b.mp4 $WORK/s3h_c.mp4 $WORK/s3h_d.mp4 \
    $WORK/s3h_a.mp4 $WORK/s3h_b.mp4 $WORK/s3h_c.mp4 $WORK/s3h_12.mp4 > $WORK/concat3h.txt
  ffmpeg -y -v error -f concat -safe 0 -i $WORK/concat3h.txt -c copy \
    -metadata title="Rain Sounds for Sleep | Rain Falling in a Quiet Garden (3 Hours)" \
    -metadata artist="Extra Dimension" \
    -metadata album="Rain Sounds for Sleep" \
    -metadata comment="Pure nature sounds: flowing water, light rain and birdsong in some segments. No music, no talking." \
    -metadata date="2026" -movflags +faststart "$OUT" && echo "DONE $(date)" >> "$STATUS"
else
  echo "INCOMPLETE $(date)" >> "$STATUS"
fi
