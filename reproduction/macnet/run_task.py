"""Run tasks through NATIVE MacNet (OpenBMB/ChatDev, macnet branch).

Configs (the system name under runs/ and judged/ encodes the config):
  chain  - 10 nodes in a line, the 15 chatdev_tasks.json prompts. Maximizes
           solution handoffs (every artifact survives 9 hops or dies).
  mlp    - 8 nodes in dense layers (4-2-2, complete bipartite between
           consecutive layers), same 15 prompts. Maximizes redundancy WITH
           working aggregation: all of a node's inputs arrive in the same
           execution layer, so MacNet's pairwise aggregation actually fires.
  net    - 8 nodes, complete DAG (28 edges), same prompts. OPTIONAL /
           exploratory: at the pinned commit the layered executor deletes
           consumed predecessor edges, so for net the aggregation condition
           (len(pre_solutions) == len(remaining predecessors)) almost never
           holds — multi-predecessor nodes silently fall back to their FIRST
           received solution and discard the rest (verified empirically,
           n=3 smoke: zero aggregation events; later contributions dropped).
           Structurally induced information discarding — interesting for
           MAST 2.4/2.5, but NOT a working "redundancy" arm. ~3x chain cost.
  rand   - 10 nodes, seeded TRUE random DAG (RAND_SEED=7, one fixed sample
           across tasks/runs: 18 edges incl. skip edges, 9 execution steps,
           7 aggregation points with fan-ins 2-3). Mixes plain handoffs and
           genuine merges in one irregular, non-layered arm. Requires the
           graph.py scheduler patch (README deviation note 11): upstream
           only aggregates layer-aligned arrivals, so without the patch any
           skip edge silently degenerates to net's first-solution fallback.
           MacNet's own generate_random is NOT used (no connectivity
           guarantee, unbounded edge count up to n(n-1)/2).
  srdd   - 10-node chain on task_selection/macnet_srdd_tasks.json with the
           SRDD persona profiles (--type <category>).

MacNet reads config.yaml/MacNetLog/WareHouse relative to cwd and re-reads
config.yaml mid-run (Node.aggregate), so every run gets its own working copy
of macnet_repo. The model stays GPT_4O in config.yaml; the proxy aliases it
to gpt-5.4-mini. Each run gets a tagged route (/t/mn_<cfg>_<slug>_runN/v1)
so calls.jsonl stays attributable under parallel execution.

The judge input is trace.log: MacNet's own MacNetLog transcript (Original
Solution / Suggestions / Optimized Solution per edge + aggregation events),
re-encoded to clean utf-8.

Usage:
  conda run -n macnet python reproduction/macnet/run_task.py --config chain Gomoku
  conda run -n macnet python reproduction/macnet/run_task.py --config rand --all --parallel 3
  conda run -n macnet python reproduction/macnet/run_task.py --config chain --nodes 3 Gomoku   # smoke
"""
import glob, json, os, random, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.join(ROOT, 'reproduction', 'macnet_repo')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')

CONFIGS = {
    'chain': dict(nodes=10, topology='chain', timeout=3600),
    'mlp': dict(nodes=8, topology='mlp', timeout=7200),
    'net': dict(nodes=8, topology='net', timeout=7200),
    'rand': dict(nodes=10, topology='rand', timeout=7200),
    'srdd': dict(nodes=10, topology='chain', timeout=3600),
}

RAND_SEED = 7  # fixed: one sampled graph, identical across tasks and runs

ALIASES = {  # same map as chatdev/run_task.py so prompts see identical names
    'TicTacToe (with display)': 'TicTacToe', 'The Crossword': 'TheCrossword',
    'Connections': 'ConnectionsNYT', 'Strands': 'StrandsNYT',
}


def edge_list(topology, n):
    """Edge strings for config.yaml's graph: field (mirrors generate_graph.py)."""
    if topology == 'chain':
        edges = [(i, i + 1) for i in range(n - 1)]
    elif topology == 'net':
        edges = [(u, v) for u in range(n) for v in range(n) if u < v]
    elif topology == 'mlp':  # same layer arithmetic as generate_mlp()
        import math
        layer_num = int(math.log(n, 2))
        layers = [n // layer_num for _ in range(layer_num)]
        layers[0] += n % layer_num
        end_ids, start_ids = [layers[0]], [0]
        for i in range(1, len(layers)):
            start_ids.append(end_ids[-1])
            end_ids.append(end_ids[-1] + layers[i])
        edges = [(u, v) for i in range(len(layers) - 1)
                 for u in range(start_ids[i], end_ids[i])
                 for v in range(start_ids[i + 1], end_ids[i + 1])]
    elif topology == 'rand':
        # Seeded TRUE random DAG (skip edges and all): node ids are the
        # topological order; a backbone gives every non-source node one
        # predecessor among earlier nodes (weak connectivity — MacNet's own
        # generate_random can emit isolated nodes), then uniform extra
        # forward edges. Total edges land in [1.5n, 2n) — a density bound
        # generate_random lacks (it samples up to n(n-1)/2, a cost hazard),
        # the one deliberate departure from "uniform over all DAGs".
        # Cross-layer aggregation works because of the graph.py scheduler
        # patch (deviation note 11); unpatched, any skip edge silently
        # degenerates to first-solution fallback like the net config.
        rng = random.Random(RAND_SEED)
        chosen = {(rng.randrange(i), i) for i in range(1, n)}
        pool = [(u, v) for u in range(n) for v in range(u + 1, n)
                if (u, v) not in chosen]
        extra = rng.randint(n // 2, n - 1)
        chosen |= set(rng.sample(pool, min(extra, len(pool))))
        edges = sorted(chosen)
    else:
        raise ValueError(topology)
    return [f'{u}->{v}' for u, v in edges]


def make_workdir(rundir, cfg):
    """Per-run working copy of macnet_repo with the graph: field rewritten."""
    workdir = os.path.join(rundir, 'repo')
    skip = {'.git', 'misc', 'tmp', 'MacNetLog', 'WareHouse'}
    if cfg != 'srdd':
        skip.add('SRDD_Profile')  # personas only used with --type
    shutil.copytree(REPO, workdir,
                    ignore=lambda d, names: [x for x in names if x in skip])
    c = CONFIGS[cfg]
    path = os.path.join(workdir, 'config.yaml')
    lines = open(path, encoding='utf-8').readlines()
    with open(path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(f"graph: {edge_list(c['topology'], c['nodes'])}\n"
                    if line.startswith('graph:') else line)
    return workdir


def run_one(cfg, task):
    name = ALIASES.get(task['task'], task['task'])
    slug = name.replace(' ', '').replace('/', '_')
    runs = os.path.join(ROOT, 'reproduction', 'runs', f'macnet-{cfg}')
    n = 1
    while os.path.exists(os.path.join(runs, slug, f'run_{n}')):
        n += 1
    rundir = os.path.join(runs, slug, f'run_{n}')
    os.makedirs(rundir)
    workdir = make_workdir(rundir, cfg)

    base, v1 = PROXY.rsplit('/', 1)
    # env bin first on PATH: graph.py shells out to `imgcat` (pip-installed
    # into the macnet env) and graphviz needs `dot`
    env = dict(os.environ, OPENAI_API_KEY='dummy',
               PATH=os.path.dirname(sys.executable) + os.pathsep +
                    os.environ.get('PATH', ''),
               BASE_URL=f'{base}/t/mn_{cfg}_{slug}_run{n}/{v1}')
    cmd = [sys.executable, 'run.py', '--task', task['task_prompt'],
           '--name', name]
    if cfg == 'srdd' and task.get('type'):
        cmd += ['--type', task['type']]
    print(f'[{cfg}/{slug}] run_{n} starting', flush=True)
    t0 = time.time()
    with open(os.path.join(rundir, 'console.txt'), 'w') as log:
        try:
            rc = subprocess.run(cmd, cwd=workdir, env=env, stdout=log,
                                stderr=subprocess.STDOUT,
                                timeout=CONFIGS[cfg]['timeout']).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    dur = time.time() - t0

    # archive cwd-relative artifacts out of the working copy, then drop it
    trace = None
    for d in sorted(glob.glob(os.path.join(workdir, 'MacNetLog', '*'))):
        shutil.move(d, os.path.join(rundir, 'macnetlog',
                                    os.path.basename(d)))
    wh = os.path.join(workdir, 'WareHouse', name)
    if os.path.isdir(wh):
        shutil.move(wh, os.path.join(rundir, 'warehouse'))
    logs = sorted(glob.glob(os.path.join(rundir, 'macnetlog', '*', '*.log')))
    if logs:
        # gbk patched to utf-8 in macnet_repo/graph.py; errors='replace'
        # guards against any stray bytes either way
        text = open(logs[-1], encoding='utf-8', errors='replace').read()
        trace = os.path.join(rundir, 'trace.log')
        with open(trace, 'w', encoding='utf-8') as f:
            f.write(text)
    shutil.rmtree(workdir, ignore_errors=True)

    result = dict(task=task['task'], project_name=name, config=cfg,
                  topology=CONFIGS[cfg]['topology'],
                  edges=edge_list(CONFIGS[cfg]['topology'],
                                  CONFIGS[cfg]['nodes']),
                  n_nodes=CONFIGS[cfg]['nodes'], run=n, rc=rc,
                  seconds=round(dur, 1),
                  trace=trace and os.path.relpath(trace, rundir),
                  original_solved=task.get('solved'),
                  cat2_likelihood_screened=task.get('cat2_likelihood_screened'),
                  category=task.get('category'))
    with open(os.path.join(rundir, 'result.json'), 'w') as f:
        json.dump(result, f, indent=1)
    print(f'[{cfg}/{slug}] rc={rc} {dur:.0f}s trace={result["trace"]}',
          flush=True)
    return result


def main():
    args = sys.argv[1:]
    if '--config' not in args:
        sys.exit(__doc__)
    i = args.index('--config')
    cfg = args[i + 1]
    args = args[:i] + args[i + 2:]
    if cfg not in CONFIGS:
        sys.exit(f'--config must be one of {list(CONFIGS)}')
    par = 1
    if '--parallel' in args:
        i = args.index('--parallel')
        par = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    if '--nodes' in args:  # smoke-test override
        i = args.index('--nodes')
        CONFIGS[cfg]['nodes'] = int(args[i + 1])
        args = args[:i] + args[i + 2:]

    tasks_file = ('macnet_srdd_tasks.json' if cfg == 'srdd'
                  else 'chatdev_tasks.json')
    tasks = json.load(open(os.path.join(ROOT, 'task_selection', tasks_file)))
    if not args:
        sys.exit(__doc__)
    sel = tasks if args == ['--all'] else [
        t for t in tasks
        if ALIASES.get(t['task'], t['task']).replace(' ', '') in args
        or t['task'] in args]
    if args != ['--all'] and len(sel) != len(args):
        sys.exit(f'unmatched task names; matched {[t["task"] for t in sel]}')
    if par == 1:
        results = [run_one(cfg, t) for t in sel]
    else:
        from concurrent.futures import ThreadPoolExecutor  # subprocess-bound
        with ThreadPoolExecutor(max_workers=par) as ex:
            results = list(ex.map(lambda t: run_one(cfg, t), sel))
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
