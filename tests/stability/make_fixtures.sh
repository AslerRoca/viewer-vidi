#!/usr/bin/env bash
# Rebuild the small fixture workspaces that test_annot.py / shot_annot.py expect
# next to them (ws_img/, ws_list/) from the CR DICOM fixtures on the ressd drive.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX=/media/zsk/ressd/research/alldata_backup/dicom/original
rm -rf "$HERE/ws_img" "$HERE/ws_list"; mkdir -p "$HERE/ws_img/sub" "$HERE/ws_list"
cp "$FIX/bpd1_20100101_1.dcm" "$FIX/bpd1_20100101_2.dcm" "$HERE/ws_img/"
cp "$FIX/bpd1_20100102_1.dcm" "$FIX/bpd1_20100101_1.dcm" "$HERE/ws_img/sub/"
printf '# comment\n%s\n../ws_img/sub/bpd1_20100102_1.dcm\n/nonexistent/x.dcm\n' "$HERE/ws_img/bpd1_20100101_1.dcm" > "$HERE/ws_list/list.txt"
printf 'id,path,label\n1,%s,a\n2,"%s",b\n' "$HERE/ws_img/bpd1_20100101_2.dcm" "$HERE/ws_img/sub/bpd1_20100102_1.dcm" > "$HERE/ws_list/cohort.csv"
echo "README not a list" > "$HERE/ws_img/notes.txt"
echo "fixtures built under $HERE (ws_img/, ws_list/ are git-ignored)"
