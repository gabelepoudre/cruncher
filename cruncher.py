"""
    Class for finding ideal solutions to functions that return floating point numbers given some args
    Uses an iterative (greedy) trial-and-error approach
    Settings exist in the form of optional args on init
"""
from itertools import product
import time
import math
import random as r


class Cruncher:
    """
    Non-Optional Args:
        function: The function that will be evaluated using variables. Assumed that function takes dictionary as argument
        variables: Arbitrarily organized variable options. Will receive it's own explainer
    Optional Args:
        points per split: Number of points problem will be split into. Minimum 3 (first mid last). Higher numbers reduce false maximums but increase time
        iterations: Number of times variables will be narrowed towards goal. Decent results around 4 (default)
        goal: Ideal output of the function. 'max' for highest. 'min' for lowest (includes negative). Anything else will be
            cast as a float and tried to achieve (example: '0')
        check_all_int: If a variable range is for an int variable (explained later), instead of attempting divide up and
            find best integer, just check every single one on every pass.
    Rules for variables:
        Set up as a dictionary. Type checked for the following formats:
            A list of two floats: Assumed range of floats to be tested
            A tuple of two ints: Assumed range of ints to be tested
            A tuple of True and False: Assumed bool. Both are tested at every iteration
            A float or int: Assumed constant. Will not be changed
    """
    def __init__(self, function, variables:dict, points_per_split:int=3, iterations:int=1, goal:str='max',
                 check_all_ints:bool=False):
        self.function = function
        self.variables = variables
        if points_per_split<3:
            raise Exception(f"Must check a minimum of 3 spots on range (start, middle, end). Given:{points_per_split}")
        self.points_per_split = points_per_split
        self.iterations = iterations
        if self.iterations < 1:
            raise Exception("Need at least one iteration")
        self.check_all_ints = check_all_ints
        self.goal = goal

        self.global_increment_storage = {}
        self._validate_variables()
        self.types = self._sort_keys()

    def _validate_variables(self):
        # Validate variables of proper format. Done only once at start for performance
        def validate_single(value_to_check):
            def validate_list(some_list):
                if len(some_list) != 2 or type(some_list[0]) not in [float,int] or type(some_list[1]) not in [float,int]:
                    return False
                else:
                    return True

            def validate_tuple(some_tuple):
                if len(some_tuple) != 2:
                    return False
                elif type(some_tuple[0]) != type(some_tuple[1]):
                    return False
                elif type(some_tuple[0]) not in [bool, int]:
                    return False
                else:
                    return True

            ty = type(value_to_check)
            if ty == int or ty == float:
                return True
            elif ty == list:
                return validate_list(value_to_check)
            elif ty == tuple:
                return validate_tuple(value_to_check)
            else:
                print("failed no recognition")
                return False

        if not self.variables:
            raise Exception("variables must exist")
        for key in self.variables.keys():
            if not validate_single(self.variables[key]):
                raise Exception(f"Failed variable validation on\nkey: {key}\tvalue: {self.variables[key]}\ttype: {type(self.variables[key])}")

    def _determine_variable_type(self, value_to_check):
        # much quicker sorting of type of value
        ty = type(value_to_check)
        if ty in [float, int]:
            return "constant"
        elif ty == list:
            return "float"
        elif ty==tuple:
            return "int" if type(value_to_check[0]) == int else "bool"
        else:
            return None

    def _sort_keys(self):
        # Returns a dictionary of arrays that indicate test types
        key_types = {}
        for key in self.variables.keys():
            ty = self._determine_variable_type(self.variables[key])
            key_types[key] = ty

        return key_types

    def _get_every_int_in_tuple(self, t: tuple):
        to_ret = []
        for x in range(t[0], t[1]+1):
            to_ret.append(x)
        return to_ret

    def _split_int_tuple_and_get_increment(self, t: tuple):
        # returns points, increment
        # gonna have some small issues with increment not being consistent, but that should be okay
        diff = t[1] - t[0]
        points = []
        points_but_float = []
        increment = diff/(self.points_per_split - 1)
        points.append(t[0])
        # used to avoid consistent loss. If rounded at every step, integers may fall away (or above) end value
        # in the worst case in this version, you repeat a check on the same integer. Should I remove dupes?
        points_but_float.append(t[0])
        for x in range(self.points_per_split-2):
            points_but_float.append(points_but_float[-1] + increment)
            # avoiding dupes. This is an iffy call but probably worth it (??)
            c = round(points_but_float[-1])
            if c not in points and c != t[1]:
                points.append(c)
        points.append(t[1])

        return points, increment

    def _pretty_print_estimated_time_in_seconds(self, seconds):
        years = 0
        months = 0
        weeks = 0
        days = 0
        hours = 0
        minutes = 0
        secs = 0
        while seconds > 1:
            if seconds - 31557600 > 1:
                seconds -= 31557600
                years += 1
            elif seconds - 2629800 > 1:
                seconds -= 2629800
                months += 1
            elif seconds - 604800 > 1:
                seconds -= 604800
                weeks += 1
            elif seconds - 86400 > 1:
                seconds -= 86400
                days += 1
            elif seconds - 3600 > 1:
                seconds -= 3600
                hours += 1
            elif seconds - 60 > 1:
                seconds -= 60
                minutes += 1
            else:
                seconds -= 1
                secs += 1

        return f"\nEstimated:\nYears: {years}, Months: {months}, Weeks: {weeks}\nDays: {days}, Hours: {hours}, Minutes: {minutes}, Seconds: {secs}"

    def _split_float_list_and_get_increment(self, l:list):
        # Returns points, increment

        diff = l[1] - l[0]
        # I could do checks like below, but they slow down the system if done on every split.
        # TODO: If i'm going to make it user friendly, it'll check this in the validation which is done once
        # if diff < 0:
        #     raise Exception("Negative difference in float range not permissible")
        points = []
        increment = diff/(self.points_per_split - 1)
        points.append(l[0])
        for x in range(self.points_per_split-2):
            points.append(points[-1]+increment)
        points.append(l[1])

        return points, increment

    def _generate_test_points(self, some_variable_dic_of_ranges):
        # I don't know how to explain what I'm doing here besides input and output
        # In: Some dictionary in the form that attribute variables is passed in
        # Out: list of dictionaries of values passable to a function
        # Side-effect: global increments are updated for use in narrowing search
        option_dic = {}
        for key in self.variables.keys():
            if self.types[key] == "constant":
                option_dic[key] = [some_variable_dic_of_ranges[key]]
                # no increment, constant
                self.global_increment_storage[key] = 0
            elif self.types[key] == "float":
                points, inc = self._split_float_list_and_get_increment(some_variable_dic_of_ranges[key])
                option_dic[key] = points
                self.global_increment_storage[key] = inc
            elif self.types[key] == "int":
                if self.check_all_ints:
                    option_dic[key] = self._get_every_int_in_tuple(some_variable_dic_of_ranges[key])
                    # no increment, check all
                    self.global_increment_storage[key] = 0
                else:
                    points, inc = self._split_int_tuple_and_get_increment(some_variable_dic_of_ranges[key])
                    option_dic[key] = points
                    self.global_increment_storage[key] = inc
            elif self.types[key] == "bool":
                option_dic[key] = [True, False]
                # no increment, boolean
                self.global_increment_storage[key] = 0
            else:
                raise Exception("Failed to identify key from types")

        # Dangerously(?) assume order of keys returned the same each time, convert to list
        arrs=[]
        l_keys=[]
        variable_list = []
        for key in option_dic.keys():
            arrs.append(option_dic[key])
            l_keys.append(key)

        # magic itertools product that creates all permutations
        for combo in list(product(*arrs)):
            new_dict = {}
            for x in range(len(combo)):
                new_dict[l_keys[x]] = combo[x]
            variable_list.append(new_dict)

        return variable_list

    def _find_ideal_choice(self, list_of_dictionary_variables:list):
        # Runs through all the variable choices, finds best given goal

        def closeness(goal, value):
            return abs(goal - value)

        # im gonna assume converting a string to a float many times over may be worse for performance
        float_of_goal = None

        best_val_var_pair = ()
        for var_set in list_of_dictionary_variables:
            if not best_val_var_pair:
                best_val_var_pair = (self.function(var_set), var_set)
            else:
                val = self.function(var_set)
                # i'd 'and' here but causes logic problems i dont want to mentally sort out
                if self.goal == 'max':
                    if val > best_val_var_pair[0]:
                        best_val_var_pair = (val, var_set)
                elif self.goal == 'min':
                    if val < best_val_var_pair[0]:
                        best_val_var_pair = (val, var_set)
                else:
                    if float_of_goal is None:
                        float_of_goal = float(self.goal)
                    if closeness(float_of_goal, val) < closeness(float_of_goal, best_val_var_pair[0]):
                        best_val_var_pair = (val, var_set)

        return best_val_var_pair

    def _convert_best_val_var_pair_into_ranges(self, best_val_var_pair:dict):
        # turn best variables vals to the type of dictionary we started with. Uses the global_increment_storage
        new_range = {}
        for key in best_val_var_pair[1].keys():
            if self.types[key] == 'constant':
                new_range[key] = best_val_var_pair[1][key]
            elif self.types[key] == 'bool':
                new_range[key] = (True, False)
            elif self.types[key] == 'int':
                if self.check_all_ints:
                    # hopefully doesn't cause a reference error
                    new_range[key] = (self.variables[key][0], self.variables[key][1])
                else:
                    inc = self.global_increment_storage[key]
                    if inc < 1:
                        start = best_val_var_pair[1][key] - 1
                        end = best_val_var_pair[1][key] + 1
                        # This code repeats because it's a pain to make it a func
                        # don't break given range no matter what.
                        if start < self.variables[key][0]:
                            start = self.variables[key][0]
                        if end > self.variables[key][1]:
                            end = self.variables[key][1]
                        new_range[key] = (start, end)
                    else:
                        start = round(best_val_var_pair[1][key] - inc)
                        end = round(best_val_var_pair[1][key] + inc)
                        # don't break given range no matter what
                        if start < self.variables[key][0]:
                            start = self.variables[key][0]
                        if end > self.variables[key][1]:
                            end = self.variables[key][1]
                        new_range[key] = (start, end)

            elif self.types[key] == 'float':
                inc = self.global_increment_storage[key]
                start = best_val_var_pair[1][key] - inc
                end = best_val_var_pair[1][key] + inc
                # don't break given range no matter what
                if start < self.variables[key][0]:
                    start = self.variables[key][0]
                if end > self.variables[key][1]:
                    end = self.variables[key][1]
                new_range[key] = [start, end]

        return new_range

    def verbose_crunch(self):
        # WARNING: CAN BE A LOT OF TEXT
        points = self._generate_test_points(self.variables)
        print("Original points:")
        for x in points:
            print('\t', x)
        print('\n')

        for x in range(self.iterations):
            ret, vars = self._find_ideal_choice(points)
            print("Findings of ideal choice:\n\t", vars, '=', ret)
            if self.goal not in ['max', 'min'] and ret == float(self.goal):
                print(f"\nfound after {x+1} iterations!")
                return ret, vars
            var_range = self._convert_best_val_var_pair_into_ranges((ret, vars))
            print("New start range:\n\t", var_range)
            points = self._generate_test_points(var_range)
            print("New points:")
            for x in points:
                print('\t', x)
            print('\n\n')

        print('Finished!\n')
        return ret, vars

    def detailed_crunch(self):
        # more detail than crunch, less detail than verbose_crunch
        points = self._generate_test_points(self.variables)

        for x in range(self.iterations):
            ret, vars = self._find_ideal_choice(points)
            print("Findings of ideal choice:\n\t", vars, '=', ret)
            if self.goal not in ['max', 'min'] and ret == float(self.goal):
                print(f"\nfound after {x+1} iterations!")
                return ret, vars
            var_range = self._convert_best_val_var_pair_into_ranges((ret, vars))
            print("New start range:\n\t", var_range)
            points = self._generate_test_points(var_range)

        print('Finished!\n')
        return ret, vars

    def crunch(self):
        points = self._generate_test_points(self.variables)
        for x in range(self.iterations):
            ret, vars = self._find_ideal_choice(points)
            if self.goal not in ['max', 'min'] and ret == float(self.goal):
                return ret, vars
            var_range = self._convert_best_val_var_pair_into_ranges((ret, vars))
            points = self._generate_test_points(var_range)

        return ret, vars

    def estimate_crunch_time(self, time_of_one_sim_in_seconds):
        num_bool = 0
        num_int = 0
        num_float = 0

        for key in self.types.keys():
            if self.types[key] == 'bool':
                num_bool += 1
            elif self.types[key] == 'int':
                num_int += 1
            elif self.types[key] == 'float':
                num_float += 1

        pp = self._pretty_print_estimated_time_in_seconds
        tos = time_of_one_sim_in_seconds

        if not self.check_all_ints:
            if num_bool != 0:
                return pp(
                    tos * self.points_per_split**(num_int + num_float) * (2 * num_bool) * self.iterations
                )
            else:
                return pp(
                    tos * self.points_per_split ** (num_int + num_float) * self.iterations
                )
        else:
            return "Time estimation not supported when checking each integer"


# Example
if __name__ == "__main__":
    def example_function(a, b, c, d, e, f, g, h, i, j):
        to_return = a
        to_return **= abs(b)
        to_return **= abs(math.sin(c))
        to_return **= abs(math.cos(j))
        if to_return != 0:
            to_return = e+f*g+h-i / to_return

        if d:
            to_return *= 2

        return to_return

    def example_wrapper(variables):
        a = variables['a']
        b = variables['b']
        c = variables['c']
        d = variables['d']
        e = variables['e']
        f = variables['f']
        g = variables['g']
        h = variables['h']
        i = variables['i']
        j = variables['j']

        return example_function(a, b, c, d, e, f, g, h, i, j)

    example_range = {
        'a': [0, 10],       # Some float
        'b': (0, 10),       # Some Integer
        'c': 5,             # Some Constant
        'd': (True, False), # Some Boolean
        'e': [0, 10],
        'f': [0, 10],
        'g': [0, 10],
        'h': [0, 10],
        'i': [0, 10],
        'j': [0, 10],
    }

    test = Cruncher(example_wrapper, example_range)
    test.iterations = 10
    test.goal = 'min'
    print(f"GOAL: Find return value of {test.goal}")
    test.points_per_split = 5
    print(f"Started 10 dimensional solve with 5 points per split and 10 iterations:")
    ret = test.crunch()
    print(f"Finished! Returned {ret[0]}")
    print(f"Found variables: {ret[1]}")
    print('\n\n------------------\n')
    test.goal = 'max'
    print(f"GOAL: Find return value of {test.goal}")
    test.points_per_split = 5
    print(f"Started 10 dimensional solve with 5 points per split and 10 iterations:")
    ret = test.crunch()
    print(f"Finished! Returned {ret[0]}")
    print(f"Found variables: {ret[1]}")
    print('\n\n------------------\n')
    for x in range(3, 8):
        goal_for_close = r.random() * 5
        start = time.time()
        test.goal = str(goal_for_close)
        print(f"GOAL: Find return value of {test.goal}")
        test.iterations = 10
        test.points_per_split = x
        print(f"Started 10 dimensional solve with {x} points per split and 10 iterations:")
        ret = test.crunch()
        print(f"Finished! Returned {ret[0]} (Inaccuracy of {abs(float(test.goal) - ret[0])})")
        print(f"Found variables: {ret[1]}")
        print(f"Time to complete: {time.time()-start}")
        print('\n\n------------------\n')












