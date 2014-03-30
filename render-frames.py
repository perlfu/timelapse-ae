#!/usr/bin/env python

import math
import pickle
import os
import re
import subprocess
import sys

def render_frame(src_path, dst_path, day, srcs, n, img_type='hdn'):
    avg_srcs = []
    for (src, f) in srcs:
        clean = src.replace("-hd.png", "")
        avg_srcs.append(("%.4f:" % f) + os.path.join(src_path, day, 'day', clean + '-' + img_type + '.png'))
    avg_dst = os.path.join(dst_path, 'plain-' + day + '-' + ("%03d" % n) + '.png')
    if not os.path.exists(avg_dst):
        avg_cmd = ['avgimg', '-m', avg_dst ] + avg_srcs
        print avg_cmd
        subprocess.call(avg_cmd)
    ann_dst = os.path.join(dst_path, 'annotated-' + day + '-' + ("%03d" % n) + '.png')
    if not os.path.exists(ann_dst):
        ann_cmd = ['convert', avg_dst, 
                '-font',        'Bookman-Light',
                '-pointsize',   '48',
                '-fill',        '#ffffffa0',
                '-gravity',     'SouthEast', 
                '-annotate',    '+20%+20%', day, 
                ann_dst ]
        print ann_cmd
        subprocess.call(ann_cmd)
    print 'ready', avg_dst
    print 'ready', ann_dst

def main(args):
    if len(args) >= 3:
        (src_path, in_file, out_path) = args[0:3]
        img_type = 'hdn'
        if len(args) > 3:
            img_type = args[3]

        with open(in_file, 'rb') as f:
            data = pickle.load(f)
        days = data['days']
        day_count = data['day_count']
        picked = data['picked']
        frame_n = 0
        for day in days:
            if day in picked:
                frame_sets = picked[day]
                for (i, ls) in zip(range(len(frame_sets)), frame_sets):
                    render_frame(src_path, out_path, day, ls, i, img_type=img_type)
                    frame_n += 1
    else:
        print 'render-frames.py <src-path> <in-file> <out-path>'

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
