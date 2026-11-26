#!/bin/bash
# 사용: fetch_gallery.sh <출력폴더> <image/... 경로들>  (쿠팡 썸네일 경로, 720px로 받음) + 미리보기 sheet.jpg
out=$1; shift; mkdir -p "$out"; i=0
for p in "$@"; do i=$((i+1)); curl -s -A "Mozilla/5.0" -o "$out/$i.img" "https://thumbnail.coupangcdn.com/thumbnails/remote/720x720ex/$p"; done
n=$i; fc=""; for j in $(seq 0 $((n-1))); do fc="$fc[$j]scale=200:200,setsar=1[s$j];"; done
ins=""; for j in $(seq 1 $n); do ins="$ins -i $out/$j.img"; done
lab=""; for j in $(seq 0 $((n-1))); do lab="$lab[s$j]"; done
ffmpeg -loglevel error -y $ins -filter_complex "${fc}${lab}hstack=$n" "$out/sheet.jpg"
