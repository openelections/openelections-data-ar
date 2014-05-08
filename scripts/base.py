import argparse
import csv
import sys

class ParserState(object):
    def __init__(self, context):
        self._context = context

    def handle_line(self, line):
        raise NotImplemented

    def enter(self):
        pass

    def exit(self):
        pass

class StateManager(object):
    def __init__(self):
        self._line_number = 0
        self._previous_line = None
        self._states = {}
        self._attrs = {}

    def _register_state(self, state):
        self._states[state.name] = state

    def _get_state(self, name):
        return self._states[name]

    def set(self, key, val):
        self._attrs[key] = val

    def get(self, key):
        return self._attrs[key]

    def has(self, key):
        return key in self._attrs

    def unset(self, key):
        try:
            del self._attrs[key]
        except KeyError:
            pass

    def change_state(self, name):
        self._current_state.exit()
        self._previous_state= self._current_state
        self._current_state = self._get_state(name)
        self._current_state.enter()

    @property
    def previous_state(self):
        return self._previous_state.name

    def handle_line(self, line):
        self._line_number += 1
        self._current_state.handle_line(line)
        self._previous_line = line

    @property
    def previous_line(self):
        return self._previous_line

    @property
    def line_number(self):
        return self._line_number


class LegendState(ParserState):
    name = 'legend'

    def handle_line(self, line):
        if line.startswith('#'): 
            name = self._parse_legend_name(line)
            self._legend.append(name)
        else:
            self._context.change_state(self._context.previous_state)

    def enter(self):
        self._legend = []

    def exit(self):
        self._context.set('legend', self._legend)

    def _parse_legend_name(self, line):
        first, second = line.split("represents")
        first, second = second.split("[")
        return first.strip()



class BaseParser(StateManager):
    def __init__(self, infile):
        super(BaseParser, self).__init__()
        self.infile = infile
        self.results = []

    def parse(self):
        for line in self.infile:
            clean_line = line.decode('utf-8').replace(u'\xa0', u' ').strip() 
            self.handle_line(clean_line)


def get_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", nargs='?', type=argparse.FileType('r'),
        default=sys.stdin, help="input filename")
    parser.add_argument("outfile", nargs='?', type=argparse.FileType('w'), 
        default=sys.stdout, help="output filename")
    return parser


def parse_csv(infile, outfile, fields, parser_cls):
    parser = parser_cls(infile)
    writer = csv.DictWriter(outfile, fields)
    parser.parse()
    writer.writeheader()
    for result in parser.results:
        writer.writerow(result)
