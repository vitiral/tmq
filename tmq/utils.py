def run_tasks(event_loop, tasks):
    results = []
    for t in tasks:
        results.append(event_loop.run_until_complete(t))
    return results
