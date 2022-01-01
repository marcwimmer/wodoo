from functools import wraps
import time
import threading
PROF_DATA = {}

def removeNonAscii(s):
    if not s:
        return ""
    return "".join(i for i in s if ord(i) < 128)

def print_prof_data():
    result = ""
    try:
        import numpy
    except:
        return ""
    for fname, data in PROF_DATA.items():
        max_time = numpy.max(data[1])
        avg_time = numpy.average(data[1])
        total_time = numpy.sum(data[1])
        result += "Function %s called %d times. \n" % (fname, data[0])
        result += 'Execution time max: %.3f, average: %.3f, total: %.3f \n' % (max_time, avg_time, total_time)
        result += "##########################################\n"
    return result


def profile(fn):
    @wraps(fn)
    def with_profiling(*args, **kwargs):
        start_time = time.time()
        ret = fn(*args, **kwargs)
        elapsed_time = float(time.time() - start_time)
        if fn.__name__ not in PROF_DATA:
            PROF_DATA[fn.__name__] = [0, []]
        PROF_DATA[fn.__name__][0] += 1
        PROF_DATA[fn.__name__][1].append(elapsed_time)

        return ret
    return with_profiling

    def __init__(self, getter):
        pass

def clear_prof_data():
    global PROF_DATA
    PROF_DATA = {}

# def writer():
    # while True:
        # import time
        # time.sleep(1)
        # with open("/tmp/profiles", "w") as f:
            # try:
                # f.write(print_prof_data())
            # except:
                # pass
# t = threading.Thread(target=writer)
# t.daemon = True
# t.start()
