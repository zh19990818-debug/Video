#!/bin/bash
# 办公室反转短片：悬疑开场 -> 暖色反转 -> 片尾
IN="$1"; OUT="$2"
F=/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc
ffmpeg -y -v error -i "$IN" \
 -f lavfi -i "color=c=black:s=720x1280:d=2.5:r=30" \
 -f lavfi -i "color=c=0x101010:s=720x1280:d=1.6:r=30" \
 -f lavfi -i "sine=f=55:d=12.2" -f lavfi -i "sine=f=58:d=12.2" \
 -filter_complex "
[1]drawtext=fontfile=$F:text='周一  17\\:58':fontsize=64:fontcolor=white:x=(w-tw)/2:y=500,
   drawtext=fontfile=$F:text='某间普通的办公室':fontsize=40:fontcolor=0xaaaaaa:x=(w-tw)/2:y=600,fade=in:0:15,fade=out:st=2:d=0.5[t];
[0:v]trim=0:6.3,setpts=PTS-STARTPTS,eq=saturation=0.35:contrast=1.25:brightness=-0.08,vignette=PI/3,
   drawbox=y=ih-330:w=iw:h=170:color=black@0.55:t=fill,
   drawtext=fontfile=$F:text='他已经盯着这东西三天了':fontsize=46:fontcolor=white:x=(w-tw)/2:y=h-290:enable='between(t,0.2,2.4)',
   drawtext=fontfile=$F:text='没人知道，里面藏着什么':fontsize=46:fontcolor=white:x=(w-tw)/2:y=h-290:enable='between(t,2.5,4.6)',
   drawtext=fontfile=$F:text='直到今天……':fontsize=56:fontcolor=0xff4040:x=(w-tw)/2:y=h-295:enable='between(t,4.7,6.3)'[a];
[0:v]trim=6.3:8.1,setpts=PTS-STARTPTS,eq=saturation=1.35:brightness=0.05,
   drawbox=y=ih-330:w=iw:h=170:color=black@0.45:t=fill,
   drawtext=fontfile=$F:text='原来，只是在研究新到的小玩意':fontsize=44:fontcolor=0xffe066:x=(w-tw)/2:y=h-290[b];
[2]drawtext=fontfile=$F:text='—— 完 ——':fontsize=56:fontcolor=white:x=(w-tw)/2:y=560,
   drawtext=fontfile=$F:text='虚构短片 · 剧情纯属娱乐':fontsize=30:fontcolor=0x888888:x=(w-tw)/2:y=660,fade=in:0:10[c];
[t][a][b][c]concat=n=4:v=1:a=0,format=yuv420p[v];
[3][4]amix=inputs=2,volume=0.25,tremolo=f=1.2:d=0.7,afade=in:d=1,
   aeval='val(0)+if(gt(t,8.8)*lt(t,10.6),0.35*sin(2*PI*880*t)*exp(-6*(t-8.8)),0)|val(0)+if(gt(t,8.8)*lt(t,10.6),0.35*sin(2*PI*880*t)*exp(-6*(t-8.8)),0)',afade=out:st=11:d=1.2,aformat=channel_layouts=stereo[au]" \
 -map "[v]" -map "[au]" -c:v libx264 -crf 20 -c:a aac -shortest "$OUT"
