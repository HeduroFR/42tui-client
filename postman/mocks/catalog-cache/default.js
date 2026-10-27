// Synthetic backend projections follow the public HTTP protocol and catalog/repository.ts.
// Deliberately small pages exercise the client's complete-snapshot download.
const http = require('node:http');
const snapshot = '11111111-1111-4111-8111-111111111111';
const rows = ['shared', 'old', 'new', null].map((track, index) => ({
  project_id: index + 1, slug: `project-${index + 1}`, name: `Project ${index + 1}`,
  kind: 'project', xp: 100, duration: null, rank: 0, track,
  section: track === null ? 'other' : 'common-core', section_source: 'rules',
  evidence_status: 'inferred', project_mode: 'solo', team_size: 1,
}));
let mode = 'ok';
let calls = [];
http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const reply = (status, body) => {res.statusCode = status; res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(body));};
  if (url.pathname === '/control') { mode = url.searchParams.get('mode') || 'ok'; calls = []; return reply(200, {}); }
  if (url.pathname === '/stats') return reply(200, calls);
  calls.push(url.pathname + url.search);
  const source = {status: 'available', stale: false, collected_at: new Date().toISOString()};
  const meta = {...source, cursus_id: 21, campus_id: 31};
  if (url.pathname === '/v1/me/curriculum') return reply(200, {
    account_id: '42', cursus_id: 21, campus_id: 31, snapshot_id: snapshot,
    track: {track: 'new', source: 'quest'}, rank: {rank: 0, source: 'project'},
    registration: {...source, project_ids: []}, sources: {projects: source},
  });
  if (url.pathname === '/v1/me/projects') return reply(200, {account_id: '42', snapshot_id: snapshot, items: [], next_cursor: null});
  if (url.pathname === '/v1/catalog/branches') return reply(200, {snapshot_id: snapshot, items: [], next_cursor: null, meta});
  if (url.pathname === '/v1/catalog/projects') {
    const track = url.searchParams.get('track');
    const section = url.searchParams.get('section');
    if (!track && section !== 'other') return reply(400, {error: 'track_required'});
    const filtered = rows.filter(p => track ? p.track === track || p.track === 'shared' : p.section === 'other');
    const offset = Number(url.searchParams.get('cursor') || 0);
    if (offset && mode === 'fail') return reply(503, {error: 'catalog_unavailable'});
    return reply(200, {snapshot_id: offset && mode === 'mixed' ? '22222222-2222-4222-8222-222222222222' : snapshot,
      items: filtered.slice(offset, offset + 1), next_cursor: offset + 1 < filtered.length ? String(offset + 1) : null, meta});
  }
  const detail = url.pathname.match(/^\/v1\/catalog\/projects\/(\d+)$/);
  if (detail) {
    const row = rows.find(p => p.project_id === Number(detail[1]));
    return row ? reply(200, {...row, snapshot_id: snapshot, description: 'Saved project description', rules: 'Saved rules', clauses: [], visual_links: [], branches: []}) : reply(404, {error: 'project_not_found'});
  }
  reply(501, {error: 'not_modeled'});
}).listen(process.env.PORT);
