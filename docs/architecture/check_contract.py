"""Verify conceptual import boundaries only; this is not product code or security proof."""
import copy
import json
from pathlib import Path


def validate(graph):
    expected = {'ui', 'application', 'executor', 'policy', 'domain', 'ports', 'adapters', 'composition'}
    if set(graph) != expected:
        raise ValueError('Unexpected or missing layer')
    for source, targets in graph.items():
        if not isinstance(targets, list) or any(t not in expected for t in targets):
            raise ValueError('Invalid target')
        if len(set(targets)) != len(targets):
            raise ValueError('Duplicate dependency')
        if source != 'composition' and 'composition' in targets:
            raise ValueError('Composition root cannot be imported')
        if source in {'application', 'executor', 'policy', 'domain', 'ports', 'ui'} and 'adapters' in targets:
            raise ValueError('Core cannot import provider implementation')
    if graph['ui'] != ['application'] or graph['domain']:
        raise ValueError('UI gateway or pure domain boundary violated')
    if set(graph['policy']) - {'domain'} or set(graph['ports']) - {'domain'}:
        raise ValueError('Policy/ports may only depend on domain')
    if set(graph['adapters']) - {'ports', 'domain'}:
        raise ValueError('Adapters may only depend on ports and domain')
    for entry in ['application', 'executor']:
        if not {'policy', 'domain', 'ports'} <= set(graph[entry]):
            raise ValueError('Execution/control entry needs policy, domain and ports')
    visited, active = set(), set()
    def visit(node):
        if node in active:
            raise ValueError('Dependency cycle')
        if node in visited:
            return
        active.add(node)
        for target in graph[node]:
            visit(target)
        active.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)


def main():
    graph = json.loads(Path(__file__).with_name('dependencies.json').read_text())
    validate(graph)
    print('PASS: conceptual layer boundaries and acyclic dependency graph')
    allowed = copy.deepcopy(graph)
    allowed['adapters'] = ['ports', 'domain']
    validate(allowed)
    print('PASS: adapters may use ports and domain')
    mutations = {
        'UI bypass': ('ui', ['executor']),
        'provider import from application': ('application', graph['application'] + ['adapters']),
        'domain coupled to storage': ('domain', ['adapters']),
        'worker without policy': ('executor', ['domain', 'ports']),
        'cycle': ('application', graph['application'] + ['ui']),
        'unknown layer': ('ports', ['missing']),
        'adapter importing application': ('adapters', ['ports', 'application']),
        'adapter importing executor': ('adapters', ['ports', 'executor']),
        'adapter importing policy': ('adapters', ['ports', 'policy']),
        'composition imported': ('adapters', ['composition']),
    }
    for name, (node, edges) in mutations.items():
        candidate = copy.deepcopy(graph)
        candidate[node] = edges
        try:
            validate(candidate)
        except ValueError:
            print('PASS: rejected ' + name)
        else:
            raise AssertionError('Invalid graph accepted: ' + name)
    print('NOT_RUN: application behavior, authorization, database, workers, live providers')


if __name__ == '__main__':
    main()
