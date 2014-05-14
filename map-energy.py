#!/usr/bin/env python

import math
import pickle
import sys

min_f = 3

def main(args):
    if len(args) >= 3:
        (data_file, frames) = args[0:2]
        with open(data_file, 'rb') as f:
            data = pickle.load(f)
        frames = int(frames)
        days = data['days']

        selected = [ 0.0 ] * len(days)
        for measure in args[2:]:
            if measure.find(':') >= 0:
                (major, minor) = measure.split(':', 2)
            else:
                (major, minor) = (measure, 'energy4')
            md = data[major][minor]
            for i in range(len(md)):
                selected[i] += md[i]

        for i in range(len(selected)):
            #selected[i] = selected[i] / (1.0 * len(args[2:]))
            selected[i] = min(selected[i], 1.0)
        
        r_frames = frames - len(days)
        if r_frames < 0:
            print 'insufficient frames available'
            sys.exit(0)

        day_frames = [ min_f ] * len(days)
        total_energy = sum(selected)

        last_r_frames = 0
        while not (r_frames == last_r_frames): 
            frames_per_e = float(r_frames) / total_energy
            for i in range(len(selected)):
                day_frames[i] += math.floor((frames_per_e * selected[i]) + 0.5)
            last_r_frames = r_frames 
            r_frames = frames - sum(day_frames)
        
        #print 'error', r_frames

        for (day, n) in zip(days, range(len(days))):
            print day, day_frames[n]
    else:
        print 'map.py', '<data-file>', '<measure>', '<frames>'

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
