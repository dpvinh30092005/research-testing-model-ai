import wilcoxon_test as wt
z, ss, sheets = wt.load()
data = wt.get_viewpoints(z, ss, sheets)

for app in ['Library fine calculator', 'Task manager']:
    d = data[app]
    vps = d['vps']
    ai_srcs = list(d['ai'].keys())
    hu_srcs = list(d['human'].keys())
    print()
    print('=== APP:', app, '===')
    print('AI sources:', ai_srcs)
    print('Human sources:', hu_srcs)
    print('Total viewpoints:', len(vps))
    print()

    ai_set = {i for i, v in enumerate(vps) if any(v['cov'].get(s) for s in ai_srcs)}
    hu_set = {i for i, v in enumerate(vps) if any(v['cov'].get(s) for s in hu_srcs)}

    ai_only  = ai_set - hu_set
    hu_only  = hu_set - ai_set
    both     = ai_set & hu_set
    neither  = set(range(len(vps))) - ai_set - hu_set

    print('  Both covered:   ', len(both))
    print('  AI only:        ', len(ai_only))
    print('  Human only:     ', len(hu_only))
    print('  Neither (blind):', len(neither))
    print()

    if ai_only:
        print('  >> AI-ONLY:')
        for i in sorted(ai_only):
            desc = vps[i].get('desc', vps[i].get('viewpoint', str(i)))
            print('    [%d] %s' % (i, desc))
    if hu_only:
        print('  >> HUMAN-ONLY:')
        for i in sorted(hu_only):
            desc = vps[i].get('desc', vps[i].get('viewpoint', str(i)))
            print('    [%d] %s' % (i, desc))
    if neither:
        print('  >> BLIND SPOT (neither):')
        for i in sorted(neither):
            desc = vps[i].get('desc', vps[i].get('viewpoint', str(i)))
            print('    [%d] %s' % (i, desc))
