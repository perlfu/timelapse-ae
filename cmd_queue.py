#!/usr/bin/env python

import os
import multiprocessing
import subprocess
import time

class CommandQueue:
    def __init__(self, n_threads=multiprocessing.cpu_count()):
        self.n_threads = n_threads
        self.ready = {}
        self.queue = {}

    def add(self, fn, deps, cmd):
        assert fn not in self.queue
        self.queue[fn] = (fn, deps, cmd)
        self.ready[fn] = False

    def next(self):
        for k in self.queue.keys():
            (fn, deps, cmd) = self.queue[k]
            ready = True
            for dep in deps:
                if dep in self.ready:
                    ready = ready and self.ready[dep]
                else:
                    ready = ready and os.path.exists(dep)
            if ready:
                del self.queue[k]
                return (fn, cmd)
        return None
   
    def sleep(self):
        time.sleep(0.1)

    def start_task(self, tasks):
        job = self.next()
        if job:
            (fn, cmd) = job
            if os.path.exists(fn):
                self.ready[fn] = True
                print 'ready:', fn
            else:
                proc = subprocess.Popen(cmd)
                print cmd
                tasks[fn] = { 'p': proc, 'fn': fn, 'cmd': cmd }
        return job

    def check_tasks(self, tasks):
        error = None
        done = []
        for (fn, task) in tasks.items():
            if task['p'].poll() is not None:
                done.append(task)
        
        for task in done:
            if task['p'].returncode:
                error = task
            print 'ready:', task['fn']
            self.ready[task['fn']] = True
            del tasks[task['fn']]

        if len(done) == 0:
            self.sleep()

        return error

    def waiting(self):
        return len(self.queue.keys())

    def run(self):
        tasks = {}
        error = None
        
        def running():
            return len(tasks.keys())

        while (self.waiting() > 0) and (not error):
            while (running() < self.n_threads) and (self.waiting() > 0):
                job = self.start_task(tasks)
                # nothing to start?
                if not job:
                    if (running() == 0) and (self.waiting() > 0):
                        # sanity check
                        print 'CommandQueue has commands which cannot start'
                        return False
                    else:
                        # check for dependencies finishing
                        break

            error = self.check_tasks(tasks)
            while (running() == self.n_threads) and (not error):
                error = self.check_tasks(tasks)

        while running() > 0:
            self.check_tasks(tasks)

        if error:
            print 'failed', error['cmd'] 
            return False
        else:
            return True
