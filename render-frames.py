#!/usr/bin/env python

import math
import pickle
import os
import re
import subprocess
import sys

def render_frame(src_path, dst_path, day, srcs, n, gn, img_type='hdn'):
    # pick mode
    if len(srcs) <= 5:
        mode = '-m'
    else:
        mode = '-g'

    # compile sources and weights
    avg_srcs = []
    for (src, f) in srcs:
        clean = src.replace("-hd.png", "")
        if mode == '-m':
            avg_srcs.append(("%.4f:" % f) + os.path.join(src_path, day, 'day', clean + '-' + img_type + '.png'))
        else:
            avg_srcs.append(os.path.join(src_path, day, 'day', clean + '-' + img_type + '.png'))

    # plain average frame
    avg_dst = os.path.join(dst_path, 'plain-' + day + '-' + ("%03d" % n) + '.png')
    plain_gn = os.path.join(dst_path, "frame-plain-%05d.png" % gn)
    if not os.path.exists(avg_dst):
        avg_cmd = ['avgimg', mode, avg_dst ] + avg_srcs
        print avg_cmd
        subprocess.call(avg_cmd)
    if not os.path.exists(plain_gn):
        os.symlink(avg_dst, plain_gn)

    # annotated frame
    ann_dst = os.path.join(dst_path, 'annotated-' + day + '-' + ("%03d" % n) + '.png')
    ann_gn = os.path.join(dst_path, "frame-annotated-%05d.png" % gn)
    if not os.path.exists(ann_dst):
        ann_cmd = ['convert', avg_dst, 
                '-font',        'Bookman-Light',
                '-pointsize',   '64',
                '-fill',        '#ffffffa0',
                '-gravity',     'SouthWest', 
                '-annotate',    '+1570%+20%', day, 
                ann_dst ]
        print ann_cmd
        subprocess.call(ann_cmd)
    if not os.path.exists(ann_gn):
        os.symlink(ann_dst, ann_gn)

    # output
    print 'ready', avg_dst, plain_gn
    print 'ready', ann_dst, ann_gn

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
                    render_frame(src_path, out_path, day, ls, i, frame_n, img_type=img_type)
                    frame_n += 1
    else:
        print 'render-frames.py <src-path> <in-file> <out-path>'

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
