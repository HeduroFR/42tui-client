# Client HTTP simulations

These mocks contain synthetic client-visible data only. No Postman workspace,
globals, credential environment or upstream investigation collection is copied.
Run from this repository root with the Postman CLI installed:

```sh
postman simulation run postman/simulations/oauth-session.sim.yaml --port 4937 --no-history --output ndjson
# In another terminal, with the simulation still running:
OAUTH_SIMULATION_URL=http://127.0.0.1:4937/oauth python -m unittest discover -s tests -p test_oauth_session_simulation.py
```

Other pairs: catalog-cache.sim.yaml → CATALOG_CACHE_SIMULATION_URL ending in
`/backend`; social.sim.yaml → SOCIAL_SIMULATION_URL ending in `/backend`;
friends-refresh.sim.yaml → FRIENDS_REFRESH_SIMULATION_URL ending in `/backend`.
Inspect each simulation's routeKey and test module before running it.
Simulation-dependent tests explicitly skip when their URL is absent; skips do
not establish end-to-end compatibility. Stop simulations with Ctrl-C.
