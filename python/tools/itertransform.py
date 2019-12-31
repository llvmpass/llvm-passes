import itertools


'''
    This file contains utility methods to modify iterables into other iterables
'''


def groupby(iterable, key_function):
    """
    Applies sorted and groupby on thhe given iterable using the key_function
    :param iterable: Iterable to group by
    :param key_function: The key function to apply
    :return: itertools.groupby(sorted(iterable, key=key_function), key=key_function)
    """
    return itertools.groupby(sorted(iterable, key=key_function), key=key_function)


def map_each_value(mapping, iterable):
    """
    Iterable is a list of tuple such as (a, [b1, b2, ..., bn]), builds a new iterable where these tuples become
    (a, [mapping(b1), mapping(b2), ..., mapping(bn)]).
    :param mapping: The function to apply to each member of the list of the second member of the tuples
    :param iterable: A list of tuple in the form (a, [b1, b2, ..., bn])
    :return: A list of tuple in the form (a, [mapping(b1), mapping(b2), ..., mapping(bn)])
    """
    return apply_to_values_of_group(lambda l: [mapping(x) for x in l], iterable)


def apply_to_values_of_group(mapping, iterable):
    """
    Transform every tuple (a, b) from iterable into (a, mapping(b))
    :param mapping: The function to apply to the second member of the tuple
    :param iterable: An iterable on tuple with two elements
    :return: A new list of tuple on which mapping has been applied on the second member
    """
    def mapping_function(x):
        group_key, data = x
        return group_key, mapping(data)

    return map(mapping_function, iterable)


def groupby_value(iterable, key_function, value_function):
    """
    Group the elements of the iterable using the key function, and isolates the value using the value function
    :param iterable: The iterable to group by
    :param key_function: The key function that will be used to generate the key (used to group the elements)
    :param value_function: The value function that will be used to produce the value of this element
    :return: An iterable in which for each element e of the original iterable,
    we can find a tuple (key_function(e), l) where l contains value_function(e)
    """
    grouped = groupby(iterable, key_function)
    return map_each_value(value_function, grouped)
