#!/usr/bin/env python

#from wand.image import Image
import astral
import datetime
import os, os.path
import re
import subprocess
import sys

#def average(files, output):
#    subprocess.call(['composite'] + files + [output]

def fn_to_date(fn):
    year = int(fn[0:2]) + 2000
    month = int(fn[2:4])
    day = int(fn[4:6])
    hour = int(fn[6:8])
    minute = int(fn[8:10])
    second = int(fn[10:12])

    return datetime.datetime(year, month, day, hour, minute, second)

def day_period(aloc, date):
    details = aloc.sun(local=True, date=date)
    t = date.time()
    dawn = details['dawn'].time()
    sunrise = details['sunrise'].time()
    sunset = details['sunset'].time()
    dusk = details['dusk'].time()
    if (t < dawn or t > dusk):
        return 'night'
    elif (t < sunrise):
        return 'dawn'
    elif (t > sunset):
        return 'dusk'
    else:
        return 'day'

def dt_string(date):
    return "%02d%02d%02d%02d%02d%02d" % (
        date.year, date.month, date.day, 
        date.hour, date.minute, date.second
    )

def day_string(date):
    return "%02d%02d%02d" % (date.year, date.month, date.day)

def month_string(date):
    return "%02d%02d" % (date.year, date.month)

def build_mapping(aloc, src_path, dst_path, files):
    mapping = {}
    average = {}
    for fn in files:
        dt      = fn_to_date(fn)
        period  = day_period(aloc, dt)
        day     = day_string(dt)
        month   = month_string(dt)
        orig    = os.path.join(src_path, fn)
        details = {
            'dt': dt,
            'period': period,
            'day': day,
            'month': month,
            'orig': orig
        }
        mapping[fn] = details

        membership = [ 
            'day/' + day + '/all', 
            'day/' + day + '/' + period,
            'month/' + month + '/all', 
            'month/' + month + '/' + period
        ]
        for i in range(-2,3):
            if i < 0:
                other = day_string(dt - datetime.timedelta(-i))
            else:
                other = day_string(dt + datetime.timedelta(+i))
            
            membership += [
                '5day/' + other + '/all',
                '5day/' + other + '/period'
            ]

        for entry in membership:
            if entry not in average:
                average[entry] = [details]
            else:
                average[entry].append(details)
    
    return (mapping, average)

def generate_base_img(dst_path, details, img_type):
    src = details['orig']
    dst = os.path.join(dst_path, details[img_type])
    print 'generate', details[img_type]
    if img_type == 'ld':
        subprocess.call(['convert', src, '-scale', '600', dst])
    elif img_type == 'hd':
        subprocess.call(['convert', src, '-adaptive-resize', '1920', dst])
    else:
        assert(0)

def preprocess(mapping, dst):
    for (fn, d) in mapping.items():
        path = os.path.join(d['day'], d['period'])
        if not os.path.exists(os.path.join(dst, path)):
            os.makedirs(os.path.join(dst, path))
        ld = os.path.join(path, dt_string(d['dt']) + '-ld.png')
        hd = os.path.join(path, dt_string(d['dt']) + '-hd.png')
        d['ld'] = ld
        d['hd'] = hd
        if not os.path.exists(os.path.join(dst, ld)):
            generate_base_img(dst, d, 'ld')
        else:
            d['ld_mtime'] = os.path.getmtime(os.path.join(dst, ld))
        if not os.path.exists(os.path.join(dst, hd)):
            generate_base_img(dst, d, 'hd')
        else:
            d['hd_mtime'] = os.path.getmtime(os.path.join(dst, ld))
            
def find_files(path):
    file_re = re.compile(r'\d{12}\.jpg')
    raw_files = os.listdir(path)
    files = []
    for fn in raw_files:
        fp = os.path.join(path, fn)
        if os.path.isfile(fp) and file_re.match(fn):
            files.append(fn)
    return files

def main(args):
    aloc = astral.Astral()['London']
    # modify for University of Kent, Canterbury
    aloc.latitude = 51.275
    aloc.longitude = 1.087
    aloc.elevation = 72.0
    
    if len(args) == 2:
        src_path = args[0]
        dst_path = args[1]
        files = find_files(src_path)

        (mapping, average) = build_mapping(aloc, src_path, dst_path, files)
        preprocess(mapping, dst_path)

if __name__ == "__main__":
    main(sys.argv[1:])
