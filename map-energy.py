#!/usr/bin/env python

import math
import pickle
import sys

min_f = 1

def main(args):
    if len(args) >= 3:
        (data_file, measure, frames) = args[0:3]
        with open(data_file, 'rb') as f:
            data = pickle.load(f)
        frames = int(frames)
        selected = data[measure]['energy4']
        days = data['days']
        
        r_frames = frames - len(days)
        if r_frames < 0:
            print 'insufficient frames available'
            sys.exit(0)

        day_frames = [ 1 ] * len(days)
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