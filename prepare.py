#!/usr/bin/env python

import astral
import datetime
import math
import os, os.path
import re
import pickle
import subprocess
import sys

from cmd_queue import CommandQueue
cmd_queue = CommandQueue()

AVGIMG = 'avgimg'
FP_CACHE = {}
CACHE_PATH = None

def _fingerprint(path):
    print 'fingerprint', path
    if os.path.exists(path):
        ppm = subprocess.check_output(['convert', path, '-gravity', 'center', '-crop', '80%', '-scale', '3x3!', '-compress', 'none', '-depth', '16', 'ppm:'])
        lines = ppm.split("\n")
        raw = (" ".join(lines[3:len(lines)])).split(" ")
        data = []
        for v in raw:
            if len(v) > 0:
                data.append(int(v))
        return tuple(data)
    else:
        print '! missing', path
        return tuple([0] * 27)

def cache_invalidate(path):
    global FP_CACHE
    if path in FP_CACHE:
        del FP_CACHE[path]

def fingerprint(path):
    global FP_CACHE
    if path not in FP_CACHE:
        FP_CACHE[path] = _fingerprint(path)    
    return FP_CACHE[path]

def fp_cache_save(path):
    global FP_CACHE
    data = {}
    for (f, fp) in FP_CACHE.items():
        if f.startswith(path):
            k = f[len(path):len(f)]
            data[k] = fp
    with open(os.path.join(path, 'fp_cache'), 'wb') as f:
        pickle.dump(data, f)

def fp_cache_load(path):
    global FP_CACHE
    if os.path.exists(os.path.join(path, 'fp_cache')):
        with open(os.path.join(path, 'fp_cache'), 'rb') as f:
            data = pickle.load(f)
        for (k, fp) in FP_CACHE.items():
            FP_CACHE[os.path.join(path, k)] = fp

def error_exit():
    global CACHE_PATH
    fp_cache_save(CACHE_PATH)
    sys.exit(1)

def flush_cmd_queue():
    if not cmd_queue.run():
        error_exit()

def fp_tone(fp):
    s = [ 0.0, 0.0, 0.0 ]
    c = 0.0
    for i in range(0, len(fp), 3):
        s[0] += fp[i + 0]
        s[1] += fp[i + 1]
        s[2] += fp[i + 2]
        c += 1.0
    for i in range(len(s)):
        s[i] /= c
    return s

def rsd(a, b):
    d = 0.0
    for i in range(min(len(a), len(b))):
        d += (float(a[i]) - float(b[i])) ** 2
    return math.sqrt(d)

def fn_to_date(fn, time_shift=None):
    dp = (fn.split('.'))[0]

    if len(dp) == 12:
        year = int(fn[0:2]) + 2000
        of = 2
    elif len(dp) == 14:
        year = int(fn[0:4])
        of = 4
    else:
        assert(0)

    month = int(fn[of:of+2])
    day = int(fn[of+2:of+4])
    hour = int(fn[of+4:of+6])
    minute = int(fn[of+6:of+8])
    second = int(fn[of+8:of+10])

    result = datetime.datetime(year, month, day, hour, minute, second)
    if time_shift:
        result = result + time_shift
    return result

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
    return "%04d%02d%02d%02d%02d%02d" % (
        date.year, date.month, date.day, 
        date.hour, date.minute, date.second
    )

def day_string(date):
    return "%04d%02d%02d" % (date.year, date.month, date.day)

def month_string(date):
    return "%04d%02d" % (date.year, date.month)

def build_mapping(aloc, src_path, dst_path, files, time_shift=None):
    mapping = {}
    average = {}
    for fn in files:
        dt      = fn_to_date(fn, time_shift=time_shift)
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
        #subprocess.call(['convert', src, '-scale', '600', dst])
        cmd_queue.add(dst, [src], ['convert', src, '-scale', '600', dst])
    elif img_type == 'hd':
        #subprocess.call(['convert', src, '-adaptive-resize', '1920', dst])
        cmd_queue.add(dst, [src], ['convert', src, '-adaptive-resize', '1920', dst])
    elif img_type == 'hdn':
        #subprocess.call(['convert', src, '-normalize', '-adaptive-resize', '1920', dst])
        cmd_queue.add(dst, [src], ['convert', src, '-normalize', '-adaptive-resize', '1920', dst])
    else:
        assert(0)
    # defer mtime load
    #details[img_type + '_mtime'] = os.path.getmtime(dst)
    cache_invalidate(dst)

def preprocess(mapping, dst):
    to_load = []
    for (fn, d) in mapping.items():
        path = os.path.join(d['day'], d['period'])
        if not os.path.exists(os.path.join(dst, path)):
            os.makedirs(os.path.join(dst, path))
        for img_type in ['ld', 'hd', 'hdn']:
            img_path = os.path.join(path, dt_string(d['dt']) + '-' + img_type + '.png')
            d[img_type] = img_path
            if not os.path.exists(os.path.join(dst, img_path)):
                generate_base_img(dst, d, img_type)
            # defer mtime load
            to_load.append((d, img_type + '_mtime', os.path.join(dst, img_path)))
    
    # flush processing
    flush_cmd_queue()

    # do deferred mtime loads
    try:
        for (d, key, path) in to_load:
            d[key] = os.path.getmtime(path)
    except Exception as e:
        print e
        error_exit()

def generate_average(dst, path, srcs, label='raw'):
    output = os.path.join(dst, path, label)
    #subprocess.call([AVGIMG, output] + srcs)
    cmd_queue.add(output, srcs, [AVGIMG, output] + srcs)
    for ext in ['avg', 'geoavg', 'min', 'max', 'diff']:
        cache_invalidate(os.path.join(dst, path, label + '-' + ext + '.png'))

def build_averages(averages, dst, img_type='ld'):
    result = {}
    to_load = []
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
            # defer mtime load
            #mtime = os.path.getmtime(os.path.join(dst, path, 'raw-avg.png'))
            to_load.append((path, os.path.join(dst, path, 'raw-avg.png')))

        result[path] = mtime

    # flush processing
    flush_cmd_queue()

    # do deferred mtime loads
    try:
        for (path, fpath) in to_load:
            result[path] = os.path.getmtime(fpath)
    except Exception as e:
        print e
        error_exit()

    return result

def reprocess_averages(averages, dst):
    for (path, mtime) in averages.items():
        for t in ['geoavg', 'min', 'max']:
            src = os.path.join(dst, path, 'raw-' + t + '.png')
            gen = {
                t + "-eq.png": ['-equalize'],
                t + "-eq-gray.png": ['-equalize', '-separate', '-average'],
                t + "-gray-eq.png": ['-separate', '-average', '-equalize'],
                t + "-gray-edges.png": [
                    '-equalize', '-separate', '-average',
                    '-scale', '128x128!', 
                    '-median', '2',
                    '-lat', '2x2-5%',
                    '-negate', 
                    '-colorspace', 'gray',
                    '-blur', '0x1'
                ]
            }
            for (fn, opts) in gen.items():
                fpath = os.path.join(dst, path, fn)
                if (not os.path.exists(fpath)) or (mtime > os.path.getmtime(fpath)):
                    print 'generate', os.path.join(path, fn)
                    #subprocess.call(['convert', src] + opts + [fpath])
                    cmd_queue.add(fpath, [src], ['convert', src] + opts + [fpath])
                    cache_invalidate(fpath)
    # flush processing
    flush_cmd_queue()

def difference(src, dst):
    print 'difference', src, dst
    result = { '3x3': 0.0, 'MSE': 0.0, 'PSNR': 0.0 }

    if not os.path.exists(src):
        print "! missing", src
        return result
    if not os.path.exists(dst):
        print "! missing", dst
        return result
    
    src_fp = fingerprint(src)
    dst_fp = fingerprint(dst)
    result['3x3'] = rsd(src_fp, dst_fp)

    for metric in ['MSE', 'PSNR']:
        try:
            vsl = subprocess.check_output(
                ['compare', '-metric', metric, src, dst, 'null:'],
                stderr=subprocess.STDOUT)
        except (subprocess.CalledProcessError) as e:
            vsl = e.output

        m = re.match(r'.*\((.+)\).*', vsl)
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

def measure_day(path, day, prev=None, img_type='geoavg-eq', period='day'):
    print 'measure', day, img_type

    day_src = os.path.join(path, 'avg', 'day', day, period, img_type + '.png') 
    if prev:
        prev_src = os.path.join(path, 'avg', 'day', prev, period, img_type + '.png')
    _5day_src = os.path.join(path, 'avg', '5day', day, period, img_type + '.png') 
    month_src = os.path.join(path, 'avg', 'month', day[0:6], period, img_type + '.png')

    fp = fingerprint(day_src)
    tone = fp_tone(fp)

    if prev:
        diff_prev = difference(prev_src, day_src)
    else:
        diff_prev = None
    
    diff_5day = difference(_5day_src, day_src)
    diff_month = difference(month_src, day_src)

    return {
        'fp': fp,
        'tone': tone,
        'prev': diff_prev,
        '5day': diff_5day,
        'month': diff_month
    }

def find_files(path):
    file_re = re.compile(r'\d{12,14}\.jpg')
    raw_files = os.listdir(path)
    files = []
    for fn in raw_files:
        fp = os.path.join(path, fn)
        if os.path.isfile(fp) and file_re.match(fn):
            files.append(fn)
    return files

def measure_days(days, dst_path):
    data = {}

    for i in range(len(days)):
        day = days[i]
        data[day] = day_results = {}

        if i > 0:
            prev_day = days[i - 1]
        else:
            prev_day = None

        for measure in ['geoavg-eq', 'min-eq', 'min-gray-eq', 'raw-geoavg', 'min-gray-edges', 'geoavg-gray-edges']:
            day_results[measure] = measure_day(dst_path, day, prev=prev_day, img_type=measure)

    return data

def main(args):
    global CACHE_PATH

    aloc = astral.Astral()['London']
    # modify for University of Kent, Canterbury
    aloc.latitude = 51.275
    aloc.longitude = 1.087
    aloc.elevation = 72.0
    
    # set a constant time shift from camera data
    time_shift = datetime.timedelta(seconds=-3600)
    
    if len(args) == 2:
        src_path = args[0]
        dst_path = args[1]
        
        CACHE_PATH = dst_path
        files = find_files(src_path)
        fp_cache_load(dst_path)
        
        (mapping, averages) = build_mapping(aloc, src_path, dst_path, files, time_shift=time_shift)
        preprocess(mapping, dst_path)
        mtimes = build_averages(averages, dst_path)
        reprocess_averages(mtimes, dst_path)
        days = day_list(mapping)
        data = measure_days(days, dst_path)
        
        with open(os.path.join(dst_path, 'measures'), 'wb') as f:
            pickle.dump(data, f)

        fp_cache_save(dst_path)

    else:
        print 'prepare.py <src-path> <dst-path>'

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
