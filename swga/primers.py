'''
Functions for handling lists of primers (filtering, updating, etc).
'''

import re
from functools import wraps
from swga import (error, warn, message)
from swga.utils import chunk_iterator
from swga.database import Primer


def _filter(fn):
    '''Wrapper for filter methods.

    Updates the internal count of primers and ensures the statement
    executes after each filter method.
    '''
    @wraps(fn)
    def func(self, *args, **kwargs):
        fn(self, *args, **kwargs)
        self._update_n()
        if not isinstance(self.primers, list):
            self.primers = list(self.primers)
        return self
    return func


def _update(fn):
    '''Wrapper for update methods.

    Updates the database in chunks after each update method.
    '''
    @wraps(fn)
    def func(self, *args, **kwargs):
        targets = fn(self, *args, **kwargs)
        show_progress = len(targets) > 300
        Primers._update_in_chunks(targets, show_progress=show_progress)
        return self
    return func


class Primers(object):
    '''A list of primers and associated methods.'''

    @staticmethod
    def select_active():
        active = Primer.select().where(Primer.active == True)
        if active.count() == 0:
            error(
                'No active primers found. Run `swga filter` or `swga activate` first.',
                exception=False)
        return Primers(active)

    def __init__(self, primers=None):
        '''Create a new list of primers.

        :param primers: a list of Primer objects or a list of primer sequences.
        If None, selects all primers.
        '''
        if primers is None:
            self.primers = list(Primer.select().execute())
        elif isinstance(primers, file):
            self.primers = read_primer_list(primers)
        else:
            self.primers = list(Primer.select().where(Primer.seq << primers).execute())
        self.n = len(self.primers)

    def __len__(self):
        return self.n

    def __getitem__(self, key):
        return self.primers[key]

    def __iter__(self):
        return iter(self.primers)
#                Primer.select().where(Primer.seq << self.primers)
#                .order_by(Primer._id).execute())

    @_filter
    def filter_min_fg_rate(self, min_bind):
        '''
        Removes primers that bind less than the given rate to the foreground
        genome.
        '''
        self.primers = list(Primer.select().where(
            (Primer.seq << self.primers) &
            (Primer.fg_freq >= min_bind)))

        message(
            '{}/{} primers bind the foreground genome >= {} times'
            .format(len(self.primers), self.n, min_bind))

    @_filter
    def filter_max_bg_rate(self, rate):
        '''
        Removes primers that bind more than the given number of times to
        the background genome.
        '''
        self.primers = list(Primer.select().where(
            (Primer.seq << self.primers) &
            (Primer.bg_freq <= rate)))

        message(
            '{}/{} primers bind the background genome <= {} times'
            .format(len(self.primers), self.n, rate))

    @_filter
    def filter_tm_range(self, min_tm, max_tm):
        '''
        Removes primers outside the given melting temp range.
        Finds melting temperatures if not already present.
        '''
        self.update_melt_temps()
        self.primers = list(Primer.select().where(
            (Primer.seq << self.primers) &
            (Primer.tm <= max_tm) &
            (Primer.tm >= min_tm)).execute())
        message(
            '{}/{} primers have a melting temp between {} and {} C'
            .format(len(self.primers), self.n, min_tm, max_tm))

    @_filter
    def limit_to(self, n):
        '''
        Sorts by background binding rate, selects the top `n` least frequently
        binding, then returns those ordered by descending bg/fg ratio.
        '''
        if n < 1:
            raise ValueError('n must be greater than 1')

        first_pass = (
            Primer.select().where(Primer.seq << self.primers)
            .order_by(Primer.bg_freq)
            .limit(n))

        self.primers = list(
            Primer.select().where(Primer.seq << first_pass)
            .order_by(Primer.ratio.desc()).execute())

    @_filter
    def filter_max_gini(self, gini_max, fg_genome_fp):
        '''
        Filters out primers with Gini coefficients greater than the max
        provided. Finds binding locations and Gini coefficients for primers
        that do not have them already.

        :param gini_max: max Gini coefficient (0-1)
        '''
        if 0 > gini_max > 1:
            raise ValueError('Gini coefficient must be between 0-1')

        (self
         .update_locations(fg_genome_fp)
         .update_gini(fg_genome_fp))

        self.primers = list(Primer.select().where(
            (Primer.seq << self.primers) &
            (Primer.gini <= gini_max)).execute())

        message(
            '{}/{} primers have a Gini coefficient <= {}'
            .format(len(self.primers), self.n, gini_max))

    @_update
    def update_locations(self, fg_genome_fp):
        '''Finds binding locations for any primers that don't have them.'''
        targets = list(Primer.select().where(
            (Primer.seq << self.primers) &
            (Primer._locations >> None)))
        if len(targets) > 0:
            message(
                'Finding binding locations for {} primers...'
                .format(len(targets)))
        for primer in targets:
            primer._update_locations(fg_genome_fp)
        return targets

    @_update
    def update_gini(self, fg_genome_fp):
        '''Calculates Gini coefs for any primers that don't have it.'''
        targets = list(Primer.select().where(
            (Primer.seq << self.primers) &
            (Primer.gini >> None)))
        if len(targets) > 0:
            message(
                'Finding Gini coefficients for {} primers...'
                .format(len(targets)))
        for primer in targets:
            primer._update_gini(fg_genome_fp)
        return targets

    @_update
    def update_melt_temps(self):
        '''Calculates melting temps for any primers that don't have it.'''
        targets = list(Primer.select().where(
            (Primer.seq << self.primers) &
            (Primer.tm >> None)))
        if len(targets) > 0:
            message(
                'Finding melting temps for {} primers...'
                .format(len(targets)))
        for primer in targets:
            primer.update_tm()
        return targets

    @_update
    def assign_ids(self):
        '''Assigns sequential ids to active primers.

        Resets any ids previously set.
        '''
        Primer.update(_id=-1).execute()
        primers = list(
            Primer.select()
            .where(Primer.seq << self.primers)
            .order_by(Primer.ratio.desc()).execute())
        for i, primer in enumerate(primers):
            primer._id = i + 1
        return primers

    def summarize(self):
        '''Output the number of primers currently in list.'''
        message('{} primers satisfy all filters so far.'.format(self.n))
        return self

    def activate(self, min_active=1):
        '''Activates all the primers in the list.

        :param min_active: The maximum number expected to activate. Warns if
        fewer than this number.
        '''
        n = (Primer.update(active=True)
             .where(Primer.seq << self.primers)
             .execute())
        message('Marked {} primers as active.'.format(n))
        if n < min_active:
            warn(
                'Fewer than {} primers were selected ({} passed all the '
                'filters). You may want to try less restrictive filtering '
                'parameters.'.format(min_active, n))
        return self

    def _update_n(self):
        n = len(self.primers)
        if n == 0:
            error('No primers left.', exception=False)
        else:
            self.n = n

    @staticmethod
    def _update_in_chunks(targets, chunksize=100, show_progress=True,
                          label='Updating primer db...'):
        '''Updates the records for the list of primers in chunks.

        Technically, this performs an upsert, where primer records are updated
        or inserted as needed. This is faster than updating the records for
        each primer individually.
        '''
        def upsert_chunk(chunk):
            Primer.delete().where(Primer.seq << chunk).execute()
            Primer.insert_many(p.to_dict() for p in chunk).execute()

        chunk_iterator(
            itr=targets,
            fn=upsert_chunk,
            n=chunksize,
            show_progress=show_progress,
            label=label)


def read_primer_list(lines):
    '''
    Reads in a list of primers, one per line, and returns the corresponding
    records from the primer database.
    '''
    seqs = [re.split(r'[ \t]+', line.strip('\n'))[0] for line in lines]
    primers = list(Primer.select().where(Primer.seq << seqs).execute())
    if len(primers) < len(seqs):
        primer_seqs = [p.seq for p in primers]
        missing = [_ for _ in seqs if _ not in primer_seqs]
        for seq in missing:
            warn(
                seq + ' not in the database; skipping. Add it manually with '
                '`swga count --input <file>` ')
    return primers
