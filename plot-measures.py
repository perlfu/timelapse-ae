#!/usr/bin/env python

import pickle
import sys

import numpy as np

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

METRICS = ['3x3', 'MSE', 'PSNR']
SERIES = ['prev', '5day', 'month']

def find_measures(data):
    return (data.values()[0]).keys()

def select_values(data, days, measure, metric):
    ys = {}
    for s in SERIES:
        ys[s] = []
    ys['avg'] = []

    for day in days:
        for s in SERIES:
            if (s in data[day][measure]) and data[day][measure][s]:
                ys[s].append(data[day][measure][s][metric])
            else:
                ys[s].append(0.0)
    
    for i in range(len(days)):
        _sum = 0.0
        for s in SERIES:
            _sum += ys[s][i]
        ys['avg'].append(_sum / float(len(SERIES)))

    return ys

def select_tones(data, days, measure):
    ys = []
    for day in days:
        tone = data[day][measure]['tone']
        ys.append((tone[0] / 65535.0, tone[1] / 65535.0, tone[2] / 65535.0))
    return ys

def pick_colour(cmap, n):
    return cmap(n)

def plot_values(pages, label, days, ys):
    print 'plot', label
    cmap = plt.cm.Paired
    fig = plt.figure()
    ax = fig.add_subplot(111)
    xs = range(len(days))
    ticks = range(0, len(days), 3)
    tick_labels = []
    for idx in ticks:
        tick_labels.append(days[idx])
    
    for (i, k) in zip(np.linspace(0, 1.0, len(ys.keys())), ys.keys()):
        ax.scatter(xs, ys[k], alpha=0.9, label=k, color=pick_colour(cmap, i))

    ax.set_xlim((xs[0], xs[-1]))
    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels, rotation=90)
    ax.set_title(label)
    ax.legend(ncol=len(ys.keys()), loc='lower right')
    plt.grid(b=True, which='both', color='0.75', linestyle='-')
    fig.savefig(pages, format='pdf', dpi=300)

def plot_tones(pages, label, days, ys):
    print 'plot', label
    fig = plt.figure()
    ax = fig.add_subplot(111)
    xs = range(len(days))
    ticks = range(0, len(days), 3)
    tick_labels = []
    for idx in ticks:
        tick_labels.append(days[idx])
    
    ax.bar(xs, ([1.0] * len(days)), alpha=1.0, color=ys, linewidth=0.0, width=1.0)
    ax.set_xlim((xs[0], xs[-1]))
    ax.set_ylim((0.0, 1.0))
    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels, rotation=90)
    ax.set_title(label)
    #plt.grid(b=True, which='both', color='0.75', linestyle='-')
    fig.savefig(pages, format='pdf', dpi=300)

def main(args):
    matplotlib.rc('xtick', labelsize=8)

    if len(args) >= 2:
        (input_file, output_file) = args[0:2]
        with open(input_file, 'rb') as f:
            data = pickle.load(f)

        pages = PdfPages(output_file)

        days = sorted(data.keys())
        measures = find_measures(data)
        for measure in measures:
            for m in METRICS:
                ys = select_values(data, days, measure, m)
                plot_values(pages, measure + ' ' + m, days, ys)

        for measure in measures:
            ys = select_tones(data, days, measure)
            plot_tones(pages, measure + ' tone', days, ys)

        pages.close()

if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)
