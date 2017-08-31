# Prototype of our C++ implementation
# in Python using NumPy arrays and
# a VERY simple W-F simulations.
# Similar to what is in ftprime
# test suite, but with diploids.
# The data structures map to what
# I'm doing on the C++ side.
# NumPy arrays containing node_dy
# and edge_dt
# are built up the same way that
# I'm populating vector<node> and
# vector<edge>.

import numpy as np
import msprime
import sys

node_dt = np.dtype([('id', np.uint32),
                    ('generation', np.float),
                    ('population', np.int32)])

edge_dt = np.dtype([('left', np.float),
                    ('right', np.float),
                    ('parent', np.int32),
                    ('child', np.int32)])

# Simulation with be popsize*SIMLEN generations
SIMLEN = 20


class MockAncestryTracker(object):
    """
    Mimicking the public API of AncestryTracker.
    """
    __nodes = None
    __edges = None

    def __init__(self):
        self.nodes = np.empty([0], dtype=node_dt)
        self.edges = np.empty([0], dtype=edge_dt)

    @property
    def nodes(self):
        return self.__nodes

    @nodes.setter
    def nodes(self, value):
        self.__nodes = value

    @property
    def edges(self):
        return self.__edges

    @edges.setter
    def edges(self, value):
        self.__edges = value

    def update_data(self, new_nodes, new_edges):
        self.nodes = np.insert(self.nodes, len(self.nodes), new_nodes)
        self.edges = np.insert(self.edges, len(self.edges), new_edges)


class ARGsimplifier(object):
    """
    Mimicking the API if our Python
    class to collect simulated 
    results and process them via msprime
    """
    __nodes = None
    __edges = None

    def __init__():
        self.__nodes = msprime.NodeTable()
        self.__edges = msprime.EdgesetTable()


def xover(rate):
    nbreaks = np.random.poisson(rate)
    if nbreaks == 0:
        return np.empty([0], dtype=np.float)
    rv = np.random.random_sample(nbreaks)
    # np.unique both sorts and purges
    # duplicate values. (Duplicate values
    # are functionally a double x-over)
    rv = np.unique(rv)
    # We "cap" the set of breakpoints
    # as in fwdpp:
    rv = np.insert(rv, len(rv), np.finfo(np.float).max)
    return rv


def split_breakpoints(breakpoints):
    """
    Take the breakpoints from a meiosis,
    and return them as segments contributed
    by gamete 1 and gamete 2

    Note: bug source could be here, if breakpoints[0] == 0.0
    """
    s1 = np.array([(0.0, breakpoints[0])], dtype=[
                  ('left', np.float), ('right', np.float)])
    s2 = np.empty([0], dtype=s1.dtype)
    for i in range(1, len(breakpoints)):
        a = breakpoints[i - 1]
        b = breakpoints[i] if i < len(breakpoints) - 1 else 1.0
        assert(a != b)
        if i % 2 == 0.:
            s1 = np.insert(s1, len(s1), (a, b))
        else:
            s2 = np.insert(s2, len(s2), (a, b))
    return (s1, s2)


def handle_recombination_update(offspring_index, parental_id1,
                                parental_id2, edges, breakpoints):
    if len(breakpoints) == 0:
        edges = np.insert(edges, len(edges),
                          (0.0, 1.0, parental_id1, offspring_index))
        return edges

    split = split_breakpoints(breakpoints)
    for i, j in split[0]:
        edges = np.insert(edges, len(edges),
                          (i, j, parental_id1, offspring_index))
    for i, j in split[1]:
        edges = np.insert(edges, len(edges),
                          (i, j, parental_id2, offspring_index))
    return edges


def wf(N, tracker, recrate, ngens):
    """
    For N diploids, the diploids list contains 2N values.
    For the i-th diploids, diploids[2*i] and diploids[2*i+1]
    represent the two chromosomes.

    We simulate constant N here, according to a Wright-Fisher
    scheme:

    1. Pick two parental indexes, each [0,N-1]
    2. The two chromosome ids are diploids[2*p] and diploids[2*p+1]
       for each parental index 'p'.
    3. We pass one parental index on to each offspring, according to
       Mendel, which means we swap parental chromosome ids 50% of the time.
    4. We do a single crossover for every mating, just so that there are
       a lot of breakpoints to handle
    """
    diploids = np.arange(2 * N, dtype=np.uint32)
    # so we pre-allocate the space. We only need
    # to do this once b/c N is constant.
    tracker.nodes = np.array([(i, 0, 0) for i in diploids], dtype=node_dt)
    # tracker.nodes = np.empty([2 * N * (ngens + 1)], dtype=node_dt)
    # tracker.nodes['id'][:len(diploids)] = diploids
    # tracker.nodes['generation'][:len(diploids)] = 0.0

    #node_id = int(len(diploids))
    next_id = len(diploids)  # This will be the next unique ID to use
    assert(max(diploids) < next_id)
    for gen in range(ngens):
        # Empty offspring list.
        # We also use this to mark the "samples" for simplify
        new_diploids = np.empty([len(diploids)], dtype=diploids.dtype)

        # Store temp nodes for this generation.
        # b/c we add 2N nodes each geneartion,
        # We can allocate it all at once.
        nodes = np.empty([2 * N], dtype=node_dt)
        nodes['population'].fill(0)
        nodes['generation'] = gen + 1
        nodes['id'] = np.arange(
            start=next_id, stop=next_id + 2 * N, dtype=nodes['id'].dtype)

        # Store temp edges for this generation
        edges = np.empty([0], dtype=edge_dt)
        # Pick 2N parents:
        parents = np.random.randint(0, N, 2 * N)
        assert(parents.max() < N)
        dip = int(0)  # dummy index for filling contents of new_diploids

        # Iterate over our chosen parents via fancy indexing.
        for parent1, parent2 in zip(parents[::2], parents[1::2]):
            # p1g1 = parent 1, gamete (chrom) 1, etc.:
            p1g1, p1g2 = diploids[2 * parent1], diploids[2 * parent1 + 1]
            p2g1, p2g2 = diploids[2 * parent2], diploids[2 * parent2 + 1]
            assert(p1g2 - p1g1 == 1)
            assert(p2g2 - p2g1 == 1)

            # Apply Mendel to p1g1 et al.
            mendel = np.random.random_sample(2)
            if mendel[0] < 0.5:
                p1g1, p1g2 = p1g2, p1g1
            if mendel[1] < 0.5:
                p2g1, p2g2 = p2g2, p2g1

            breakpoints = xover(recrate)

            edges = handle_recombination_update(
                next_id, p1g1, p1g1, edges, breakpoints)

            # Update offspring container for
            # offspring dip, chrom 1:
            new_diploids[2 * dip] = next_id

            # Add new node for offpsring dip, chrom 1
            # nodes = np.insert(nodes, len(nodes), (next_id, gen + 1, 0))
            #tracker.nodes[node_id] = (next_id, gen + 1, 0)

            # Repeat process for parent 2's contribution.
            # Stuff is now being inherited by node next_id + 1
            breakpoints = xover(recrate)
            edges = handle_recombination_update(
                next_id + 1, p2g1, p2g1, edges, breakpoints)

            new_diploids[2 * dip + 1] = next_id + 1

            # nodes = np.insert(nodes, len(nodes), (next_id + 1, gen + 1, 0))

            # Update our dummy variables.
            next_id += 2
            dip += 1

        tracker.update_data(nodes, edges)
        # print(len(tracker.nodes),len(tracker.edges))
        assert(dip == N)
        assert(len(new_diploids) == 2 * N)
        diploids = new_diploids
        assert(max(diploids) < next_id)

    return (diploids)


def expensive_check(popsize, edges, nodes):
    """
    A brute-force post-hoc check of the
    nodes and edges that we generated
    in the simulation
    """
    assert(len(edges) == SIMLEN * popsize * 4 * popsize)

    # Check that all parent/child IDs are
    # in expected range.
    for gen in range(1, SIMLEN * popsize + 1):
        min_parental_id = 2 * popsize * (gen - 1)
        max_parental_id = 2 * popsize * (gen - 1) + 2 * popsize
        min_child_id = max_parental_id
        max_child_id = min_child_id + 2 * popsize

        node_gen_m1 = nodes[np.argwhere(
            nodes['generation'] == float(gen - 1)).flatten()]
        assert(len(node_gen_m1) == 2 * popsize)
        if any(i < min_parental_id or i >= max_parental_id for i in node_gen_m1['id']) is True:
            raise RuntimeError("generation", gen - 1, "confused")

        node_gen = nodes[np.argwhere(
            nodes['generation'] == float(gen)).flatten()]
        assert(len(node_gen) == 2 * popsize)
        if any(i < min_child_id or i >= max_child_id for i in node_gen['id']) is True:
            raise RuntimeError("generation", gen, "confused")

        edges_gen = edges[(gen - 1) * 4 * popsize:(gen - 1)
                          * 4 * popsize + 4 * popsize]

        if any(i not in node_gen_m1['id'] for i in edges_gen['parent']) is True:
            raise RuntimeError(
                "parent not found in expected slice of node table")

        if any(i not in node_gen['id'] for i in edges_gen['child']) is True:
            raise RuntimeError(
                "child not found in expected slice of node table")

        if any(i < min_parental_id or i >= max_parental_id for i in edges_gen['parent']) is True:
            raise RuntimeError("Bad parent")

        if any(i < min_child_id or i >= max_child_id for i in edges_gen['child']) is True:
            raise RuntimeError("Bad child")


if __name__ == "__main__":
    popsize = int(sys.argv[1])
    theta = float(sys.argv[2])
    rho = float(sys.argv[3])
    nsam = int(sys.argv[4])  # sample size to take and add mutations to
    seed = int(sys.argv[5])

    np.random.seed(seed)

    tracker = MockAncestryTracker()
    recrate = rho / float(4 * popsize)
    samples = wf(popsize, tracker, recrate, SIMLEN * popsize)

    # Check that our sample IDs are as expected:
    # if __debug__:
    #     min_sample = SIMLEN * popsize * 2 * popsize
    #     max_sample = SIMLEN * popsize * 2 * popsize + 2 * popsize
    #     if any(i < min_sample or i >= max_sample for i in samples) is True:
    #         raise RuntimeError("Houston, we have a problem.")
    # assert(np.array_equal(samples, np.arange(
    #     min_sample, max_sample, dtype=samples.dtype)))

    # Make local names for convenience
    nodes = tracker.nodes
    edges = tracker.edges

    # if __debug__:
    #     expensive_check(popsize, edges, nodes)

    max_gen = nodes['generation'].max()
    assert(int(max_gen) == SIMLEN * popsize)

    # Convert node times from forwards to backwards
    nodes['generation'] = nodes['generation'] - max_gen
    nodes['generation'] = nodes['generation'] * -1.0

    # Construct and populate msprime's tables
    flags = np.empty([len(nodes)], dtype=np.uint32)
    flags.fill(1)
    nt = msprime.NodeTable()
    nt.set_columns(flags=flags,
                   population=nodes['population'],
                   time=nodes['generation'])

    es = msprime.EdgesetTable()
    es.set_columns(left=edges['left'],
                   right=edges['right'],
                   parent=edges['parent'],
                   children=edges['child'],
                   children_length=[1] * len(edges))

    # Sort
    msprime.sort_tables(nodes=nt, edgesets=es)

    # Simplify: this is where the magic happens
    # PLR: since these tables aren't valid, you gotta use simplify_tables, not load them into a tree sequence
    msprime.simplify_tables(samples=samples.tolist(), nodes=nt, edgesets=es)

    # Create a tree sequence
    x = msprime.load_tables(nodes=nt, edgesets=es)

    # Lets look at the MRCAS.
    # This is where things go badly:
    MRCAS = [t.get_time(t.get_root()) for t in x.trees()]

    # Throw down some mutations
    # onto a sample of size nsam
    # We'll copy tables here,
    # just to see what happens.
    # PLR: these .copy()s aren't doing anything: just overwritten before
    nt_s = nt.copy()
    es_s = es.copy()

    nsam_samples = np.random.choice(2 * popsize, nsam, replace=False)
    # PLR: TreeSequence.simplify() *returns* the modified tree sequence, leaving x unmodified
    # you could alternatively do everything here with tables
    xs = x.simplify(nsam_samples.tolist())
    xs.dump_tables(nodes=nt_s, edgesets=es_s)
    msp_rng = msprime.RandomGenerator(seed)
    mutations = msprime.MutationTable()
    sites = msprime.SiteTable()
    mutgen = msprime.MutationGenerator(msp_rng, theta / float(4 * popsize))
    mutgen.generate(nt_s, es_s, sites, mutations)
    x = msprime.load_tables(nodes=nt_s, edgesets=es_s,
                            sites=sites, mutations=mutations)
    print(sites.num_rows)