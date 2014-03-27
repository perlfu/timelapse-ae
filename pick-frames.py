#!/usr/bin/env python

import math
import pickle
import os
import re
import sys

def load_day_counts(frames):
    with open(frames, 'r') as f:
        lines = f.readlines()
    days = []
    day_count = {}
    for line in lines:
        (day, count) = line.split(" ")
        days.append(day)
        day_count[day] = int(float(count))
    return (days, day_count)

def read_frame_list(path, day):
    d_path = os.path.join(path, day, 'day')
    file_re = re.compile(r'\d+-hd.png')
    raw_files = os.listdir(d_path)
    files = []
    for fn in raw_files:
        if file_re.match(fn):
            files.append(fn)
    return sorted(files)

def normalise_set(picks):
    total = sum([w for (f,w) in picks])
    return [(f,w/total) for (f,w) in picks]

def pick_day_frames(frames, count):
    shift = float(len(frames)) / float(count)
    mid_point = shift / 2.0
    min_weight = min(1.0 / shift, 1.0)
    result = []
    p = mid_point
    while p < len(frames):
        weight = []
        picked = []
        for i in range(len(frames)):
            if i != p:
                weight.append(min(1.0 / abs(i - p), 1.0))
            else:
                weight.append(1.0)
        i_min_weight = min_weight
        while len(picked) == 0:
            for i in range(len(frames)):
                if weight[i] > i_min_weight:
                    picked.append((frames[i], weight[i]))
            i_min_weight /= 2.0
        p += shift
        result.append(normalise_set(picked))
    return result

def main(args):
    if len(args) >= 3:
        (path, frames, out_file) = args[0:3]
        (days, day_count) = load_day_counts(frames)
        picked = {}
        result = { 'days': days, 'day_count': day_count, 'picked': picked }
        errors = []
        for day in days:
            try:
                src_frames = read_frame_list(path, day)
                frame_sets = pick_day_frames(src_frames, day_count[day])
                picked[day] = frame_sets
                print day, day_count[day]
                for (i, ls) in zip(range(len(frame_sets)), frame_sets):
                    for (f,w) in ls:
                        print "  % d %.5f %s" % (i, w, f)
            except OSError as e:
                errors.append(day)
        with open(out_file, 'wb') as f: 
            data = pickle.dump(result, f)
    else:
        print 'pick-frames.py <path> <in-file> <out-file>'

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
