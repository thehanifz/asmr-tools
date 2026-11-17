#!/bin/bash
# Render final Rain Garden 1 jam — per segmen 15 menit, tahan restart:
# segmen yang sudah jadi (durasi ~900 dtk) dilewati saat skrip diulang.
set -u
SRC=/home/hatch/workspace/projects/asmr-tools/media/video/merge_loop_Rain_falling_in_garden_7f0c1a96_720p.mp4
WORK=/home/hatch/workspace/asmr-service/work
OUT=/home/hatch/workspace/asmr-service/output/rain-sounds-for-sleep-rain-falling-in-a-quiet-garden-1-hour.mp4
STATUS=$WORK/render_status.txt
ENC=(-c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p -c:a aac -b:a 256k)
echo "START $(date)" >> "$STATUS"

seg_ok () { # $1=file -> 0 bila durasi 899..901
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null) || return 1
  awk "BEGIN{exit !($d>=899 && $d<=901)}"
}

if ! seg_ok $WORK/seg1.mp4; then
  ffmpeg -y -v error -ss 0 -t 900 -i "$SRC" -loop 1 -t 15 -i $WORK/intro_text.png \
    -filter_complex "[1:v]format=rgba,fade=t=in:st=2:d=2:alpha=1,fade=t=out:st=10:d=2:alpha=1[ov];[0:v]fade=t=in:st=0:d=2[vf];[vf][ov]overlay=0:0[vout];[0:a]afade=t=in:st=0:d=3[aout]" \
    -map "[vout]" -map "[aout]" "${ENC[@]}" $WORK/seg1.mp4 && echo "SEG1 OK $(date)" >> "$STATUS"
fi
if ! seg_ok $WORK/seg2.mp4; then
  ffmpeg -y -v error -ss 900 -t 900 -i "$SRC" "${ENC[@]}" $WORK/seg2.mp4 && echo "SEG2 OK $(date)" >> "$STATUS"
fi
if ! seg_ok $WORK/seg3.mp4; then
  ffmpeg -y -v error -ss 1800 -t 900 -i "$SRC" "${ENC[@]}" $WORK/seg3.mp4 && echo "SEG3 OK $(date)" >> "$STATUS"
fi
if ! seg_ok $WORK/seg4.mp4; then
  ffmpeg -y -v error -ss 2700 -t 900 -i "$SRC" \
    -vf "fade=t=out:st=895:d=5" -af "afade=t=out:st=890:d=10" "${ENC[@]}" $WORK/seg4.mp4 && echo "SEG4 OK $(date)" >> "$STATUS"
fi

if seg_ok $WORK/seg1.mp4 && seg_ok $WORK/seg2.mp4 && seg_ok $WORK/seg3.mp4 && seg_ok $WORK/seg4.mp4; then
  printf "file '%s'\nfile '%s'\nfile '%s'\nfile '%s'\n" $WORK/seg1.mp4 $WORK/seg2.mp4 $WORK/seg3.mp4 $WORK/seg4.mp4 > $WORK/concat.txt
  ffmpeg -y -v error -f concat -safe 0 -i $WORK/concat.txt -c copy \
    -metadata title="Rain Sounds for Sleep | Rain Falling in a Quiet Garden (1 Hour)" \
    -metadata artist="Xtra Dimention" \
    -metadata album="Rain Sounds for Sleep" \
    -metadata comment="Pure nature sounds: flowing water, light rain and birdsong in some segments. No music, no talking." \
    -metadata date="2026" -movflags +faststart "$OUT" && echo "DONE $(date)" >> "$STATUS"
else
  echo "INCOMPLETE $(date)" >> "$STATUS"
fi
