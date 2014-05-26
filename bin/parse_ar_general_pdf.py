#!/usr/bin/env python

import re

from openelexdata.us.ar.base import (ParserState, BaseParser, LegendState,
    get_arg_parser, parse_csv)
from openelexdata.us.ar.util import parse_date

county_re = re.compile(r'^[\.a-zA-Z ]+ County$')

def strip_county(line):
    return re.sub(r'\(.+ County\)', '', line).strip()

def remove_unicode(s):
    replacements = [
        (u'\u2013', '-'),
        (u'\u2014', '-'),
        (u'\u2019', "'"),
    ]
    for original, replacement in replacements:
        s = s.replace(original, replacement)
    return s

class RootState(ParserState):
    name = 'root'
    _date_re = re.compile(r'(May|June|November) \d{1,2}(th|), \d{4}')

    def handle_line(self, line):
        if self._date_re.match(line):
            self._context.set('date', parse_date(line))
        elif line == "Vote totals for all candidates":
            self._context.change_state('vote_totals')
        elif line == "County Summary":
            self._context.change_state('county_summaries')


class VoteTotalsState(ParserState):
    name = 'vote_totals'

    def handle_line(self, line):
        if line == "Certification Report":
            self._context.change_state('root')
        elif line.startswith("Proposed"):
            self._context.set('proposal', strip_county(line))
            self._context.change_state('proposal')
        elif line != "":
            self._context.set('office', strip_county(line))
            self._context.change_state('contest_totals')


class ProposalState(ParserState):
    name = 'proposal'

    def handle_line(self, line):
        if line.startswith("Under"):
            self._context.change_state(self._context.previous_state)
        elif line.startswith("For") or line.startswith("Against"):
            self._parse_result(line)
        elif line != "" and not self._context.has('proposal_description'):
            self._context.set('proposal_description', line)
        elif line != "" and self._context.has('proposal_description'):
            desc = self._context.get('proposal_description')
            desc = desc + " " + line
            self._context.set('proposal_description', desc)

    def exit(self):
        self._context.unset('proposal')
        self._context.unset('proposal_description')

    def _parse_result(self, line):
        bits = re.split(r'\s+', line)

        try:
            jurisdiction = self._context.get('county')
            reporting_level = 'county'
        except KeyError:
            jurisdiction = "Arkansas"
            reporting_level = 'contest'

        result = {
            'date': self._context.get('date'),
            'proposal': self._context.get('proposal'),
            'proposal_description': self._context.get('proposal_description'),
            'candidate': bits[0],
            'reporting_level': reporting_level, 
            'jurisdiction': jurisdiction, 
            'votes': bits[1].replace(',', ''),
            'percentage': bits[2].replace('%', ''),
        }
        self._context.results.append(result)


class ContestTotalsState(ParserState):
    name = 'contest_totals'

    def handle_line(self, line):
        if line == "":
            return

        self._parse_result(line)
        if line.startswith("Under"):
            self._context.change_state(self._context.previous_state)

    def exit(self):
        self._context.unset('office')

    def _parse_result(self, line):
        clean_line = line.replace('-', '')
        party = ""
        if "Democrat" in clean_line:
            party = "Democrat"
            clean_line = clean_line.replace("Democrat","")
        elif "Republican" in clean_line:
            party = "Republican"
            clean_line = clean_line.replace("Republican", "")
        elif "Non Partisan Judicial" in clean_line:
            clean_line = clean_line.replace("Non Partisan Judicial", "")

        try:
            jurisdiction = self._context.get('county')
            reporting_level = 'county'
        except KeyError:
            jurisdiction = "Arkansas"
            reporting_level = 'contest'

        bits = re.split(r'\s+', clean_line)
        result = {
            'date': self._context.get('date'),
            'office': self._context.get('office'),
            'candidate': ' '.join(bits[:-2]),
            'party': party,
            'reporting_level': reporting_level, 
            'jurisdiction': jurisdiction, 
            'votes': bits[-2].replace(',', ''),
            'percentage': bits[-1].replace('%', ''),
        }
        self._context.results.append(result)



class CountySummariesState(ParserState):
    name = 'county_summaries'

    def handle_line(self, line):
        if county_re.match(line):
            self._context.set('county', line)
            self._context.change_state('county_summary')


class CountySummaryState(ParserState):
    name = 'county_summary'

    def handle_line(self, line):
        if county_re.match(line):
            current_county = self._context.get('county')
            self._context.set('county', line)
            if "Yell" in current_county and "Arkansas" in line:
                self._context.change_state('county_precinct_results')
        elif line.startswith("Proposed"):
            self._context.set('proposal', strip_county(line))
            self._context.change_state('proposal')
        elif line != "":
            self._context.set('office', strip_county(line))
            self._context.change_state('contest_totals')


class CountyPrecinctResultsState(ParserState):
    name = 'county_precinct_results'

    def handle_line(self, line):
        if line == "" or line == "Official Results" or line == "2002 General":
            return
        elif county_re.match(line):
            self._context.set('county', line)
        elif line.startswith("All Unopposed Candidates"):
            self._context.change_state('unopposed_candidates_result')
        else:
            if "Proposed" in line:
                self._context.set('proposal', line)
                self._context.set('office', "")
            else:
                self._context.set('office', line)
                self._context.set('proposal', "")
            self._context.change_state('county_precinct_result')


class CountyPrecinctResultState(ParserState):
    name = 'county_precinct_result'

    def handle_line(self, line):
        if "LEGEND" in line:
            self._context.change_state('legend')
        elif line.startswith("1"):
            # Header row, e.g.
            # 1 2 3 4 5
            return
        elif line.startswith("Totals"):
            self._context.unset('legend')
            self._context.change_state('county_precinct_results')
        elif line != "":
            # HACK: Deal with record split across 3 lines
            if self._context.has('split_result'):
                line = self._context.previous_line + " CITY " + line
                self._context.unset('split_result')
            self._parse_result(line)

    def _parse_result(self, line):
        legend = self._context.get('legend')
        bits = re.split(r'\s+', line)
        precinct = remove_unicode(' '.join(bits[:-len(legend)]))
        votes = bits[-len(legend):]
        try:
            assert len(votes) == len(legend)
        except AssertionError:
            # HACK: Deal with record split across 2 lines
            if line.startswith("FLETCHER/CROOKED CREEK "):
                self._context.set('split_result', True)
                return
            elif line == "CITY":
                # This is the line following the split result line
                # ignore it.
                return
            else:
                raise

        for i in range(len(votes)):
            name = legend[i]

            result = {
                'date': self._context.get('date'),
                'proposal': self._context.get('proposal'),
                'office': self._context.get('office'),
                'candidate': name,
                'reporting_level': 'precinct',
                'jurisdiction': precinct,
                'county': self._context.get('county'),
                'votes': votes[i].replace(',', ''),
            }
            self._context.results.append(result)


class UnopposedCandidatesResultState(ParserState):
    name = 'unopposed_candidates_result'

    def handle_line(self, line):
        if line == "":
            pass
        elif line.startswith("Votes"):
            # Header row
            pass
        elif line.startswith("Totals"):
            self._context.change_state('county_precinct_results')
        else:
            self._parse_result(line)

    def _parse_result(self, line):
        bits = re.split(r'\s+', line)
        precinct = remove_unicode(' '.join(bits[:-2]))

        result = {
            'date': self._context.get('date'),
            'office': self._context.get('office'),
            'candidate': "All Unopposed Candidates",
            'reporting_level': 'precinct',
            'jurisdiction': precinct, 
            'county': self._context.get('county'),
            'votes': bits[-2],
            'under_votes': bits[-1],
        }
        self._context.results.append(result)


class ResultParser(BaseParser):
    def __init__(self, infile):
        super(ResultParser, self).__init__(infile)
        self._register_state(RootState(self))
        self._register_state(VoteTotalsState(self))
        self._register_state(ProposalState(self))
        self._register_state(ContestTotalsState(self))
        self._register_state(CountySummariesState(self))
        self._register_state(CountySummaryState(self))
        self._register_state(CountyPrecinctResultsState(self))
        self._register_state(CountyPrecinctResultState(self))
        self._register_state(LegendState(self))
        self._register_state(UnopposedCandidatesResultState(self))
        self._current_state = self._get_state('root')


fields = [
    'date',
    'office',
    'proposal',
    'proposal_description',
    'candidate',
    'party',
    'reporting_level',
    'jurisdiction',
    'county',
    'votes',
    'under_votes',
    'percentage',
]


if __name__ == "__main__":
    args = get_arg_parser().parse_args()
    parse_csv(args.infile, args.outfile, fields, ResultParser)
