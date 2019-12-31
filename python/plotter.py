#! /usr/bin/env python3
import json
from collections import OrderedDict
import pprint
import time

import numpy as np
import matplotlib.pyplot as plt

import tools.plotter_read_config as config_reader
import tools.itertransform as it

pp = pprint.PrettyPrinter(indent=4)


# ======================================================================================================================
# -- GENERAL FLOW


def _main():
    """
    Main function : read the args, read the json files, build a list of tuple (opt, benchmark name, time), transforms
    it to build a graph.
    To transform the list of tuples, we use itertools and some functions built from it, trying to respect the
    "flat is better than nested" principe.
    """
    configuration = config_reader.extract_args()

    opt_of_interest = configuration.opt_list
    reference_opt = configuration.ref_opt

    _, benchmark_list, data_tuples = _extract_json_files(configuration.files_to_read)

    # TODO : extract the categories of interest from the arguments or the config file
    categories = [
        'test-suite :: SingleSource',
        'test-suite :: MultiSource',
        'test-suite :: Bitcode'
    ]

    print("Studied pass order : " + ",".join(opt_of_interest))

    # >> data_tuples = list of (opt, benchmark, time)
    # The key is (opt, benchmark). For each benchmark we want to only have one time
    listed_times_per_group = it.groupby_value(data_tuples, key_function=lambda x: x[0:2], value_function=lambda x: x[2])
    reduced_times = it.apply_to_values_of_group(min_list_not_zero, listed_times_per_group)
    ungrouped = map(lambda x: (x[0][0], x[0][1], x[1]), reduced_times)

    # >> ungrouped = list of (opt, benchmark, min_time)
    # Remove benchmark that don't interest us
    is_valid, categorization = _build_startswith_benchmark_name(categories)
    filtered_benchmarks = filter(is_valid, ungrouped)
    # Remove self made test as a similar test was actually already integrated in the test suite
    filtered_benchmarks = filter(lambda x: x[1].find("get.test") == -1, filtered_benchmarks)

    # Compute speedup
    grouped_benchmark_speedup = it.groupby_value(filtered_benchmarks, lambda x: x[1], lambda x: (x[0], x[2]))
    dict_grouped_benchmark = it.apply_to_values_of_group(fuse_in_dicts, grouped_benchmark_speedup)

    # >> dict_grouped_benchmark = list of (benchmark, a dict {opt : min_time})

    if configuration.plot_type != "time_plot":
        speedup_computer = build_speedup_computer(opt_of_interest, reference_opt, speedup_computation)
        speedup_list = it.apply_to_values_of_group(speedup_computer, dict_grouped_benchmark)
        speedup_list = filter(lambda t: t[1] is not None, speedup_list)
    else:
        speedup_list = dict_grouped_benchmark

    if configuration.min_time is not None:
        speedup_list = filter(has_min_time_less_than(configuration.min_time), speedup_list)

    # >> speedup_list = list of (benchmark, list of (opt, speedup)) (unless time_plot)

    # Regroup the times of the benchmarks of the same kind
    # TODO : it would be more appropriate to delegate the specific processing of each build plot function
    if configuration.plot_type == "bar":
        categorized = it.groupby_value(speedup_list, lambda x: categorization(x[0]), lambda x: x[1])
        # >> categorized = list of [benchmark_group, list of (list of (opt, speedup) ) ]

        geom = it.apply_to_values_of_group(reduce_list_of_tuple_list_to_tuple_list(geometric_average), categorized)
        flat_geom = list(_flatten_tuple_list(geom))
        # >> flat_geom = list of [benchmark_group, list of (opt, average of speedup) ]
        pp.pprint(flat_geom)
        pl = build_bar_plot(flat_geom, opt_of_interest, categories, reference_opt)
    elif configuration.plot_type == "plot":
        # We only have to sort the speedup_list
        sort_reference_point_opt = configuration.sort_opt
        print("The reference pass sequence is {} ; Pass are sorted using speedup of {}"
              .format(reference_opt, sort_reference_point_opt))
        index_of_sort_reference = opt_of_interest.index(sort_reference_point_opt)
        sorted_speedup = sorted(speedup_list, key=lambda x: x[1][index_of_sort_reference])

        pl = build_scatter_plot(sorted_speedup, opt_of_interest,
                                configuration.plot_config['bot'], configuration.plot_config['top'])
    elif configuration.plot_type == "time_plot":
        pl = build_scatter_time_plot(speedup_list, opt_of_interest[0], opt_of_interest[1])
    else:
        print("Plot type unknonw (" + str(configuration.plot_type) + ")")
        exit(1)

    if pl is not None:
        if configuration.display:
            pl.show()

        if configuration.output_file is not None:
            pl.savefig(configuration.output_file)


# ======================================================================================================================
# -- DRAWING THE PLOTS


def build_bar_plot(data, opts_of_interest, categories, reference_opt):
    number_of_bar_group = len(categories)

    fig, ax = plt.subplots()
    ind = np.arange(number_of_bar_group)

    nb_of_opt_order = len(opts_of_interest)
    width = 0.70 / nb_of_opt_order

    measures = OrderedDict()

    for data_tuple in data:
        category, opt, avg = data_tuple
        if opt not in measures:
            measures[opt] = [0] * len(categories)

        measures[opt][categories.index(category)] = avg

    i = 0
    for opt_order in opts_of_interest:
        if opt_order in measures:
            ax.bar(ind - (nb_of_opt_order - 1) * width / 2 + width * i, measures[opt_order], width, label=opt_order)

        i = i + 1

    ax.set_ylabel('Mean execution time relatively to {reference}'.format(reference=reference_opt))
    ax.set_title('Speedup of some phase order relatively to {reference} on LLVM'.format(reference=reference_opt))
    ax.set_xticks(ind)

    labels = [x[x.rfind(":: ") + 3:] for x in categories]

    ax.set_xticklabels(labels)
    ax.legend()

    return plt


def build_scatter_plot(sorted_speedup, opt_of_interest, bottom=0.5, top=5.0):
    x = []  # Number of the benchmarks
    y_vector = [[] for x in range(len(opt_of_interest))]

    current_x = 1
    for benchmark in sorted_speedup:
        x.append(current_x)
        current_y_vector = 0
        for time_tuple in benchmark[1]:
            y_vector[current_y_vector].append(time_tuple[1])
            current_y_vector = current_y_vector + 1

        current_x = current_x + 1

    colors = [u'b', u'g', u'r', u'c', u'm', u'y', u'k']

    fig = plt.figure()
    ax = fig.add_subplot(111)

    artists = {}

    for i in range(len(opt_of_interest)):
        color = colors[i % len(colors)]
        # We put another color edge if we have more than len(colors)
        # TODO : debug this feature
        edge_color = colors[(i + i // len(colors)) % len(colors)]

        artist = ax.scatter(x, y_vector[i], c=color, edgecolor=edge_color, s=5, label=opt_of_interest[i], picker=True)
        artists[artist] = i

    def on_click(event):
        # Retrieve the informations about the event that generated the click
        opt_num = artists[event.artist]
        id_of_benchmark = event.ind[0]

        # Match ids with names that a human can understand
        name_of_opt = opt_of_interest[opt_num]
        name_of_benchmark = sorted_speedup[id_of_benchmark][0]
        speedup = y_vector[opt_num][id_of_benchmark]

        # Display with timestamp to differentiate the different click actions
        current_timestamp = time.strftime("%H-%M-%S")
        print("[{}] [{}] {} has a speedup of {} ".format(current_timestamp, name_of_opt, name_of_benchmark, speedup))

    fig.canvas.mpl_connect('pick_event', on_click)
    axes = plt.gca()
    axes.set_xlim(left=1, right=len(x))
    axes.set_ylim(bottom=bottom, top=top)  # We limit ymax because some benchmark hit a 6000x speedup

    plt.title("Comparing speedup of different options")
    plt.legend(loc=2)

    return plt


def build_scatter_time_plot(time_list, x_axis_opt, y_axis_opt):
    time_list = list(time_list)  # Remove consumability of the iterable

    blue_points = { 'benchmarks': [], 'x': [], 'y': [], 'c': 'blue'}
    red_points = { 'benchmarks': [], 'x': [], 'y': [], 'c': 'red'}
    green_points = { 'benchmarks': [], 'x': [], 'y': [], 'c': 'green'}

    for benchmark in time_list:
        x_position = benchmark[1][x_axis_opt]
        y_position = benchmark[1][y_axis_opt]

        MARGIN_ERROR = 0.02

        if x_position / y_position < (1.00 - MARGIN_ERROR):
            points_category = green_points
        elif y_position / x_position < (1.00 - MARGIN_ERROR):
            points_category = red_points
        else:
            points_category = blue_points

        points_category['benchmarks'].append(benchmark)
        points_category['x'].append(x_position)
        points_category['y'].append(y_position)

    fig = plt.figure()
    ax = fig.add_subplot(111)

    artists = {}

    for points_to_draw in [blue_points, red_points, green_points]:
        artist = ax.scatter(points_to_draw['x'], points_to_draw['y'], s=5, picker=True)
        artists[artist] = points_to_draw

    # TOOD : draw x = y line in background

    def on_click(event):
        id_of_benchmark = event.ind[0]
        points_category = artists[event.artist]
        benchmark = points_category['benchmarks'][id_of_benchmark]
        current_timestamp = time.strftime("%H-%M-%S")
        print("[{}] {} : {} = {} ; {} = {} ".format(current_timestamp, benchmark[0],
                                                    x_axis_opt, benchmark[1][x_axis_opt],
                                                    y_axis_opt, benchmark[1][y_axis_opt]))

    fig.canvas.mpl_connect('pick_event', on_click)
    axes = plt.gca()
    axes.set_xlim(left=0)
    axes.set_ylim(bottom=0)

    # plt.title("Comparing speedup of different options")
    # plt.legend(loc=2)

    return plt


# ======================================================================================================================
# -- Json file reading


def _extract_json_files(list_of_jsons):
    """
    Open every jsons specified and builds a list of tuple (opt, benchmark_name, time) from every json passed
    :param list_of_jsons: A dict in the form {'opt_name': list of json files that stores the results of this opt}
    :return: a list of opt, a set of benchmarks and a list of tuple (opt, benchmark_name, time)
    """
    opt_list = []
    benchmarks = set()
    tuples = []

    for opt in list_of_jsons:
        opt_list.append(opt)
        for json_file in list_of_jsons[opt]:
            _extract_json_file(tuples, benchmarks, opt, json_file)

    return opt_list, benchmarks, tuples


def _extract_json_file(list_to_fill, benchmarks, opt, json_file):
    """
    Open the json file, for each benchmark found, add to list_ot_fill a tuple (opt, benchmark_name, time) and add the
    benchmark to the list benchmarks if not present.
    """
    parsed_json = json.load(open(json_file))
    parsed_json = parsed_json['tests']

    # MicroBenchmarks have a strange exec_time because of multi threading so you may want to exclude them
    exclude_micro_benchmark = False

    for run_test in parsed_json:
        if not is_a_valid_benchmark(run_test):  # Fail
            continue

        if not exclude_micro_benchmark or run_test['name'].find("MicroBenchmarks") == -1:
            benchmark_name, time_measure = extract_data_from_benchmark(run_test)

            tuple_to_add = (opt, benchmark_name, time_measure)
            list_to_fill.append(tuple_to_add)
            benchmarks.add(benchmark_name)


def is_a_valid_benchmark(run_test):
    """
    Returns true if the given run_test dict contains an execution time for a benchmark
    :param run_test: A dictionary built from a json file generated by llvm-lit
    :return: True if the given run test contains an execution time
    """
    return 'metrics' in run_test and 'exec_time' in run_test['metrics']


def extract_data_from_benchmark(run_test):
    """
    Returns the name of the benchmark and the execution time from the given run_test
    :param run_test: The run test entry
    :return: A tuple containing the name of the benchmark and the execution time.
    """
    return run_test['name'], float(run_test['metrics']['exec_time'])


# ======================================================================================================================
# -- Extra data manipulation utility functions


def fuse_in_dicts(tuples):
    """
    Transform a list of tuple (a, b) into a dict {a: b}
    :param tuples: The list of tuple (a, b)
    :return: A dictionary in which for each tuple (a, b), there is an entry {a: b}
    """
    d = {}
    for t in tuples:
        d[t[0]] = t[1]
    return d


def build_speedup_computer(opts_of_interest, reference_opt, speedup_compute):
    """
    Builds a function that transforms a list of (opt, time) into a list of (opt, speedup)
    :param opts_of_interest: The list of opt to consider
    :param reference_opt: The opt that has the reference time
    :param speedup_compute: The function used to compute the speedup (typically f(a, b) = a / b)
    :return: A function that is able to transform a list of (opt, time) into a list of (opt, speedup)
    """
    def built_function(a):
        relative_speedup = []

        if reference_opt not in a:
            return None

        reference_time = a[reference_opt]

        for opt_of_interest in opts_of_interest:
            if opt_of_interest not in a:
                return None

            relative_speedup.append((opt_of_interest, speedup_compute(reference_time, a[opt_of_interest])))

        return relative_speedup
    return built_function


def speedup_computation(reference, time):
    """
    Computes the speedup of the given time relatively to the reference time (returns reference time / time)
    """
    return reference / time


def _flatten_tuple_list(tuple_list):
    """
    Generator to transform a list of tuple (a, b, [c, d, ..., z]) into a list of (a, b, c), (a, b, d), ..., (a, b, z)
    :param tuple_list: The list of tuple to flatten
    :return: The flatten list
    """
    for group_tuple in tuple_list:
        for sub_tuple in group_tuple[-1]:
            yield group_tuple[:-1] + sub_tuple


def _build_startswith_benchmark_name(categories):
    """
    Returns two function :
    - is_valid(x) that says if categorization(x[1]] is not None
    - categorization(x) that gives the first string s in categories that verify x.startswith(s)
    :param categories: A list of string prefix of interest
    :return: see description
    """
    def categorization(benchmark_name):
        for category in categories:
            if benchmark_name.startswith(category):
                return category

        return None

    def is_valid(t):
        return categorization(t[1]) is not None

    return is_valid, categorization


def reduce_list_of_tuple_list_to_tuple_list(func):
    """
    Builds a function that transforms a list of (list of (opt, measure)) into the list of (opt, func(list of measures))
    """
    def vectorized_func(x):
        # Build for each opt the list of measures
        opt = OrderedDict()

        for list_of_benchmarks in x:
            for opt_name, measure in list_of_benchmarks:
                if opt_name not in opt:
                    opt[opt_name] = []

                opt[opt_name].append(measure)

        # Apply the func function to each list
        result_list = []
        for opt_name in opt:
            result_list.append((opt_name, func(opt[opt_name])))
        return result_list

    return vectorized_func


# ======================================================================================================================
# -- List of numbers reduction functions


def min_list_not_zero(numbers):
    """
    Returns the min value in the iterable numbers, excluding .
    The idea is if we kept 0 values, computing a speedup would be impossible.
    Raises exception if the list is empty
    :param numbers: The list of numbers
    :return: The min value in numbers that is different than 0. None if such number is not found
    """
    if len(numbers) == 0:
        raise Exception("ReducedExecTimes::min_function called on empty list")

    # We don't use the standard method which is min = number[0] then iterates on number[1:] because number[0] may
    # be invalid
    minimum = None

    for e in numbers:
        if e == 0:
            continue

        if minimum is None:
            minimum = e
        elif e < minimum:
            minimum = e

    return minimum


def geometric_average(numbers):
    """
    Builds the geometric average of the numbers
    :param numbers: The numbers
    :return: The geometric average
    """
    average = 1.0
    nb = 0
    for n in numbers:
        average = average * n
        nb = nb + 1

    if nb == 0:
        return 0.0

    return pow(average, 1 / nb)


def has_min_time_less_than(time):
    """
    Returns a function that filter the tuple (a, b) in which b is a dict that pairs (c, d), and there is at least one d
    value that is less than time
    :param time: The minimal time of the values in the dict of the tuples
    :return: A filter function
    """
    def filter_function(t):
        for _, time_measure in t[1]:
            if time_measure < time:
                return False

        return True
    return filter_function


# ==========


if __name__ == "__main__":
    _main()
