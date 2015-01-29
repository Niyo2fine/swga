import os
import sys
import argparse
import swga.commands as commands
from swga import default_config_file

usage="""Usage: swga [-c --config CFG_FILE] <command> [options]

Commands:
  init:             initializes a directory with a pre-filled parameters file
  autopilot:        runs a complete workflow based on parameters file

Other commands:
  count:            find kmer counts in foreground and background genomes
  filter:           filter kmers according to various criteria
  locate:           locate primers in a genome and store locations in file
  flatten:          flatten a genome file for easy searching
  mkgraph:          create heterodimer compatibility graph
  sets:             find compatible sets of primers in graph
  score:            score sets of primers
  export:           export information about primer sets in various formats

Options:
  --config FILE     path to config file (default %s)
  -q, --quiet       suppress messages
"""

def main():
    command_opts = {'init':commands.init.main,
                    'autopilot':commands.autopilot.main,
                    'count':commands.mer_count.main,
                    'flatten':commands.flatten.main,
                    'filter':commands.filter_primers.main,
                    'locate':commands.locate.main,
                    'mkgraph':commands.make_graph.main,
                    'sets':commands.find_sets.main,
                    'score':commands.process_sets.main,
                    'export':commands.export.main}
    cfg_file = default_config_file
    parser = argparse.ArgumentParser(usage=usage % cfg_file,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     add_help=False)
    parser.add_argument('command', type=str, choices=command_opts.keys())
    parser.add_argument('-c', '--config', metavar="CFG_FILE",
                        help='path to config file (default: %(default)s)',
                        default=cfg_file)
    parser.add_argument('-q', '--quiet', action='store_true')                        
    args, remaining = parser.parse_known_args()
    command_opts[args.command](remaining, args.config, args.quiet)


if __name__ == '__main__':
    main()