// This file defines a C++ class to record
// nodes and edges during a sim.  It also
// gets the data ready to send to msprime
// and cleanup after msprime simplifies things.
// The ancestry_tracer is mainly a book-keeper
// and it is exposed to Python as 
// wfarg.AncestryTracker.
// 
// This implementation does not have to be 
// header-only.  However, it is easier (lazier)
// to do that, and we'll fix that when moving things to
// fwdpy11.

#ifndef ANCESTRY_ANCESTRY_TRACKER_HPP__
#define ANCESTRY_ANCESTRY_TRACKER_HPP__

#include <iostream>
#include <algorithm>
#include <vector>
#include <map>
#include <limits>
#include <cstdint>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "node.hpp"
#include "edge.hpp"

struct ancestry_tracker
{
    using integer_type = decltype(edge::parent);
    /// Nodes:
    std::vector<node> nodes;
    /// The ARG:
    std::vector<edge> edges;
    /// The edges generated for each generation:
    std::vector<edge> temp;
    /// This is used as the sample indexes for msprime:
    std::vector<integer_type> offspring_indexes;
    integer_type generation, next_index, first_parental_index;
    std::uint32_t lastN;
    decltype(node::generation) last_gc_time;
    ancestry_tracker(const integer_type N)
        : nodes{ std::vector<node>() }, edges{ std::vector<edge>() },
          temp{ std::vector<edge>() },
          offspring_indexes{ std::vector<integer_type>() }, generation{ 1 },
          next_index{ 2 * N }, first_parental_index{ 0 },
          lastN{ static_cast<std::uint32_t>(N) }, last_gc_time{ 0.0 }
    {
        nodes.reserve(2 * N);
        edges.reserve(2 * N);
        temp.reserve(N);

        //Initialize 2N nodes for the generation 0
        for (integer_type i = 0; i < 2 * N; ++i)
            {
                //ID, time 0, population 0
                nodes.emplace_back(make_node(i, 0.0, 0));
            }
    }

    std::tuple<integer_type, integer_type>
    get_parent_ids(const std::uint32_t p, const int did_swap)
    {
        return std::make_tuple(
            first_parental_index + 2 * static_cast<integer_type>(p) + did_swap,
            first_parental_index + 2 * static_cast<integer_type>(p)
                + !did_swap);
    }

    std::tuple<integer_type, integer_type>
    get_next_indexes()
    {
        auto rv = std::make_tuple(next_index, next_index + 1);
        next_index += 2;
        offspring_indexes.push_back(std::get<0>(rv));
        offspring_indexes.push_back(std::get<1>(rv));
        return rv;
    }

    void
    add_edges(const std::vector<std::pair<double, double>>& breakpoints,
              const integer_type parent, const integer_type child)
    {
        for (auto&& bi : breakpoints)
            {
                temp.emplace_back(
                    make_edge(bi.first, bi.second, parent, child));
            }
    }

    void
    finish_generation()
    {
        for (auto&& oi : offspring_indexes)
            {
                nodes.emplace_back(make_node(oi, generation, 0));
            }
        edges.insert(edges.end(), temp.begin(), temp.end());
        lastN = next_index - first_parental_index;
        first_parental_index = offspring_indexes.front();

        temp.clear();
        ++generation;
    }

    void
    prep_for_gc()
    {
        if (nodes.empty())
            return;

        //convert forward time to backwards time
        auto max_gen = nodes.back().generation;
        for (auto& n : nodes)
            {
                n.generation -= max_gen;
                n.generation *= -1.0;
            }
    }

    void
    post_process_gc(pybind11::tuple t)
    {
        pybind11::bool_ gc = t[0].cast<bool>();
        if (!gc)
            return;

        last_gc_time = generation;
        next_index = t[1].cast<integer_type>();
        // establish last parental index:
        first_parental_index = 0;
        nodes.clear();
        edges.clear();
    }
};

#endif
