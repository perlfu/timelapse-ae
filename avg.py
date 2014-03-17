#!/usr/bin/env python

import astral
import datetime
import os, os.path
import re
import subprocess
import sys

AVGIMG = 'avgimg'

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
            os.path.join('day', day, 'all'),
            os.path.join('day', day, period),
            os.path.join('month', month, 'all'),
            os.path.join('month', month, period)
        ]
        for i in range(-2,3):
            if i < 0:
                other = day_string(dt - datetime.timedelta(-i))
            else:
                other = day_string(dt + datetime.timedelta(+i))
            
            membership += [
                os.path.join('5day', other, 'all'),
                os.path.join('5day', other, period)
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
    d[img_type + '_mtime'] = os.path.getmtime(dst)

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

def generate_average(dst, path, srcs, label='raw'):
    subprocess.call([AVGIMG, os.path.join(dst, path, label)] + srcs)

def build_averages(averages, dst, img_type='ld'):
    result = {}
    for (path, srcs) in averages.items():
        path = os.path.join('avg', path)

        most_recent = 0
        for src in srcs:
            src_mtime = src[img_type + '_mtime']
            if src_mtime > most_recent:
                most_recent = src_mtime

        mtime = 0
        if not os.path.exists(os.path.join(dst, path)):
            os.makedirs(os.path.join(dst, path))
        elif os.path.exists(os.path.join(dst, path, 'raw-avg.png')):
            mtime = os.path.getmtime(os.path.join(dst, path, 'raw-avg.png'))

        if most_recent >= mtime:
            src_paths = []
            for src in srcs:
                src_paths.append(os.path.join(dst, src[img_type]))
            generate_average(dst, path, src_paths)
            mtime = os.path.getmtime(os.path.join(dst, path, 'raw-avg.png'))

        result[path] = mtime

    return result

def reprocess_averages(averages, dst):
    for (path, mtime) in averages.items():
        for t in ['geoavg', 'min', 'max']:
            src = os.path.join(dst, path, 'raw-' + t + '.png')
            gen = {
                t + "-eq.png": ['-equalize'],
                t + "-eq-gray.png": ['-equalize', '-separate', '-average'],
                t + "-gray-eq.png": ['-separate', '-average', '-equalize']
            }
            for (fn, opts) in gen.items():
                fpath = os.path.join(dst, path, fn)
                if (not os.path.exists(fpath)) or (mtime > os.path.getmtime(fpath)):
                    print 'generate', os.path.join(path, fn)
                    subprocess.call(['convert', src] + opts + [fpath])

def fingerprint(path):
    ppm = subprocess.check_output(['convert', path, '-gravity', 'center', '-crop', '80%', '-scale', '3x3!', '-compress', 'none', '-depth', '16', 'ppm:'])
    lines = ppm.split("\n")
    raw = (" ".join(lines[3:len(lines)])).split(" ")
    data = []
    for v in raw:
        if len(v) > 0:
            data.append(int(v))
    return data

def rsd(a, b):
    d = 0.0
    for i in range(min(len(a), len(b))):
        d += (float(a[i]) - float(b[i])) ** 2
    return math.sqrt(d)

def comparison(src, dst):
    result = {}
    for metric in ['MSE', 'PSNR']:
        vsl = subprocess.check_output(['compare', '-metric', metric, src, dst, 'null:'])
        m = re.match(r'.*\((.+)\)')
        if m:
            v = float(m.group(1))
        else:
            v = float(vsl)
        result[metric] = v
    return result

def day_list(mapping):
    days = {}
    for (fn, d) in mapping.items():
        days[d['day']] = True
    return sorted(days.keys())

def measure_day(path, day, img_type):
    # get tone measures
    # compare to: previous day, 5-day window, month
    pass

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

        (mapping, averages) = build_mapping(aloc, src_path, dst_path, files)
        preprocess(mapping, dst_path)
        mtimes = build_averages(averages, dst_path)
        reprocess_averages(mtimes, dst_path)
    else:
        print 'avg <src> <dst>'

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)