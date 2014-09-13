#!/usr/bin/env python

import math
import pickle
import sys

from datetime import datetime

def usage():
    print 'remove-frames.py', '[weekend]', '<in>', '<out>'

def is_weekend(ds):
    dt = datetime(year=int(ds[0:4]), month=int(ds[4:6]), day=int(ds[6:8]))
    wd = dt.isoweekday()
    return ((wd == 6) or (wd == 7))

def remove_weekends(days):
    output = []
    removed = 0.0
    for (day, frames) in days:
        if is_weekend(day):
            removed += frames
        else:
            output.append((day, frames))
    return (output, removed)

def distribute_spare_frames(days, spare_f):
    total_f = 0.0
    for (day, frames) in days:
        total_f += frames
    output = []
    final_f = 0.0
    for (day, frames) in days:
        frames += math.floor(((frames / total_f) * spare_f) + 0.5) 
        output.append((day, frames))
        final_f += frames
    print 'moved %d frames to produce %d final (diff %d)' % (spare_f, final_f, final_f - (total_f + spare_f))
    return output

def save_frames(fn, days):
    with open(fn, 'w') as f:
        for (day, frames) in days:
            print >>f, day, frames

def main(args):
    if len(args) >= 3:
        op_type = args[0]
        in_file = args[1]
        out_file = args[2]

        days = []
        with open(in_file, 'r') as f:
            for line in f.readlines():
                parts = line.split(" ")
                days.append((parts[0], float(parts[1])))

        n_days = len(days)
        if op_type == 'weekend':
            (days, spare_f) = remove_weekends(days)
            print "removed %d days" % (n_days - len(days))
            days = distribute_spare_frames(days, spare_f)
            save_frames(out_file, days)
        else:
            usage()
    else:
        usage()

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
